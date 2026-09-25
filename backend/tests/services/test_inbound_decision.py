"""Décision #38 / ADR-0007 §16 — InboundDecisionService on a real (SQLite) DB.

Drives the webhook's deterministic path and the background free-text path end
to end (no network: Twilio and the model are mocked) and checks what is — and
is not — written.
"""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.routes import twilio_inbound as webhook
from app.db.models import (
    Base,
    InboundReplyEvent,
    ManagerPrompt,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.inbound_decision import InboundDecisionService
from app.services.manager_decision import (
    BUTTON_ACCEPT,
    BUTTON_CONFIRM_NO,
    BUTTON_CONFIRM_YES,
    BUTTON_CORRECT,
    BUTTON_REJECT,
    PROMPT_WINDOW,
)
from app.services.receipts import ReceiptsService

HOTEL = "hotel_decision"
PHONE = "+15557654321"
NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)  # far from "today": no wall-clock dependency


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed(db, *, pending: int = 1, dispatched_ago=timedelta(hours=1), actual_covers=None):
    profile = RestaurantProfile(
        id=_uuid.uuid4(), tenant_id=HOTEL, property_name="P", outlet_name="O",
        phone_number=PHONE, total_seats=50,
    )
    db.add(profile)
    await db.commit()
    recs = []
    for i in range(pending):
        rec = StaffingRecommendation(
            id=_uuid.uuid4(), tenant_id=HOTEL, property_id=profile.id, anomaly_id=_uuid.uuid4(),
            message_text=f"Add {i + 1} server(s).", window_start=NOW, window_end=NOW,
            predicted_covers=140.0, status="dispatched",
            dispatched_at=NOW - dispatched_ago - timedelta(minutes=i),
            actual_covers=actual_covers,
        )
        db.add(rec)
        recs.append(rec)
    await db.commit()
    return profile, recs


async def _events(db):
    return (await db.execute(select(InboundReplyEvent).order_by(InboundReplyEvent.created_at))).scalars().all()


async def _prompts(db):
    return (await db.execute(select(ManagerPrompt))).scalars().all()


async def _reload(db, rec):
    await db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_accept_button_records_with_button_source_and_no_reason_prompt(db):
    profile, [rec] = await _seed(db)
    plan = await InboundDecisionService(db).handle_deterministic(profile, "", BUTTON_ACCEPT, NOW)
    rec = await _reload(db, rec)
    assert (rec.status, rec.action, rec.decision_source) == ("accepted", "accepted", "button")
    assert plan.text == "Validation enregistrée."  # never a reason prompt after an accept
    assert await _prompts(db) == []
    [ev] = await _events(db)
    assert (ev.result, ev.decision, ev.decision_source, ev.channel) == ("recorded", "accepted", "button", "button")


@pytest.mark.asyncio
@pytest.mark.parametrize("payload,decision,prompt_text", [
    (BUTTON_REJECT, "rejected", "Une raison ? (facultatif)"),
    (BUTTON_CORRECT, "modified", "Quel changement, et pourquoi ? (facultatif)"),
])
async def test_reject_or_correct_button_asks_optional_reason(db, payload, decision, prompt_text):
    profile, [rec] = await _seed(db)
    plan = await InboundDecisionService(db).handle_deterministic(profile, "", payload, NOW)
    rec = await _reload(db, rec)
    assert rec.status == decision and rec.decision_source == "button"
    assert prompt_text in plan.text
    [p] = await _prompts(db)
    assert (p.kind, p.status) == ("reason_request", "pending")


@pytest.mark.asyncio
async def test_unknown_button_payload_records_nothing(db):
    profile, [rec] = await _seed(db)
    plan = await InboundDecisionService(db).handle_deterministic(profile, "", "evil.payload", NOW)
    assert (await _reload(db, rec)).status == "dispatched"
    assert plan.extras["why"] == "unknown_button_payload"


# ---------------------------------------------------------------------------
# HITL confirmation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decline_of_a_change_is_recorded_as_rejected(db):
    """ADR-0007 §17.8: "non merci on garde tel quel" answering a recommendation
    that adds staff is a rejection, recorded without confirmation."""
    profile, [rec] = await _seed(db)
    rec.recommended_headcount = 2
    await db.commit()
    plan = await InboundDecisionService(db).handle_deterministic(
        profile, "non merci on garde tel quel", "", NOW)
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source, rec.decided_by) == ("rejected", "keyword", "human_whatsapp")
    assert plan.result == "recorded"
    assert await _prompts(db) != []  # the optional reason request, not a confirmation
    assert all(p.kind == "reason_request" for p in await _prompts(db))


@pytest.mark.asyncio
async def test_ambiguous_keyword_writes_nothing_until_confirmed(db):
    # recommended_headcount unset → whether a change is proposed cannot be told
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    plan = await svc.handle_deterministic(profile, "non merci on garde tel quel", "", NOW)
    assert plan.result == "confirmation_requested" and plan.buttons == "confirm"
    assert plan.text.startswith("Je note un refus, c'est bien ça ?")
    assert (await _reload(db, rec)).status == "dispatched"  # nothing written

    plan = await svc.handle_deterministic(profile, "oui", "", NOW + timedelta(minutes=2))
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source) == ("rejected", "keyword_confirmed")
    assert plan.result == "confirmed"
    results = [e.result for e in await _events(db)]
    assert results == ["confirmation_requested", "confirmed"]


@pytest.mark.asyncio
async def test_confirmation_button_yes(db):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "pas besoin", "", NOW)
    await svc.handle_deterministic(profile, "", BUTTON_CONFIRM_YES, NOW + timedelta(minutes=1))
    assert (await _reload(db, rec)).status == "rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [("non", ""), ("", BUTTON_CONFIRM_NO)])
async def test_confirmation_declined_writes_nothing(db, answer):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "non merci", "", NOW)
    plan = await svc.handle_deterministic(profile, answer[0], answer[1], NOW + timedelta(minutes=1))
    rec = await _reload(db, rec)
    assert rec.status == "dispatched" and rec.action is None
    assert plan.result == "declined" and plan.buttons == "decision"
    [p] = await _prompts(db)
    assert p.status == "declined"


@pytest.mark.asyncio
async def test_unconfirmed_after_window_is_recorded_as_unconfirmed(db):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "non merci", "", NOW)
    n = await svc.expire_stale_prompts(NOW + PROMPT_WINDOW + timedelta(seconds=1))
    assert n == 1
    rec = await _reload(db, rec)
    assert rec.status == "dispatched" and rec.action is None  # never a decision
    [p] = await _prompts(db)
    assert p.status == "expired"
    assert [e.result for e in await _events(db)] == ["confirmation_requested", "confirmation_expired"]

    # A late "oui" no longer confirms anything.
    plan = await svc.handle_deterministic(profile, "oui", "", NOW + timedelta(hours=2))
    assert plan.result == "recorded"  # "oui" is now an explicit accept keyword…
    assert (await _reload(db, rec)).decision_source == "keyword"  # …not a confirmation


@pytest.mark.asyncio
async def test_new_decision_supersedes_open_confirmation(db):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "non merci", "", NOW)
    await svc.handle_deterministic(profile, "", BUTTON_ACCEPT, NOW + timedelta(minutes=1))
    assert (await _reload(db, rec)).status == "accepted"
    [p] = await _prompts(db)
    assert p.status == "superseded"


# ---------------------------------------------------------------------------
# (b) bare acknowledgement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bare_ack_one_pending_in_window_records_accepted(db):
    profile, [rec] = await _seed(db)
    await InboundDecisionService(db).handle_deterministic(profile, "ok merci", "", NOW)
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source) == ("accepted", "bare_ack_rule")


@pytest.mark.asyncio
async def test_bare_ack_two_pending_asks_confirmation(db):
    profile, recs = await _seed(db, pending=2)
    plan = await InboundDecisionService(db).handle_deterministic(profile, "👍", "", NOW)
    assert plan.result == "confirmation_requested"
    for r in recs:
        assert (await _reload(db, r)).status == "dispatched"
    [p] = await _prompts(db)
    assert p.origin == "bare_ack" and p.recommendation_id == recs[0].id  # the most recent


@pytest.mark.asyncio
async def test_bare_ack_outside_window_asks_then_confirms(db):
    profile, [rec] = await _seed(db, dispatched_ago=timedelta(hours=13))
    svc = InboundDecisionService(db)
    plan = await svc.handle_deterministic(profile, "ok", "", NOW)
    assert plan.result == "confirmation_requested"
    await svc.handle_deterministic(profile, "oui", "", NOW + timedelta(minutes=1))
    assert (await _reload(db, rec)).decision_source == "bare_ack_confirmed"


@pytest.mark.asyncio
async def test_bare_ack_nothing_pending_records_nothing(db):
    profile, _ = await _seed(db, pending=0)
    plan = await InboundDecisionService(db).handle_deterministic(profile, "merci", "", NOW)
    assert plan.result == "not_recorded" and plan.extras["why"] == "no_pending_recommendation"


# ---------------------------------------------------------------------------
# Independence of decision and outcome (§16.6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("actual", [None, 20.0, 400.0])
async def test_decision_does_not_depend_on_actual_covers(db, actual):
    profile, [rec] = await _seed(db, actual_covers=actual)
    await InboundDecisionService(db).handle_deterministic(profile, "ok", "", NOW)
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source) == ("accepted", "bare_ack_rule")


# ---------------------------------------------------------------------------
# Background free-text path (the route's _bg_receipt_feedback)
# ---------------------------------------------------------------------------

class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _model(answer: dict | str):
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=answer if isinstance(answer, str) else json.dumps(answer))
    return llm


async def _bg(db, body, llm, reply_mock):
    with (
        patch.object(webhook, "AsyncSessionLocal", lambda: _SessionCtx(db)),
        patch.object(webhook, "ReceiptsService", lambda s: ReceiptsService(s, llm=llm)),
        patch.object(webhook, "_now", lambda: NOW),
        patch.object(webhook._twilio_client, "send_whatsapp", reply_mock),
        patch("app.mcp_server.tool_submit_feedback_to_memory",
              AsyncMock(return_value={"status": "ok"})) as memory,
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        await webhook._bg_receipt_feedback(from_number=f"whatsapp:{PHONE}", body=body)
    return memory


@pytest.mark.asyncio
async def test_model_stance_above_threshold_is_written(db):
    _, [rec] = await _seed(db)
    reply = AsyncMock()
    memory = await _bg(db, "merci mais on ne va pas suivre cette fois",
                       _model({"stance": "decline_proposal", "confidence": 0.93}), reply)
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source) == ("rejected", "model_auto")
    assert float(rec.decision_confidence) == 0.93
    assert memory.await_args.kwargs["outcome"] == "rejected"
    assert "Une raison ? (facultatif)" in reply.await_args.args[1]


@pytest.mark.asyncio
async def test_low_confidence_model_stance_asks_and_writes_nothing(db):
    _, [rec] = await _seed(db)
    reply = AsyncMock()
    memory = await _bg(db, "hmm je sais pas trop",
                       _model({"stance": "decline_proposal", "confidence": 0.55}), reply)
    assert (await _reload(db, rec)).status == "dispatched"
    memory.assert_not_awaited()
    sent = reply.await_args.args[1]
    assert sent.startswith("Je note un refus, c'est bien ça ?") and "OUI ou NON" in sent
    [p] = await _prompts(db)
    assert (p.kind, p.origin, p.proposed_decision) == ("decision_confirmation", "model", "rejected")


@pytest.mark.asyncio
async def test_model_error_records_nothing_and_asks_for_a_decision(db):
    _, [rec] = await _seed(db)
    reply = AsyncMock()
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("api down"))
    memory = await _bg(db, "blah blah", llm, reply)
    assert (await _reload(db, rec)).status == "dispatched"  # old path wrote "modified"
    memory.assert_not_awaited()
    assert "ACCEPTER, REFUSER ou CORRIGER" in reply.await_args.args[1]
    [ev] = await _events(db)
    assert (ev.result, ev.why) == ("not_recorded", "llm_error")


@pytest.mark.asyncio
async def test_reason_in_same_reply_is_stored_typed_and_no_prompt(db):
    _, [rec] = await _seed(db)
    reply = AsyncMock()
    await _bg(db, "non, le mariage est annulé", _model({
        "stance": "decline_proposal", "confidence": 0.95, "reason": "wedding cancelled",
        "reason_route": "upstream_filter", "reason_route_confidence": 0.8,
    }), reply)
    [ev] = await _events(db)
    assert (ev.reason_text, ev.reason_route) == ("wedding cancelled", "upstream_filter")
    assert await _prompts(db) == []  # already have the reason: do not ask
    assert "raison" not in reply.await_args.args[1]


@pytest.mark.asyncio
async def test_reason_reply_is_routed_and_never_changes_the_decision(db):
    profile, [rec] = await _seed(db)
    await InboundDecisionService(db).handle_deterministic(profile, "", BUTTON_REJECT, NOW)
    reply = AsyncMock()
    # The reason text reads like an acceptance: it must NOT flip the decision.
    await _bg(db, "en fait c'est bon on suit, budget gelé ce mois",
              _model({"route": "policy", "confidence": 0.9}), reply)
    rec = await _reload(db, rec)
    assert (rec.status, rec.decision_source) == ("rejected", "button")
    ev = (await _events(db))[-1]
    assert (ev.result, ev.reason_route) == ("reason_captured", "policy")
    assert ev.decision is None
    assert reply.await_args.args[1] == "Merci, c'est noté."


@pytest.mark.asyncio
async def test_reason_below_route_threshold_stays_unrouted(db):
    profile, _ = await _seed(db)
    await InboundDecisionService(db).handle_deterministic(profile, "", BUTTON_CORRECT, NOW)
    await _bg(db, "pas le moment", _model({"route": "memory", "confidence": 0.4}), AsyncMock())
    ev = (await _events(db))[-1]
    assert ev.result == "reason_captured" and ev.reason_route is None
    assert float(ev.reason_route_confidence) == 0.4


@pytest.mark.asyncio
async def test_bare_ack_after_reason_request_closes_it_without_decision(db):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "", BUTTON_REJECT, NOW)
    plan = await svc.handle_deterministic(profile, "ok", "", NOW + timedelta(minutes=1))
    assert plan.result == "reason_captured"
    assert (await _reload(db, rec)).status == "rejected"
    [p] = await _prompts(db)
    assert p.status == "answered"


# ---------------------------------------------------------------------------
# Metrics from the DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capture_metrics_from_events(db):
    profile, recs = await _seed(db, pending=3)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "", BUTTON_ACCEPT, NOW)              # recorded (button)
    await svc.handle_deterministic(profile, "non merci", "", NOW)                # confirmation
    await svc.handle_deterministic(profile, "oui", "", NOW)                      # confirmed
    await svc.handle_deterministic(profile, "no thanks", "", NOW)                # confirmation
    await svc.expire_stale_prompts(NOW + PROMPT_WINDOW + timedelta(seconds=1))   # expired
    m = await svc.capture_metrics(HOTEL, NOW - timedelta(days=1), NOW + timedelta(days=1))
    assert m.decision_seeking_replies == 3
    assert m.decisions_written == 2
    assert m.capture_rate == round(2 / 3, 4)
    assert m.by_source == {"button": 1, "keyword_confirmed": 1}
    assert m.confirmation_rate == 0.5
    assert m.confirmation_timeout_rate == 0.5


# ---------------------------------------------------------------------------
# KPI endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decision_capture_endpoint_is_tenant_scoped(db):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.routes.kpi import get_decision_capture

    profile, _ = await _seed(db)
    with pytest.raises(HTTPException) as exc:
        await get_decision_capture("other_hotel", 7, SimpleNamespace(hotel_id=HOTEL), db)
    assert exc.value.status_code == 403

    real_now = datetime.now(tz=timezone.utc)
    await InboundDecisionService(db).handle_deterministic(profile, "", BUTTON_ACCEPT, real_now)
    resp = await get_decision_capture(HOTEL, 7, SimpleNamespace(hotel_id=HOTEL), db)
    assert resp.decisions_written == 1 and resp.by_source == {"button": 1}
    assert resp.capture_rate == 1.0


@pytest.mark.asyncio
async def test_confirmation_after_recommendation_was_decided_writes_nothing(db):
    profile, [rec] = await _seed(db)
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(profile, "non merci", "", NOW)
    rec.status = "accepted"  # decided on the dashboard meanwhile
    await db.commit()
    plan = await svc.handle_deterministic(profile, "oui", "", NOW + timedelta(minutes=1))
    assert plan.extras["why"] == "recommendation_no_longer_pending"
    assert (await _reload(db, rec)).status == "accepted"
    [p] = await _prompts(db)
    assert p.status == "superseded"


# ---------------------------------------------------------------------------
# ADR-0007 §19 — stance × the stored recommendation's proposal
# ---------------------------------------------------------------------------

_KEEP = {"recommended_delta_staff": 0, "decision_rule": "newsvendor"}


@pytest.mark.asyncio
@pytest.mark.parametrize("headcount,task_class,risk,body,expected", [
    # "pas besoin" (open decision closed by §19): rejects ADD, asks for REDUCE
    (2, "staffing.add", None, "pas besoin", ("recorded", "rejected")),
    (-1, "staffing.reduce", None, "pas besoin", ("confirmation_requested", "dispatched")),
    (0, "staffing.add", _KEEP, "pas besoin", ("recorded", "accepted")),
    (None, None, None, "pas besoin", ("confirmation_requested", "dispatched")),
    # keep current: accepts a "keep the usual staffing" recommendation
    (0, "staffing.add", _KEEP, "non merci on garde tel quel", ("recorded", "accepted")),
    (0, "staffing.add", _KEEP, "non merci", ("confirmation_requested", "dispatched")),
    (-2, "staffing.reduce", None, "on garde tel quel", ("recorded", "rejected")),
    # a plain "non" refuses whatever was proposed
    (0, "staffing.add", _KEEP, "non", ("recorded", "rejected")),
])
async def test_lexicon_reply_is_read_against_the_stored_proposal(
        db, headcount, task_class, risk, body, expected):
    profile, [rec] = await _seed(db)
    rec.recommended_headcount, rec.task_class, rec.risk_assessment = headcount, task_class, risk
    await db.commit()
    plan = await InboundDecisionService(db).handle_deterministic(profile, body, "", NOW)
    rec = await _reload(db, rec)
    assert (plan.result, rec.status) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("headcount,risk,status", [
    (2, None, "rejected"),           # keep current vs "add 2 staff" → rejected
    (0, _KEEP, "accepted"),          # keep current vs "keep the usual staffing" → accepted
    (None, None, "dispatched"),      # direction unknown → confirmation, nothing written
])
async def test_route_shows_the_model_the_proposal_and_maps_its_stance(db, headcount, risk, status):
    _, [rec] = await _seed(db)
    rec.recommended_headcount, rec.risk_assessment = headcount, risk
    await db.commit()
    llm = _model({"stance": "keep_current", "confidence": 0.95})
    await _bg(db, "on reste sur le planning prévu ce soir", llm, AsyncMock())
    content = llm.complete.await_args.kwargs["messages"][0]["content"]
    assert content.endswith("Manager reply: on reste sur le planning prévu ce soir")
    if headcount == 2:
        assert content.startswith("Recommendation: ADD 2 staff for ")
    assert (await _reload(db, rec)).status == status


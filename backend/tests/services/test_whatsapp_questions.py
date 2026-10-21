"""HOS-357 + HOS-354 — a manager's question on WhatsApp, and the staffing figure
of a counter, on a real (SQLite) DB. Twilio and the models are mocked.

The rule under test: a question is never a decision. A position stated in a
question is confirmed, never written; a staffing figure ("2 extras") is quoted
back and reaches ``retained_delta_staff`` only with a correction the manager
made or confirmed.
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
    ConversationalQuery,
    InboundReplyEvent,
    ManagerPrompt,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.explainability_service import ExplainabilityService
from app.services.inbound_decision import InboundDecisionService
from app.services.manager_decision import compute_capture_metrics
from app.services.receipts import ReceiptsService

HOTEL = "hotel_questions"
PHONE = "+15550001111"
NOW = datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
EXPLANATION = "Concert au Zénith ce soir : la demande prévue est en hausse."


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed(db, *, delta: int = 3, status: str = "dispatched"):
    """One recommendation proposing +``delta`` extra staff (newsvendor rule)."""
    profile = RestaurantProfile(
        id=_uuid.uuid4(), tenant_id=HOTEL, property_name="P", outlet_name="O",
        phone_number=PHONE, total_seats=50,
    )
    db.add(profile)
    await db.commit()
    rec = StaffingRecommendation(
        id=_uuid.uuid4(), tenant_id=HOTEL, property_id=profile.id, anomaly_id=_uuid.uuid4(),
        message_text=f"+{delta} extras au service du soir.", triggering_factor="concert",
        window_start=NOW, window_end=NOW, predicted_covers=140.0, status=status,
        dispatched_at=NOW - timedelta(hours=1),
        risk_assessment={"recommended_delta_staff": delta, "decision_rule": "newsvendor"},
    )
    db.add(rec)
    await db.commit()
    return profile, rec


async def _events(db):
    return (await db.execute(select(InboundReplyEvent))).scalars().all()


async def _prompts(db, status: str | None = None):
    q = select(ManagerPrompt)
    if status:
        q = q.where(ManagerPrompt.status == status)
    return (await db.execute(q)).scalars().all()


def _model(answer: dict):
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=json.dumps(answer))
    return llm


def _no_model():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=AssertionError("the model must not be called"))
    return llm


async def _ask(db, profile, body, llm=None):
    """handle_question with a fixed explanation and the receipts parser."""
    parse = ReceiptsService(db, llm=llm or _no_model()).parse_inbound
    return await InboundDecisionService(db).handle_question(
        profile, body, EXPLANATION, parse, NOW, request_id="r1")


def _unchanged(rec):
    return (rec.status, rec.action, rec.decision_source, rec.retained_delta_staff) == (
        "dispatched", None, None, None)


# ---------------------------------------------------------------------------
# A question alone: explained, nothing written, open prompt left alone
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_question_alone_is_explained_and_writes_nothing(db):
    profile, rec = await _seed(db)
    plan = await _ask(db, profile, "pourquoi ?", _model({"stance": "none", "confidence": 0.9}))
    await db.refresh(rec)
    assert _unchanged(rec)
    assert plan.text == EXPLANATION
    assert plan.buttons == "decision"            # how to decide, via the buttons / text hint
    assert await _prompts(db) == []
    [ev] = await _events(db)
    assert (ev.result, ev.why, ev.decision) == ("question_answered", "explained", None)


@pytest.mark.asyncio
async def test_question_leaves_an_open_prompt_untouched(db):
    profile, rec = await _seed(db)
    db.add(ManagerPrompt(
        created_at=NOW - timedelta(minutes=5), tenant_id=HOTEL, property_id=profile.id,
        recommendation_id=rec.id, kind="decision_confirmation", proposed_decision="rejected",
        origin="model", confidence=0.6, status="pending",
        expires_at=NOW + timedelta(minutes=55), request_id="r0",
    ))
    await db.commit()
    await _ask(db, profile, "c'est pour quel service ?", _model({"stance": "none", "confidence": 0.9}))
    [prompt] = await _prompts(db)
    assert prompt.status == "pending"            # neither closed nor replaced, like recap


@pytest.mark.asyncio
async def test_question_does_not_count_as_a_decision_seeking_reply(db):
    profile, _ = await _seed(db)
    await _ask(db, profile, "pourquoi ?", _model({"stance": "none", "confidence": 0.9}))
    rows = [{"result": e.result, "decision_source": e.decision_source, "why": e.why}
            for e in await _events(db)]
    metrics = compute_capture_metrics(rows)
    assert metrics.decision_seeking_replies == 0


# ---------------------------------------------------------------------------
# A question with a position: explained, then confirmed — never written
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_question_with_a_figure_quotes_it_and_writes_nothing(db):
    profile, rec = await _seed(db, delta=3)
    plan = await _ask(db, profile, "pourquoi 3 extras ? 2 suffisent")   # no model call
    await db.refresh(rec)
    assert _unchanged(rec)
    assert plan.text.startswith(EXPLANATION + "\n\n")
    assert "Je note 2 extras au lieu de 3, c'est bien ça ?" in plan.text
    assert plan.buttons == "confirm"
    [prompt] = await _prompts(db)
    assert (prompt.kind, prompt.proposed_decision, prompt.origin, prompt.retained_delta_staff) == (
        "decision_confirmation", "modified", "question", 2)


@pytest.mark.asyncio
async def test_yes_writes_the_quoted_figure(db):
    profile, rec = await _seed(db, delta=3)
    await _ask(db, profile, "pourquoi 3 extras ? 2 suffisent")
    plan = await InboundDecisionService(db).handle_deterministic(profile, "oui", "", NOW)
    await db.refresh(rec)
    assert (rec.status, rec.decision_source, rec.retained_delta_staff) == (
        "modified", "question_confirmed", 2)
    assert plan.text.startswith("Correction enregistrée : 2 extras.")
    assert "Une raison ? (facultatif)" in plan.text   # the change is known: only why


@pytest.mark.asyncio
async def test_no_writes_nothing(db):
    profile, rec = await _seed(db, delta=3)
    await _ask(db, profile, "pourquoi 3 extras ? 2 suffisent")
    await InboundDecisionService(db).handle_deterministic(profile, "non", "", NOW)
    await db.refresh(rec)
    assert _unchanged(rec)


@pytest.mark.asyncio
async def test_confident_model_position_in_a_question_is_still_confirmed(db):
    profile, rec = await _seed(db)
    plan = await _ask(db, profile, "ok mais pourquoi ?",
                      _model({"stance": "adopt_proposal", "confidence": 0.99}))
    await db.refresh(rec)
    assert _unchanged(rec)
    assert "Je note une validation, c'est bien ça ?" in plan.text
    [prompt] = await _prompts(db)
    assert (prompt.proposed_decision, prompt.origin) == ("accepted", "question")


@pytest.mark.asyncio
async def test_bare_number_in_a_question_asks_the_unit(db):
    profile, rec = await _seed(db)
    plan = await _ask(db, profile, "pourquoi ? plutôt 2")
    await db.refresh(rec)
    assert _unchanged(rec)
    assert plan.text.endswith("2 quoi ? Pour que je le note, répondez par exemple « 2 extras » ou « 2 de moins ».")
    assert await _prompts(db) == []
    [ev] = await _events(db)
    assert (ev.result, ev.why) == ("question_answered", "figure_unit_unknown")


@pytest.mark.asyncio
async def test_covers_figure_in_a_question_is_not_a_correction(db):
    profile, rec = await _seed(db)
    plan = await _ask(db, profile, "pourquoi 140 covers ?", _model({"stance": "none", "confidence": 0.9}))
    await db.refresh(rec)
    assert _unchanged(rec) and rec.actual_covers is None
    assert plan.result == "question_answered"


@pytest.mark.asyncio
async def test_no_pending_recommendation_no_model_call(db):
    profile, _ = await _seed(db, status="accepted")
    plan = await _ask(db, profile, "pourquoi 3 extras ? 2 suffisent")
    assert plan.text == EXPLANATION and plan.buttons is None
    assert await _prompts(db) == []


# ---------------------------------------------------------------------------
# The route's background task, end to end
# ---------------------------------------------------------------------------

class _SessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_bg_question_answers_the_manager_number_and_records_nothing(db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "PII_HASH_PEPPER", "test-pepper-not-a-real-secret")
    _, rec = await _seed(db, delta=3)
    reply = AsyncMock(return_value="SM1")
    explainer_llm = AsyncMock()
    explainer_llm.complete = AsyncMock(return_value=EXPLANATION)
    with (
        patch.object(webhook, "AsyncSessionLocal", lambda: _SessionCtx(db)),
        patch.object(webhook, "ReceiptsService", lambda s: ReceiptsService(s, llm=_no_model())),
        patch.object(webhook, "ExplainabilityService", lambda: ExplainabilityService(llm=explainer_llm)),
        patch.object(webhook, "_now", lambda: NOW),
        patch.object(webhook._twilio_client, "send_whatsapp", reply),
    ):
        await webhook._bg_question(from_number=f"whatsapp:{PHONE}", body="pourquoi 3 extras ? 2 suffisent")

    await db.refresh(rec)
    assert _unchanged(rec)
    to, text = reply.await_args.args
    assert to == f"whatsapp:{PHONE}"                 # the number, never the stored digest
    assert text.startswith(EXPLANATION) and "Je note 2 extras au lieu de 3" in text
    [query] = (await db.execute(select(ConversationalQuery))).scalars().all()
    assert query.status == "answered" and query.from_number != PHONE
    assert query.tenant_id == HOTEL                   # the hotel's key, not the property UUID


# ---------------------------------------------------------------------------
# HOS-354 — the figure of a counter outside a question
# ---------------------------------------------------------------------------

async def _free_text(db, profile, body, answer):
    feedback = await ReceiptsService(db, llm=_model(answer)).parse_inbound(
        body, InboundDecisionService.proposal_of(
            (await InboundDecisionService(db).pending_recommendations(profile))[0]))
    plan, _, _ = await InboundDecisionService(db).handle_free_text(profile, feedback, NOW, "r2")
    return feedback, plan


@pytest.mark.asyncio
async def test_counter_with_a_figure_is_written_with_it(db):
    profile, rec = await _seed(db, delta=3)
    _, plan = await _free_text(db, profile, "plutôt 2 extras",
                               {"stance": "counter_value", "confidence": 0.95})
    await db.refresh(rec)
    assert (rec.status, rec.decision_source, rec.retained_delta_staff) == ("modified", "model_auto", 2)
    assert plan.text.startswith("Correction enregistrée : 2 extras.")


@pytest.mark.asyncio
async def test_low_confidence_counter_quotes_the_figure_then_writes_it_on_yes(db):
    profile, rec = await _seed(db, delta=3)
    _, plan = await _free_text(db, profile, "plutôt 2 extras je pense",
                               {"stance": "counter_value", "confidence": 0.6})
    await db.refresh(rec)
    assert _unchanged(rec)
    assert plan.text.startswith("Je note 2 extras au lieu de 3, c'est bien ça ?")
    await InboundDecisionService(db).handle_deterministic(profile, "oui", "", NOW)
    await db.refresh(rec)
    assert (rec.status, rec.decision_source, rec.retained_delta_staff) == (
        "modified", "model_confirmed", 2)


@pytest.mark.asyncio
async def test_role_noun_without_marker_is_not_written_as_a_delta(db):
    profile, rec = await _seed(db, delta=3)
    await _free_text(db, profile, "mais 3 serveurs au lieu de 4",
                     {"stance": "counter_value", "confidence": 0.95})
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("modified", None)   # extra, or a total?


@pytest.mark.asyncio
async def test_figure_is_ignored_when_the_decision_is_not_a_correction(db):
    profile, rec = await _seed(db, delta=3)
    await _free_text(db, profile, "non, pas 2 extras non plus",
                     {"stance": "decline_proposal", "confidence": 0.95})
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("rejected", None)


@pytest.mark.asyncio
async def test_covers_and_staff_in_one_reply_are_kept_apart(db):
    profile, rec = await _seed(db, delta=3)
    feedback, _ = await _free_text(db, profile, "dinner covers 180, 2 extras would have been enough",
                                   {"stance": "counter_value", "confidence": 0.95})
    await db.refresh(rec)
    assert feedback.actual_value == 180.0             # covers → actual_covers (route, HOS-250 guard)
    assert rec.retained_delta_staff == 2              # staff → retained_delta_staff
    assert rec.status == "modified"


@pytest.mark.asyncio
async def test_figure_given_after_quel_changement_completes_the_correction(db):
    profile, rec = await _seed(db, delta=3)
    await _free_text(db, profile, "on fait autrement ce soir",
                     {"stance": "counter_value", "confidence": 0.95})
    [prompt] = await _prompts(db, status="pending")
    assert prompt.kind == "reason_request"
    plan = await InboundDecisionService(db).handle_reason(
        profile, prompt, "1 de plus seulement, le groupe a annulé", None, None, NOW, "r3")
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("modified", 1)
    assert plan.text == "Merci, c'est noté : 1 extra."


@pytest.mark.asyncio
async def test_reason_never_overwrites_a_figure_or_touches_a_refusal(db):
    profile, rec = await _seed(db, delta=3)
    await _free_text(db, profile, "non merci", {"stance": "decline_proposal", "confidence": 0.95})
    [prompt] = await _prompts(db, status="pending")
    await InboundDecisionService(db).handle_reason(
        profile, prompt, "2 extras auraient suffi", None, None, NOW, "r4")
    await db.refresh(rec)
    assert (rec.status, rec.retained_delta_staff) == ("rejected", None)

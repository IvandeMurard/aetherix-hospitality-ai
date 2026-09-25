"""ADR-0007 §17.2–17.3, §17.6 — deterministic recap, WhatsApp commands,
"corriger mardi" revision, weekly push rule, MCP recap tool, and the single
acceptance definition shared with the KPI route.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    Base,
    InboundReplyEvent,
    ManagerPrompt,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.decision_recap import (
    RecRow,
    acceptance_rate,
    build_recap,
    period_bounds,
    render_text,
    summarize,
)
from app.services.inbound_decision import InboundDecisionService
from app.services.manager_decision import (
    BUTTON_CONFIRM_YES,
    compute_capture_metrics,
    match_keyword,
    match_recap_command,
    match_revision_command,
)
from app.workers.recap_dispatcher import SESSION_WINDOW, push_mode

HOTEL = "hotel_recap"
PHONE = "+15550001111"
# Thursday 24/09/2026 12:00 UTC (RECEIPT_TIMEZONE defaults to UTC)
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
MON = date(2026, 9, 21)


def _row(status="dispatched", decided_by=None, source=None, predicted=None, actual=None,
         day=0, waiting=False, latency_min=30):
    received = datetime(2026, 9, 21, 8, tzinfo=timezone.utc) + timedelta(days=day)
    return RecRow(
        id=_uuid.uuid4(), received_at=received, window_start=received + timedelta(hours=11),
        status=status, decided_by=decided_by, decision_source=source,
        actioned_at=received + timedelta(minutes=latency_min) if decided_by else None,
        predicted_covers=predicted, actual_covers=actual, awaiting_confirmation=waiting,
    )


# ---------------------------------------------------------------------------
# Pure: summarize + render
# ---------------------------------------------------------------------------

def test_summary_counts_sources_and_forecast_error():
    rows = [
        _row("accepted", "human_whatsapp", "button", 100, 80, day=0),
        _row("rejected", "human_whatsapp", "keyword", 150, 150, day=1),
        _row("modified", "human_via_host", "host_relay", day=1),
        _row("accepted", "human_whatsapp", "model_confirmed", day=2),
        _row("dispatched", waiting=True, day=2),
        _row("dispatched", day=3),
        _row("accepted", None, None, day=3),  # legacy, unattributed
    ]
    s = summarize(rows, "week", MON, NOW.date())
    assert (s.received, s.accepted, s.rejected, s.corrected) == (7, 3, 1, 1)
    assert (s.no_reply, s.awaiting_confirmation) == (1, 1)
    assert s.by_source == {"button": 1, "keyword": 1, "host": 1, "confirmed": 1, "unattributed": 1}
    assert s.by_decided_by == {"human_whatsapp": 3, "human_via_host": 1, "unattributed": 1}
    # human rate excludes the unattributed legacy row: 2 accepted / 4 decided
    assert (s.human.decided, s.human.accepted, s.human.acceptance_rate) == (4, 2, 0.5)
    assert s.human.override_rate == 0.5
    assert s.human.median_response_minutes == 30.0
    # |100-80|/80 = 25 %, 0 % → 12.5 % over 2 days, 2 observations
    assert (s.forecast_error_pct, s.forecast_error_days, s.forecast_error_observations) == (12.5, 2, 2)


def test_agent_decisions_never_feed_human_rates():
    rows = [_row("accepted", "host_agent_autonomous", "host_agent")] * 3 + [
        _row("rejected", "human_via_host", "host_relay")]
    s = summarize(rows, "week", MON, NOW.date())
    assert (s.human.decided, s.human.acceptance_rate) == (1, 0.0)
    assert (s.agent.decided, s.agent.acceptance_rate) == (3, 1.0)


def test_acceptance_rate_is_none_without_decisions():
    assert acceptance_rate(0, 0) is None


def test_render_fr_compact_block():
    rows = [_row("accepted", "human_whatsapp", "button", 100, 80), _row("dispatched")]
    text = render_text(summarize(rows, "week", MON, NOW.date()), "fr")
    assert text.splitlines() == [
        "Récap semaine · 21/09–24/09",
        "Recommandations reçues : 2",
        "Validées 1 · Refusées 0 · Corrigées 0",
        "Sans réponse 1 · À confirmer 0",
        "Écart moyen prévision/réel : 25 % (1 jour mesuré)",
        "Décidé via : bouton 1",
        "Décision mal enregistrée ? Répondez « corriger mardi ».",
    ]


def test_render_en_and_no_actuals_says_so():
    text = render_text(summarize([_row("rejected", "human_whatsapp", "keyword")], "day",
                                 NOW.date(), NOW.date()), "en")
    assert text.startswith("Recap day · 24/09–24/09")
    assert "Forecast error: no actual covers entered in this period." in text
    assert "%" not in text


def test_render_no_data_says_so_and_nothing_else():
    text = render_text(summarize([], "month", date(2026, 9, 1), NOW.date()), "fr")
    assert text == "Récap mois · 01/09–24/09\nAucune recommandation sur la période."


def test_period_bounds():
    assert period_bounds("day", NOW) == (NOW.date(), NOW.date())
    assert period_bounds("week", NOW) == (MON, NOW.date())
    assert period_bounds("month", NOW) == (date(2026, 9, 1), NOW.date())


# ---------------------------------------------------------------------------
# Pure: command parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body,period,locale", [
    ("recap", "week", None), ("Récap", "week", "fr"), ("recap jour", "day", "fr"),
    ("recap semaine", "week", "fr"), ("RECAP MOIS", "month", "fr"), ("recap day", "day", "en"),
    ("recap week", "week", "en"), ("recap month", "month", "en"), ("summary", "week", "en"),
    ("recap aujourd'hui", "day", "fr"),
])
def test_recap_commands(body, period, locale):
    cmd = match_recap_command(body)
    assert (cmd.period, cmd.locale) == (period, locale)


@pytest.mark.parametrize("body", ["recap hier", "recap de la semaine stp", "le recap", "ok"])
def test_not_recap_commands(body):
    assert match_recap_command(body) is None


def test_revision_commands_and_modify_keyword_stay_apart():
    assert match_revision_command("corriger") is None
    assert match_keyword("corriger").units == ("counter",)
    cmd = match_revision_command("corriger mardi refus")
    assert (cmd.weekday, cmd.decision, cmd.ref) == (1, "rejected", "mardi")
    assert match_revision_command("fix yesterday accepted").days_ago == 1
    assert match_revision_command("corriger 21/09").target_date(NOW.date()) == date(2026, 9, 21)
    assert match_revision_command("corriger mardi").target_date(NOW.date()) == date(2026, 9, 22)
    assert match_revision_command("corriger jeudi").target_date(NOW.date()) == NOW.date()
    assert match_revision_command("corriger mardi bof") is None


def test_revisions_and_recaps_are_not_decision_seeking():
    m = compute_capture_metrics([
        {"result": "recap_served"}, {"result": "revision_requested"},
        {"result": "revised", "decision_source": "manager_revision"},
        {"result": "recorded", "decision_source": "button"},
    ])
    assert (m.decision_seeking_replies, m.decisions_written, m.revisions) == (1, 1, 1)


# ---------------------------------------------------------------------------
# Weekly push — 24 h rule
# ---------------------------------------------------------------------------

def test_push_mode_rules():
    assert push_mode(False, "HX1", NOW, NOW) == "not_opted_in"
    assert push_mode(True, "HX1", None, NOW) == "template"
    assert push_mode(True, "", NOW - timedelta(hours=2), NOW) == "session"
    assert push_mode(True, "", NOW - SESSION_WINDOW + timedelta(minutes=10), NOW) == "outside_window"
    assert push_mode(True, "", None, NOW) == "outside_window"


# ---------------------------------------------------------------------------
# DB: recap, WhatsApp commands, revision
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _profile(db, opt_in=False):
    p = RestaurantProfile(id=_uuid.uuid4(), tenant_id=HOTEL, property_name="P", outlet_name="O",
                          phone_number=PHONE, total_seats=50, weekly_recap_opt_in=opt_in)
    db.add(p)
    await db.commit()
    return p


async def _rec(db, profile, *, day: date, status="dispatched", decided_by=None, source=None,
               predicted=120.0, actual=None, tenant=HOTEL):
    ws = datetime(day.year, day.month, day.day, 19, tzinfo=timezone.utc)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(), tenant_id=tenant, property_id=profile.id, anomaly_id=_uuid.uuid4(),
        message_text="m", window_start=ws, window_end=ws, dispatched_at=ws - timedelta(hours=8),
        status=status, decided_by=decided_by, decision_source=source,
        actioned_at=ws - timedelta(hours=7) if decided_by else None,
        predicted_covers=predicted, actual_covers=actual,
    )
    db.add(rec)
    await db.commit()
    return rec


@pytest.mark.asyncio
async def test_build_recap_is_tenant_scoped_and_counts_pending_confirmation(db):
    p = await _profile(db)
    await _rec(db, p, day=MON, status="accepted", decided_by="human_whatsapp", source="keyword",
               actual=100.0)
    waiting = await _rec(db, p, day=date(2026, 9, 23))
    await _rec(db, p, day=MON, status="accepted", decided_by="human_whatsapp", tenant="other")
    await _rec(db, p, day=date(2026, 9, 14), status="rejected", decided_by="human_whatsapp")  # last week
    db.add(ManagerPrompt(tenant_id=HOTEL, property_id=p.id, recommendation_id=waiting.id,
                         kind="decision_confirmation", proposed_decision="rejected",
                         status="pending", expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
    await db.commit()
    s = await build_recap(db, HOTEL, "week", now=NOW)
    assert (s.received, s.accepted, s.awaiting_confirmation, s.no_reply) == (2, 1, 1, 0)
    assert (s.forecast_error_pct, s.forecast_error_days) == (20.0, 1)


@pytest.mark.asyncio
async def test_whatsapp_recap_command_replies_with_the_template(db):
    p = await _profile(db)
    await _rec(db, p, day=MON, status="rejected", decided_by="human_whatsapp", source="button")
    plan = await InboundDecisionService(db).handle_deterministic(p, "recap semaine", "", NOW)
    assert plan.result == "recap_served"
    assert plan.text.startswith("Récap semaine · 21/09–24/09\nRecommandations reçues : 1")
    [ev] = (await db.execute(select(InboundReplyEvent))).scalars().all()
    assert (ev.result, ev.why) == ("recap_served", "week")


@pytest.mark.asyncio
async def test_recap_does_not_disturb_a_pending_confirmation(db):
    p = await _profile(db)
    rec = await _rec(db, p, day=date(2026, 9, 24))
    prompt = ManagerPrompt(tenant_id=HOTEL, property_id=p.id, recommendation_id=rec.id,
                           kind="decision_confirmation", proposed_decision="rejected", origin="model",
                           status="pending", expires_at=NOW + timedelta(minutes=30))
    db.add(prompt)
    await db.commit()
    await InboundDecisionService(db).handle_deterministic(p, "recap", "", NOW)
    await db.refresh(prompt)
    assert prompt.status == "pending"


@pytest.mark.asyncio
async def test_revision_goes_through_confirmation_then_replaces_the_decision(db):
    p = await _profile(db)
    rec = await _rec(db, p, day=date(2026, 9, 22), status="accepted", decided_by="human_whatsapp",
                     source="bare_ack_rule")
    svc = InboundDecisionService(db)

    info = await svc.handle_deterministic(p, "corriger mardi", "", NOW)
    assert info.result == "revision_info"
    assert info.text.startswith("Mardi 22/09 : Validation enregistrée.")
    await db.refresh(rec)
    assert rec.status == "accepted"

    ask = await svc.handle_deterministic(p, "corriger mardi refus", "", NOW)
    assert ask.result == "revision_requested" and ask.buttons == "confirm"
    assert "je remplace une validation par un refus" in ask.text
    await db.refresh(rec)
    assert rec.status == "accepted"  # nothing written before yes

    done = await svc.handle_deterministic(p, "", BUTTON_CONFIRM_YES, NOW + timedelta(minutes=1))
    await db.refresh(rec)
    assert done.result == "revised"
    assert (rec.status, rec.decision_source, rec.decided_by) == (
        "rejected", "manager_revision", "human_whatsapp")
    ev = (await db.execute(select(InboundReplyEvent).where(InboundReplyEvent.result == "revised"))).scalars().one()
    assert ev.why == "revised_from_accepted"


@pytest.mark.asyncio
async def test_revision_declined_changes_nothing(db):
    p = await _profile(db)
    rec = await _rec(db, p, day=date(2026, 9, 22), status="rejected", decided_by="human_whatsapp",
                     source="keyword")
    svc = InboundDecisionService(db)
    await svc.handle_deterministic(p, "corriger mardi validation", "", NOW)
    plan = await svc.handle_deterministic(p, "non", "", NOW + timedelta(minutes=1))
    await db.refresh(rec)
    assert plan.result == "revision_declined" and rec.status == "rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize("seed,why", [(0, "no_decision_that_day"), (2, "several_recommendations_that_day")])
async def test_revision_needs_exactly_one_decision_that_day(db, seed, why):
    p = await _profile(db)
    for _ in range(seed):
        await _rec(db, p, day=date(2026, 9, 22), status="accepted", decided_by="human_whatsapp")
    plan = await InboundDecisionService(db).handle_deterministic(p, "corriger mardi refus", "", NOW)
    assert (plan.result, plan.extras["why"]) == ("revision_info", why)
    assert (await db.execute(select(ManagerPrompt))).scalars().all() == []


@pytest.mark.asyncio
async def test_whatsapp_decision_records_decided_by_and_policy(db):
    p = await _profile(db)
    rec = await _rec(db, p, day=date(2026, 9, 24))
    await InboundDecisionService(db).handle_deterministic(p, "oui", "", NOW)
    await db.refresh(rec)
    assert (rec.decided_by, rec.decision_policy_version) == ("human_whatsapp", "default-human-validation-v1")


# ---------------------------------------------------------------------------
# Weekly push on DB, MCP recap tool, KPI route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weekly_push_outside_window_is_not_sent(db):
    from app.workers import recap_dispatcher

    p = await _profile(db, opt_in=True)
    with patch.object(recap_dispatcher, "_twilio") as tw:
        tw.send_whatsapp = AsyncMock()
        mode = await recap_dispatcher.dispatch_weekly_recap(db, p, NOW)
    assert mode == "outside_window"
    tw.send_whatsapp.assert_not_awaited()


@pytest.mark.asyncio
async def test_weekly_push_inside_session_sends_last_weeks_recap(db):
    from app.workers import recap_dispatcher

    p = await _profile(db, opt_in=True)
    await _rec(db, p, day=date(2026, 9, 15), status="accepted", decided_by="human_whatsapp", source="button")
    db.add(InboundReplyEvent(tenant_id=HOTEL, property_id=p.id, channel="text", result="recap_served",
                             created_at=NOW - timedelta(hours=3)))
    await db.commit()
    with patch.object(recap_dispatcher, "_twilio") as tw:
        tw.send_whatsapp = AsyncMock()
        mode = await recap_dispatcher.dispatch_weekly_recap(db, p, NOW)
    assert mode == "session"
    text = tw.send_whatsapp.await_args.args[1]
    assert text.startswith("Récap semaine · 14/09–20/09\nRecommandations reçues : 1")


@pytest.mark.asyncio
async def test_mcp_recap_tool_same_content(db):
    from app.mcp_core import MCPAuthError
    from app.mcp_server import tool_get_decision_recap

    p = await _profile(db)
    await _rec(db, p, day=date.today(), status="accepted", decided_by="human_whatsapp", source="button")
    out = await tool_get_decision_recap(HOTEL, db, period="day", locale="en")
    assert out["recap"]["accepted"] == 1
    assert out["text"].startswith("Recap day")
    with pytest.raises(MCPAuthError):
        await tool_get_decision_recap(HOTEL, db, period="year")


@pytest.mark.asyncio
async def test_kpi_acceptance_route_uses_the_recap_definition(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import kpi
    from app.db.session import get_db

    p = await _profile(db)
    today = date.today()
    await _rec(db, p, day=today, status="accepted", decided_by="human_whatsapp", source="button")
    await _rec(db, p, day=today, status="rejected", decided_by="human_via_host", source="host_relay")
    await _rec(db, p, day=today, status="accepted", decided_by="host_agent_autonomous", source="host_agent")
    await _rec(db, p, day=today, status="accepted")  # legacy, unattributed
    await _rec(db, p, day=today)                     # no reply

    app = FastAPI()
    app.include_router(kpi.router, prefix="/api/v1")

    async def _db():
        yield db

    tok = MagicMock(hotel_id=HOTEL, scopes=["receipts:read"])
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[kpi._kpi_auth] = lambda: tok
    with TestClient(app) as client:
        body = client.get(f"/api/v1/kpi/{HOTEL}/recommendation_acceptance?days=7").json()
    assert (body["rolling_rate"], body["decided"], body["accepted"]) == (0.5, 2, 1)
    assert body["agent_decided"] == 1 and body["no_reply"] == 1
    assert body["by_decided_by"]["unattributed"] == 1
    assert body["daily"][-1]["rate"] == 0.5
    assert "human decisions only" in body["definition"]

"""HOS-317 (Story 16.16) — Decision Ledger end-to-end.

AC3: "for recommendation X, what did the manager answer and what actually
happened" — answered in one query, across the five tables that used to hold the
loop in fragments.

Covered:
  1.  Full loop — context → recommendation → WhatsApp answer → measured outcome
  2.  Dashboard accept/reject wins over the WhatsApp memory row
  3.  Unanswered recommendation is still a ledger row (is_closed False)
  4.  Tenant isolation guard on get_decision
  5.  abs_pct_error computed only when both legs exist
  6.  Abstention telemetry joined via request_id
  7.  list_decisions ordering + closed_only filter
  8.  The write paths actually stamp recommendation_id (the edge HOS-317 added)
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    AgentActionLog,
    Base,
    DemandAnomaly,
    OperationalMemory,
    StaffingRecommendation,
)
from app.services.decision_ledger import DecisionLedgerService

HOTEL = "hotel_ledger"
OTHER_HOTEL = "hotel_other"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# Seeding helpers — one per leg of the loop
# ---------------------------------------------------------------------------

async def _seed_context(session, *, tenant_id=HOTEL, property_id=None):
    """Leg 1 — the demand anomaly that triggered the recommendation."""
    now = datetime.now(tz=timezone.utc)
    anomaly = DemandAnomaly(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        property_id=property_id or _uuid.uuid4(),
        window_start=now + timedelta(hours=4),
        window_end=now + timedelta(hours=8),
        expected_demand=140,
        baseline_demand=95,
        deviation_pct=47.4,
        direction="surge",
        triggering_factors=[{"type": "event", "label": "Convention centre gala"}],
        status="ready_to_push",
        detected_at=now - timedelta(hours=2),
    )
    session.add(anomaly)
    await session.flush()
    return anomaly


async def _seed_recommendation(
    session,
    anomaly=None,
    *,
    tenant_id=HOTEL,
    predicted_covers=140.0,
    dispatched=True,
):
    """Leg 2 — the recommendation emitted for that context.

    `anomaly_id` is NOT NULL: a recommendation always descends from a detected
    anomaly, so the helper seeds one when the caller doesn't care about it.
    """
    now = datetime.now(tz=timezone.utc)
    if anomaly is None:
        anomaly = await _seed_context(session, tenant_id=tenant_id)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        property_id=anomaly.property_id,
        anomaly_id=anomaly.id,
        message_text="Add 2 servers for tonight's dinner service.",
        triggering_factor="Convention centre gala",
        recommended_headcount=2,
        window_start=now + timedelta(hours=4),
        window_end=now + timedelta(hours=8),
        roi_net=310.00,
        status="dispatched" if dispatched else "ready_to_push",
        dispatched_at=now - timedelta(hours=1) if dispatched else None,
        dispatch_channel="whatsapp" if dispatched else None,
        predicted_covers=predicted_covers,
    )
    session.add(rec)
    await session.flush()
    return rec


async def _seed_manager_answer(
    session, rec, *, feedback="followed", request_id="req-ledger-1"
):
    """Leg 3 — the manager's WhatsApp answer (operational_memory)."""
    mem = OperationalMemory(
        id=_uuid.uuid4(),
        hotel_id=rec.tenant_id,
        reflection=f"[rec={rec.id}] outcome=accepted notes=took the extra cover",
        manager_feedback=feedback,
        outcome="accepted",
        memory_type="feedback",
        embedding_pending=True,
        request_id=request_id,
        recommendation_id=rec.id,
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(mem)
    await session.flush()
    return mem


async def _seed_outcome(session, rec, *, actual=155.0, request_id="req-ledger-1"):
    """Leg 4 — the measured outcome (ground truth on both surfaces)."""
    now = datetime.now(tz=timezone.utc)
    rec.actual_covers = actual
    rec.actual_covers_source = "manager_feedback"
    rec.actual_covers_at = now
    mem = OperationalMemory(
        id=_uuid.uuid4(),
        hotel_id=rec.tenant_id,
        reflection=f"actual covers {actual} vs predicted {rec.predicted_covers} on {now.date()}",
        memory_type="ground_truth",
        tags=["ground_truth", "covers_correction"],
        embedding_pending=True,
        request_id=request_id,
        recommendation_id=rec.id,
        created_at=now,
    )
    session.add(mem)
    await session.flush()
    return mem


# ---------------------------------------------------------------------------
# 1. The AC3 query
# ---------------------------------------------------------------------------

class TestFullLoop:
    @pytest.mark.asyncio
    async def test_context_recommendation_answer_outcome(self, db_session):
        anomaly = await _seed_context(db_session)
        rec = await _seed_recommendation(db_session, anomaly)
        await _seed_manager_answer(db_session, rec)
        await _seed_outcome(db_session, rec, actual=155.0)
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)

        assert record is not None
        # Leg 1 — source context + data quality
        assert record.anomaly_id == anomaly.id
        assert record.direction == "surge"
        assert record.deviation_pct == pytest.approx(47.4)
        assert record.triggering_factors[0]["label"] == "Convention centre gala"
        # Leg 2 — recommendation emitted
        assert record.recommended_headcount == 2
        assert record.predicted_covers == pytest.approx(140.0)
        assert record.dispatch_channel == "whatsapp"
        # Leg 3 — manager answer
        assert record.manager_response == "followed"
        assert record.manager_response_channel == "whatsapp"
        assert record.feedback_memory_id is not None
        # Leg 4 — measured outcome
        assert record.actual_covers == pytest.approx(155.0)
        assert record.actual_covers_source == "manager_feedback"
        assert record.outcome_memory_id is not None
        # The loop is closed, and quantified.
        assert record.is_closed is True
        assert record.abs_pct_error == pytest.approx(9.68, abs=0.01)
        assert len(record.memory_ids) == 2

    @pytest.mark.asyncio
    async def test_unknown_recommendation_returns_none(self, db_session):
        service = DecisionLedgerService(db_session)
        assert await service.get_decision(_uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# 2-3. Manager response: two channels, and the absence of one
# ---------------------------------------------------------------------------

class TestManagerResponse:
    @pytest.mark.asyncio
    async def test_dashboard_action_wins_over_memory_row(self, db_session):
        """action_logger writes the column; WhatsApp writes the memory row.
        When both exist the explicit dashboard decision is authoritative."""
        rec = await _seed_recommendation(db_session)
        rec.action = "rejected"
        rec.actioned_at = datetime.now(tz=timezone.utc)
        await _seed_manager_answer(db_session, rec, feedback="followed")
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)

        assert record.manager_response == "rejected"
        assert record.manager_response_channel == "dashboard"
        # …without losing the WhatsApp trace.
        assert record.feedback_memory_id is not None

    @pytest.mark.asyncio
    async def test_unanswered_recommendation_is_still_a_ledger_row(self, db_session):
        """A dispatched recommendation nobody answered is the most interesting
        row in an adoption audit — it must not disappear from the ledger."""
        rec = await _seed_recommendation(db_session)
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)

        assert record is not None
        assert record.manager_response is None
        assert record.manager_response_channel is None
        assert record.is_closed is False
        assert record.abs_pct_error is None


# ---------------------------------------------------------------------------
# 4. Tenant isolation
# ---------------------------------------------------------------------------

class TestIsolation:
    @pytest.mark.asyncio
    async def test_tenant_guard_blocks_cross_property_read(self, db_session):
        rec = await _seed_recommendation(db_session, tenant_id=HOTEL)
        await db_session.commit()
        service = DecisionLedgerService(db_session)

        assert await service.get_decision(rec.id, tenant_id=HOTEL) is not None
        assert await service.get_decision(rec.id, tenant_id=OTHER_HOTEL) is None

    @pytest.mark.asyncio
    async def test_list_decisions_is_scoped_to_tenant(self, db_session):
        await _seed_recommendation(db_session, tenant_id=HOTEL)
        await _seed_recommendation(db_session, tenant_id=OTHER_HOTEL)
        await db_session.commit()

        records = await DecisionLedgerService(db_session).list_decisions(HOTEL)

        assert len(records) == 1
        assert records[0].tenant_id == HOTEL


# ---------------------------------------------------------------------------
# 5. Error only when both legs exist
# ---------------------------------------------------------------------------

class TestAbsPctError:
    @pytest.mark.asyncio
    async def test_none_without_outcome(self, db_session):
        rec = await _seed_recommendation(db_session, predicted_covers=140.0)
        await db_session.commit()
        record = await DecisionLedgerService(db_session).get_decision(rec.id)
        assert record.abs_pct_error is None

    @pytest.mark.asyncio
    async def test_none_when_actual_is_zero(self, db_session):
        """Guard against division by zero — a closed venue reports 0 covers."""
        rec = await _seed_recommendation(db_session, predicted_covers=140.0)
        await _seed_outcome(db_session, rec, actual=0.0)
        await db_session.commit()
        record = await DecisionLedgerService(db_session).get_decision(rec.id)
        assert record.abs_pct_error is None

    @pytest.mark.asyncio
    async def test_exact_forecast_is_zero_error(self, db_session):
        rec = await _seed_recommendation(db_session, predicted_covers=120.0)
        await _seed_outcome(db_session, rec, actual=120.0)
        await db_session.commit()
        record = await DecisionLedgerService(db_session).get_decision(rec.id)
        assert record.abs_pct_error == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 6. Abstention telemetry joins in via request_id
# ---------------------------------------------------------------------------

class TestAbstentionTelemetry:
    @pytest.mark.asyncio
    async def test_abstention_reason_joined_from_action_log(self, db_session):
        rec = await _seed_recommendation(db_session)
        await _seed_manager_answer(db_session, rec, request_id="req-abstain")
        db_session.add(
            AgentActionLog(
                id=_uuid.uuid4(),
                hotel_id=HOTEL,
                tool_name="submit_feedback_to_memory",
                status="ok",
                request_id="req-abstain",
                abstention_reason="parser_low_confidence",
                abstention_layer="parser",
                created_at=datetime.now(tz=timezone.utc),
            )
        )
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)

        assert record.request_id == "req-abstain"
        assert record.abstention_reason == "parser_low_confidence"
        assert record.abstention_layer == "parser"
        assert record.agent_status == "ok"

    @pytest.mark.asyncio
    async def test_action_log_of_another_hotel_is_not_joined(self, db_session):
        """request_id alone must never cross the tenant boundary."""
        rec = await _seed_recommendation(db_session, tenant_id=HOTEL)
        await _seed_manager_answer(db_session, rec, request_id="req-shared")
        db_session.add(
            AgentActionLog(
                id=_uuid.uuid4(),
                hotel_id=OTHER_HOTEL,
                tool_name="submit_feedback_to_memory",
                status="tool_error",
                request_id="req-shared",
                abstention_reason="ood_unsupported_input",
                created_at=datetime.now(tz=timezone.utc),
            )
        )
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)

        assert record.abstention_reason is None
        assert record.agent_status is None


# ---------------------------------------------------------------------------
# 7. Listing
# ---------------------------------------------------------------------------

class TestListDecisions:
    @pytest.mark.asyncio
    async def test_newest_first_and_limit(self, db_session):
        older = await _seed_recommendation(db_session)
        older.created_at = datetime.now(tz=timezone.utc) - timedelta(days=3)
        newer = await _seed_recommendation(db_session)
        newer.created_at = datetime.now(tz=timezone.utc)
        await db_session.commit()

        records = await DecisionLedgerService(db_session).list_decisions(HOTEL)
        assert [r.recommendation_id for r in records] == [newer.id, older.id]

        capped = await DecisionLedgerService(db_session).list_decisions(HOTEL, limit=1)
        assert len(capped) == 1

    @pytest.mark.asyncio
    async def test_closed_only_keeps_the_measurable_population(self, db_session):
        open_rec = await _seed_recommendation(db_session)
        closed_rec = await _seed_recommendation(db_session)
        await _seed_manager_answer(db_session, closed_rec)
        await _seed_outcome(db_session, closed_rec)
        await db_session.commit()

        service = DecisionLedgerService(db_session)
        assert len(await service.list_decisions(HOTEL)) == 2

        closed = await service.list_decisions(HOTEL, closed_only=True)
        assert [r.recommendation_id for r in closed] == [closed_rec.id]
        assert open_rec.id not in [r.recommendation_id for r in closed]


# ---------------------------------------------------------------------------
# 8. The write paths stamp the edge
# ---------------------------------------------------------------------------

class TestWritePathsStampTheLink:
    @pytest.mark.asyncio
    async def test_submit_feedback_to_memory_sets_recommendation_id(self, db_session):
        """Without this, the MCP feedback tool leaves the answer joinable only
        by a LIKE on free text — the gap HOS-317 closes."""
        from app.mcp_server import tool_submit_feedback_to_memory

        rec = await _seed_recommendation(db_session)
        await db_session.commit()

        result = await tool_submit_feedback_to_memory(
            hotel_id=HOTEL,
            recommendation_id=str(rec.id),
            outcome="accepted",
            db=db_session,
            notes="ran with 2 extra servers",
            request_id="req-mcp-1",
        )
        await db_session.commit()

        record = await DecisionLedgerService(db_session).get_decision(rec.id)
        assert result["memory_id"] is not None
        assert record.manager_response == "followed"
        assert str(record.feedback_memory_id) == result["memory_id"]

    @pytest.mark.asyncio
    async def test_persist_actual_covers_sets_recommendation_id(self, db_session):
        from app.services.receipts import ReceiptsService

        rec = await _seed_recommendation(db_session, predicted_covers=140.0)
        await db_session.commit()

        memory = await ReceiptsService(db_session).persist_actual_covers(
            rec, 150.0, request_id="req-gt-1"
        )
        await db_session.commit()

        assert memory is not None
        assert memory.recommendation_id == rec.id

        record = await DecisionLedgerService(db_session).get_decision(rec.id)
        assert record.outcome_memory_id == memory.id
        assert record.actual_covers == pytest.approx(150.0)
        assert record.abs_pct_error == pytest.approx(6.67, abs=0.01)

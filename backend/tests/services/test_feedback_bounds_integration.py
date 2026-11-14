"""HOS-250 (Epic 12 G-3) — feedback bounds integration on persist_actual_covers.

Verifies that an aberrant actual_covers is NOT propagated to the training path
(no ground_truth row, recommendation untouched) while a plausible value behaves
exactly as in HOS-200.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import (
    AgentActionLog,
    Base,
    OperationalMemory,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.receipts import ReceiptsService


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_profile(session, *, tenant_id="hotel_g3", total_seats=50):
    session.add(
        RestaurantProfile(
            id=_uuid.uuid4(),
            tenant_id=tenant_id,
            property_name="Test Hotel",
            outlet_name="Test Restaurant",
            total_seats=total_seats,  # capacity ceiling = 50 × 4.5 × 1.5 = 337.5
        )
    )
    await session.commit()


async def _seed_recommendation(session, *, tenant_id="hotel_g3", predicted_covers=140.0):
    now = datetime.now(tz=timezone.utc)
    rec = StaffingRecommendation(
        id=_uuid.uuid4(),
        tenant_id=tenant_id,
        property_id=_uuid.uuid4(),
        anomaly_id=_uuid.uuid4(),
        message_text="Add 2 servers.",
        triggering_factor="Event",
        recommended_headcount=2,
        window_start=now,
        window_end=now,
        predicted_covers=predicted_covers,
        status="dispatched",
    )
    session.add(rec)
    await session.commit()
    return rec


@pytest.mark.asyncio
async def test_aberrant_value_rejected_not_propagated(db_session):
    await _seed_profile(db_session)
    rec = await _seed_recommendation(db_session)
    svc = ReceiptsService(db_session, llm=AsyncMock())

    with (
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        result = await svc.persist_actual_covers(rec, 5000.0, request_id="req-bad")
        await db_session.commit()

    # Rejected → no memory returned, recommendation untouched, no ground_truth row.
    assert result is None
    assert rec.actual_covers is None
    mem_rows = (
        await db_session.execute(
            select(OperationalMemory).where(
                OperationalMemory.memory_type == "ground_truth"
            )
        )
    ).scalars().all()
    assert mem_rows == []

    # AC3 — a typed trip row was logged.
    trips = (
        await db_session.execute(
            select(AgentActionLog).where(
                AgentActionLog.tool_name == "feedback.ingestion"
            )
        )
    ).scalars().all()
    assert len(trips) == 1
    assert trips[0].error_code == "implausible_feedback"


@pytest.mark.asyncio
async def test_aberrant_value_rejected_when_turns_unconfigured(db_session):
    # Property with seats known but turns NULL (incompletely-onboarded / migrated
    # profile) → turns_sum == 0. The capacity ceiling must still be enforced via
    # the default-turns fallback, not bypassed (HOS-250 QA-S4 hardening).
    db_session.add(
        RestaurantProfile(
            id=_uuid.uuid4(),
            tenant_id="hotel_g3",
            property_name="Test Hotel",
            outlet_name="Test Restaurant",
            total_seats=50,  # ceiling via default turns = 50 × 3 × 1.5 = 225
            turns_breakfast=None,
            turns_lunch=None,
            turns_dinner=None,
        )
    )
    await db_session.commit()
    rec = await _seed_recommendation(db_session)
    svc = ReceiptsService(db_session, llm=AsyncMock())

    with (
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        result = await svc.persist_actual_covers(rec, 5000.0, request_id="req-null-turns")
        await db_session.commit()

    assert result is None
    assert rec.actual_covers is None


@pytest.mark.asyncio
async def test_historical_max_excludes_flagged_rows(db_session):
    """HOS-268: a previously flagged-but-ingested value must NOT raise the
    historical max, or the soft sanity bound self-erodes (each aberrant value
    admits the next). Seats are huge here so only the historical bound is live."""
    # Large capacity so the ceiling never fires — isolate the historical check.
    db_session.add(
        RestaurantProfile(
            id=_uuid.uuid4(),
            tenant_id="hotel_g3",
            property_name="Test Hotel",
            outlet_name="Test Restaurant",
            total_seats=100_000,
        )
    )
    # Legit history: max 100 (manager_feedback). Plus a flagged 10000 that must be
    # ignored when computing the historical max.
    now = datetime.now(tz=timezone.utc)
    for covers, source in ((100.0, "manager_feedback"), (10_000.0, "manager_feedback_flagged")):
        rec = StaffingRecommendation(
            id=_uuid.uuid4(), tenant_id="hotel_g3", property_id=_uuid.uuid4(),
            anomaly_id=_uuid.uuid4(), message_text="x", triggering_factor="e",
            recommended_headcount=2, window_start=now, window_end=now,
            predicted_covers=100.0, actual_covers=covers, actual_covers_source=source,
            status="accepted",
        )
        db_session.add(rec)
    await db_session.commit()

    svc = ReceiptsService(db_session, llm=AsyncMock())
    # 500 > 100 × 3 (historical multiplier) → flagged. If the flagged 10000 had
    # counted, the threshold would be 30000 and 500 would pass — the bug.
    verdict = await svc._check_feedback_bounds("hotel_g3", 500.0)
    assert verdict.plausible is False
    assert verdict.severity == "flag"


@pytest.mark.asyncio
async def test_plausible_value_persists_as_before(db_session):
    await _seed_profile(db_session)
    rec = await _seed_recommendation(db_session)
    svc = ReceiptsService(db_session, llm=AsyncMock())

    mem = await svc.persist_actual_covers(rec, 120.0, request_id="req-ok")
    await db_session.commit()

    assert mem is not None
    assert float(rec.actual_covers) == 120.0
    assert rec.actual_covers_source == "manager_feedback"
    assert mem.tags == ["ground_truth", "covers_correction"]


# ---------------------------------------------------------------------------
# Rule B (PO 14/11/2026, HOS-366, audit of silences case 10): a bounds lookup
# that fails is an "unverified" verdict, never BoundsVerdict(True, "ok").
# ---------------------------------------------------------------------------

def _failing_lookup(monkeypatch):
    async def boom(self, tenant_id):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(ReceiptsService, "_bounds_inputs", boom)


@pytest.mark.asyncio
async def test_lookup_failure_is_unverified_not_ok(db_session, monkeypatch):
    _failing_lookup(monkeypatch)
    verdict = await ReceiptsService(db_session, llm=AsyncMock())._check_feedback_bounds("hotel_g3", 120.0)
    assert verdict.plausible is False
    assert verdict.severity == "unverified"
    assert verdict.reason == "guardrail_not_verified"


@pytest.mark.asyncio
async def test_unverified_value_is_recorded_but_never_a_measured_actual(db_session, monkeypatch):
    await _seed_profile(db_session)
    rec = await _seed_recommendation(db_session)
    _failing_lookup(monkeypatch)
    svc = ReceiptsService(db_session, llm=AsyncMock())

    error = AsyncMock()
    with (
        patch("app.services.ops_dispatcher.dispatch_error", error),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        mem = await svc.persist_actual_covers(rec, 120.0, request_id="req-unv")
        await db_session.commit()

    # Recorded with an explicit marker; no measured actual for any reader.
    assert rec.actual_covers is None
    assert rec.actual_covers_source == "manager_feedback_unverified"
    assert rec.actual_covers_at is not None
    # The figure is kept for a human to verify, tagged.
    assert mem is not None and "not_verified" in mem.tags
    assert "120.0" in mem.reflection and mem.reflection.startswith("unverified")
    # The typed event (NFR2), in the caller's transaction, + an ops error (P1).
    trips = (
        await db_session.execute(
            select(AgentActionLog).where(AgentActionLog.tool_name == "feedback.ingestion")
        )
    ).scalars().all()
    assert len(trips) == 1
    assert trips[0].error_code == "guardrail_not_verified"
    assert trips[0].payload["severity"] == "unverified"
    error.assert_awaited_once()


@pytest.mark.asyncio
async def test_unverified_value_feeds_neither_training_nor_the_live_error(db_session, monkeypatch):
    from app.services import learning_store

    await _seed_profile(db_session)
    rec = await _seed_recommendation(db_session)
    _failing_lookup(monkeypatch)
    with (
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        await ReceiptsService(db_session, llm=AsyncMock()).persist_actual_covers(rec, 120.0)
        await db_session.commit()

    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    rows = await learning_store.recommendation_rows(db_session, "hotel_g3", since)
    assert rows[0]["actual_covers"] is None           # learning loop / calibration skip it
    assert rows[0]["actual_covers_source"] == "manager_feedback_unverified"
    # The bounds' own historical max ignores it too.
    monkeypatch.undo()
    _, _, hist = await ReceiptsService(db_session, llm=AsyncMock())._bounds_inputs("hotel_g3")
    assert hist is None


@pytest.mark.asyncio
async def test_lookup_failure_does_not_abort_the_callers_transaction(db_session):
    """The lookup runs in a SAVEPOINT: a failing query must not take the
    caller's pending writes down with it."""
    from sqlalchemy import text

    await _seed_profile(db_session)
    rec = await _seed_recommendation(db_session)
    svc = ReceiptsService(db_session, llm=AsyncMock())

    async def broken_lookup(self, tenant_id):
        await self.db.execute(text("SELECT * FROM table_that_does_not_exist"))

    with (
        patch.object(ReceiptsService, "_bounds_inputs", broken_lookup),
        patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()),
    ):
        mem = await svc.persist_actual_covers(rec, 120.0, request_id="req-sp")
        await db_session.commit()

    assert mem is not None
    stored = (
        await db_session.execute(
            select(StaffingRecommendation).where(StaffingRecommendation.id == rec.id)
        )
    ).scalars().one()
    assert stored.actual_covers_source == "manager_feedback_unverified"


def test_crash_inside_the_bounds_check_is_unverified_not_ok():
    from app.services import feedback_guard

    v = feedback_guard.evaluate(None)  # type: ignore[arg-type]
    assert v.plausible is False and v.severity == "unverified"
    assert v.reason == "guardrail_not_verified"

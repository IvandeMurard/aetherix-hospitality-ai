"""Weekly learning pass worker (ADR-0007 §18.5)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_pass_records_typed_trip_and_isolates_failures():
    from app.db.models import AgentActionLog, Base, LearningItem, RestaurantProfile, StaffingRecommendation
    from app.workers import learning_loop_worker as w

    engine = create_async_engine("sqlite+aiosqlite:///:memory:",
                                 connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    risk = {"task_class": "staffing.add", "uncertainty": {"status": "calibrated", "calibration_version": "v1"},
            "options": {"accept": {"delta_staff": 2, "capacity_covers": 140.0, "shortfall_probability": 0.1},
                        "refuse": {"delta_staff": 0, "capacity_covers": 100.0, "shortfall_probability": 0.7}}}
    async with maker() as db:
        for t in ("h1", "h2"):
            db.add(RestaurantProfile(tenant_id=t, property_name="P", outlet_name="O", total_seats=80))
        for i in range(40):  # said 10 %, happened every time → miscalibrated
            db.add(StaffingRecommendation(
                tenant_id="h1", property_id=uuid.uuid4(), anomaly_id=uuid.uuid4(), message_text="m",
                window_start=NOW - timedelta(days=i + 1), window_end=NOW - timedelta(days=i + 1, hours=-4),
                status="accepted", decided_by="human_whatsapp", risk_assessment=risk,
                actual_covers=150, predicted_covers=120, actual_covers_source="manager_feedback",
                created_at=NOW - timedelta(days=i + 1),
            ))
        await db.commit()

    real_run_pass = w.learning_store.run_pass

    async def _run_pass(db, tenant_id, **kw):
        if tenant_id == "h2":
            raise RuntimeError("boom")
        return await real_run_pass(db, tenant_id, **kw)

    with patch.object(w, "AsyncSessionLocal", maker), \
         patch.object(w.learning_store, "run_pass", _run_pass), \
         patch("app.services.ops_dispatcher.dispatch_anomaly", AsyncMock()) as alert:
        out = await w.run_learning_pass(now=NOW)
    assert out["h1"]["alerts"] == 1 and out["h2"] == {"error": True}
    alert.assert_awaited_once()
    async with maker() as db:
        trips = (await db.execute(select(AgentActionLog))).scalars().all()
        assert [(t.tool_name, t.error_code) for t in trips] == [(w.TRIP_TOOL, "risk_statement_miscalibrated")]
        assert all(i.status == "proposed" for i in (await db.execute(select(LearningItem))).scalars().all())
    await engine.dispose()

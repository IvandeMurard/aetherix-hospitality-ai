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

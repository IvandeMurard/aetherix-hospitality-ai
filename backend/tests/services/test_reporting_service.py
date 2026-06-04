"""HOS-200 (Story 10.10 / P3-10) — ReportingService real-rows path.

Verifies that `_get_weekly_data` reads ground-truth StaffingRecommendation rows
(manager-reported actual covers) and that `generate_weekly_metrics` prefers them
over the demo mock, falling back only when no ground-truth rows exist (AC4).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base, StaffingRecommendation
from app.services.reporting_service import ReportingService

WEEK_START = date(2026, 6, 1)  # Monday
TENANT = "pilot_hotel"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_rec(
    session: AsyncSession,
    *,
    day_offset: int,
    predicted: float,
    actual: float | None,
    tenant_id: str = TENANT,
) -> None:
    ws = datetime.combine(
        WEEK_START + timedelta(days=day_offset), time(19, 0), tzinfo=timezone.utc
    )
    rec = StaffingRecommendation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        property_id=uuid.uuid4(),
        anomaly_id=uuid.uuid4(),
        message_text="m",
        window_start=ws,
        window_end=ws,
        predicted_covers=predicted,
        actual_covers=actual,
        actual_covers_source="manager_feedback" if actual is not None else None,
        actual_covers_at=ws if actual is not None else None,
        status="dispatched",
    )
    session.add(rec)
    await session.commit()


class TestGetWeeklyData:
    @pytest.mark.asyncio
    async def test_returns_real_rows_with_actual_covers(self, db_session):
        await _seed_rec(db_session, day_offset=0, predicted=100.0, actual=90.0)
        await _seed_rec(db_session, day_offset=2, predicted=170.0, actual=175.0)
        # Row without actual_covers must be excluded.
        await _seed_rec(db_session, day_offset=3, predicted=120.0, actual=None)

        svc = ReportingService(db_service=db_session)
        data = await svc._get_weekly_data(TENANT, WEEK_START)

        assert len(data) == 2
        assert {d["actual_covers"] for d in data} == {90.0, 175.0}
        assert all("predicted_covers" in d for d in data)

    @pytest.mark.asyncio
    async def test_excludes_other_tenants_and_other_weeks(self, db_session):
        await _seed_rec(db_session, day_offset=0, predicted=100.0, actual=90.0)
        await _seed_rec(
            db_session, day_offset=0, predicted=100.0, actual=90.0, tenant_id="other"
        )
        # Next week — outside the 7-day window.
        await _seed_rec(db_session, day_offset=8, predicted=100.0, actual=90.0)

        svc = ReportingService(db_service=db_session)
        data = await svc._get_weekly_data(TENANT, WEEK_START)

        assert len(data) == 1

    @pytest.mark.asyncio
    async def test_no_db_returns_empty(self):
        svc = ReportingService()  # no session wired
        assert await svc._get_weekly_data(TENANT, WEEK_START) == []


class TestGenerateWeeklyMetrics:
    @pytest.mark.asyncio
    async def test_uses_real_rows_when_present(self, db_session):
        # Perfect prediction → MAPE 0, distinguishable from the mock (~2.4%).
        await _seed_rec(db_session, day_offset=0, predicted=100.0, actual=100.0)
        await _seed_rec(db_session, day_offset=1, predicted=150.0, actual=150.0)

        svc = ReportingService(db_service=db_session)
        svc._dispatch_ops = AsyncMock()  # isolate from Obsidian/Linear side effects
        result = await svc.generate_weekly_metrics(TENANT, WEEK_START)

        assert result["metrics"]["mape"] == 0.0
        assert result["metrics"]["total_covers"] == 250

    @pytest.mark.asyncio
    async def test_falls_back_to_mock_when_no_real_rows(self, db_session):
        # Empty DB → no ground-truth rows → demo mock (7 days, total 945 covers).
        svc = ReportingService(db_service=db_session)
        svc._dispatch_ops = AsyncMock()  # isolate from Obsidian/Linear side effects
        result = await svc.generate_weekly_metrics(TENANT, WEEK_START)

        assert result["metrics"]["total_covers"] == 945

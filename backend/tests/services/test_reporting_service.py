"""Weekly report = the deterministic recap for one week (ADR-0007 §17.1).

Pins what the old "Friday Audit" got wrong:
  * no mock data on any tenant path — an empty week says "no measured data",
    with no metric;
  * no savings / ROI / SaaS cost, no £ or $, no marketing sentence;
  * measured numbers only, from the same definition as the recap.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, StaffingRecommendation
from app.services import reporting_service
from app.services.reporting_service import NO_DATA_STATUS, ReportingService

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


async def _seed(session: AsyncSession, *, day: int, predicted: float, actual, status="dispatched",
                decided_by=None, source=None, tenant=TENANT):
    ws = datetime.combine(WEEK_START + timedelta(days=day), time(19, 0), tzinfo=timezone.utc)
    session.add(StaffingRecommendation(
        id=uuid.uuid4(), tenant_id=tenant, property_id=uuid.uuid4(), anomaly_id=uuid.uuid4(),
        message_text="m", window_start=ws, window_end=ws,
        dispatched_at=ws - timedelta(hours=6),
        predicted_covers=predicted, actual_covers=actual,
        status=status, decided_by=decided_by, decision_source=source,
        actioned_at=ws - timedelta(hours=5) if decided_by else None,
    ))
    await session.commit()


def test_no_mock_data_path_remains():
    assert not hasattr(ReportingService, "_get_mock_weekly_data")
    assert not hasattr(ReportingService, "_calculate_savings")
    src = open(reporting_service.__file__, encoding="utf-8").read()
    for forbidden in ("£", "$50", "roi_multiplier", "optimizing your labor"):
        assert forbidden not in src.split('"""', 2)[2], forbidden


@pytest.mark.asyncio
async def test_empty_week_says_no_measured_data(db_session):
    svc = ReportingService(db_service=db_session)
    svc._dispatch_ops = AsyncMock()
    result = await svc.generate_weekly_metrics(TENANT, WEEK_START)

    assert result["status"] == NO_DATA_STATUS
    assert result["financial_impact"] is None
    assert "pas encore de donnée mesurée" in result["summary_text"]
    for word in ("MAPE", "Accuracy", "€", "£", "$"):
        assert word not in result["summary_text"]
    svc._dispatch_ops.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_db_never_falls_back_to_mock():
    result = await ReportingService().generate_weekly_metrics(TENANT, WEEK_START, locale="en")
    assert result["status"] == NO_DATA_STATUS
    assert result["recap"] is None
    assert result["summary_text"] == "Weekly report: no measured data yet for this period."


@pytest.mark.asyncio
async def test_measured_week_uses_the_recap_definition(db_session):
    await _seed(db_session, day=0, predicted=100.0, actual=80.0, status="accepted",
                decided_by="human_whatsapp", source="keyword")
    await _seed(db_session, day=1, predicted=150.0, actual=150.0, status="rejected",
                decided_by="human_whatsapp", source="button")
    await _seed(db_session, day=2, predicted=120.0, actual=None)
    await _seed(db_session, day=0, predicted=10.0, actual=10.0, tenant="other")

    svc = ReportingService(db_service=db_session)
    svc._dispatch_ops = AsyncMock()
    result = await svc.generate_weekly_metrics(TENANT, WEEK_START)

    r = result["recap"]
    assert result["status"] == "ok"
    assert (r["received"], r["accepted"], r["rejected"], r["no_reply"]) == (3, 1, 1, 1)
    # |100-80|/80 = 25 %, |150-150|/150 = 0 % → mean 12.5 % over 2 days
    assert r["forecast_error_pct"] == 12.5
    assert r["forecast_error_days"] == 2
    assert r["human"]["acceptance_rate"] == 0.5
    assert result["financial_impact"] is None
    assert "12.5 % (2 jours mesurés)" in result["summary_text"]
    svc._dispatch_ops.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_ops_writes_measured_note(tmp_path, monkeypatch, db_session):
    """HOS-211 regression kept: the real _dispatch_ops must not crash and
    writes the internal note, with measured numbers only."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    await _seed(db_session, day=0, predicted=100.0, actual=100.0, status="accepted",
                decided_by="human_whatsapp", source="keyword")
    result = await ReportingService(db_service=db_session).generate_weekly_metrics(TENANT, WEEK_START)

    notes = list(tmp_path.rglob("*.md"))
    assert notes, "expected a weekly note to be written"
    body = notes[0].read_text(encoding="utf-8")
    assert "savings" not in body.lower() and "ROI" not in body
    assert result["recap"]["forecast_error_pct"] == 0.0

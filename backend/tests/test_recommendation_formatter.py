"""Tests for Story 3.3c (HOS-23): Format Staffing Recommendations for Dispatch.

Tests are structured in three tiers:
  1. Pure unit tests — stateless functions (format_message, _extract_triggering_factor)
  2. Service integration tests — in-memory SQLite for DB interaction tests
  3. Route / worker tests — lightweight FastAPI TestClient or mock-based

SQLite limitations:
  - No JSONB type: handled by using JSON in the ORM model (models.py uses JSON for
    weather_factors/event_factors; JSONB is only on WeatherForecast/LocalEvent which
    we don't touch in these tests).
  - ON CONFLICT (upsert): not supported on some SQLite versions; the formatter
    uses ON CONFLICT DO NOTHING which IS supported in SQLite >= 3.24.
  - No RETURNING clause: mitigated by the service not relying on it for
    StaffingRecommendation inserts (formatter does a separate SELECT to check
    existence before inserting).

Note on JSONB columns in DemandAnomaly: the DemandAnomaly.triggering_factors column
is declared as JSONB (Postgres-only). SQLite cannot create that table via SQLAlchemy's
create_all. We therefore test the DB-interaction layer via a dedicated SQLite
fixture that creates tables with raw DDL (plain TEXT for triggering_factors), and
verify the pure-function layer via unit tests with mock objects.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

from app.services.recommendation_formatter import (
    RecommendationFormatterService,
    _extract_triggering_factor,
    format_message,
)
from app.services.roi_calculator import ROICalculatorService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_T0 = datetime(2026, 3, 23, 18, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 3, 23, 21, 0, 0, tzinfo=timezone.utc)

_SURGE_FACTOR = "Tech conference nearby"
_LULL_FACTOR = "rainy weather"

# ---------------------------------------------------------------------------
# SQLite DDL for the tables used by the formatter (avoiding JSONB / Postgres)
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS demand_anomalies (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    expected_demand REAL,
    baseline_demand REAL,
    deviation_pct REAL,
    direction TEXT NOT NULL,
    triggering_factors TEXT,
    status TEXT NOT NULL DEFAULT 'detected',
    detected_at TEXT,
    roi_revenue_opp REAL,
    roi_labor_cost REAL,
    roi_net REAL,
    recommendation_text TEXT
);

CREATE TABLE IF NOT EXISTS staffing_recommendations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    anomaly_id TEXT NOT NULL UNIQUE,
    message_text TEXT NOT NULL,
    triggering_factor TEXT,
    recommended_headcount INTEGER,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    roi_net REAL,
    roi_labor_cost REAL,
    status TEXT NOT NULL DEFAULT 'ready_to_push',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def db_engine():
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s


# ---------------------------------------------------------------------------
# Helpers to seed the in-memory DB
# ---------------------------------------------------------------------------


def _anomaly_id() -> str:
    return str(uuid.uuid4())


def _tenant_id() -> str:
    return str(uuid.uuid4())


async def _insert_anomaly(
    session: AsyncSession,
    *,
    anomaly_id: str,
    tenant_id: str,
    property_id: str = "prop-001",
    direction: str = "surge",
    status: str = "roi_positive",
    deviation_pct: float = 30.0,
    expected_demand: float = 130.0,
    baseline_demand: float = 100.0,
    roi_revenue_opp: float = 800.0,
    roi_labor_cost: float = 180.0,
    roi_net: float = 620.0,
    triggering_factors=None,
    window_start: datetime = _T0,
    window_end: datetime = _T1,
) -> None:
    factors = triggering_factors or [{"label": _SURGE_FACTOR, "weight": 0.9}]
    await session.execute(
        text(
            """
            INSERT INTO demand_anomalies
              (id, tenant_id, property_id, direction, status, deviation_pct,
               expected_demand, baseline_demand,
               roi_revenue_opp, roi_labor_cost, roi_net,
               triggering_factors, window_start, window_end, detected_at)
            VALUES
              (:id, :tenant_id, :property_id, :direction, :status, :deviation_pct,
               :expected_demand, :baseline_demand,
               :roi_revenue_opp, :roi_labor_cost, :roi_net,
               :triggering_factors, :window_start, :window_end, :detected_at)
            """
        ),
        {
            "id": anomaly_id,
            "tenant_id": tenant_id,
            "property_id": property_id,
            "direction": direction,
            "status": status,
            "deviation_pct": deviation_pct,
            "expected_demand": expected_demand,
            "baseline_demand": baseline_demand,
            "roi_revenue_opp": roi_revenue_opp,
            "roi_labor_cost": roi_labor_cost,
            "roi_net": roi_net,
            "triggering_factors": json.dumps(factors),
            "window_start": window_start.isoformat() if window_start else None,
            "window_end": window_end.isoformat() if window_end else None,
            "detected_at": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    await session.flush()


# ---------------------------------------------------------------------------
# format_message() — pure function tests (AC #1, #2, #3)
# ---------------------------------------------------------------------------


def test_format_message_surge_includes_headcount():
    """AC #1: directive includes headcount."""
    msg = format_message("surge", 3, 800, 180, _T0, _T1, _SURGE_FACTOR)
    assert "3" in msg


def test_format_message_surge_includes_revenue():
    """AC #1: directive includes estimated revenue."""
    msg = format_message("surge", 3, 800, 180, _T0, _T1, _SURGE_FACTOR)
    assert "800" in msg


def test_format_message_surge_includes_labor_cost():
    """AC #3: directive includes estimated labor cost."""
    msg = format_message("surge", 3, 800, 180, _T0, _T1, _SURGE_FACTOR)
    assert "180" in msg


def test_format_message_surge_includes_triggering_factor():
    """AC #2: directive includes triggering factor."""
    msg = format_message("surge", 3, 800, 180, _T0, _T1, _SURGE_FACTOR)
    assert _SURGE_FACTOR in msg


def test_format_message_surge_includes_time_window():
    """Directive contains the formatted time window."""
    msg = format_message("surge", 3, 800, 180, _T0, _T1, _SURGE_FACTOR)
    assert "18:00" in msg
    assert "21:00" in msg


def test_format_message_surge_pound_sign():
    """Directive uses £ currency symbol."""
    msg = format_message("surge", 2, 500, 100, _T0, _T1, "event")
    assert "£" in msg


def test_format_message_lull_different_text():
    """Lull messages use reduction language."""
    msg = format_message("lull", -2, 0, 90, _T0, _T1, _LULL_FACTOR)
    assert "reducing" in msg.lower() or "reduce" in msg.lower()


def test_format_message_lull_no_revenue():
    """Lull messages do not mention capturing additional covers."""
    msg = format_message("lull", -2, 0, 90, _T0, _T1, _LULL_FACTOR)
    assert "additional covers" not in msg


def test_format_message_lull_includes_triggering_factor():
    """Lull messages still include the triggering factor."""
    msg = format_message("lull", -2, 0, 90, _T0, _T1, _LULL_FACTOR)
    assert _LULL_FACTOR in msg


def test_format_message_lull_uses_abs_headcount():
    """Lull headcount is expressed as a positive number (no minus sign)."""
    msg = format_message("lull", -3, 0, 90, _T0, _T1, "quiet period")
    assert "3" in msg
    assert "-3" not in msg


# ---------------------------------------------------------------------------
# _extract_triggering_factor() — pure helper tests
# ---------------------------------------------------------------------------


def test_extract_factor_picks_highest_weight():
    mock_anomaly = MagicMock()
    # triggering_factors is now one flat list in the real anomaly model
    factors = [
        {"label": "Rain", "weight": 0.3},
        {"label": "Concert", "weight": 0.7},
        {"label": "Conference", "weight": 0.95},
    ]
    assert _extract_triggering_factor(factors) == "Conference"


def test_extract_factor_fallback_when_none():
    assert _extract_triggering_factor(None) == "demand anomaly detected"


def test_extract_factor_fallback_empty_list():
    assert _extract_triggering_factor([]) == "demand anomaly detected"


def test_extract_factor_single_dict():
    """Single factor stored as a plain dict (edge case)."""
    factor = {"label": "Heat wave", "weight": 0.6}
    assert _extract_triggering_factor(factor) == "Heat wave"


def test_extract_factor_no_weight_key():
    """Factors without a weight key default to 0 but still return their label."""
    factors = [{"label": "Local event"}]
    assert _extract_triggering_factor(factors) == "Local event"


# ---------------------------------------------------------------------------
# ROICalculatorService.recommended_headcount — unit tests
# ---------------------------------------------------------------------------


def test_roi_headcount_lull():
    svc = ROICalculatorService()
    assert svc.recommended_headcount(-10.0) == 0


def test_roi_headcount_low_surge():
    svc = ROICalculatorService()
    assert svc.recommended_headcount(25.0) == 1


def test_roi_headcount_mid_surge():
    svc = ROICalculatorService()
    assert svc.recommended_headcount(40.0) == 2


def test_roi_headcount_high_surge():
    svc = ROICalculatorService()
    assert svc.recommended_headcount(60.0) == 3


def test_roi_headcount_very_high_surge():
    svc = ROICalculatorService()
    assert svc.recommended_headcount(90.0) == 4


# ---------------------------------------------------------------------------
# RecommendationFormatterService — DB integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_for_property_creates_recommendation(session: AsyncSession):
    """AC #4: recommendation saved linked to anomaly."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid)

    svc = RecommendationFormatterService()
    count = await svc.run_for_property(session, property_id="prop-001")
    assert count == 1

    row = (await session.execute(
        text("SELECT anomaly_id, status FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).fetchone()
    assert row is not None
    assert row[1] == "ready_to_push"


@pytest.mark.asyncio
async def test_run_for_property_updates_anomaly_status_to_ready_to_push(session: AsyncSession):
    """AC #5: anomaly status transitions roi_positive → ready_to_push."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid)

    svc = RecommendationFormatterService()
    await svc.run_for_property(session, property_id="prop-001")

    row = (await session.execute(
        text("SELECT status FROM demand_anomalies WHERE id = :aid"),
        {"aid": aid},
    )).fetchone()
    assert row[0] == "ready_to_push"


@pytest.mark.asyncio
async def test_idempotency_no_duplicate_on_rerun(session: AsyncSession):
    """AC #8: re-running does not duplicate recommendations."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid)

    svc = RecommendationFormatterService()

    # First run creates recommendation (status changes to ready_to_push)
    count_first = await svc.run_for_property(session, property_id="prop-001")
    assert count_first == 1

    # Second run: anomaly is no longer roi_positive → no new recs created
    count_second = await svc.run_for_property(session, property_id="prop-001")
    assert count_second == 0

    total = (await session.execute(
        text("SELECT COUNT(*) FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).scalar()
    assert total == 1


@pytest.mark.asyncio
async def test_skips_non_roi_positive_anomalies(session: AsyncSession):
    """Only anomalies with status='roi_positive' are formatted."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid, status="detected")

    svc = RecommendationFormatterService()
    count = await svc.run_for_property(session, property_id="prop-001")
    assert count == 0


@pytest.mark.asyncio
async def test_recommendation_includes_triggering_factor(session: AsyncSession):
    """AC #2: recommendation message includes the triggering factor."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(
        session,
        anomaly_id=aid,
        tenant_id=tid,
        triggering_factors=[{"label": "Tech conference nearby", "weight": 0.9}],
    )

    svc = RecommendationFormatterService()
    await svc.run_for_property(session, property_id="prop-001")

    row = (await session.execute(
        text("SELECT message_text, triggering_factor FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).fetchone()
    assert "Tech conference nearby" in row[0]
    assert row[1] == "Tech conference nearby"


@pytest.mark.asyncio
async def test_recommendation_includes_labor_cost(session: AsyncSession):
    """AC #3: recommendation message includes estimated labor cost."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid, roi_labor_cost=180.0)

    svc = RecommendationFormatterService()
    await svc.run_for_property(session, property_id="prop-001")

    row = (await session.execute(
        text("SELECT message_text FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).fetchone()
    assert "180" in row[0]


@pytest.mark.asyncio
async def test_skips_anomaly_without_window_times(session: AsyncSession):
    """Anomalies with NULL window_start/end are skipped gracefully."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(
        session,
        anomaly_id=aid,
        tenant_id=tid,
        window_start=None,  # type: ignore[arg-type]
        window_end=None,  # type: ignore[arg-type]
    )
    # Override the inserted values to NULL
    await session.execute(
        text("UPDATE demand_anomalies SET window_start = NULL, window_end = NULL WHERE id = :aid"),
        {"aid": aid},
    )
    await session.flush()

    svc = RecommendationFormatterService()
    count = await svc.run_for_property(session, property_id="prop-001")
    assert count == 0


@pytest.mark.asyncio
async def test_run_full_scan_processes_multiple_properties(session: AsyncSession):
    """run_full_scan processes anomalies across different properties."""
    tid = _tenant_id()
    aid1 = _anomaly_id()
    aid2 = _anomaly_id()
    await _insert_anomaly(session, anomaly_id=aid1, tenant_id=tid, property_id="prop-001")
    await _insert_anomaly(session, anomaly_id=aid2, tenant_id=tid, property_id="prop-002")

    svc = RecommendationFormatterService()
    count = await svc.run_full_scan(session)
    assert count == 2


@pytest.mark.asyncio
async def test_recommendation_linked_to_originating_anomaly(session: AsyncSession):
    """AC #4: recommendation is linked to the originating anomaly."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid)

    svc = RecommendationFormatterService()
    await svc.run_for_property(session, property_id="prop-001")

    row = (await session.execute(
        text("SELECT anomaly_id FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).fetchone()
    assert row[0] == aid


@pytest.mark.asyncio
async def test_lull_recommendation_different_message(session: AsyncSession):
    """Lull anomalies produce a reduction directive, not a staffing-up message."""
    aid = _anomaly_id()
    tid = _tenant_id()
    await _insert_anomaly(
        session,
        anomaly_id=aid,
        tenant_id=tid,
        direction="lull",
        deviation_pct=-25.0,
        roi_revenue_opp=0.0,
        roi_net=0.0,
        triggering_factors=[{"label": "quiet mid-week", "weight": 0.4}],
    )

    svc = RecommendationFormatterService()
    await svc.run_for_property(session, property_id="prop-001")

    row = (await session.execute(
        text("SELECT message_text FROM staffing_recommendations WHERE anomaly_id = :aid"),
        {"aid": aid},
    )).fetchone()
    msg = row[0].lower()
    assert "reducing" in msg or "reduce" in msg


@pytest.mark.asyncio
async def test_run_full_scan_idempotent_second_call(session: AsyncSession):
    """run_full_scan is idempotent — second call creates no duplicates."""
    tid = _tenant_id()
    aid = _anomaly_id()
    await _insert_anomaly(session, anomaly_id=aid, tenant_id=tid)

    svc = RecommendationFormatterService()
    count1 = await svc.run_full_scan(session)
    count2 = await svc.run_full_scan(session)

    assert count1 == 1
    assert count2 == 0

    total = (await session.execute(
        text("SELECT COUNT(*) FROM staffing_recommendations")
    )).scalar()
    assert total == 1


# ---------------------------------------------------------------------------
# Worker chain test (AC #6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_chains_formatter_after_roi():
    """AC #6: worker module imports RecommendationFormatterService and chains it."""
    from app.workers import anomaly_scan as worker_module

    # Verify the formatter service is wired into the worker
    assert hasattr(worker_module, "_formatter_service"), (
        "Worker must expose _formatter_service for auto-chain (AC #6)"
    )
    assert isinstance(
        worker_module._formatter_service, RecommendationFormatterService
    )


# ---------------------------------------------------------------------------
# Route tests (AC #7)
# ---------------------------------------------------------------------------


def _build_test_app(mock_session: AsyncSession) -> FastAPI:
    """Build a minimal FastAPI app with the anomalies router and a mock DB."""
    from fastapi import FastAPI, HTTPException
    from app.core.error_handlers import problem_details_handler
    from app.api.routes.anomalies import router as anomalies_router
    from app.db.session import get_db
    from app.core.security import get_current_user

    app = FastAPI()
    app.add_exception_handler(HTTPException, problem_details_handler)

    async def override_get_db():
        yield mock_session

    async def override_get_current_user():
        return {"id": str(uuid.uuid4()), "email": "test@example.com"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.include_router(anomalies_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_format_route_returns_202(session: AsyncSession):
    """AC #7: POST /api/v1/anomalies/format returns 202 Accepted."""
    app = _build_test_app(session)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/anomalies/format")
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_format_route_returns_202_with_property_id(session: AsyncSession):
    """Route accepts optional propertyId in camelCase body."""
    app = _build_test_app(session)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/anomalies/format",
        json={"propertyId": str(uuid.uuid4())},
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_format_route_response_body_accepted(session: AsyncSession):
    """Response body contains accepted=True."""
    app = _build_test_app(session)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/anomalies/format")
    data = response.json()
    assert data.get("accepted") is True


@pytest.mark.asyncio
async def test_format_route_idempotent_double_call(session: AsyncSession):
    """AC #8: calling the route twice does not raise an error."""
    app = _build_test_app(session)
    client = TestClient(app, raise_server_exceptions=False)

    r1 = client.post("/api/v1/anomalies/format")
    r2 = client.post("/api/v1/anomalies/format")

    assert r1.status_code == 202
    assert r2.status_code == 202

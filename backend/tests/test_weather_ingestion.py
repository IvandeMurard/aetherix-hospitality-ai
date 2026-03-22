"""Tests for WeatherIngestionService — HOS-83 Story 3.1.

Coverage:
  Unit:
    - _normalize(): maps Open-Meteo response correctly
    - _normalize(): skips unparseable timestamps
    - _normalize(): handles missing/short arrays gracefully
  Integration (mocked HTTP + in-memory SQLite):
    - sync_for_tenant(): raises ValueError when GPS missing
    - sync_for_tenant(): calls Open-Meteo and persists records
    - Idempotency: re-running sync does NOT create duplicate rows
    - Cross-tenant isolation: tenant A cannot see tenant B rows
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, RestaurantProfile, WeatherForecast
from app.schemas.weather import WeatherForecastRecord
from app.services.weather_ingestion import WeatherIngestionService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_session():
    """In-memory async SQLite session for integration tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as session:
        yield session

    await engine.dispose()


def _make_profile(tenant_id: str, lat: float | None = 48.8566, lng: float | None = 2.3522) -> RestaurantProfile:
    return RestaurantProfile(
        id=tenant_id,
        tenant_id=tenant_id,
        property_name="Test Hotel",
        outlet_name="Test Restaurant",
        total_seats=100,
        latitude=lat,
        longitude=lng,
    )


def _open_meteo_payload(n_hours: int = 4) -> Dict[str, Any]:
    """Build a minimal Open-Meteo-like payload with n_hours hourly slots."""
    times = [f"2026-03-22T{h:02d}:00" for h in range(n_hours)]
    return {
        "latitude": 48.8566,
        "longitude": 2.3522,
        "timezone": "Europe/Paris",
        "hourly": {
            "time": times,
            "temperature_2m": [10.0 + h for h in range(n_hours)],
            "precipitation_probability": [20 * h % 100 for h in range(n_hours)],
            "weathercode": [1, 2, 3, 61][: n_hours] + [1] * max(0, n_hours - 4),
            "windspeed_10m": [5.0 + h for h in range(n_hours)],
        },
    }


# ---------------------------------------------------------------------------
# Unit tests — _normalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_maps_all_fields(self):
        payload = _open_meteo_payload(n_hours=2)
        records = WeatherIngestionService._normalize(payload)

        assert len(records) == 2
        r0 = records[0]
        assert r0.temperature_c == 10.0
        assert r0.precipitation_prob == 0
        assert r0.condition_code == 1
        assert r0.wind_speed_kmh == 5.0
        assert r0.forecast_timestamp.tzinfo is not None  # UTC-aware

    def test_skips_unparseable_timestamp(self, caplog):
        payload = {
            "hourly": {
                "time": ["not-a-date", "2026-03-22T01:00"],
                "temperature_2m": [10.0, 11.0],
                "precipitation_probability": [10, 20],
                "weathercode": [1, 2],
                "windspeed_10m": [5.0, 6.0],
            }
        }
        import logging
        with caplog.at_level(logging.WARNING):
            records = WeatherIngestionService._normalize(payload)
        assert len(records) == 1
        assert records[0].temperature_c == 11.0

    def test_handles_short_arrays(self):
        """Arrays shorter than `time` should not raise IndexError."""
        payload = {
            "hourly": {
                "time": ["2026-03-22T00:00", "2026-03-22T01:00"],
                "temperature_2m": [10.0],   # shorter
                "precipitation_probability": [],
                "weathercode": [],
                "windspeed_10m": [],
            }
        }
        records = WeatherIngestionService._normalize(payload)
        assert len(records) == 2
        assert records[0].temperature_c == 10.0
        assert records[1].temperature_c is None

    def test_empty_payload(self):
        records = WeatherIngestionService._normalize({})
        assert records == []


# ---------------------------------------------------------------------------
# Integration tests — sync_for_tenant (mocked HTTP)
# ---------------------------------------------------------------------------

class TestSyncForTenant:
    @pytest.mark.asyncio
    async def test_raises_when_no_gps(self, async_session):
        profile = _make_profile("tenant_no_gps", lat=None, lng=None)
        async_session.add(profile)
        await async_session.commit()

        service = WeatherIngestionService()
        with pytest.raises(ValueError, match="GPS coordinates"):
            await service.sync_for_tenant(async_session, profile)

    @pytest.mark.asyncio
    async def test_persists_records(self, async_session):
        profile = _make_profile("tenant_paris")
        async_session.add(profile)
        await async_session.commit()

        payload = _open_meteo_payload(n_hours=3)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)

        service = WeatherIngestionService(http_client=mock_client)
        inserted = await service.sync_for_tenant(async_session, profile)

        assert inserted == 3
        mock_client.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_idempotency_no_duplicates(self, async_session):
        """Running sync twice for same property+window must not create duplicates."""
        profile = _make_profile("tenant_idempotent")
        async_session.add(profile)
        await async_session.commit()

        payload = _open_meteo_payload(n_hours=2)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)

        service = WeatherIngestionService(http_client=mock_client)

        # First sync
        first_run = await service.sync_for_tenant(async_session, profile)
        # Second sync — same data
        second_run = await service.sync_for_tenant(async_session, profile)

        assert first_run == 2
        # Second run should insert 0 new rows (all conflict)
        assert second_run == 0

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation(self, async_session):
        """Rows inserted for tenant A must not be visible when querying tenant B."""
        profile_a = _make_profile("tenant_a")
        profile_b = _make_profile("tenant_b", lat=51.5074, lng=-0.1278)
        async_session.add_all([profile_a, profile_b])
        await async_session.commit()

        payload_a = _open_meteo_payload(n_hours=2)
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = payload_a

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_resp)
        service = WeatherIngestionService(http_client=mock_client)

        await service.sync_for_tenant(async_session, profile_a)

        from sqlalchemy.future import select
        rows_b = (
            await async_session.execute(
                select(WeatherForecast).where(WeatherForecast.tenant_id == "tenant_b")
            )
        ).scalars().all()

        assert rows_b == [], "Tenant B must not see Tenant A's weather rows"

    @pytest.mark.asyncio
    async def test_http_failure_does_not_raise_after_retries(self, async_session):
        """After all retries exhausted, the exception propagates to the caller
        (the background task wrapper catches it — but the service itself reraises)."""
        profile = _make_profile("tenant_fail")
        async_session.add(profile)
        await async_session.commit()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

        service = WeatherIngestionService(http_client=mock_client)
        with pytest.raises(httpx.ConnectError):
            await service.sync_for_tenant(async_session, profile)

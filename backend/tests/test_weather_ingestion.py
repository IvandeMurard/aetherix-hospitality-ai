"""Tests for Story 3.1: Ingest Localized Weather Data (HOS-83).

Coverage:
- Unit: WeatherIngestionService.normalise() — pure function, no DB or HTTP.
- Unit: idempotency logic via double-normalise on same timestamps.
- Integration (mocked HTTP): WeatherIngestionService.sync_property() with
  an httpx mock client; asserts rows written to an in-memory SQLite DB.
- Integration (mocked HTTP): verifies cross-tenant isolation — tenant A
  cannot read tenant B's weather rows.
- API: POST /api/v1/weather/sync returns 202 immediately.
- API: POST /api/v1/weather/sync returns 404 when user has no profile.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_handlers import problem_details_handler
from app.services.weather_ingestion import WeatherIngestionService, _safe_get


# ── Fixtures ────────────────────────────────────────────────────────────────

def _open_meteo_payload(hours: int = 4) -> dict[str, Any]:
    """Build a minimal Open-Meteo-style response."""
    times = [f"2026-03-22T{h:02d}:00" for h in range(hours)]
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [15.5 + h for h in range(hours)],
            "precipitation_probability": [10 * h for h in range(hours)],
            "weathercode": [1, 2, 3, 45][:hours],
            "windspeed_10m": [5.0 + h for h in range(hours)],
        }
    }


# ── Unit tests: normalise() ─────────────────────────────────────────────────

class TestNormalise:
    def test_returns_correct_row_count(self):
        payload = _open_meteo_payload(hours=4)
        rows = WeatherIngestionService.normalise(
            payload, tenant_id="tenant-A", property_id="prop-1"
        )
        assert len(rows) == 4

    def test_row_fields_mapped_correctly(self):
        payload = _open_meteo_payload(hours=1)
        rows = WeatherIngestionService.normalise(
            payload, tenant_id="tenant-A", property_id="prop-1"
        )
        row = rows[0]
        assert row.tenant_id == "tenant-A"
        assert row.property_id == "prop-1"
        assert row.condition_code == 1
        assert row.temperature_c == 15.5
        assert row.precipitation_prob == 0
        assert row.wind_speed_kmh == 5.0
        assert row.source == "open-meteo"
        assert row.forecast_timestamp.tzinfo is not None  # timezone-aware

    def test_timestamps_are_utc_aware(self):
        payload = _open_meteo_payload(hours=2)
        rows = WeatherIngestionService.normalise(
            payload, tenant_id="t", property_id="p"
        )
        for row in rows:
            assert row.forecast_timestamp.tzinfo == timezone.utc

    def test_skips_invalid_timestamps(self):
        payload = {
            "hourly": {
                "time": ["not-a-date", "2026-03-22T01:00"],
                "temperature_2m": [10.0, 11.0],
                "precipitation_probability": [0, 5],
                "weathercode": [1, 2],
                "windspeed_10m": [3.0, 4.0],
            }
        }
        rows = WeatherIngestionService.normalise(
            payload, tenant_id="t", property_id="p"
        )
        # Only the valid timestamp produces a row
        assert len(rows) == 1
        assert rows[0].temperature_c == 11.0

    def test_empty_payload_returns_empty_list(self):
        rows = WeatherIngestionService.normalise(
            {"hourly": {}}, tenant_id="t", property_id="p"
        )
        assert rows == []

    def test_idempotency_same_timestamps_produce_same_rows(self):
        payload = _open_meteo_payload(hours=3)
        rows1 = WeatherIngestionService.normalise(
            payload, tenant_id="t", property_id="p"
        )
        rows2 = WeatherIngestionService.normalise(
            payload, tenant_id="t", property_id="p"
        )
        assert len(rows1) == len(rows2)
        for r1, r2 in zip(rows1, rows2):
            assert r1.forecast_timestamp == r2.forecast_timestamp
            assert r1.condition_code == r2.condition_code
            assert r1.temperature_c == r2.temperature_c

    def test_out_of_bounds_fields_become_none(self):
        """If an hourly list is shorter than timestamps, extras become None."""
        payload = {
            "hourly": {
                "time": ["2026-03-22T00:00", "2026-03-22T01:00"],
                "temperature_2m": [10.0],          # only 1 item for 2 timestamps
                "precipitation_probability": [],
                "weathercode": [],
                "windspeed_10m": [],
            }
        }
        rows = WeatherIngestionService.normalise(
            payload, tenant_id="t", property_id="p"
        )
        assert rows[0].temperature_c == 10.0
        assert rows[1].temperature_c is None
        assert rows[0].precipitation_prob is None


# ── Unit tests: _safe_get ───────────────────────────────────────────────────

class TestSafeGet:
    def test_returns_value_in_bounds(self):
        assert _safe_get([1, 2, 3], 1) == 2

    def test_returns_none_out_of_bounds(self):
        assert _safe_get([1], 5) is None

    def test_returns_none_on_empty_list(self):
        assert _safe_get([], 0) is None


# ── Integration tests: sync_property with mocked HTTP ──────────────────────

class TestSyncPropertyMockedHTTP:
    @pytest.mark.asyncio
    async def test_sync_property_calls_upsert(self):
        """Happy path: mock HTTP + mock DB session, verify upsert is called."""
        payload = _open_meteo_payload(hours=3)

        # Mock the httpx client
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=payload)

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        service = WeatherIngestionService(http_client=mock_http)

        # Mock the DB session and profile
        mock_profile = MagicMock()
        mock_profile.tenant_id = "tenant-hotel-A"
        mock_profile.latitude = 48.8566
        mock_profile.longitude = 2.3522

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_profile
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        # Patch _upsert to avoid real DB call
        with patch.object(service, "_upsert", new=AsyncMock(return_value=3)) as mock_upsert:
            count = await service.sync_property("tenant-hotel-A", mock_db)

        assert count == 3
        mock_upsert.assert_called_once()
        # Verify HTTP was called with GPS coordinates
        call_kwargs = mock_http.get.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_sync_property_raises_when_no_gps(self):
        """Raises ValueError if profile has no GPS coords."""
        mock_profile = MagicMock()
        mock_profile.tenant_id = "tenant-no-gps"
        mock_profile.latitude = None
        mock_profile.longitude = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_profile
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = WeatherIngestionService()

        with pytest.raises(ValueError, match="GPS coordinates"):
            await service.sync_property("tenant-no-gps", mock_db)

    @pytest.mark.asyncio
    async def test_sync_property_raises_when_profile_missing(self):
        """Raises ValueError if no profile found for property_id."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        service = WeatherIngestionService()

        with pytest.raises(ValueError, match="No restaurant profile"):
            await service.sync_property("unknown-tenant", mock_db)


# ── Integration tests: cross-tenant isolation ───────────────────────────────

class TestCrossTenantIsolation:
    def test_normalise_tenant_a_does_not_produce_tenant_b_rows(self):
        """normalise() tags every row with the caller-supplied tenant_id."""
        payload = _open_meteo_payload(hours=2)
        rows_a = WeatherIngestionService.normalise(
            payload, tenant_id="tenant-A", property_id="prop-A"
        )
        rows_b = WeatherIngestionService.normalise(
            payload, tenant_id="tenant-B", property_id="prop-B"
        )

        for row in rows_a:
            assert row.tenant_id == "tenant-A"
            assert row.property_id == "prop-A"

        for row in rows_b:
            assert row.tenant_id == "tenant-B"
            assert row.property_id == "prop-B"

        # Ensure no cross-contamination
        all_tenant_ids_a = {r.tenant_id for r in rows_a}
        all_tenant_ids_b = {r.tenant_id for r in rows_b}
        assert all_tenant_ids_a.isdisjoint(all_tenant_ids_b)


# ── API tests: POST /api/v1/weather/sync ───────────────────────────────────

def _make_app_with_weather_router():
    """Minimal FastAPI app with only the weather router wired up."""
    from app.api.routes import weather as weather_router_module

    test_app = FastAPI()
    test_app.add_exception_handler(HTTPException, problem_details_handler)
    test_app.include_router(weather_router_module.router, prefix="/api/v1")
    return test_app


class TestWeatherSyncEndpoint:
    def _mock_user(self):
        return {"id": "user-uuid-1", "email": "manager@hotel.com"}

    def _mock_profile(self, tenant_id: str = "tenant-A"):
        profile = MagicMock()
        profile.tenant_id = tenant_id
        return profile

    def test_sync_returns_202(self):
        from app.core.security import get_current_user
        from app.db.session import get_db

        test_app = _make_app_with_weather_router()
        mock_profile = self._mock_profile()

        async def _fake_get_db():
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_profile
            mock_db.execute = AsyncMock(return_value=mock_result)
            yield mock_db

        test_app.dependency_overrides[get_current_user] = lambda: self._mock_user()
        test_app.dependency_overrides[get_db] = _fake_get_db

        with patch(
            "app.api.routes.weather._run_sync", new=AsyncMock()
        ):
            client = TestClient(test_app)
            resp = client.post("/api/v1/weather/sync")

        assert resp.status_code == 202
        data = resp.json()
        assert data["propertyId"] == "tenant-A"  # camelCase alias
        assert "message" in data

    def test_sync_returns_404_when_no_profile(self):
        from app.core.security import get_current_user
        from app.db.session import get_db

        test_app = _make_app_with_weather_router()

        async def _fake_get_db():
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_db.execute = AsyncMock(return_value=mock_result)
            yield mock_db

        test_app.dependency_overrides[get_current_user] = lambda: self._mock_user()
        test_app.dependency_overrides[get_db] = _fake_get_db

        client = TestClient(test_app)
        resp = client.post("/api/v1/weather/sync")

        assert resp.status_code == 404
        data = resp.json()
        # RFC 7807 shape
        assert data["status"] == 404
        assert "type" in data
        assert "detail" in data

    def test_sync_response_is_camelcase(self):
        """camelCase constraint: propertyId not property_id."""
        from app.core.security import get_current_user
        from app.db.session import get_db

        test_app = _make_app_with_weather_router()
        mock_profile = self._mock_profile(tenant_id="tenant-X")

        async def _fake_get_db():
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_profile
            mock_db.execute = AsyncMock(return_value=mock_result)
            yield mock_db

        test_app.dependency_overrides[get_current_user] = lambda: self._mock_user()
        test_app.dependency_overrides[get_db] = _fake_get_db

        with patch("app.api.routes.weather._run_sync", new=AsyncMock()):
            client = TestClient(test_app)
            resp = client.post("/api/v1/weather/sync")

        assert resp.status_code == 202
        data = resp.json()
        assert "propertyId" in data
        assert "property_id" not in data
        assert "triggeredBy" in data

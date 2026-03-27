"""Tests for WeatherIngestionService -- HOS-83 Story 3.1.

Coverage:
  Unit:
    - normalise(): maps Open-Meteo response correctly
    - normalise(): skips unparseable timestamps
    - normalise(): handles arrays shorter than timestamps
  Integration (mocked HTTP):
    - sync_property(): raises ValueError when GPS missing
    - sync_property(): raises ValueError when no profile found
    - sync_property(): happy path with mocked HTTP + DB
  Cross-tenant isolation:
    - normalise() tags every row with the supplied tenant_id
  API:
    - POST /api/v1/weather/sync returns 202 immediately
    - POST /api/v1/weather/sync returns 404 when user has no profile
    - Response uses camelCase aliases (propertyId not property_id)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_handlers import problem_details_handler
from app.services.weather_ingestion import WeatherIngestionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_meteo_payload(hours: int = 4) -> dict[str, Any]:
    """Build a minimal Open-Meteo-style hourly response."""
    times = [f"2026-03-22T{h:02d}:00" for h in range(hours)]
    codes = [1, 2, 3, 45, 61]
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [15.5 + h for h in range(hours)],
            "precipitation_probability": [10 * h for h in range(hours)],
            "weathercode": codes[:hours],
            "windspeed_10m": [5.0 + h for h in range(hours)],
        }
    }


# ---------------------------------------------------------------------------
# Unit tests -- normalise()
# ---------------------------------------------------------------------------

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
        assert row.forecast_timestamp.tzinfo is not None

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
        assert len(rows) == 1
        assert rows[0].temperature_c == 11.0

    def test_handles_short_arrays(self):
        """Arrays shorter than `time` list should yield None for missing slots."""
        payload = {
            "hourly": {
                "time": ["2026-03-22T00:00", "2026-03-22T01:00"],
                "temperature_2m": [10.0],   # only 1 item for 2 timestamps
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

    def test_empty_payload_returns_empty_list(self):
        rows = WeatherIngestionService.normalise(
            {"hourly": {}}, tenant_id="t", property_id="p"
        )
        assert rows == []

    def test_idempotency_same_input_same_output(self):
        payload = _open_meteo_payload(hours=3)
        rows1 = WeatherIngestionService.normalise(payload, tenant_id="t", property_id="p")
        rows2 = WeatherIngestionService.normalise(payload, tenant_id="t", property_id="p")
        assert len(rows1) == len(rows2)
        for r1, r2 in zip(rows1, rows2):
            assert r1.forecast_timestamp == r2.forecast_timestamp
            assert r1.condition_code == r2.condition_code


# ---------------------------------------------------------------------------
# Integration tests -- sync_property (mocked HTTP + DB)
# ---------------------------------------------------------------------------

class TestSyncPropertyMockedHTTP:
    @pytest.mark.asyncio
    async def test_happy_path_calls_upsert(self):
        """Mock HTTP + DB; verify _upsert is called with the right row count."""
        payload = _open_meteo_payload(hours=3)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=payload)

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        service = WeatherIngestionService(http_client=mock_http)

        mock_profile = MagicMock()
        mock_profile.tenant_id = "tenant-hotel-A"
        mock_profile.latitude = 48.8566
        mock_profile.longitude = 2.3522

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_profile
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "_upsert", new=AsyncMock(return_value=3)) as mock_upsert:
            count = await service.sync_property("tenant-hotel-A", mock_db)

        assert count == 3
        mock_upsert.assert_called_once()
        mock_http.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_when_no_gps(self):
        mock_profile = MagicMock()
        mock_profile.tenant_id = "tenant-no-gps"
        mock_profile.latitude = None
        mock_profile.longitude = None

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_profile
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="GPS coordinates"):
            await WeatherIngestionService().sync_property("tenant-no-gps", mock_db)

    @pytest.mark.asyncio
    async def test_raises_when_profile_missing(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ValueError, match="No restaurant profile"):
            await WeatherIngestionService().sync_property("unknown-tenant", mock_db)


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    def test_normalise_tags_rows_with_caller_tenant(self):
        payload = _open_meteo_payload(hours=2)
        rows_a = WeatherIngestionService.normalise(payload, tenant_id="A", property_id="pA")
        rows_b = WeatherIngestionService.normalise(payload, tenant_id="B", property_id="pB")

        for r in rows_a:
            assert r.tenant_id == "A"
        for r in rows_b:
            assert r.tenant_id == "B"

        ids_a = {r.tenant_id for r in rows_a}
        ids_b = {r.tenant_id for r in rows_b}
        assert ids_a.isdisjoint(ids_b)


# ---------------------------------------------------------------------------
# API tests -- POST /api/v1/weather/sync
# ---------------------------------------------------------------------------

def _make_weather_app() -> FastAPI:
    from app.api.routes import weather as weather_module
    app = FastAPI()
    app.add_exception_handler(HTTPException, problem_details_handler)
    app.include_router(weather_module.router, prefix="/api/v1")
    return app


class TestWeatherSyncEndpoint:
    def _user(self):
        return {"id": "user-uuid-1", "email": "manager@hotel.com"}

    def _mock_profile(self, tenant_id: str = "tenant-A") -> MagicMock:
        p = MagicMock()
        p.tenant_id = tenant_id
        p.latitude = 48.8566
        p.longitude = 2.3522
        p.owner_id = "user-uuid-1"
        return p

    def _db_with_profile(self, profile):
        async def _fake_db():
            mock_db = AsyncMock()
            result = MagicMock()
            result.scalars.return_value.first.return_value = profile
            mock_db.execute = AsyncMock(return_value=result)
            yield mock_db
        return _fake_db

    def test_sync_returns_202(self):
        from app.core.security import get_current_user
        from app.db.session import get_db

        app = _make_weather_app()
        app.dependency_overrides[get_current_user] = lambda: self._user()
        app.dependency_overrides[get_db] = self._db_with_profile(self._mock_profile())

        with patch("app.api.routes.weather._run_sync", new=AsyncMock()):
            resp = TestClient(app).post("/api/v1/weather/sync")

        assert resp.status_code == 202

    def test_sync_returns_404_when_no_profile(self):
        from app.core.security import get_current_user
        from app.db.session import get_db

        app = _make_weather_app()
        app.dependency_overrides[get_current_user] = lambda: self._user()
        app.dependency_overrides[get_db] = self._db_with_profile(None)

        resp = TestClient(app).post("/api/v1/weather/sync")

        assert resp.status_code == 404

    def test_sync_response_is_camelcase(self):
        from app.core.security import get_current_user
        from app.db.session import get_db

        app = _make_weather_app()
        app.dependency_overrides[get_current_user] = lambda: self._user()
        app.dependency_overrides[get_db] = self._db_with_profile(
            self._mock_profile(tenant_id="tenant-X")
        )

        with patch("app.api.routes.weather._run_sync", new=AsyncMock()):
            resp = TestClient(app).post("/api/v1/weather/sync")

        assert resp.status_code == 202
        data = resp.json()
        assert "propertyId" in data
        assert "property_id" not in data

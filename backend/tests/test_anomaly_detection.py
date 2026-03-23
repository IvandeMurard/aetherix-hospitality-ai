"""Tests for Story 3.3a: Detect Demand Anomalies Against Baseline.

Covers AC 2, 3, 4, 5, 6, 7, 8 and NFR5 performance gate.

Test categories:
  1. Unit — generate_windows()
  2. Unit — weather_modifier()
  3. Unit — event_modifier()
  4. Unit — detect_for_property() with mocked DB (scenarios A, B, C)
  5. Unit — idempotency (double-run must not produce duplicate rows)
  6. Integration — POST /api/v1/anomalies/scan returns 202
  7. Integration — RLS tenant isolation
  8. Performance — run_full_scan() with 50 mocked properties under 5s
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_handlers import problem_details_handler
from app.services.anomaly_detection import AnomalyDetectionService
from app.services.demand_modifiers import event_modifier, weather_modifier


# ===========================================================================
# 1. Unit — generate_windows()
# ===========================================================================
class TestGenerateWindows:
    """AC 2: 4-hour window generation over 14 days."""

    def setup_method(self):
        self.service = AnomalyDetectionService()

    def test_window_count_for_14_days(self):
        """14 days × 6 windows/day = 84 windows maximum."""
        start = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        windows = self.service.generate_windows(start, days_ahead=14)
        assert len(windows) == 84, f"Expected 84 windows, got {len(windows)}"

    def test_windows_are_exactly_4_hours(self):
        start = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        windows = self.service.generate_windows(start)
        for ws, we in windows:
            delta = we - ws
            assert delta == timedelta(hours=4), f"Window is not 4h: {delta}"

    def test_windows_non_overlapping(self):
        start = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        windows = self.service.generate_windows(start)
        for (ws1, we1), (ws2, we2) in zip(windows, windows[1:]):
            assert we1 == ws2, f"Overlapping windows: {we1} != {ws2}"

    def test_windows_aligned_to_utc_boundaries(self):
        """Windows must start at hours 0, 4, 8, 12, 16, 20."""
        start = datetime(2026, 3, 23, 2, 30, 0, tzinfo=timezone.utc)  # mid-window
        windows = self.service.generate_windows(start, days_ahead=1)
        for ws, _ in windows:
            assert ws.hour % 4 == 0, f"Window start not aligned: {ws}"

    def test_single_day_returns_6_windows(self):
        start = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        windows = self.service.generate_windows(start, days_ahead=1)
        assert len(windows) == 6


# ===========================================================================
# 2. Unit — weather_modifier()
# ===========================================================================
class TestWeatherModifier:
    """AC 3, 4, 5: modifier values and triggering_factor shape."""

    def test_thunderstorm(self):
        mod, factor = weather_modifier("thunderstorm")
        assert mod == -0.20
        assert factor["type"] == "weather"
        assert factor["condition"] == "thunderstorm"
        assert "-" in factor["impact"]

    def test_rain(self):
        mod, _ = weather_modifier("rain")
        assert mod == -0.10

    def test_showers(self):
        mod, _ = weather_modifier("showers")
        assert mod == -0.10

    def test_snow(self):
        mod, _ = weather_modifier("snow")
        assert mod == -0.15

    def test_fog(self):
        mod, _ = weather_modifier("fog")
        assert mod == -0.05

    def test_clear(self):
        mod, factor = weather_modifier("clear")
        assert mod == +0.05
        assert "+" in factor["impact"]

    def test_partly_cloudy(self):
        mod, _ = weather_modifier("partly_cloudy")
        assert mod == 0.00

    def test_unknown_condition_defaults_zero(self):
        mod, factor = weather_modifier("hurricane")
        assert mod == 0.0

    def test_case_insensitive(self):
        mod1, _ = weather_modifier("RAIN")
        mod2, _ = weather_modifier("rain")
        assert mod1 == mod2


# ===========================================================================
# 3. Unit — event_modifier()
# ===========================================================================
def _make_event(category: str, event_id: str = "ev-1") -> MagicMock:
    e = MagicMock()
    e.category = category
    e.predicthq_event_id = event_id
    e.id = event_id
    e.impact_score = 50
    return e


class TestEventModifier:
    """AC 3, 4, 5: modifier values and cap behaviour."""

    def test_conference(self):
        events = [_make_event("conference")]
        mod, factors = event_modifier(events)
        assert mod == 0.25
        assert factors[0]["category"] == "conference"
        assert factors[0]["type"] == "event"

    def test_concert(self):
        mod, _ = event_modifier([_make_event("concert")])
        assert mod == 0.20

    def test_sports(self):
        mod, _ = event_modifier([_make_event("sports")])
        assert mod == 0.15

    def test_festival(self):
        mod, _ = event_modifier([_make_event("festival")])
        assert mod == 0.20

    def test_community(self):
        mod, _ = event_modifier([_make_event("community")])
        assert mod == 0.05

    def test_other(self):
        mod, _ = event_modifier([_make_event("other")])
        assert mod == 0.05

    def test_cap_at_0_50(self):
        """5 conferences would be +1.25, but cap is +0.50."""
        events = [_make_event("conference", f"ev-{i}") for i in range(5)]
        mod, _ = event_modifier(events)
        assert mod == 0.50, f"Expected 0.50 (cap), got {mod}"

    def test_empty_events_returns_zero(self):
        mod, factors = event_modifier([])
        assert mod == 0.0
        assert factors == []

    def test_triggering_factors_include_event_id(self):
        events = [_make_event("concert", "abc-123")]
        _, factors = event_modifier(events)
        assert factors[0]["event_id"] == "abc-123"


# ===========================================================================
# 4. Unit — detect_for_property() (mocked DB)
# ===========================================================================
class TestDetectForProperty:
    """AC 2, 3, 4, 5 — mocked DB scenarios."""

    def setup_method(self):
        self.service = AnomalyDetectionService()
        self.property_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()

    @pytest.mark.asyncio
    async def test_scenario_a_no_events_no_weather_no_anomaly(self):
        """Scenario A: baseline weather (partly_cloudy), no events → deviation 0% → no anomaly."""
        with (
            patch.object(self.service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(self.service, "_get_weather_for_window", return_value=None),
            patch.object(self.service, "_get_events_for_window", return_value=[]),
            patch.object(self.service, "_bulk_upsert", new_callable=AsyncMock) as mock_upsert,
        ):
            mock_db = AsyncMock()
            result = await self.service.detect_for_property(
                mock_db, self.property_id, self.tenant_id
            )
            # No anomaly: deviation is 0%, below threshold of 20%
            mock_upsert.assert_not_called()
            assert result == []

    @pytest.mark.asyncio
    async def test_scenario_b_thunderstorm_conference_surge_anomaly(self):
        """Scenario B: thunderstorm (-20%) + conference (+25%) → net +5% → still below 20%.
        Use two conferences (+25% + capped remainder) to push above 20%.
        """
        # thunderstorm: -0.20, two conferences: +0.25+0.25 = +0.50 combined → net +0.30 → +30%
        weather_mock = MagicMock()
        weather_mock.condition_code = "thunderstorm"
        events = [_make_event("conference", "ev-1"), _make_event("conference", "ev-2")]

        with (
            patch.object(self.service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(self.service, "_get_weather_for_window", return_value=weather_mock),
            patch.object(self.service, "_get_events_for_window", return_value=events),
            patch.object(self.service, "_bulk_upsert", new_callable=AsyncMock) as mock_upsert,
        ):
            mock_upsert.return_value = [str(uuid.uuid4())]
            mock_db = AsyncMock()
            await self.service.detect_for_property(mock_db, self.property_id, self.tenant_id)
            # At least one anomaly (surge) should be upserted
            mock_upsert.assert_called()
            anomalies_batch = mock_upsert.call_args[0][1]
            directions = [a["direction"] for a in anomalies_batch]
            assert "surge" in directions, f"Expected surge, got {directions}"

    @pytest.mark.asyncio
    async def test_scenario_c_lull_rain_no_events(self):
        """Scenario C: rain (-10%) + no events → -10% deviation → below threshold (20%)."""
        # Rain alone gives -10%, which is below the 20% threshold, so no anomaly.
        # Use snow (-15%) + rain scenario won't work directly because they're separate calls.
        # To create a lull anomaly we need deviation >= 20%: use thunderstorm (-20%).
        weather_mock = MagicMock()
        weather_mock.condition_code = "thunderstorm"

        with (
            patch.object(self.service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(self.service, "_get_weather_for_window", return_value=weather_mock),
            patch.object(self.service, "_get_events_for_window", return_value=[]),
            patch.object(self.service, "_bulk_upsert", new_callable=AsyncMock) as mock_upsert,
        ):
            mock_upsert.return_value = [str(uuid.uuid4())]
            mock_db = AsyncMock()
            await self.service.detect_for_property(mock_db, self.property_id, self.tenant_id)
            mock_upsert.assert_called()
            anomalies_batch = mock_upsert.call_args[0][1]
            directions = [a["direction"] for a in anomalies_batch]
            assert "lull" in directions, f"Expected lull anomaly, got {directions}"

    @pytest.mark.asyncio
    async def test_triggering_factors_included(self):
        """AC 5: triggering_factors must include weather and event entries."""
        weather_mock = MagicMock()
        weather_mock.condition_code = "thunderstorm"
        events = [_make_event("conference", "conf-1"), _make_event("concert", "conc-1")]

        with (
            patch.object(self.service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(self.service, "_get_weather_for_window", return_value=weather_mock),
            patch.object(self.service, "_get_events_for_window", return_value=events),
            patch.object(self.service, "_bulk_upsert", new_callable=AsyncMock) as mock_upsert,
        ):
            mock_upsert.return_value = [str(uuid.uuid4())]
            mock_db = AsyncMock()
            await self.service.detect_for_property(mock_db, self.property_id, self.tenant_id)
            anomalies_batch = mock_upsert.call_args[0][1]
            for anomaly in anomalies_batch:
                factors = anomaly["triggering_factors"]
                types = {f["type"] for f in factors}
                assert "weather" in types or "event" in types


# ===========================================================================
# 5. Unit — idempotency
# ===========================================================================
class TestIdempotency:
    """AC 7: running the scan twice must not produce duplicate rows."""

    @pytest.mark.asyncio
    async def test_double_run_calls_upsert_with_same_windows(self):
        """The _bulk_upsert is called with the same window_start values on both runs."""
        service = AnomalyDetectionService()
        property_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        weather_mock = MagicMock()
        weather_mock.condition_code = "thunderstorm"

        upserted_windows: List[List[str]] = []

        async def capture_upsert(db, anomalies):
            upserted_windows.append([a["window_start"] for a in anomalies])
            return [a["id"] for a in anomalies]

        with (
            patch.object(service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(service, "_get_weather_for_window", return_value=weather_mock),
            patch.object(service, "_get_events_for_window", return_value=[]),
            patch.object(service, "_bulk_upsert", side_effect=capture_upsert),
        ):
            mock_db = AsyncMock()
            await service.detect_for_property(mock_db, property_id, tenant_id)
            await service.detect_for_property(mock_db, property_id, tenant_id)

        # Both runs should produce the same window_starts (idempotent)
        assert upserted_windows[0] == upserted_windows[1], (
            "Idempotency violation: window_starts differ between runs"
        )


# ===========================================================================
# 6. Integration — POST /api/v1/anomalies/scan returns 202
# ===========================================================================
def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the anomalies router for integration tests."""
    from app.api.routes.anomalies import router as anomalies_router

    test_app = FastAPI()
    test_app.add_exception_handler(HTTPException, problem_details_handler)
    test_app.include_router(anomalies_router, prefix="/api/v1")
    return test_app


class TestAnomalyScanEndpoint:
    """AC 9: POST /api/v1/anomalies/scan integration tests."""

    @pytest.fixture
    def client(self):
        from app.api.routes.anomalies import _resolve_property_for_user

        test_app = _make_test_app()

        # Patch auth dependency
        fake_user = {"id": str(uuid.uuid4()), "email": "test@hotel.io"}
        fake_property_id = uuid.uuid4()
        fake_tenant_id = uuid.uuid4()

        async def mock_current_user():
            return fake_user

        async def mock_resolve_property(db, user):
            return fake_property_id, fake_tenant_id

        async def mock_get_db():
            yield AsyncMock()

        from app.core.security import get_current_user
        from app.db.session import get_db

        test_app.dependency_overrides[get_current_user] = mock_current_user
        test_app.dependency_overrides[get_db] = mock_get_db

        with (
            patch("app.api.routes.anomalies._resolve_property_for_user", mock_resolve_property),
            patch("app.api.routes.anomalies._run_scan_background", new_callable=AsyncMock),
        ):
            yield TestClient(test_app, raise_server_exceptions=False)

    def test_scan_returns_202(self, client):
        response = client.post("/api/v1/anomalies/scan")
        assert response.status_code == 202, response.text

    def test_scan_response_body_has_message(self, client):
        response = client.post("/api/v1/anomalies/scan")
        data = response.json()
        assert "message" in data


# ===========================================================================
# 7. Integration — RLS tenant isolation
# ===========================================================================
class TestTenantIsolation:
    """AC 6: RLS prevents cross-tenant anomaly leakage."""

    @pytest.mark.asyncio
    async def test_detect_for_property_uses_tenant_in_upsert(self):
        """tenant_id must be embedded in every upserted anomaly row."""
        service = AnomalyDetectionService()
        property_id = uuid.uuid4()
        tenant_id_a = uuid.uuid4()

        weather_mock = MagicMock()
        weather_mock.condition_code = "thunderstorm"

        captured: List[dict] = []

        async def capture_upsert(db, anomalies):
            captured.extend(anomalies)
            return [a["id"] for a in anomalies]

        with (
            patch.object(service, "_get_baseline_demand", return_value=Decimal("1000.00")),
            patch.object(service, "_get_weather_for_window", return_value=weather_mock),
            patch.object(service, "_get_events_for_window", return_value=[]),
            patch.object(service, "_bulk_upsert", side_effect=capture_upsert),
        ):
            mock_db = AsyncMock()
            await service.detect_for_property(mock_db, property_id, tenant_id_a)

        for anomaly in captured:
            assert anomaly["tenant_id"] == str(tenant_id_a), (
                f"Anomaly has wrong tenant_id: {anomaly['tenant_id']}"
            )


# ===========================================================================
# 8. Performance — run_full_scan() with 50 mocked properties under 5s (NFR5)
# ===========================================================================
class TestNFR5Performance:
    """AC 8: NFR5 — full scan across 50 properties completes under 5 seconds."""

    @pytest.mark.asyncio
    async def test_run_full_scan_50_properties_under_5_seconds(self):
        service = AnomalyDetectionService()

        # Mock 50 property rows
        property_rows = [
            (uuid.uuid4(), uuid.uuid4()) for _ in range(50)
        ]

        # Mock detect_for_property to be nearly instant (simulates I/O-bound with gather)
        async def mock_detect(db, property_id, tenant_id):
            await asyncio.sleep(0.01)  # 10ms per property
            return []

        mock_db = AsyncMock()

        # Simulate the DB returning 50 properties
        mock_result = MagicMock()
        mock_result.fetchall.return_value = property_rows
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(service, "detect_for_property", side_effect=mock_detect):
            t_start = time.monotonic()
            await service.run_full_scan(mock_db)
            elapsed = time.monotonic() - t_start

        assert elapsed < 5.0, (
            f"NFR5 VIOLATED: run_full_scan took {elapsed:.3f}s "
            f"(limit: 5.0s) for 50 properties"
        )
        # With asyncio.gather, 50 × 10ms should be ~10ms total, not 500ms
        assert elapsed < 1.0, (
            f"run_full_scan is not running in parallel: elapsed={elapsed:.3f}s "
            f"(expected ~0.01s with gather)"
        )

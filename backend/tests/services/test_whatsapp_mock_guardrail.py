"""HOS-303 — mock-forecast guardrail on the manager-facing WhatsApp path.

The untrained-model fallback (PredictionResult.is_mock=True, hardcoded 45
covers) must never ground a manager-facing LLM reply:
- AC2a: outside DEMO_MODE the covers/staffing are withheld from the LLM
  context and a typed trip row is recorded (NFR2, ADR-0009).
- AC2b: in DEMO_MODE the numbers pass through but visibly marked as demo data.
- AC3: a real (is_mock=False) forecast is untouched and records no trip.
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub heavy optional dependencies not installed in CI before app imports.
for _mod in ("pandas", "prophet", "qdrant_client", "redis", "twilio"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from app.db.models import RestaurantProfile  # noqa: E402
from app.services import whatsapp_service as ws  # noqa: E402
from app.services.whatsapp_service import (  # noqa: E402
    REASON_MOCK_FORECAST,
    WhatsAppService,
    _record_mock_forecast_trip,
)


def _profile() -> RestaurantProfile:
    p = RestaurantProfile()
    p.tenant_id = "tenant-demo"
    p.property_name = "Hotel Kleber"
    p.outlet_name = "Le Bistrot Kleber"
    p.total_seats = 120
    p.manager_name = "Sophie"
    p.agent_tone_profile = "luxury"
    return p


def _make_service(llm_return: str = "ok") -> WhatsAppService:
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=llm_return)

    with patch("app.services.whatsapp_service.get_llm_provider", return_value=mock_llm), \
         patch("app.services.whatsapp_service.AetherixEngine"), \
         patch("app.services.whatsapp_service.MemoryService"):
        svc = WhatsAppService()

    svc._llm = mock_llm
    return svc


_MOCK_FORECAST = {
    "prediction": {"covers": 45, "confidence": 0.85, "is_mock": True},
    "historical_patterns": [],
    "staffing_recommendation": {"servers": 3},
}

_REAL_FORECAST = {
    "prediction": {"covers": 95, "confidence": 0.82, "is_mock": False},
    "historical_patterns": [],
    "staffing_recommendation": {"servers": 6},
}


class TestMockForecastSuppressed:
    """AC2a — outside DEMO_MODE: covers withheld + typed trip recorded."""

    @pytest.mark.asyncio
    async def test_mock_covers_never_reach_llm_context(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_MOCK_FORECAST)

        with patch.object(ws, "DEMO_MODE", False), \
             patch.object(ws, "_record_mock_forecast_trip", new_callable=AsyncMock):
            await svc._generate_response("forecast?", "tenant-demo", _profile())

        system = svc._llm.complete.call_args.kwargs["system"]
        assert "45" not in system
        # Same rendering as the forecast-failure path: covers placeholder.
        assert "Hotel Kleber" in system

    @pytest.mark.asyncio
    async def test_typed_trip_recorded_once(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_MOCK_FORECAST)

        with patch.object(ws, "DEMO_MODE", False), \
             patch.object(ws, "_record_mock_forecast_trip", new_callable=AsyncMock) as trip:
            await svc._generate_response("forecast?", "tenant-demo", _profile())

        trip.assert_awaited_once_with("tenant-demo")

    @pytest.mark.asyncio
    async def test_llm_still_replies_without_numbers(self):
        svc = _make_service("Je n'ai pas encore de prévision fiable.")
        svc.engine.get_forecast = AsyncMock(return_value=_MOCK_FORECAST)

        with patch.object(ws, "DEMO_MODE", False), \
             patch.object(ws, "_record_mock_forecast_trip", new_callable=AsyncMock):
            result = await svc._generate_response("forecast?", "tenant-demo", _profile())

        assert result == "Je n'ai pas encore de prévision fiable."


class TestMockForecastDemoMode:
    """AC2b — DEMO_MODE: numbers pass but visibly marked as demo data."""

    @pytest.mark.asyncio
    async def test_covers_marked_as_demo(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_MOCK_FORECAST)

        with patch.object(ws, "DEMO_MODE", True), \
             patch.object(ws, "_record_mock_forecast_trip", new_callable=AsyncMock) as trip:
            await svc._generate_response("forecast?", "tenant-demo", _profile())

        system = svc._llm.complete.call_args.kwargs["system"]
        assert "45" in system
        assert "demo data" in system
        trip.assert_not_awaited()


class TestRealForecastUntouched:
    """AC3 — is_mock=False: passthrough, no trip, no marker."""

    @pytest.mark.asyncio
    async def test_real_covers_pass_through(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_REAL_FORECAST)

        with patch.object(ws, "DEMO_MODE", False), \
             patch.object(ws, "_record_mock_forecast_trip", new_callable=AsyncMock) as trip:
            await svc._generate_response("forecast?", "tenant-demo", _profile())

        system = svc._llm.complete.call_args.kwargs["system"]
        assert "95" in system
        assert "demo data" not in system
        trip.assert_not_awaited()


class TestTripRecorder:
    """The recorder writes one AgentActionLog row with the typed reason."""

    @pytest.mark.asyncio
    async def test_trip_row_shape(self):
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_db)
        cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.whatsapp_service.AsyncSessionLocal", return_value=cm):
            await _record_mock_forecast_trip("tenant-demo")

        mock_db.add.assert_called_once()
        row = mock_db.add.call_args.args[0]
        assert row.error_code == REASON_MOCK_FORECAST
        assert row.status == "tool_error"
        assert row.payload["kind"] == "trip"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_failure_is_non_fatal(self):
        with patch(
            "app.services.whatsapp_service.AsyncSessionLocal",
            side_effect=RuntimeError("db down"),
        ):
            # Must not raise — a guardrail failure never breaks the reply path.
            await _record_mock_forecast_trip("tenant-demo")

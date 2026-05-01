"""Tests for WhatsAppService._generate_response() LLM delegation (Prompt B Task 4).

Coverage:
- AC1: LLM is called with a system prompt when profile and forecast load successfully
- AC2: Forecast failure falls back to minimal context but LLM is still called
- AC3: AgentConstitutionService failure still calls LLM with system=None
- AC4: LLM exception returns graceful fallback string
- AC5: LLM response is returned verbatim (no keyword filtering applied)
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies that are not installed in CI
# (pandas, prophet, qdrant_client, redis) before any app import occurs.
# ---------------------------------------------------------------------------
for _mod in ("pandas", "prophet", "qdrant_client", "redis", "twilio"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from app.db.models import RestaurantProfile  # noqa: E402
from app.services.whatsapp_service import WhatsAppService  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile() -> RestaurantProfile:
    p = RestaurantProfile()
    p.tenant_id = "tenant-demo"
    p.property_name = "Hotel Kleber"
    p.outlet_name = "Le Bistrot Kleber"
    p.total_seats = 120
    p.manager_name = "Sophie"
    p.agent_tone_profile = "luxury"
    return p


def _make_service(llm_return: str = "LLM response text") -> WhatsAppService:
    """Return a WhatsAppService with all heavy dependencies mocked."""
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=llm_return)

    with patch("app.services.whatsapp_service.get_llm_provider", return_value=mock_llm), \
         patch("app.services.whatsapp_service.AetherixEngine"), \
         patch("app.services.whatsapp_service.MemoryService"):
        svc = WhatsAppService()

    svc._llm = mock_llm
    return svc


_FAKE_FORECAST = {
    "prediction": {"covers": 95, "confidence": 0.82},
    "historical_patterns": [],
    "staffing_recommendation": {"servers": 6},
}


# ---------------------------------------------------------------------------
# AC1 — LLM called with system prompt on happy path
# ---------------------------------------------------------------------------

class TestGenerateResponseHappyPath:
    @pytest.mark.asyncio
    async def test_llm_called_with_system_kwarg(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)
        profile = _profile()

        await svc._generate_response("What's the forecast tonight?", "tenant-demo", profile)

        call_kwargs = svc._llm.complete.call_args.kwargs
        assert "system" in call_kwargs
        assert "Hotel Kleber" in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_user_message_passed_verbatim(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)

        await svc._generate_response("How many staff tonight?", "tenant-demo", _profile())

        messages = svc._llm.complete.call_args.kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "How many staff tonight?"

    @pytest.mark.asyncio
    async def test_returns_llm_response(self):
        svc = _make_service("95 covers expected tonight.")
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)

        result = await svc._generate_response("forecast?", "tenant-demo", _profile())

        assert result == "95 covers expected tonight."


# ---------------------------------------------------------------------------
# AC2 — Forecast failure: minimal context, LLM still called
# ---------------------------------------------------------------------------

class TestGenerateResponseForecastFailure:
    @pytest.mark.asyncio
    async def test_llm_called_despite_forecast_exception(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(side_effect=Exception("DB unavailable"))

        await svc._generate_response("forecast?", "tenant-demo", _profile())

        svc._llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_prompt_still_rendered_with_minimal_context(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(side_effect=RuntimeError("timeout"))

        await svc._generate_response("staffing?", "tenant-demo", _profile())

        call_kwargs = svc._llm.complete.call_args.kwargs
        # System prompt is rendered even without forecast data
        assert "system" in call_kwargs
        assert "Hotel Kleber" in call_kwargs["system"]


# ---------------------------------------------------------------------------
# AC3 — AgentConstitutionService failure: LLM called with system=None
# ---------------------------------------------------------------------------

class TestGenerateResponseConstitutionFailure:
    @pytest.mark.asyncio
    async def test_llm_called_without_system_when_constitution_fails(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)

        # AgentConstitutionService is a deferred local import — patch at source module
        with patch(
            "app.services.agent_constitution.AgentConstitutionService.build_system_prompt",
            side_effect=Exception("render error"),
        ):
            await svc._generate_response("hello?", "tenant-demo", _profile())

        call_kwargs = svc._llm.complete.call_args.kwargs
        assert "system" not in call_kwargs


# ---------------------------------------------------------------------------
# AC4 — LLM exception returns graceful fallback
# ---------------------------------------------------------------------------

class TestGenerateResponseLlmFailure:
    @pytest.mark.asyncio
    async def test_llm_exception_returns_fallback_string(self):
        svc = _make_service()
        svc._llm.complete = AsyncMock(side_effect=RuntimeError("overloaded"))
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)

        result = await svc._generate_response("forecast?", "tenant-demo", _profile())

        assert "trouble" in result.lower() or "try again" in result.lower()


# ---------------------------------------------------------------------------
# AC5 — No keyword filtering: any message reaches the LLM
# ---------------------------------------------------------------------------

class TestGenerateResponseNoKeywordFilter:
    @pytest.mark.parametrize("message", [
        "What should I order?",
        "How is the weather?",
        "Bonjour!",
        "Can you explain the staffing rationale?",
    ])
    @pytest.mark.asyncio
    async def test_arbitrary_messages_reach_llm(self, message: str):
        svc = _make_service("ok")
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)

        result = await svc._generate_response(message, "tenant-demo", _profile())

        svc._llm.complete.assert_awaited_once()
        assert result == "ok"

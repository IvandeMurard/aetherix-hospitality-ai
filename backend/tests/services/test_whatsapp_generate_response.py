"""Tests for WhatsAppService._generate_response() LLM delegation (Prompt B Task 4).

Coverage:
- AC1: LLM is called with a system prompt when profile and forecast load successfully
- AC2: Forecast failure falls back to minimal context but LLM is still called
- AC3: AgentConstitutionService failure → no LLM call, deterministic reply +
  typed trip (HOS-366, rule B; it used to call the LLM with system=None)
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
from app.services import whatsapp_service  # noqa: E402
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
# AC3 — AgentConstitutionService failure. HOS-366 (rule B, audit of silences
# case 11) reverses the old behaviour, which this test used to freeze ("LLM
# called with system=None"): no model call without the constitution — a
# deterministic reply and a typed trip instead.
# ---------------------------------------------------------------------------

class TestGenerateResponseConstitutionFailure:
    @pytest.mark.asyncio
    async def test_no_llm_call_when_constitution_fails(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)
        trip = AsyncMock()

        # AgentConstitutionService is a deferred local import — patch at source module
        with patch(
            "app.services.agent_constitution.AgentConstitutionService.build_system_prompt",
            side_effect=Exception("render error"),
        ), patch("app.services.whatsapp_service._record_constitution_trip", trip):
            result = await svc._generate_response("hello?", "tenant-demo", _profile())

        svc._llm.complete.assert_not_awaited()
        assert result == whatsapp_service.no_constitution_reply("fr")
        trip.assert_awaited_once()
        assert trip.await_args.args[0] == "tenant-demo"
        assert "render error" in trip.await_args.args[1]

    @pytest.mark.asyncio
    async def test_blank_constitution_is_treated_as_missing(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)
        with patch(
            "app.services.agent_constitution.AgentConstitutionService.build_system_prompt",
            return_value="   ",
        ), patch("app.services.whatsapp_service._record_constitution_trip", AsyncMock()):
            await svc._generate_response("hello?", "tenant-demo", _profile())
        svc._llm.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reply_follows_the_manager_locale(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value=_FAKE_FORECAST)
        profile = _profile()
        profile.manager_locale = "en"
        with patch(
            "app.services.agent_constitution.AgentConstitutionService.build_system_prompt",
            side_effect=Exception("render error"),
        ), patch("app.services.whatsapp_service._record_constitution_trip", AsyncMock()):
            result = await svc._generate_response("hello?", "tenant-demo", profile)
        assert result == whatsapp_service.no_constitution_reply("en")
        assert "%" not in result

    @pytest.mark.asyncio
    async def test_trip_writes_a_typed_row_and_alerts_ops(self):
        store: list = []

        class _Sess:
            async def __aenter__(self): return self
            async def __aexit__(self, *_): return False
            def add(self, obj): store.append(obj)
            async def commit(self): return None

        error = AsyncMock()
        with patch.object(whatsapp_service, "AsyncSessionLocal", lambda: _Sess()), \
                patch("app.services.ops_dispatcher.dispatch_error", error):
            await whatsapp_service._record_constitution_trip("tenant-demo", "render error")
        assert len(store) == 1
        assert store[0].error_code == "constitution_unavailable"
        assert store[0].tool_name == whatsapp_service.CONSTITUTION_TOOL
        error.assert_awaited_once()


class TestNotVerifiedForecastIsMarkedForTheModel:
    @pytest.mark.asyncio
    async def test_not_verified_forecast_is_marked_in_the_constitution_context(self):
        svc = _make_service()
        svc.engine.get_forecast = AsyncMock(return_value={
            **_FAKE_FORECAST, "forecast_guardrail": {"tier": "not_verified", "verified": False},
        })
        await svc._generate_response("forecast?", "tenant-demo", _profile())
        system = svc._llm.complete.call_args.kwargs["system"]
        assert "NOT VERIFIED" in system


@pytest.mark.parametrize("prompt,expected", [
    (None, "constitution_unavailable"),
    ("", "constitution_unavailable"),
    ("You are Aetherix…", None),
])
def test_evaluate_constitution_gate(prompt, expected):
    breach = whatsapp_service.evaluate_constitution_gate(prompt)
    assert (breach[0] if breach else None) == expected


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

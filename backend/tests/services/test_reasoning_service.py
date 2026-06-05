"""Tests for ReasoningService LLM provider injection (HOS-120 — LLM-2).

Coverage:
- AC1: ReasoningService accepts an LLMProvider via __init__ (DI)
- AC2: generate_explanation() calls provider.complete() and returns claude_used=True
- AC3: RuntimeError (missing key) triggers silent heuristic fallback, no dispatch
- AC4: Other LLM exceptions trigger dispatch_error and heuristic fallback
- AC5: Heuristic fallback produces a valid summary when no patterns are available
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.reasoning_service import ReasoningService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm(return_value: str = "LLM explanation text.") -> AsyncMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=return_value)
    llm.model_id = "claude/claude-sonnet-4-6"
    return llm


_CONTEXT = {"weather": {"condition": "sunny"}, "events": [], "occupancy": 0.8}
_PATTERNS = [{"date": "2025-12-01", "actual_covers": 120, "score": 0.9}]
_DATE = date(2026, 4, 7)


# ---------------------------------------------------------------------------
# AC1 — DI accepted
# ---------------------------------------------------------------------------

class TestReasoningServiceDI:
    def test_accepts_llm_provider(self):
        llm = _mock_llm()
        service = ReasoningService(llm=llm)
        assert service._llm is llm

    def test_default_uses_factory(self):
        from app.providers.fallback_provider import FallbackLLMProvider
        service = ReasoningService()
        assert isinstance(service._llm, FallbackLLMProvider)


# ---------------------------------------------------------------------------
# AC2 — Happy path
# ---------------------------------------------------------------------------

class TestReasoningServiceHappyPath:
    @pytest.mark.asyncio
    async def test_returns_claude_used_true(self):
        llm = _mock_llm("Dinner will be busy due to the event nearby.")
        service = ReasoningService(llm=llm)

        result = await service.generate_explanation(
            predicted_covers=150,
            confidence=0.85,
            target_date=_DATE,
            service_type="dinner",
            context=_CONTEXT,
            similar_patterns=_PATTERNS,
        )

        assert result["claude_used"] is True
        assert result["summary"] == "Dinner will be busy due to the event nearby."
        llm.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_correct_max_tokens_and_temperature(self):
        llm = _mock_llm("ok")
        service = ReasoningService(llm=llm)

        await service.generate_explanation(
            predicted_covers=100,
            confidence=0.7,
            target_date=_DATE,
            service_type="lunch",
            context=_CONTEXT,
            similar_patterns=[],
        )

        call_kwargs = llm.complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 300
        assert call_kwargs["temperature"] == 0.3
        # single user message
        assert call_kwargs["messages"][0]["role"] == "user"


# ---------------------------------------------------------------------------
# AC3 — RuntimeError → silent heuristic fallback
# ---------------------------------------------------------------------------

class TestReasoningServiceMissingKey:
    @pytest.mark.asyncio
    async def test_runtime_error_returns_heuristic_no_dispatch(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("ANTHROPIC_API_KEY not set"))

        with patch("app.services.ops_dispatcher.dispatch_error") as mock_dispatch:
            service = ReasoningService(llm=llm)
            result = await service.generate_explanation(
                predicted_covers=80,
                confidence=0.6,
                target_date=_DATE,
                service_type="breakfast",
                context=_CONTEXT,
                similar_patterns=_PATTERNS,
            )

        assert result["claude_used"] is False
        assert "fallback_reason" not in result   # RuntimeError path — no dispatch field
        mock_dispatch.assert_not_called()

    @pytest.mark.asyncio
    async def test_runtime_error_summary_is_non_empty(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("ANTHROPIC_API_KEY not set"))

        service = ReasoningService(llm=llm)
        result = await service.generate_explanation(
            predicted_covers=80,
            confidence=0.6,
            target_date=_DATE,
            service_type="breakfast",
            context=_CONTEXT,
            similar_patterns=[],
        )

        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0


# ---------------------------------------------------------------------------
# AC4 — Generic exception → dispatch_error + heuristic
# ---------------------------------------------------------------------------

class TestReasoningServiceApiError:
    @pytest.mark.asyncio
    async def test_api_exception_returns_fallback_reason(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=ValueError("rate_limit"))

        dispatched: list = []

        async def _fake_dispatch(**kwargs):
            dispatched.append(kwargs)

        with patch("app.services.ops_dispatcher.dispatch_error", new=_fake_dispatch):
            service = ReasoningService(llm=llm)
            result = await service.generate_explanation(
                predicted_covers=200,
                confidence=0.9,
                target_date=_DATE,
                service_type="dinner",
                context=_CONTEXT,
                similar_patterns=_PATTERNS,
            )

        assert result["claude_used"] is False
        assert "rate_limit" in result["fallback_reason"]


# ---------------------------------------------------------------------------
# AC5 — Heuristic summary always non-empty
# ---------------------------------------------------------------------------

class TestReasoningServiceHeuristic:
    def test_heuristic_no_patterns(self):
        service = ReasoningService(llm=_mock_llm())
        result = service._heuristic_explanation(
            predicted=90,
            confidence=0.75,
            dt=_DATE,
            svc="lunch",
            context={},
            patterns=[],
        )
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 10
        assert result["claude_used"] is False

    def test_heuristic_with_patterns(self):
        service = ReasoningService(llm=_mock_llm())
        result = service._heuristic_explanation(
            predicted=120,
            confidence=0.88,
            dt=_DATE,
            svc="dinner",
            context=_CONTEXT,
            patterns=_PATTERNS,
        )
        assert "120" in result["summary"]
        assert "dinner" in result["summary"].lower()


# ---------------------------------------------------------------------------
# HOS-201 (P3-11) — named events in the forecast explanation
# ---------------------------------------------------------------------------

class TestNamedEvents:
    def _build(self, events: list) -> str:
        service = ReasoningService(llm=_mock_llm())
        ctx = {"weather": {"condition": "sunny"}, "events": events, "occupancy": 0.8}
        return service._build_prompt(
            150, 0.85, _DATE, "dinner", ctx, _PATTERNS, None,
        )

    def test_prompt_names_events_ac_example_fields(self):
        """AC1: events with name/distance_km render as a named, located line."""
        prompt = self._build(
            [{"name": "PSG vs Arsenal", "distance_km": 2.1, "category": "Sports"}]
        )
        assert "PSG vs Arsenal" in prompt
        assert "2.1 km" in prompt
        assert "events nearby" not in prompt  # the old opaque count is gone

    def test_prompt_names_events_real_ingestion_fields(self):
        """AC3: real local_events dicts use title/category/phq_attendance."""
        prompt = self._build([
            {"title": "Concert Bercy", "category": "Music", "phq_attendance": 15000},
            {"title": "Tech conference", "category": "Conferences", "phq_attendance": 4000},
        ])
        assert "Concert Bercy" in prompt
        assert "Music" in prompt
        assert "~15,000 expected" in prompt
        assert "Tech conference" in prompt

    def test_prompt_empty_events_fallback(self):
        """AC2: empty events → 'No events nearby' fallback."""
        prompt = self._build([])
        assert "No events nearby" in prompt

    def test_heuristic_names_events(self):
        """AC4: the heuristic fallback names events consistently."""
        service = ReasoningService(llm=_mock_llm())
        ctx = {
            "weather": {"condition": "rain"},
            "events": [{"title": "PSG vs Arsenal", "category": "Sports"}],
            "occupancy": 0.9,
        }
        result = service._heuristic_explanation(
            predicted=180, confidence=0.9, dt=_DATE, svc="dinner",
            context=ctx, patterns=_PATTERNS,
        )
        assert "PSG vs Arsenal" in result["summary"]
        assert "nearby event(s)" not in result["summary"]  # old count phrasing gone

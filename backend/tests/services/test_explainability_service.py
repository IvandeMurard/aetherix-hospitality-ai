"""Tests for ExplainabilityService LLM provider injection (HOS-120 — LLM-2).

Coverage:
- AC1: ExplainabilityService accepts an LLMProvider via __init__ (DI)
- AC2: _call_claude() calls provider.complete() and returns stripped text
- AC3: RuntimeError (missing key) returns _FALLBACK_REPLY with warning log
- AC4: Generic exception returns _FALLBACK_REPLY with error log
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.explainability_service import ExplainabilityService, _FALLBACK_REPLY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm(return_value: str = "Here is your explanation.") -> MagicMock:
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=return_value)
    llm.model_id = "claude/claude-sonnet-4-6"
    return llm


def _make_recommendation() -> MagicMock:
    rec = MagicMock()
    rec.window_start = None
    rec.window_end = None
    rec.roi_net = None
    rec.roi_labor_cost = None
    rec.message_text = "Add 2 staff for dinner rush"
    rec.recommended_headcount = 8
    rec.triggering_factor = "surge"
    rec.anomaly_id = None
    return rec


# ---------------------------------------------------------------------------
# AC1 — DI accepted
# ---------------------------------------------------------------------------

class TestExplainabilityServiceDI:
    def test_accepts_llm_provider(self):
        llm = _mock_llm()
        service = ExplainabilityService(llm=llm)
        assert service._llm is llm

    def test_default_uses_factory(self):
        from app.providers.fallback_provider import FallbackLLMProvider
        service = ExplainabilityService()
        assert isinstance(service._llm, FallbackLLMProvider)


# ---------------------------------------------------------------------------
# AC2 — Happy path
# ---------------------------------------------------------------------------

class TestExplainabilityServiceCallClaude:
    @pytest.mark.asyncio
    async def test_returns_stripped_text(self):
        llm = _mock_llm("  Explanation with leading spaces.  ")
        service = ExplainabilityService(llm=llm)

        result = await service._call_claude(
            query_body="Why do we need extra staff?",
            recommendation=_make_recommendation(),
            anomaly=None,
        )

        assert result == "Explanation with leading spaces."

    @pytest.mark.asyncio
    async def test_passes_correct_params(self):
        llm = _mock_llm("ok")
        service = ExplainabilityService(llm=llm)

        await service._call_claude(
            query_body="Why?",
            recommendation=_make_recommendation(),
            anomaly=None,
        )

        call_kwargs = llm.complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 400
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["messages"][0]["role"] == "user"


# ---------------------------------------------------------------------------
# AC3 — RuntimeError → fallback with warning
# ---------------------------------------------------------------------------

class TestExplainabilityServiceMissingKey:
    @pytest.mark.asyncio
    async def test_runtime_error_returns_fallback(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("ANTHROPIC_API_KEY not set"))

        service = ExplainabilityService(llm=llm)
        result = await service._call_claude(
            query_body="Explain?",
            recommendation=_make_recommendation(),
            anomaly=None,
        )

        assert result == _FALLBACK_REPLY

    @pytest.mark.asyncio
    async def test_runtime_error_logs_warning(self, caplog):
        import logging
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("ANTHROPIC_API_KEY not set"))

        service = ExplainabilityService(llm=llm)
        with caplog.at_level(logging.WARNING, logger="app.services.explainability_service"):
            await service._call_claude(
                query_body="Explain?",
                recommendation=_make_recommendation(),
                anomaly=None,
            )

        assert any("not set" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC4 — Generic exception → fallback with error log
# ---------------------------------------------------------------------------

class TestExplainabilityServiceApiError:
    @pytest.mark.asyncio
    async def test_exception_returns_fallback(self):
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=ConnectionError("timeout"))

        service = ExplainabilityService(llm=llm)
        result = await service._call_claude(
            query_body="Explain?",
            recommendation=_make_recommendation(),
            anomaly=None,
        )

        assert result == _FALLBACK_REPLY

    @pytest.mark.asyncio
    async def test_exception_logs_error(self, caplog):
        import logging
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=ConnectionError("timeout"))

        service = ExplainabilityService(llm=llm)
        with caplog.at_level(logging.ERROR, logger="app.services.explainability_service"):
            await service._call_claude(
                query_body="Why?",
                recommendation=_make_recommendation(),
                anomaly=None,
            )

        assert any("timeout" in r.message for r in caplog.records)

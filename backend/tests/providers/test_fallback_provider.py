"""Tests for FallbackLLMProvider and factory auto-failover wiring.

Coverage:
- AC1: FallbackLLMProvider satisfies LLMProvider protocol
- AC2: Returns primary's response when primary succeeds
- AC3: Transparently retries with fallback when primary raises any exception
- AC4: Passes identical call arguments to fallback
- AC5: Propagates fallback exception if both providers fail
- AC6: Logs a WARNING when primary fails
- AC7: model_id shows primary→fallback composite identifier
- AC8: Factory wraps in FallbackLLMProvider when LLM_FALLBACK_BACKEND is set
- AC9: Factory returns plain provider when LLM_FALLBACK_BACKEND is unset
- AC10: Factory ignores fallback when primary == fallback backend
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.base import LLMProvider
from app.providers.fallback_provider import FallbackLLMProvider
from app.providers.factory import get_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_provider(name: str, return_value: str = "ok") -> MagicMock:
    p = MagicMock()
    p.complete = AsyncMock(return_value=return_value)
    p.model_id = name
    return p


def _failing_provider(name: str, exc: Exception) -> MagicMock:
    p = MagicMock()
    p.complete = AsyncMock(side_effect=exc)
    p.model_id = name
    return p


_MESSAGES = [{"role": "user", "content": "explain forecast"}]


# ---------------------------------------------------------------------------
# AC1 — Protocol
# ---------------------------------------------------------------------------

class TestFallbackProviderProtocol:
    def test_satisfies_llm_provider_protocol(self):
        provider = FallbackLLMProvider(
            primary=_mock_provider("claude/x"),
            fallback=_mock_provider("gemini/y"),
        )
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# AC2 — Primary success path
# ---------------------------------------------------------------------------

class TestFallbackProviderPrimarySuccess:
    @pytest.mark.asyncio
    async def test_returns_primary_response_when_ok(self):
        primary = _mock_provider("claude/sonnet", "Primary answer.")
        fallback = _mock_provider("gemini/flash", "Fallback answer.")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        result = await provider.complete(messages=_MESSAGES)

        assert result == "Primary answer."
        fallback.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_primary_called_with_correct_args(self):
        primary = _mock_provider("claude/sonnet", "ok")
        fallback = _mock_provider("gemini/flash", "ok")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        await provider.complete(
            messages=_MESSAGES,
            max_tokens=300,
            temperature=0.3,
            system="You are a hotel assistant.",
        )

        primary.complete.assert_awaited_once_with(
            messages=_MESSAGES,
            max_tokens=300,
            temperature=0.3,
            system="You are a hotel assistant.",
        )


# ---------------------------------------------------------------------------
# AC3 — Transparent failover
# ---------------------------------------------------------------------------

class TestFallbackProviderFailover:
    @pytest.mark.asyncio
    async def test_falls_back_on_api_error(self):
        primary = _failing_provider("claude/sonnet", ConnectionError("timeout"))
        fallback = _mock_provider("gemini/flash", "Fallback response.")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        result = await provider.complete(messages=_MESSAGES)

        assert result == "Fallback response."

    @pytest.mark.asyncio
    async def test_falls_back_on_runtime_error_missing_key(self):
        primary = _failing_provider(
            "claude/sonnet", RuntimeError("ANTHROPIC_API_KEY not set")
        )
        fallback = _mock_provider("gemini/flash", "Gemini took over.")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        result = await provider.complete(messages=_MESSAGES)

        assert result == "Gemini took over."

    @pytest.mark.asyncio
    async def test_falls_back_on_any_exception_type(self):
        for exc in [ValueError("bad"), TimeoutError("slow"), Exception("generic")]:
            primary = _failing_provider("claude/sonnet", exc)
            fallback = _mock_provider("gemini/flash", "ok")
            provider = FallbackLLMProvider(primary=primary, fallback=fallback)
            result = await provider.complete(messages=_MESSAGES)
            assert result == "ok"


# ---------------------------------------------------------------------------
# AC4 — Fallback receives identical arguments
# ---------------------------------------------------------------------------

class TestFallbackProviderArgPassthrough:
    @pytest.mark.asyncio
    async def test_fallback_receives_same_args(self):
        primary = _failing_provider("claude/sonnet", RuntimeError("fail"))
        fallback = _mock_provider("gemini/flash", "ok")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        await provider.complete(
            messages=_MESSAGES,
            max_tokens=400,
            temperature=0.5,
            system="Be concise.",
        )

        fallback.complete.assert_awaited_once_with(
            messages=_MESSAGES,
            max_tokens=400,
            temperature=0.5,
            system="Be concise.",
        )


# ---------------------------------------------------------------------------
# AC5 — Both fail → fallback exception propagates
# ---------------------------------------------------------------------------

class TestFallbackProviderBothFail:
    @pytest.mark.asyncio
    async def test_raises_fallback_exception_when_both_fail(self):
        primary = _failing_provider("claude/sonnet", RuntimeError("primary down"))
        fallback = _failing_provider("gemini/flash", ConnectionError("fallback down"))

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        with pytest.raises(ConnectionError, match="fallback down"):
            await provider.complete(messages=_MESSAGES)


# ---------------------------------------------------------------------------
# AC6 — Warning log on primary failure
# ---------------------------------------------------------------------------

class TestFallbackProviderLogging:
    @pytest.mark.asyncio
    async def test_logs_warning_on_primary_failure(self, caplog):
        import logging
        primary = _failing_provider("claude/sonnet", RuntimeError("API down"))
        fallback = _mock_provider("gemini/flash", "ok")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        with caplog.at_level(logging.WARNING, logger="app.providers.fallback_provider"):
            await provider.complete(messages=_MESSAGES)

        assert any("fallback" in r.message.lower() for r in caplog.records)
        assert any("claude/sonnet" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# AC7 — Composite model_id
# ---------------------------------------------------------------------------

class TestFallbackProviderModelId:
    def test_model_id_is_composite(self):
        primary = _mock_provider("claude/claude-sonnet-4-6")
        fallback = _mock_provider("gemini/gemini-2.0-flash")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        assert provider.model_id == "claude/claude-sonnet-4-6→gemini/gemini-2.0-flash"


# ---------------------------------------------------------------------------
# AC8 — Factory wires fallback automatically
# ---------------------------------------------------------------------------

class TestFactoryFallbackWiring:
    def test_factory_returns_fallback_provider_when_env_set(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.setenv("LLM_FALLBACK_BACKEND", "gemini")
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert "claude" in provider.model_id
        assert "gemini" in provider.model_id

    def test_fallback_model_id_shows_both_providers(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.setenv("LLM_FALLBACK_BACKEND", "gemini")
        provider = get_llm_provider()
        assert "→" in provider.model_id


# ---------------------------------------------------------------------------
# AC9 — Factory without fallback env var returns plain provider
# ---------------------------------------------------------------------------

class TestFactoryNoFallback:
    def test_no_fallback_env_returns_plain_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.delenv("LLM_FALLBACK_BACKEND", raising=False)
        provider = get_llm_provider()
        assert not isinstance(provider, FallbackLLMProvider)

    def test_empty_fallback_env_returns_plain_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.setenv("LLM_FALLBACK_BACKEND", "")
        provider = get_llm_provider()
        assert not isinstance(provider, FallbackLLMProvider)


# ---------------------------------------------------------------------------
# AC10 — Same primary and fallback backend is ignored
# ---------------------------------------------------------------------------

class TestFactorySameBackend:
    def test_same_backend_does_not_wrap(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.setenv("LLM_FALLBACK_BACKEND", "claude")
        provider = get_llm_provider()
        assert not isinstance(provider, FallbackLLMProvider)

"""Tests for FallbackLLMProvider and factory auto-failover wiring.

Coverage:
- AC1: FallbackLLMProvider satisfies LLMProvider protocol
- AC2: Returns primary's response when primary succeeds
- AC3: Transparently retries with fallback when primary raises transient errors
- AC4: Passes identical call arguments to fallback
- AC5: Propagates fallback exception if both providers fail
- AC6: Logs a WARNING when primary fails (transient), ERROR when non-transient
- AC7: model_id shows primary→fallback composite identifier
- AC8: Factory always returns FallbackLLMProvider (Claude primary, Gemini fallback)
- AC9: 4xx (non-transient) errors from primary are re-raised without fallback
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider
from app.providers.fallback_provider import FallbackLLMProvider, _is_transient_error

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
            model=None,
        )

    @pytest.mark.asyncio
    async def test_model_override_reaches_primary_only(self):
        """HOS-283: the per-call model= override is a vendor-specific ID. It
        reaches the primary; the fallback runs on its own default model, since
        a Claude model ID sent to Gemini is rejected and kills the failover."""
        primary = _failing_provider("claude/sonnet", TimeoutError("boom"))
        fallback = _mock_provider("gemini/flash", "ok")

        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        result = await provider.complete(
            messages=_MESSAGES,
            model="claude-haiku-4-5-20251001",
        )

        assert result == "ok"
        assert primary.complete.await_args.kwargs["model"] == "claude-haiku-4-5-20251001"
        assert fallback.complete.await_args.kwargs["model"] is None

    @pytest.mark.asyncio
    async def test_override_does_not_break_failover_on_real_gemini(self):
        """Regression: with the real GeminiProvider as fallback, an overridden
        call must reach Gemini with a Gemini model, not the Claude ID."""
        from app.providers.gemini_provider import GeminiProvider

        primary = _failing_provider("claude/sonnet", TimeoutError("boom"))
        gemini = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
        response = MagicMock()
        response.text = "ok"
        gemini._client = MagicMock()
        gemini._client.aio.models.generate_content = AsyncMock(return_value=response)

        provider = FallbackLLMProvider(primary=primary, fallback=gemini)
        result = await provider.complete(
            messages=_MESSAGES,
            model="claude-haiku-4-5-20251001",
        )

        assert result == "ok"
        call = gemini._client.aio.models.generate_content.await_args
        assert call.kwargs["model"] == "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# AC3 — Transparent failover (transient errors only)
# ---------------------------------------------------------------------------

class TestFallbackProviderFailover:
    @pytest.mark.asyncio
    async def test_falls_back_on_network_error(self):
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
    async def test_falls_back_on_5xx_error(self):
        class _ServerError(Exception):
            status_code = 503

        primary = _failing_provider("claude/sonnet", _ServerError("overloaded"))
        fallback = _mock_provider("gemini/flash", "ok")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)
        result = await provider.complete(messages=_MESSAGES)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout_and_generic_errors(self):
        for exc in [TimeoutError("slow"), Exception("generic")]:
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
            model=None,
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
# AC8 — Factory always wires FallbackLLMProvider (Claude → Gemini)
# ---------------------------------------------------------------------------

class TestFactoryFallbackWiring:
    def test_factory_always_returns_fallback_provider(self):
        """Failover is always on — no env var needed."""
        from app.providers.claude_provider import ClaudeProvider
        from app.providers.gemini_provider import GeminiProvider
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert isinstance(provider._primary, ClaudeProvider)
        assert isinstance(provider._fallback, GeminiProvider)

    def test_model_id_shows_both_providers(self):
        provider = get_llm_provider()
        assert "claude" in provider.model_id
        assert "gemini" in provider.model_id
        assert "→" in provider.model_id


# ---------------------------------------------------------------------------
# AC9 — 4xx errors are NOT retried on fallback
# ---------------------------------------------------------------------------

class _BadRequestError(Exception):
    status_code = 400


class _AuthError(Exception):
    status_code = 401


class _UnprocessableError(Exception):
    http_status = 422


class TestFallbackProviderNonTransientErrors:
    @pytest.mark.asyncio
    async def test_4xx_error_is_reraised_not_retried(self):
        primary = _failing_provider("claude/sonnet", _BadRequestError("invalid input"))
        fallback = _mock_provider("gemini/flash", "ok")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        with pytest.raises(_BadRequestError):
            await provider.complete(messages=_MESSAGES)

        fallback.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auth_error_is_reraised_not_retried(self):
        primary = _failing_provider("claude/sonnet", _AuthError("unauthorized"))
        fallback = _mock_provider("gemini/flash", "ok")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        with pytest.raises(_AuthError):
            await provider.complete(messages=_MESSAGES)

        fallback.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_logs_error_on_non_transient_failure(self, caplog):
        import logging
        primary = _failing_provider("claude/sonnet", _BadRequestError("bad input"))
        fallback = _mock_provider("gemini/flash", "ok")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        with caplog.at_level(logging.ERROR, logger="app.providers.fallback_provider"):
            with pytest.raises(_BadRequestError):
                await provider.complete(messages=_MESSAGES)

        assert any("NOT falling back" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _is_transient_error unit tests
# ---------------------------------------------------------------------------

class TestIsTransientError:
    def test_4xx_status_code_not_transient(self):
        assert not _is_transient_error(_BadRequestError())
        assert not _is_transient_error(_AuthError())

    def test_422_via_http_status_attr_not_transient(self):
        assert not _is_transient_error(_UnprocessableError())

    def test_5xx_is_transient(self):
        class _ServerError(Exception):
            status_code = 503
        assert _is_transient_error(_ServerError())

    def test_connection_error_is_transient(self):
        assert _is_transient_error(ConnectionError("refused"))

    def test_timeout_error_is_transient(self):
        assert _is_transient_error(TimeoutError("slow"))

    def test_generic_exception_no_status_is_transient(self):
        assert _is_transient_error(RuntimeError("ANTHROPIC_API_KEY not set"))
        assert _is_transient_error(Exception("generic"))


# ---------------------------------------------------------------------------
# HOS-282 — fallback health-check canary (never raises)
# ---------------------------------------------------------------------------

class TestFallbackHealthCheck:
    @pytest.mark.asyncio
    async def test_returns_true_when_fallback_responds(self):
        primary = _mock_provider("claude/sonnet", "ignored")
        fallback = _mock_provider("gemini/flash", "pong")
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        assert await provider.check_fallback_health() is True
        fallback.complete.assert_awaited_once()
        primary.complete.assert_not_awaited()  # health check never touches primary

    @pytest.mark.asyncio
    async def test_returns_false_and_warns_when_fallback_raises(self, caplog):
        import logging

        primary = _mock_provider("claude/sonnet")
        fallback = _failing_provider(
            "gemini/flash", RuntimeError("GEMINI_API_KEY not set")
        )
        provider = FallbackLLMProvider(primary=primary, fallback=fallback)

        with caplog.at_level(logging.WARNING):
            result = await provider.check_fallback_health()

        assert result is False
        assert any("health-check FAILED" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_returns_false_on_empty_response(self):
        provider = FallbackLLMProvider(
            primary=_mock_provider("claude/sonnet"),
            fallback=_mock_provider("gemini/flash", "   "),
        )
        assert await provider.check_fallback_health() is False

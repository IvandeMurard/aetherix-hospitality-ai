"""Tests for ClaudeProvider and get_llm_provider() factory (HOS-119 — LLM-1).

Coverage:
- AC1: LLMProvider protocol definition
- AC2: ClaudeProvider happy path (mocked AsyncAnthropic)
- AC3: Lazy key validation — no raise at instantiation, raises at complete()
- AC4: Factory always returns FallbackLLMProvider with ClaudeProvider as primary
- Additional: system prompt routing, model_id property
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import LLMProvider
from app.providers.claude_provider import ClaudeProvider
from app.providers.factory import get_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(text: str) -> MagicMock:
    """Build a minimal Anthropic Messages API response mock."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ---------------------------------------------------------------------------
# AC1 — Protocol definition
# ---------------------------------------------------------------------------

class TestLLMProviderProtocol:
    def test_claude_provider_satisfies_protocol(self):
        """ClaudeProvider must be recognised as an LLMProvider at runtime."""
        provider = ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-6")
        assert isinstance(provider, LLMProvider)

    def test_protocol_requires_complete_and_model_id(self):
        """LLMProvider protocol surface: complete() + model_id."""
        # A minimal no-op implementation satisfies the protocol
        class _MinimalProvider:
            async def complete(self, messages, max_tokens=500, temperature=0.3, system=None):
                return "ok"

            @property
            def model_id(self) -> str:
                return "test/model"

        assert isinstance(_MinimalProvider(), LLMProvider)


# ---------------------------------------------------------------------------
# AC2 — ClaudeProvider happy path
# ---------------------------------------------------------------------------

class TestClaudeProviderComplete:
    @pytest.mark.asyncio
    async def test_complete_returns_text(self):
        """complete() calls AsyncAnthropic.messages.create and returns text."""
        mock_response = _make_mock_response("Dinner tonight looks busy.")

        with patch("app.providers.claude_provider.AsyncAnthropic") as MockAnthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockAnthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-6")
            result = await provider.complete(
                messages=[{"role": "user", "content": "Why is dinner busy?"}],
                max_tokens=300,
                temperature=0.3,
            )

        assert result == "Dinner tonight looks busy."
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_passes_correct_kwargs(self):
        """complete() passes model, max_tokens, temperature, messages to the SDK."""
        mock_response = _make_mock_response("ok")

        with patch("app.providers.claude_provider.AsyncAnthropic") as MockAnthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockAnthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-6")
            await provider.complete(
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10,
                temperature=0.0,
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_tokens"] == 10
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["messages"] == [{"role": "user", "content": "ping"}]
        assert "system" not in call_kwargs  # not passed when None

    @pytest.mark.asyncio
    async def test_complete_routes_system_prompt_to_top_level_field(self):
        """system= kwarg must be passed as Anthropic's top-level system field."""
        mock_response = _make_mock_response("ok")

        with patch("app.providers.claude_provider.AsyncAnthropic") as MockAnthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockAnthropic.return_value = mock_client

            provider = ClaudeProvider(api_key="sk-test")
            await provider.complete(
                messages=[{"role": "user", "content": "hello"}],
                system="You are Aetherix.",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "You are Aetherix."
        # system must NOT appear as a message role
        for msg in call_kwargs["messages"]:
            assert msg.get("role") != "system"


# ---------------------------------------------------------------------------
# AC3 — Lazy key validation
# ---------------------------------------------------------------------------

class TestClaudeProviderLazyKeyValidation:
    def test_instantiation_does_not_raise_without_key(self, monkeypatch):
        """No exception at instantiation when ANTHROPIC_API_KEY is absent."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Should not raise
        provider = ClaudeProvider(api_key="")
        assert provider is not None

    @pytest.mark.asyncio
    async def test_complete_raises_runtime_error_without_key(self, monkeypatch):
        """complete() raises RuntimeError when no key is available."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = ClaudeProvider(api_key="")
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY not set"):
            await provider.complete(messages=[{"role": "user", "content": "ping"}])

    @pytest.mark.asyncio
    async def test_complete_uses_env_key_set_after_instantiation(self, monkeypatch):
        """complete() picks up ANTHROPIC_API_KEY if set after instantiation."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = ClaudeProvider(api_key="")

        # Set the key after instantiation
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-late-set")
        mock_response = _make_mock_response("ok")

        with patch("app.providers.claude_provider.AsyncAnthropic") as MockAnthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            MockAnthropic.return_value = mock_client

            result = await provider.complete(
                messages=[{"role": "user", "content": "ping"}]
            )

        assert result == "ok"


# ---------------------------------------------------------------------------
# AC4 — Factory always returns FallbackLLMProvider with Claude as primary
# ---------------------------------------------------------------------------

class TestGetLlmProviderFactory:
    def test_factory_returns_fallback_provider(self):
        """get_llm_provider() always returns a FallbackLLMProvider."""
        from app.providers.fallback_provider import FallbackLLMProvider
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert isinstance(provider, LLMProvider)

    def test_primary_is_claude(self):
        """Primary provider inside FallbackLLMProvider is ClaudeProvider."""
        from app.providers.fallback_provider import FallbackLLMProvider
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert isinstance(provider._primary, ClaudeProvider)

    def test_factory_uses_llm_model_env_var(self, monkeypatch):
        """LLM_MODEL env var is forwarded to the Claude primary."""
        from app.providers.fallback_provider import FallbackLLMProvider
        monkeypatch.setenv("LLM_MODEL", "claude-opus-4-6")
        provider = get_llm_provider()
        assert isinstance(provider, FallbackLLMProvider)
        assert provider._primary.model_id == "claude/claude-opus-4-6"


# ---------------------------------------------------------------------------
# model_id property
# ---------------------------------------------------------------------------

class TestClaudeProviderModelId:
    def test_model_id_format(self):
        provider = ClaudeProvider(api_key="sk-x", model="claude-sonnet-4-6")
        assert provider.model_id == "claude/claude-sonnet-4-6"

    def test_model_id_reflects_custom_model(self):
        provider = ClaudeProvider(api_key="sk-x", model="claude-haiku-4-5-20251001")
        assert provider.model_id == "claude/claude-haiku-4-5-20251001"

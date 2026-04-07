"""Tests for ClaudeProvider and get_llm_provider() factory (HOS-119 — LLM-1).

Coverage:
- AC1: LLMProvider protocol definition
- AC2: ClaudeProvider happy path (mocked AsyncAnthropic)
- AC3: Lazy key validation — no raise at instantiation, raises at complete()
- AC4: Factory returns LLMProvider instance for LLM_BACKEND=claude
- AC5: Factory raises NotImplementedError for unsupported backend
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
# AC4 — Factory returns correct type
# ---------------------------------------------------------------------------

class TestGetLlmProviderFactory:
    def test_default_backend_returns_claude_provider(self, monkeypatch):
        """Default (LLM_BACKEND unset) returns a ClaudeProvider."""
        monkeypatch.delenv("LLM_BACKEND", raising=False)
        provider = get_llm_provider()
        assert isinstance(provider, LLMProvider)
        assert isinstance(provider, ClaudeProvider)

    def test_explicit_claude_backend(self, monkeypatch):
        """LLM_BACKEND=claude returns ClaudeProvider."""
        monkeypatch.setenv("LLM_BACKEND", "claude")
        provider = get_llm_provider()
        assert isinstance(provider, ClaudeProvider)

    def test_factory_uses_llm_model_env_var(self, monkeypatch):
        """LLM_MODEL env var is forwarded to ClaudeProvider."""
        monkeypatch.setenv("LLM_BACKEND", "claude")
        monkeypatch.setenv("LLM_MODEL", "claude-opus-4-6")
        provider = get_llm_provider()
        assert isinstance(provider, ClaudeProvider)
        assert provider.model_id == "claude/claude-opus-4-6"


# ---------------------------------------------------------------------------
# AC5 — Unknown backend raises NotImplementedError
# ---------------------------------------------------------------------------

class TestGetLlmProviderUnknownBackend:
    def test_unknown_backend_raises(self, monkeypatch):
        """NotImplementedError raised with the backend name in the message."""
        monkeypatch.setenv("LLM_BACKEND", "gpt-9000")
        with pytest.raises(NotImplementedError, match="gpt-9000"):
            get_llm_provider()

    def test_empty_backend_raises(self, monkeypatch):
        """Empty string backend raises NotImplementedError."""
        monkeypatch.setenv("LLM_BACKEND", "")
        with pytest.raises(NotImplementedError):
            get_llm_provider()


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

"""Tests for GeminiProvider and factory gemini branch.

Coverage:
- AC1: GeminiProvider satisfies LLMProvider protocol
- AC2: complete() calls aio.models.generate_content and returns text
- AC3: system param routes to system_instruction in GenerateContentConfig
- AC4: max_tokens → max_output_tokens, temperature passed correctly
- AC5: Lazy key validation — no raise at init, RuntimeError at complete()
- AC6: factory returns GeminiProvider for LLM_BACKEND=gemini
- AC7: message role "assistant" maps to Gemini "model" role
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import LLMProvider
from app.providers.gemini_provider import GeminiProvider, _to_gemini_contents
from app.providers.factory import get_llm_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_client(text: str = "Gemini response.") -> MagicMock:
    """Return a mock google.genai.Client with aio.models.generate_content mocked."""
    response = MagicMock()
    response.text = text

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=response)

    mock_client = MagicMock()
    mock_client.aio.models = mock_aio_models
    return mock_client


# ---------------------------------------------------------------------------
# AC1 — Protocol
# ---------------------------------------------------------------------------

class TestGeminiProviderProtocol:
    def test_satisfies_llm_provider_protocol(self):
        provider = GeminiProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_model_id_format(self):
        provider = GeminiProvider(api_key="x", model="gemini-2.0-flash")
        assert provider.model_id == "gemini/gemini-2.0-flash"


# ---------------------------------------------------------------------------
# AC2 — Happy path
# ---------------------------------------------------------------------------

class TestGeminiProviderComplete:
    @pytest.mark.asyncio
    async def test_complete_returns_text(self):
        mock_client = _make_mock_client("Busy Saturday due to event nearby.")

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(api_key="sk-test")
            result = await provider.complete(
                messages=[{"role": "user", "content": "Explain forecast"}],
                max_tokens=300,
                temperature=0.3,
            )

        assert result == "Busy Saturday due to event nearby."
        mock_client.aio.models.generate_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_passes_correct_model(self):
        mock_client = _make_mock_client("ok")

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(api_key="sk-test", model="gemini-2.0-flash")
            await provider.complete(messages=[{"role": "user", "content": "ping"}])

        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# AC3 — system param → system_instruction
# ---------------------------------------------------------------------------

class TestGeminiProviderSystemPrompt:
    @pytest.mark.asyncio
    async def test_system_routes_to_config_system_instruction(self):
        mock_client = _make_mock_client("ok")

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(api_key="sk-test")
            await provider.complete(
                messages=[{"role": "user", "content": "hello"}],
                system="You are a hotel operations assistant.",
            )

        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.system_instruction == "You are a hotel operations assistant."

    @pytest.mark.asyncio
    async def test_no_system_omits_system_instruction(self):
        mock_client = _make_mock_client("ok")

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(api_key="sk-test")
            await provider.complete(
                messages=[{"role": "user", "content": "hello"}],
                system=None,
            )

        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.system_instruction is None


# ---------------------------------------------------------------------------
# AC4 — max_tokens and temperature mapping
# ---------------------------------------------------------------------------

class TestGeminiProviderConfig:
    @pytest.mark.asyncio
    async def test_max_tokens_maps_to_max_output_tokens(self):
        mock_client = _make_mock_client("ok")

        with patch("google.genai.Client", return_value=mock_client):
            provider = GeminiProvider(api_key="sk-test")
            await provider.complete(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=300,
                temperature=0.3,
            )

        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        config = call_kwargs["config"]
        assert config.max_output_tokens == 300
        assert config.temperature == 0.3


# ---------------------------------------------------------------------------
# AC5 — Lazy key validation
# ---------------------------------------------------------------------------

class TestGeminiProviderLazyKeyValidation:
    def test_instantiation_does_not_raise_without_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = GeminiProvider(api_key="")
        assert provider is not None

    @pytest.mark.asyncio
    async def test_complete_raises_runtime_error_without_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = GeminiProvider(api_key="")

        with pytest.raises(RuntimeError, match="GEMINI_API_KEY not set"):
            await provider.complete(messages=[{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_complete_uses_env_key_set_after_instantiation(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = GeminiProvider(api_key="")

        monkeypatch.setenv("GEMINI_API_KEY", "sk-late-set")
        mock_client = _make_mock_client("late key response")

        with patch("google.genai.Client", return_value=mock_client):
            result = await provider.complete(
                messages=[{"role": "user", "content": "ping"}]
            )

        assert result == "late key response"


# ---------------------------------------------------------------------------
# AC6 — Factory
# ---------------------------------------------------------------------------

class TestGetLlmProviderGemini:
    def test_gemini_backend_returns_gemini_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "gemini")
        provider = get_llm_provider()
        assert isinstance(provider, GeminiProvider)
        assert isinstance(provider, LLMProvider)

    def test_gemini_uses_llm_model_env_var(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "gemini")
        monkeypatch.setenv("LLM_MODEL", "gemini-2.0-flash")
        provider = get_llm_provider()
        assert provider.model_id == "gemini/gemini-2.0-flash"

    def test_error_message_lists_gemini(self, monkeypatch):
        monkeypatch.setenv("LLM_BACKEND", "unknown-future-model")
        with pytest.raises(NotImplementedError, match="gemini"):
            get_llm_provider()


# ---------------------------------------------------------------------------
# AC7 — Message role conversion
# ---------------------------------------------------------------------------

class TestToGeminiContents:
    def test_user_role_preserved(self):
        result = _to_gemini_contents([{"role": "user", "content": "hello"}])
        assert result == [{"role": "user", "parts": [{"text": "hello"}]}]

    def test_assistant_role_maps_to_model(self):
        result = _to_gemini_contents([{"role": "assistant", "content": "ok"}])
        assert result == [{"role": "model", "parts": [{"text": "ok"}]}]

    def test_multi_turn_conversation(self):
        messages = [
            {"role": "user", "content": "Why surge?"},
            {"role": "assistant", "content": "Event nearby."},
            {"role": "user", "content": "Which event?"},
        ]
        result = _to_gemini_contents(messages)
        assert [r["role"] for r in result] == ["user", "model", "user"]

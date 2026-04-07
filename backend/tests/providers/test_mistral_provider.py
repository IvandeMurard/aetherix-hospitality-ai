"""Tests for MistralEmbeddingProvider and get_embedding_provider() factory (HOS-121 — LLM-3).

Coverage:
- AC1: EmbeddingProvider protocol definition (embed + dimensions)
- AC2: MistralEmbeddingProvider.embed() calls API and returns list[float]
- AC3: Zero-vector fallback when MISTRAL_API_KEY is absent
- AC4: Factory returns EmbeddingProvider with dimensions == 1024 for EMBEDDING_BACKEND=mistral
- Additional: model passed to SDK, dimensions property
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import EmbeddingProvider
from app.providers.mistral_provider import MistralEmbeddingProvider
from app.providers.factory import get_embedding_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 1024


def _make_mock_response(embedding: list[float]) -> MagicMock:
    """Build a minimal Mistral EmbeddingResponse mock."""
    data_item = MagicMock()
    data_item.embedding = embedding
    response = MagicMock()
    response.data = [data_item]
    return response


def _make_mock_mistral(embedding: list[float]) -> MagicMock:
    mock_client = MagicMock()
    mock_client.embeddings.create_async = AsyncMock(
        return_value=_make_mock_response(embedding)
    )
    return mock_client


# ---------------------------------------------------------------------------
# AC1 — Protocol definition
# ---------------------------------------------------------------------------

class TestEmbeddingProviderProtocol:
    def test_mistral_provider_satisfies_protocol(self):
        provider = MistralEmbeddingProvider(api_key="sk-test")
        assert isinstance(provider, EmbeddingProvider)

    def test_protocol_requires_embed_and_dimensions(self):
        class _MinimalProvider:
            async def embed(self, text: str) -> list[float]:
                return [0.0]

            @property
            def dimensions(self) -> int:
                return 1024

        assert isinstance(_MinimalProvider(), EmbeddingProvider)


# ---------------------------------------------------------------------------
# AC2 — Happy path
# ---------------------------------------------------------------------------

class TestMistralProviderEmbed:
    @pytest.mark.asyncio
    async def test_embed_returns_vector(self):
        expected = [0.1] * _DIM

        with patch("mistralai.client.sdk.Mistral") as MockMistral:
            mock_client = _make_mock_mistral(expected)
            MockMistral.return_value = mock_client

            provider = MistralEmbeddingProvider(api_key="sk-test")
            result = await provider.embed("dinner service forecast")

        assert result == expected
        mock_client.embeddings.create_async.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_embed_passes_correct_model_and_inputs(self):
        expected = [0.2] * _DIM

        with patch("mistralai.client.sdk.Mistral") as MockMistral:
            mock_client = _make_mock_mistral(expected)
            MockMistral.return_value = mock_client

            provider = MistralEmbeddingProvider(api_key="sk-test", model="mistral-embed")
            await provider.embed("hello world")

        call_kwargs = mock_client.embeddings.create_async.call_args.kwargs
        assert call_kwargs["model"] == "mistral-embed"
        assert call_kwargs["inputs"] == ["hello world"]


# ---------------------------------------------------------------------------
# AC3 — Zero-vector fallback
# ---------------------------------------------------------------------------

class TestMistralProviderZeroVectorFallback:
    def test_instantiation_does_not_raise_without_key(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        provider = MistralEmbeddingProvider(api_key="")
        assert provider is not None

    @pytest.mark.asyncio
    async def test_embed_returns_zero_vector_without_key(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        provider = MistralEmbeddingProvider(api_key="")
        result = await provider.embed("some text")
        assert result == [0.0] * _DIM
        assert len(result) == _DIM

    @pytest.mark.asyncio
    async def test_embed_uses_env_key_set_after_instantiation(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        provider = MistralEmbeddingProvider(api_key="")

        # Key set after instantiation
        monkeypatch.setenv("MISTRAL_API_KEY", "sk-late-set")
        expected = [0.5] * _DIM

        with patch("mistralai.client.sdk.Mistral") as MockMistral:
            mock_client = _make_mock_mistral(expected)
            MockMistral.return_value = mock_client

            result = await provider.embed("late key test")

        assert result == expected


# ---------------------------------------------------------------------------
# AC4 — Factory
# ---------------------------------------------------------------------------

class TestGetEmbeddingProviderFactory:
    def test_factory_returns_mistral_provider(self):
        provider = get_embedding_provider()
        assert isinstance(provider, EmbeddingProvider)
        assert isinstance(provider, MistralEmbeddingProvider)

    def test_factory_dimensions_are_1024(self):
        provider = get_embedding_provider()
        assert provider.dimensions == 1024

    def test_factory_uses_embedding_model_env_var(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL", "mistral-embed")
        provider = get_embedding_provider()
        assert isinstance(provider, MistralEmbeddingProvider)


# ---------------------------------------------------------------------------
# dimensions property
# ---------------------------------------------------------------------------

class TestMistralProviderDimensions:
    def test_dimensions_is_1024(self):
        provider = MistralEmbeddingProvider(api_key="sk-x")
        assert provider.dimensions == 1024

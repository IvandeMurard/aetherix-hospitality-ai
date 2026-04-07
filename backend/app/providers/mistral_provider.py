"""MistralEmbeddingProvider — EmbeddingProvider implementation backed by Mistral AI.

Wraps the Mistral SDK's async embedding endpoint behind the ``EmbeddingProvider``
protocol so that ``rag_service`` and ``memory_service`` never import from
``mistralai`` directly.

Zero-vector fallback:
    When ``MISTRAL_API_KEY`` is absent the provider returns a vector of zeros
    instead of raising.  This preserves the existing dev/test behaviour where
    embedding lookups degrade gracefully to unordered pgvector results rather
    than crashing.
"""
from __future__ import annotations

import os

from app.providers.base import EmbeddingProvider  # noqa: F401 — satisfies Protocol

# Mistral's ``mistral-embed`` model produces 1024-dimensional embeddings.
_MISTRAL_DIM = 1024


class MistralEmbeddingProvider:
    """Wraps the Mistral SDK's ``embeddings.create_async`` behind ``EmbeddingProvider``.

    Instantiation never raises even when ``MISTRAL_API_KEY`` is absent —
    the provider returns a zero-vector so the app can start without live creds.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "mistral-embed",
    ) -> None:
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")
        self._model = model
        self._client = None
        if self._api_key:
            from mistralai.client.sdk import Mistral

            self._client = Mistral(api_key=self._api_key)

    # ------------------------------------------------------------------
    # EmbeddingProvider protocol
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Return a 1024-dim embedding vector for *text*.

        Falls back to ``[0.0] * 1024`` when no API key is configured, mirroring
        the zero-vector stub used in ``rag_service.py`` before this abstraction.

        Args:
            text: The text to embed.

        Returns:
            A list of 1024 floats representing the embedding.
        """
        if self._client is None:
            # One last attempt — key may have been set after instantiation.
            key = os.getenv("MISTRAL_API_KEY", "")
            if not key:
                return [0.0] * _MISTRAL_DIM
            self._api_key = key
            from mistralai.client.sdk import Mistral

            self._client = Mistral(api_key=key)

        response = await self._client.embeddings.create_async(
            model=self._model,
            inputs=[text],
        )
        return response.data[0].embedding

    @property
    def dimensions(self) -> int:
        return _MISTRAL_DIM

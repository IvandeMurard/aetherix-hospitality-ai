"""Protocol definitions for LLM and Embedding providers.

Both protocols use ``runtime_checkable`` so that ``isinstance()`` guards work
at runtime (e.g. in factory assertions and unit tests).
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for LLM text-completion providers.

    Concrete implementations: ``ClaudeProvider`` (primary).
    Future: GeminiProvider, OpenAIProvider.
    """

    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.3,
        system: str | None = None,
    ) -> str:
        """Return the model's plain-text response.

        Args:
            messages:    Conversation turns — list of ``{"role": "user"|"assistant", "content": str}``.
            max_tokens:  Hard cap on output tokens.
            temperature: Sampling temperature (0 = deterministic).
            system:      Optional system-level instruction.  Providers that
                         support a dedicated system field (e.g. Anthropic) use
                         it directly; others prepend it as a system message.
        """
        ...

    @property
    def model_id(self) -> str:
        """Human-readable model identifier for logging (e.g. ``"claude/claude-sonnet-4-6"``)."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal interface for text embedding providers.

    Concrete implementations: ``MistralEmbeddingProvider`` (primary).
    Future: OpenAIEmbeddingProvider.
    """

    async def embed(self, text: str) -> list[float]:
        """Return a float vector for *text*.

        Returns a zero-vector of length ``self.dimensions`` when the provider
        is not configured (no API key), enabling CI/test runs without credentials.
        """
        ...

    @property
    def dimensions(self) -> int:
        """Embedding vector length (e.g. 1024 for Mistral, 1536 for OpenAI)."""
        ...

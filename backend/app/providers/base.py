"""Protocol definitions for LLM and Embedding providers.

Both protocols use ``runtime_checkable`` so that ``isinstance()`` guards work
at runtime (e.g. in factory assertions and unit tests).
"""
from __future__ import annotations

from typing import Literal, Protocol, get_args, runtime_checkable

# Vendor-neutral capability tier (Décision #35). Callers ask for a tier, never
# for a model ID: each provider maps the tier to its own model, so a tier
# survives a failover and a provider swap. A vendor model ID in a service is a
# leak — it broke the Claude→Gemini fallback before this contract (HOS-283).
ModelTier = Literal["fast", "reasoning"]
MODEL_TIERS: tuple[str, ...] = get_args(ModelTier)


def resolve_tier_model(tier: str, *, reasoning: str, fast: str) -> str:
    """Map a capability tier to a provider's concrete model ID.

    Raises ``ValueError`` on an unknown tier rather than silently routing to a
    default: a misrouted call is invisible, a raised one is not.
    """
    if tier == "reasoning":
        return reasoning
    if tier == "fast":
        return fast
    raise ValueError(f"Unknown model tier {tier!r} — expected one of {MODEL_TIERS}")


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
        tier: ModelTier = "reasoning",
    ) -> str:
        """Return the model's plain-text response.

        Args:
            messages:    Conversation turns — list of ``{"role": "user"|"assistant", "content": str}``.
            max_tokens:  Hard cap on output tokens.
            temperature: Sampling temperature (0 = deterministic).
            system:      Optional system-level instruction.  Providers that
                         support a dedicated system field (e.g. Anthropic) use
                         it directly; others prepend it as a system message.
            tier:        Capability tier (Décision #35). ``"reasoning"`` (default)
                         is the provider's main model; ``"fast"`` its cheap,
                         low-latency one (classification, extraction). Each
                         provider maps the tier to its own model ID.
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

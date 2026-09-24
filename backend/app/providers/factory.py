"""Provider factories — construct LLM and Embedding providers from env vars.

Environment variables
---------------------
ANTHROPIC_API_KEY  : Claude API key (primary LLM)
GEMINI_API_KEY     : Gemini API key (automatic fallback — no config needed)
LLM_MODEL               : Claude "reasoning" tier (default: "claude-sonnet-4-6")
LLM_FAST_MODEL          : Claude "fast" tier (default: "claude-haiku-4-5-20251001")
LLM_FALLBACK_MODEL      : Gemini "reasoning" tier (default: "gemini-2.0-flash")
LLM_FALLBACK_FAST_MODEL : Gemini "fast" tier (default: "gemini-2.0-flash")

Callers never name a model: they pass ``tier="fast"|"reasoning"`` and each
provider maps it (Décision #35). Swapping a model is an env change here.

MISTRAL_API_KEY    : Mistral API key (embeddings)
EMBEDDING_MODEL    : Mistral model override (default: "mistral-embed")

Failover behaviour
------------------
get_llm_provider() always returns a FallbackLLMProvider wrapping Claude
(primary) and Gemini (fallback). If Claude fails for any reason — API error,
rate limit, timeout, missing key — the call is transparently retried on
Gemini. No env var or human action required.
"""
from __future__ import annotations

import os
from functools import lru_cache

from app.providers.base import EmbeddingProvider, LLMProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Return a FallbackLLMProvider: Claude primary, Gemini automatic fallback.

    Failover is always active. If Claude fails for any reason the call is
    retried on Gemini transparently — no configuration needed.
    """
    from app.providers.claude_provider import ClaudeProvider
    from app.providers.fallback_provider import FallbackLLMProvider
    from app.providers.gemini_provider import GeminiProvider

    return FallbackLLMProvider(
        primary=ClaudeProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
            fast_model=os.getenv("LLM_FAST_MODEL", "claude-haiku-4-5-20251001"),
        ),
        fallback=GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("LLM_FALLBACK_MODEL", "gemini-2.0-flash"),
            fast_model=os.getenv("LLM_FALLBACK_FAST_MODEL", "gemini-2.0-flash"),
        ),
    )


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """Return the Mistral embedding provider."""
    from app.providers.mistral_provider import MistralEmbeddingProvider

    return MistralEmbeddingProvider(
        api_key=os.getenv("MISTRAL_API_KEY", ""),
        model=os.getenv("EMBEDDING_MODEL", "mistral-embed"),
    )

"""Provider factories — construct LLM and Embedding providers from env vars.

Environment variables
---------------------
ANTHROPIC_API_KEY  : Claude API key (primary LLM)
GEMINI_API_KEY     : Gemini API key (automatic fallback — no config needed)
LLM_MODEL          : Claude model override (default: "claude-sonnet-4-6")
LLM_FALLBACK_MODEL : Gemini model override (default: "gemini-2.0-flash")

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

from app.providers.base import EmbeddingProvider, LLMProvider


def get_llm_provider() -> LLMProvider:
    """Return a FallbackLLMProvider: Claude primary, Gemini automatic fallback.

    Failover is always active. If Claude fails for any reason the call is
    retried on Gemini transparently — no configuration needed.
    """
    from app.providers.claude_provider import ClaudeProvider
    from app.providers.gemini_provider import GeminiProvider
    from app.providers.fallback_provider import FallbackLLMProvider

    return FallbackLLMProvider(
        primary=ClaudeProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
        ),
        fallback=GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("LLM_FALLBACK_MODEL", "gemini-2.0-flash"),
        ),
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the Mistral embedding provider."""
    from app.providers.mistral_provider import MistralEmbeddingProvider

    return MistralEmbeddingProvider(
        api_key=os.getenv("MISTRAL_API_KEY", ""),
        model=os.getenv("EMBEDDING_MODEL", "mistral-embed"),
    )

"""Provider factories — construct LLM and Embedding providers from env vars.

Environment variables
---------------------
LLM_BACKEND          : "claude" (default)  |  "gemini"
LLM_FALLBACK_BACKEND : optional — "gemini" | "claude"
                       When set, enables automatic failover: if the primary
                       LLM fails for any reason (API error, rate limit,
                       timeout, missing key), the call is transparently
                       retried on the fallback provider.
                       Example: LLM_BACKEND=claude + LLM_FALLBACK_BACKEND=gemini
LLM_MODEL            : model name for the primary provider
                       claude default: "claude-sonnet-4-6"
                       gemini default: "gemini-2.0-flash"
LLM_FALLBACK_MODEL   : model name for the fallback provider (same defaults)

EMBEDDING_BACKEND    : "mistral" (default)
EMBEDDING_MODEL      : model name passed to the provider (default: "mistral-embed")

Adding a new provider requires:
  1. A new file in ``app/providers/`` (e.g. ``openai_provider.py``)
  2. A new branch in ``_build_llm_provider()`` below
  3. Zero changes to ``app/services/``
"""
from __future__ import annotations

import os

from app.providers.base import EmbeddingProvider, LLMProvider


def _build_llm_provider(backend: str, model_env: str = "LLM_MODEL") -> LLMProvider:
    """Construct a concrete LLMProvider for *backend*.

    Args:
        backend:   Backend name ("claude" or "gemini").
        model_env: Name of the env var that holds the model name.
    """
    if backend == "claude":
        from app.providers.claude_provider import ClaudeProvider

        return ClaudeProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv(model_env, "claude-sonnet-4-6"),
        )

    if backend == "gemini":
        from app.providers.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv(model_env, "gemini-2.0-flash"),
        )

    raise NotImplementedError(
        f"LLM backend '{backend}' is not implemented. "
        "Supported values: 'claude', 'gemini'. "
        "Add a new provider file and branch in app/providers/factory.py."
    )


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider, wrapped in automatic failover if configured.

    When ``LLM_FALLBACK_BACKEND`` is set, returns a ``FallbackLLMProvider``
    that transparently retries on the fallback whenever the primary fails —
    no human intervention required.

    Raises:
        NotImplementedError: When a backend name is unsupported.
    """
    primary_backend = os.getenv("LLM_BACKEND", "claude").lower()
    primary = _build_llm_provider(primary_backend, model_env="LLM_MODEL")

    fallback_backend = os.getenv("LLM_FALLBACK_BACKEND", "").lower()
    if fallback_backend and fallback_backend != primary_backend:
        from app.providers.fallback_provider import FallbackLLMProvider

        fallback = _build_llm_provider(fallback_backend, model_env="LLM_FALLBACK_MODEL")
        return FallbackLLMProvider(primary=primary, fallback=fallback)

    return primary


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured Embedding provider.

    Raises:
        NotImplementedError: When ``EMBEDDING_BACKEND`` names an unsupported backend.
    """
    backend = os.getenv("EMBEDDING_BACKEND", "mistral").lower()

    if backend == "mistral":
        from app.providers.mistral_provider import MistralEmbeddingProvider

        return MistralEmbeddingProvider(
            api_key=os.getenv("MISTRAL_API_KEY", ""),
            model=os.getenv("EMBEDDING_MODEL", "mistral-embed"),
        )

    raise NotImplementedError(
        f"Embedding backend '{backend}' is not implemented. "
        "Supported values: 'mistral'. "
        "Add a new provider file and branch in app/providers/factory.py."
    )

"""Provider factories — construct LLM and Embedding providers from env vars.

Environment variables
---------------------
LLM_BACKEND       : "claude" (default)  |  "gemini"  |  future: "openai"
LLM_MODEL         : model name passed to the provider
                    claude default: "claude-sonnet-4-6"
                    gemini default: "gemini-2.0-flash"
EMBEDDING_BACKEND : "mistral" (default) |  future: "openai"
EMBEDDING_MODEL   : model name passed to the provider (default: "mistral-embed")

Adding a new provider requires:
  1. A new file in ``app/providers/`` (e.g. ``openai_provider.py``)
  2. A new ``elif`` branch below
  3. Zero changes to ``app/services/``
"""
from __future__ import annotations

import os

from app.providers.base import EmbeddingProvider, LLMProvider


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider.

    Raises:
        NotImplementedError: When ``LLM_BACKEND`` names an unsupported backend.
    """
    backend = os.getenv("LLM_BACKEND", "claude").lower()

    if backend == "claude":
        from app.providers.claude_provider import ClaudeProvider

        return ClaudeProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
        )

    if backend == "gemini":
        from app.providers.gemini_provider import GeminiProvider

        return GeminiProvider(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "gemini-2.0-flash"),
        )

    raise NotImplementedError(
        f"LLM backend '{backend}' is not implemented. "
        "Supported values: 'claude', 'gemini'. "
        "Add a new provider file and branch in app/providers/factory.py."
    )


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

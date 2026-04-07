"""LLM and Embedding provider abstractions for Aetherix.

This package defines the `LLMProvider` and `EmbeddingProvider` protocols so
that business services (reasoning, explainability, RAG, memory) depend on the
interface rather than a specific vendor SDK.

Usage::

    from app.providers.factory import get_llm_provider, get_embedding_provider

    llm = get_llm_provider()          # driven by LLM_BACKEND env var
    embedding = get_embedding_provider()  # driven by EMBEDDING_BACKEND env var

See: docs/bmad/_bmad-output/implementation-artifacts/0-llm-provider-abstraction.md
"""

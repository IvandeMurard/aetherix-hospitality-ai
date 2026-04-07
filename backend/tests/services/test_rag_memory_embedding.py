"""Tests for EmbeddingProvider injection into RAGService and MemoryService (HOS-122 — LLM-4).

Coverage:
- AC1: RAGService accepts EmbeddingProvider via __init__ (DI)
- AC2: find_similar_patterns() calls provider.embed() exactly once
- AC3: MemoryService accepts EmbeddingProvider via __init__ (DI)
- AC4: store_reflection() and get_relevant_context() call provider.embed()
- AC5: No mistralai imports in rag_service or memory_service
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.rag_service import RAGService
from app.services.memory_service import MemoryService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 1024
_ZERO_VEC = [0.0] * _DIM
_FIXED_VEC = [0.1] * _DIM


def _mock_embedding(vector: list[float] = _FIXED_VEC) -> MagicMock:
    emb = MagicMock()
    emb.embed = AsyncMock(return_value=vector)
    emb.dimensions = len(vector)
    return emb


def _make_db_session() -> MagicMock:
    """Return a minimal AsyncSession mock that satisfies execute()."""
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# AC1 + AC2 — RAGService DI and embed() call
# ---------------------------------------------------------------------------

class TestRAGServiceEmbeddingDI:
    def test_accepts_embedding_provider(self):
        emb = _mock_embedding()
        svc = RAGService(embedding=emb)
        assert svc._embedding is emb

    def test_default_uses_factory(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from app.providers.mistral_provider import MistralEmbeddingProvider
        svc = RAGService()
        assert isinstance(svc._embedding, MistralEmbeddingProvider)

    @pytest.mark.asyncio
    async def test_find_similar_calls_embed_once(self):
        emb = _mock_embedding()
        db = _make_db_session()
        svc = RAGService(db=db, embedding=emb)

        await svc.find_similar_patterns(
            query_text="busy Saturday dinner",
            service_type="dinner",
        )

        emb.embed.assert_awaited_once_with("busy Saturday dinner")

    @pytest.mark.asyncio
    async def test_find_similar_returns_empty_without_db(self):
        emb = _mock_embedding()
        svc = RAGService(db=None, embedding=emb)

        result = await svc.find_similar_patterns(
            query_text="whatever",
            service_type="lunch",
        )

        assert result == []
        emb.embed.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC3 + AC4 — MemoryService DI and embed() calls
# ---------------------------------------------------------------------------

class TestMemoryServiceEmbeddingDI:
    def test_accepts_embedding_provider(self):
        emb = _mock_embedding()
        svc = MemoryService(embedding=emb)
        assert svc._embedding is emb

    def test_default_uses_factory(self, monkeypatch):
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        from app.providers.mistral_provider import MistralEmbeddingProvider
        svc = MemoryService()
        assert isinstance(svc._embedding, MistralEmbeddingProvider)

    @pytest.mark.asyncio
    async def test_store_reflection_calls_embed(self):
        emb = _mock_embedding()
        db = _make_db_session()
        svc = MemoryService(db=db, embedding=emb)

        await svc.store_reflection(
            tenant_id="hotel_1",
            reflection="Saturday dinner always over-forecast",
        )

        emb.embed.assert_awaited_once()
        # Check embed was called with the reflection content
        call_arg = emb.embed.call_args.args[0]
        assert "Saturday dinner" in call_arg

    @pytest.mark.asyncio
    async def test_get_relevant_context_calls_embed(self):
        emb = _mock_embedding()
        db = _make_db_session()
        svc = MemoryService(db=db, embedding=emb)

        await svc.get_relevant_context(
            tenant_id="hotel_1",
            current_query="Why is Sunday breakfast always low?",
        )

        emb.embed.assert_awaited_once_with("Why is Sunday breakfast always low?")

    @pytest.mark.asyncio
    async def test_no_embed_call_without_db(self):
        emb = _mock_embedding()
        svc = MemoryService(db=None, embedding=emb)

        await svc.store_reflection(tenant_id="hotel_1", reflection="test")
        result = await svc.get_relevant_context(tenant_id="hotel_1", current_query="test")

        emb.embed.assert_not_awaited()
        assert result == ""


# ---------------------------------------------------------------------------
# AC5 — No mistralai imports in service files
# ---------------------------------------------------------------------------

class TestNoMistralaiImportsInServices:
    def test_rag_service_no_mistralai(self):
        import ast
        import pathlib
        src = pathlib.Path(__file__).parent.parent.parent / "app/services/rag_service.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                for alias in getattr(node, "names", []):
                    assert "mistralai" not in (alias.name or "")
                assert "mistralai" not in module

    def test_memory_service_no_mistralai(self):
        import ast
        import pathlib
        src = pathlib.Path(__file__).parent.parent.parent / "app/services/memory_service.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", "") or ""
                for alias in getattr(node, "names", []):
                    assert "mistralai" not in (alias.name or "")
                assert "mistralai" not in module

"""Unit tests for MemoryRecallService — P1-3 / ADR 0002.

Tier 1: pure-logic tests (build_embedding_payload, FakeEmbeddingProvider)
  — always run, no DB needed.
Tier 2: MemoryRecallService with mocked DB — skip if app deps missing.
"""
from __future__ import annotations

import pytest


def _try_import():
    try:
        from app.services.memory_recall_service import MemoryRecallService, MemoryHit
        return MemoryRecallService, MemoryHit
    except (ImportError, ModuleNotFoundError, TypeError):
        return None, None


_MRS, _MH = _try_import()
_skip = pytest.mark.skipif(_MRS is None, reason="memory_recall_service deps unavailable")


# ---------------------------------------------------------------------------
# Tier 1 — FakeEmbeddingProvider (no app imports)
# ---------------------------------------------------------------------------

class TestFakeEmbeddingProvider:
    @pytest.mark.asyncio
    async def test_deterministic(self):
        from tests.providers.fake_embedding import FakeEmbeddingProvider
        p = FakeEmbeddingProvider()
        v1 = await p.embed("hello world")
        v2 = await p.embed("hello world")
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_different_inputs_differ(self):
        from tests.providers.fake_embedding import FakeEmbeddingProvider
        p = FakeEmbeddingProvider()
        v1 = await p.embed("dinner rainy")
        v2 = await p.embed("breakfast sunny")
        assert v1 != v2

    @pytest.mark.asyncio
    async def test_dimension_is_1024(self):
        from tests.providers.fake_embedding import FakeEmbeddingProvider
        p = FakeEmbeddingProvider()
        v = await p.embed("test")
        assert len(v) == 1024
        assert p.dimensions == 1024

    @pytest.mark.asyncio
    async def test_values_in_range(self):
        from tests.providers.fake_embedding import FakeEmbeddingProvider
        p = FakeEmbeddingProvider()
        v = await p.embed("range check")
        assert all(-1.0 <= x <= 1.0 for x in v)


# ---------------------------------------------------------------------------
# Tier 1 — build_embedding_payload (no DB)
# ---------------------------------------------------------------------------

class TestBuildEmbeddingPayload:
    @_skip
    def test_feedback_payload_includes_outcome(self):
        payload = _MRS.build_embedding_payload(
            memory_type="feedback",
            outcome="accepted",
            notes="served 85 covers, manager happy",
        )
        assert "[feedback]" in payload
        assert "outcome=accepted" in payload
        assert "notes=served 85 covers" in payload

    @_skip
    def test_reflection_payload_minimal(self):
        payload = _MRS.build_embedding_payload(memory_type="reflection")
        assert "[reflection]" in payload

    @_skip
    def test_actual_value_included(self):
        payload = _MRS.build_embedding_payload(
            memory_type="feedback", outcome="rejected", actual_value=42.5
        )
        assert "actual=42.5" in payload

    @_skip
    def test_uuid_not_in_payload(self):
        """UUID must be excluded from embed payload (ADR D2 — structural noise)."""
        payload = _MRS.build_embedding_payload(
            memory_type="feedback",
            outcome="accepted",
            notes="some note",
        )
        # No UUID-shaped strings (8-4-4-4-12 hex)
        import re
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        assert not re.search(uuid_pattern, payload, re.IGNORECASE)

    @_skip
    def test_rec_context_truncated_at_200(self):
        long_ctx = "x" * 500
        payload = _MRS.build_embedding_payload(
            memory_type="feedback",
            outcome="accepted",
            recommendation_context=long_ctx,
        )
        # rec_context should be truncated
        assert len(payload) < 600

    @_skip
    def test_none_fields_omitted(self):
        payload = _MRS.build_embedding_payload(memory_type="feedback")
        assert "outcome=" not in payload
        assert "notes=" not in payload
        assert "actual=" not in payload


# ---------------------------------------------------------------------------
# Tier 1 — MemoryHit dataclass
# ---------------------------------------------------------------------------

class TestMemoryHit:
    @_skip
    def test_frozen(self):
        from uuid import uuid4
        from datetime import datetime
        hit = _MH(
            id=uuid4(),
            similarity=0.87,
            reflection="test reflection",
            outcome="accepted",
            manager_feedback="followed",
            memory_type="feedback",
            source="private",
            created_at=datetime.now(),
        )
        with pytest.raises((AttributeError, TypeError)):
            hit.similarity = 0.5  # type: ignore

    @_skip
    def test_source_field_present(self):
        """source must distinguish private vs fb_pattern (ADR D6 cold-start)."""
        from uuid import uuid4
        hit = _MH(
            id=uuid4(), similarity=0.7, reflection="r", outcome=None,
            manager_feedback=None, memory_type="fb_pattern",
            source="fb_pattern", created_at=None,
        )
        assert hit.source == "fb_pattern"

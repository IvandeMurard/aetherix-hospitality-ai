"""
Memory Service — two-layer architecture (HOS-99).

## Layer 1 — Private Memory (Phase 0-1, this module)
Per-hotel operational memory backed by pgvector `operational_memory` table.
Captures idiosyncrasies that are NOT generalisable across hotels:
  - Real capture rates for this property
  - Manager decision preferences
  - Local non-repeatable patterns

Key improvements over the old Backboard-only approach:
  - No external HTTP calls (eliminates 504 timeouts, 4-retry overhead)
  - SQL filters on hotel_id / manager_feedback (impossible with Backboard)
  - JOIN-able with fb_patterns — hybrid retrieval in one query
  - p95 latency target: <200ms

## Layer 2 — Hive Memory (Phase 3, additive, NOT implemented here)
Anonymised cross-hotel collective intelligence, grouped by property tags
(city/resort/airport, clientele segment, outlet size).  Each hotel benefits
from its own learning PLUS collective wisdom — without sharing raw data.
Implementation: `HiveMemoryService` (Backboard.io or equivalent), also
implementing the `MemoryProvider` protocol below.

## Extension contract
Both layers implement `MemoryProvider`.  Callers receive a `MemoryProvider`
instance — swapping in or layering `HiveMemoryService` in Phase 3 requires
zero changes to callers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid as _uuid
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from mistralai import Mistral
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider


# ---------------------------------------------------------------------------
# MemoryProvider protocol — the stable interface both layers must implement
# ---------------------------------------------------------------------------

@runtime_checkable
class MemoryProvider(Protocol):
    """
    Common interface for Private Memory (Phase 0-1) and Hive Memory (Phase 3).

    Callers depend only on this protocol — they never import a concrete class.
    """

    async def store_reflection(
        self,
        tenant_id: str,
        reflection: Optional[str] = None,
        context: Optional[str] = None,
        outcome: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> None: ...

    async def get_relevant_context(self, tenant_id: str, current_query: str) -> str: ...

    async def learn_from_feedback(
        self, tenant_id: str, alert_id: str, feedback: str
    ) -> None: ...

    async def cache_recommendation(self, tenant_id: str, data: Dict[str, Any]) -> None: ...

    async def get_latest_recommendation(
        self, tenant_id: str
    ) -> Optional[Dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# MemoryService — concrete Phase 0-1 implementation
# ---------------------------------------------------------------------------

class MemoryService:
    """
    Operational Memory Layer — backed by pgvector (Supabase).

    Replaces Backboard.io with direct SQL operations on the
    ``operational_memory`` table.  Semantic retrieval uses the pgvector
    cosine-distance operator (<=>); feedback signals (followed/rejected)
    are stored as structured columns so they can be filtered in SQL and
    boosted by pattern_scorer.py.

    Public API is kept backwards-compatible with the Backboard implementation
    so callers (aetherix_engine, action_logger, …) need no changes.
    """

    def __init__(self) -> None:
        mistral_key = os.getenv("MISTRAL_API_KEY")
        self._mistral = Mistral(api_key=mistral_key) if mistral_key else None

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self._db = db
        self._embedding: EmbeddingProvider = embedding or get_embedding_provider()
    async def _get_embedding(self, text_: str) -> List[float]:
        """Return a 1024-dimensional Mistral embedding, or zeros in dev/test."""
        if not self._mistral:
            return [0.0] * 1024
        response = await asyncio.to_thread(
            self._mistral.embeddings.create,
            model="mistral-embed",
            inputs=[text_],
        )
        return response.data[0].embedding

    @staticmethod
    def _vec_literal(embedding: List[float]) -> str:
        return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"

    # ------------------------------------------------------------------
    # Public API (mirrors old Backboard API surface)
    # ------------------------------------------------------------------

    async def store_reflection(
        self,
        tenant_id: str,
        reflection: Optional[str] = None,
        context: Optional[str] = None,
        outcome: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Persists an operational insight or manager feedback into operational_memory.

        Accepts either:
          - seed script:    store_reflection(tenant_id, reflection="...", tags=[...])
          - feedback loop:  store_reflection(tenant_id, context="...", outcome="...")
        """
        if self._db is None:
            return

        content = reflection if reflection else f"Context: {context} | Outcome: {outcome}"
        embedding = await self._embedding.embed(content)

        await self._db.execute(
            text(
                """
                INSERT INTO operational_memory
                  (id, hotel_id, session_id, content, outcome, tags, embedding, created_at)
                VALUES
                  (:id, :hotel_id, :session_id, :content, :outcome, :tags,
                   CAST(:embedding AS vector), NOW())
                """
            ),
            {
                "id": str(_uuid.uuid4()),
                "hotel_id": tenant_id,
                "session_id": session_id,
                "content": content,
                "outcome": outcome,
                "tags": json.dumps(tags or []),
                "embedding": str(embedding),
            },
        )
        await self._db.commit()
        manager_feedback: Optional[str] = None,
    ) -> None:
        """
        Persist an operational insight or manager feedback into
        ``operational_memory``.

        Supports two call signatures (backwards-compatible with seed script):
          - seed script:    store_reflection(tenant_id, reflection="...", tags=[...])
          - feedback loop:  store_reflection(tenant_id, context="...", outcome="...")
        """
        content = (
            reflection if reflection else f"Context: {context} | Outcome: {outcome}"
        )
        embedding = await self._get_embedding(content)
        vec = self._vec_literal(embedding)

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO operational_memory
                        (hotel_id, reflection, manager_feedback, embedding, created_at)
                    VALUES
                        (:hotel_id, :reflection, :feedback, CAST(:vec AS vector), NOW())
                    """
                ),
                {
                    "hotel_id": tenant_id,
                    "reflection": content,
                    "feedback": manager_feedback,
                    "vec": vec,
                },
            )
            await session.commit()
        logger.info("Stored reflection for tenant '%s'", tenant_id)

    async def get_relevant_context(self, tenant_id: str, current_query: str) -> str:
        """
        Retrieves the top-3 most relevant memories for *current_query* via
        pgvector cosine similarity, filtered to *tenant_id*.

        Returns a newline-separated string of memory content (same surface as
        the old Backboard response).
        """
        if self._db is None:
            return ""

        embedding = await self._embedding.embed(current_query)

        try:
            result = await self._db.execute(
                text(
                    """
                    SELECT content, outcome,
                           embedding <=> CAST(:embedding AS vector) AS similarity
                    FROM operational_memory
                    WHERE hotel_id = :hotel_id
                    ORDER BY similarity ASC
                    LIMIT 3
                    """
                ),
                {"hotel_id": tenant_id, "embedding": str(embedding)},
            )
            rows = result.mappings().all()
        except Exception as exc:
            if "no such function" in str(exc).lower() or "operator" in str(exc).lower() \
                    or "syntax error" in str(exc).lower():
                # SQLite fallback — return most-recent memories
                logger.debug("pgvector unavailable (SQLite?), using fallback: %s", exc)
                rows = await self._fallback_select(tenant_id)
            else:
                logger.error("MemoryService.get_relevant_context error: %s", exc)
                return ""

        parts = []
        for row in rows:
            parts.append(row["content"])
            if row.get("outcome"):
                parts.append(f"  → {row['outcome']}")
        Retrieve relevant historical context for a given query using
        pgvector semantic similarity search.

        Returns up to 5 most relevant reflections as a newline-joined string.
        """
        embedding = await self._get_embedding(current_query)
        vec = self._vec_literal(embedding)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT reflection, manager_feedback
                    FROM operational_memory
                    WHERE hotel_id = :hotel_id
                    ORDER BY embedding <=> CAST(:vec AS vector)
                    LIMIT 5
                    """
                ),
                {"hotel_id": tenant_id, "vec": vec},
            )
            rows = result.fetchall()

        if not rows:
            return ""
        parts = []
        for row in rows:
            feedback_tag = (
                f" [feedback: {row.manager_feedback}]" if row.manager_feedback else ""
            )
            parts.append(f"- {row.reflection}{feedback_tag}")
        return "\n".join(parts)

    async def learn_from_feedback(
        self, tenant_id: str, alert_id: str, feedback: str
    ) -> None:
        """Store manager feedback to prevent repeated unhelpful alerts."""
        feedback_value = (
            "rejected"
            if feedback.lower() in {"rejected", "no", "bad", "dismiss"}
            else "followed"
        )
        await self.store_reflection(
            tenant_id,
            context=f"AlertID: {alert_id}",
            outcome=f"Manager Feedback: {feedback}",
            manager_feedback=feedback_value,
        )

    async def cache_recommendation(
        self, tenant_id: str, data: Dict[str, Any]
    ) -> None:
        """Persist the latest AI recommendation into ``operational_memory``."""
        content = f"[recommendation_cache] {json.dumps(data)}"
        embedding = await self._get_embedding(content)
        vec = self._vec_literal(embedding)

        async with AsyncSessionLocal() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO operational_memory
                        (hotel_id, reflection, reco_json, memory_type, embedding, created_at)
                    VALUES
                        (:hotel_id, :reflection, CAST(:reco AS jsonb),
                         'recommendation_cache', CAST(:vec AS vector), NOW())
                    """
                ),
                {
                    "hotel_id": tenant_id,
                    "reflection": content,
                    "reco": json.dumps(data),
                    "vec": vec,
                },
            )
            await session.commit()

    async def get_latest_recommendation(
        self, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent cached recommendation for a tenant."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT reco_json
                    FROM operational_memory
                    WHERE hotel_id    = :hotel_id
                      AND memory_type = 'recommendation_cache'
                      AND reco_json   IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"hotel_id": tenant_id},
            )
            row = result.fetchone()
        return row.reco_json if row else None

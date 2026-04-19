"""
Memory Service — two-layer architecture (HOS-99).

## Layer 1 — Private Memory (Phase 0-1, this module)
Per-hotel operational memory backed by pgvector `operational_memory` table.
Captures idiosyncrasies that are NOT generalisable across hotels:
  - Real capture rates for this property
  - Manager decision preferences
  - Local non-repeatable patterns

## Layer 2 — Hive Memory (Phase 3, additive, NOT implemented here)
Anonymised cross-hotel collective intelligence, grouped by property tags.
Implementation: `HiveMemoryService` (Backboard.io or equivalent).

## Extension contract
Both layers implement `MemoryProvider`. Callers receive a `MemoryProvider`
instance — swapping in or layering `HiveMemoryService` in Phase 3 requires
zero changes to callers.
"""
from __future__ import annotations

import json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider

logger = logging.getLogger(__name__)


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

    async def recall(
        self,
        tenant_id: str,
        query_embedding: list[float],
        k: int = 5,
        min_similarity: float = 0.5,
    ) -> list: ...  # returns list[MemoryHit] — avoid circular import on type


# ---------------------------------------------------------------------------
# MemoryService — concrete Phase 0-1 implementation
# ---------------------------------------------------------------------------

class MemoryService:
    """
    Operational Memory Layer — backed by pgvector (Supabase).

    Replaces Backboard.io with direct SQL operations on the
    ``operational_memory`` table. Semantic retrieval uses the pgvector
    cosine-distance operator (<=>); feedback signals (followed/rejected)
    are stored as structured columns so they can be filtered in SQL and
    boosted by pattern_scorer.py.
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self._db = db
        self._embedding: EmbeddingProvider = embedding or get_embedding_provider()

    # ------------------------------------------------------------------
    # Public API
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
        logger.info("Stored reflection for tenant '%s'", tenant_id)

    async def get_relevant_context(self, tenant_id: str, current_query: str) -> str:
        """
        Retrieves the top-3 most relevant memories for *current_query* via
        pgvector cosine similarity, filtered to *tenant_id*.

        Returns a newline-separated string of memory content.
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
            if (
                "no such function" in str(exc).lower()
                or "operator" in str(exc).lower()
                or "syntax error" in str(exc).lower()
            ):
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
            outcome=f"Manager Feedback: {feedback} [{feedback_value}]",
        )

    async def cache_recommendation(
        self, tenant_id: str, data: Dict[str, Any]
    ) -> None:
        """Persist the latest AI recommendation into ``operational_memory``."""
        if self._db is None:
            return

        content = f"[recommendation_cache] {json.dumps(data)}"
        embedding = await self._embedding.embed(content)

        await self._db.execute(
            text(
                """
                INSERT INTO operational_memory
                    (id, hotel_id, content, reco_json, memory_type, embedding, created_at)
                VALUES
                    (:id, :hotel_id, :content, CAST(:reco AS jsonb),
                     'recommendation_cache', CAST(:embedding AS vector), NOW())
                """
            ),
            {
                "id": str(_uuid.uuid4()),
                "hotel_id": tenant_id,
                "content": content,
                "reco": json.dumps(data),
                "embedding": str(embedding),
            },
        )
        await self._db.commit()

    async def get_latest_recommendation(
        self, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve the most recent cached recommendation for a tenant."""
        if self._db is None:
            return None

        result = await self._db.execute(
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fallback_select(self, tenant_id: str) -> List[Any]:
        """Plain SELECT without vector ops — SQLite fallback."""
        if self._db is None:
            return []
        result = await self._db.execute(
            text(
                """
                SELECT content, outcome
                FROM operational_memory
                WHERE hotel_id = :hotel_id
                ORDER BY created_at DESC
                LIMIT 3
                """
            ),
            {"hotel_id": tenant_id},
        )
        return result.mappings().all()

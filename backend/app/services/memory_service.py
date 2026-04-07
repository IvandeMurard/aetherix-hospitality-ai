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

import json
import logging
import uuid as _uuid
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

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

    async def get_latest_recommendation(self, tenant_id: str) -> Optional[Dict[str, Any]]: ...

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Cognitive Memory Layer backed by the `operational_memory` Supabase table.

    Accepts an injected AsyncSession so callers control the DB transaction.
    All methods silently no-op when no session is provided.
    """

    def __init__(
        self,
        db: Optional[AsyncSession] = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self._db = db
        self._embedding: EmbeddingProvider = embedding or get_embedding_provider()

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
        return "\n".join(parts)

    async def learn_from_feedback(
        self, tenant_id: str, alert_id: str, feedback: str
    ) -> None:
        """Stores manager feedback to prevent repeated unhelpful alerts."""
        await self.store_reflection(
            tenant_id,
            context=f"AlertID: {alert_id}",
            outcome=f"Manager Feedback: {feedback}",
        )

    async def cache_recommendation(
        self, tenant_id: str, data: Dict[str, Any]
    ) -> None:
        """Persists the latest recommendation payload into operational_memory."""
        if self._db is None:
            return
        content = f"[recommendation_cache] {json.dumps(data)}"
        await self.store_reflection(tenant_id, reflection=content, tags=["recommendation_cache"])

    async def get_latest_recommendation(
        self, tenant_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieves the most recent cached recommendation for *tenant_id*."""
        if self._db is None:
            return None
        try:
            result = await self._db.execute(
                text(
                    """
                    SELECT content FROM operational_memory
                    WHERE hotel_id = :hotel_id
                      AND content LIKE '%recommendation_cache%'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"hotel_id": tenant_id},
            )
            row = result.mappings().first()
            if row is None:
                return None
            raw = row["content"]
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
            return None
        except Exception as exc:
            logger.error("MemoryService.get_latest_recommendation error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fallback_select(self, tenant_id: str) -> List[Any]:
        """Plain SELECT without vector ops — used when pgvector is unavailable."""
        result = await self._db.execute(
            text(
                """
                SELECT content, outcome, NULL AS similarity
                FROM operational_memory
                WHERE hotel_id = :hotel_id
                ORDER BY created_at DESC
                LIMIT 3
                """
            ),
            {"hotel_id": tenant_id},
        )
        return result.mappings().all()

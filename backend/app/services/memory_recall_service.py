"""MemoryRecallService — semantic retrieval from operational_memory (ADR 0002 · P1-3).

Public surface:
    MemoryHit         — typed result row (D4)
    MemoryRecallService.recall(...)  — cosine-similarity search with cold-start fallback (D4, D6)
    MemoryRecallService.build_embedding_payload(...)  — structured concat payload (D2)

Design constraints:
    - hotel_id is always the first filter — no cross-tenant data access.
    - Embedding computation is caller's responsibility (pass the vector in).
    - Cold-start delegates to RAGService.find_similar_patterns — no cross-hotel
      operational_memory access (Decision #2 privacy boundary).
    - All DB queries pass hotel_id as a bound parameter (never f-string injected).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DEFAULT_MIN_SIMILARITY = 0.50
_DEFAULT_K = 5
_DEFAULT_MEMORY_TYPES = ("feedback", "reflection")


@dataclass(frozen=True)
class MemoryHit:
    id: UUID
    similarity: float          # 1 - cosine_distance, higher = closer (0..1)
    reflection: str
    outcome: Optional[str]
    manager_feedback: Optional[str]  # followed | rejected | neutral
    memory_type: str
    source: str                # "private" | "fb_pattern"
    created_at: Optional[datetime]


class MemoryRecallService:
    """Semantic recall from operational_memory with cold-start fallback."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def recall(
        self,
        hotel_id: str,
        query_embedding: list[float],
        k: int = _DEFAULT_K,
        min_similarity: float = _DEFAULT_MIN_SIMILARITY,
        memory_types: Sequence[str] = _DEFAULT_MEMORY_TYPES,
        since: Optional[datetime] = None,
        only_followed: bool = False,
    ) -> list[MemoryHit]:
        """Return up to k MemoryHits ordered by cosine similarity descending.

        Falls back to fb_patterns (via RAGService) when private memory is empty.
        Never accesses another hotel's operational_memory rows.
        """
        hits = await self._recall_private(
            hotel_id, query_embedding, k, min_similarity, memory_types, since, only_followed
        )
        if hits:
            return hits
        return await self._cold_start_fallback(hotel_id, query_embedding, k)

    async def check_cosine_dedup(
        self,
        hotel_id: str,
        query_embedding: list[float],
        threshold: float = 0.98,
        days_window: int = 7,
    ) -> Optional[UUID]:
        """Return the id of an existing row if cosine similarity > threshold (ADR D7).

        Returns None if no duplicate found.
        """
        sql = text("""
            SELECT id
            FROM operational_memory
            WHERE hotel_id = :hotel_id
              AND memory_type = 'feedback'
              AND embedding_pending = FALSE
              AND embedding IS NOT NULL
              AND created_at > NOW() - make_interval(days => :days)
              AND 1 - (embedding <=> CAST(:q AS vector)) > :threshold
            ORDER BY embedding <=> CAST(:q AS vector) ASC
            LIMIT 1
        """)
        try:
            result = await self._db.execute(
                sql,
                {
                    "hotel_id": hotel_id,
                    "q": str(query_embedding),
                    "threshold": threshold,
                    "days": days_window,
                },
            )
            row = result.fetchone()
            return UUID(str(row[0])) if row else None
        except Exception as exc:
            logger.warning("cosine dedup check failed (non-blocking): %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _recall_private(
        self,
        hotel_id: str,
        query_embedding: list[float],
        k: int,
        min_similarity: float,
        memory_types: Sequence[str],
        since: Optional[datetime],
        only_followed: bool,
    ) -> list[MemoryHit]:
        conditions = [
            "hotel_id = :hotel_id",
            "memory_type = ANY(:memory_types)",
            "embedding IS NOT NULL",
            "embedding_pending = FALSE",
        ]
        params: dict[str, Any] = {
            "hotel_id": hotel_id,
            "memory_types": list(memory_types),
            "q": str(query_embedding),
            "k": k,
        }
        if since:
            conditions.append("created_at >= :since")
            params["since"] = since
        if only_followed:
            conditions.append("manager_feedback = 'followed'")

        where = " AND ".join(conditions)
        sql = text(f"""
            SELECT
                id,
                1 - (embedding <=> CAST(:q AS vector)) AS similarity,
                reflection,
                outcome,
                manager_feedback,
                memory_type,
                created_at
            FROM operational_memory
            WHERE {where}
            ORDER BY embedding <=> CAST(:q AS vector) ASC
            LIMIT :k
        """)
        try:
            result = await self._db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            logger.warning("memory recall query failed: %s", exc)
            return []

        return [
            MemoryHit(
                id=UUID(str(row[0])),
                similarity=float(row[1]),
                reflection=row[2] or "",
                outcome=row[3],
                manager_feedback=row[4],
                memory_type=row[5],
                source="private",
                created_at=row[6],
            )
            for row in rows
            if float(row[1]) >= min_similarity
        ]

    async def _cold_start_fallback(
        self,
        hotel_id: str,
        query_embedding: list[float],
        k: int,
    ) -> list[MemoryHit]:
        """Fall back to fb_patterns (RAGService) — no cross-hotel private memory."""
        try:
            from app.services.rag_service import RAGService  # lazy import avoids circular dep

            rag = RAGService(self._db)
            patterns = await rag.find_similar_patterns_by_embedding(
                query_embedding, tenant_id=hotel_id, limit=k
            )
            return [
                MemoryHit(
                    id=UUID(str(p.get("id", "00000000-0000-0000-0000-000000000000"))),
                    similarity=float(p.get("similarity", 0.5)),
                    reflection=p.get("description", "") or p.get("context_summary", ""),
                    outcome=None,
                    manager_feedback=None,
                    memory_type="fb_pattern",
                    source="fb_pattern",
                    created_at=None,
                )
                for p in (patterns or [])
            ]
        except Exception as exc:
            logger.warning("cold-start fallback failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Payload builder (ADR D2)
    # ------------------------------------------------------------------

    @staticmethod
    def build_embedding_payload(
        memory_type: str,
        outcome: Optional[str] = None,
        notes: Optional[str] = None,
        actual_value: Optional[float] = None,
        recommendation_context: Optional[str] = None,
    ) -> str:
        """Build the structured concat string that gets embedded (ADR D2).

        The UUID is intentionally excluded — it's structural noise and would
        dominate bag-of-tokens similarity without adding semantic content.
        """
        parts = [f"[{memory_type}]"]
        if outcome:
            parts.append(f"outcome={outcome}")
        if recommendation_context:
            parts.append(f"rec_context={recommendation_context[:200]}")
        if notes:
            parts.append(f"notes={notes}")
        if actual_value is not None:
            parts.append(f"actual={actual_value}")
        return " | ".join(parts)

"""
RAG Service — pgvector retrieval layer (HOS-99).

Replaces the old Qdrant + Mistral stack with a single SQL query against
the `fb_patterns` table in Supabase (PostgreSQL + pgvector extension).

A single SQL query with the pgvector cosine-distance operator (<=>)
replaces the two-hop Qdrant → embedding round-trip, keeping p95 latency
well within the 500 ms MCP target.

Embedding generation is delegated to an injected ``EmbeddingProvider``.
Zero-vector fallback is preserved when no API key is configured (dev mode).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.demo_events import demo_emit
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider

logger = logging.getLogger(__name__)

# Dimension must match the vector(1024) column in fb_patterns.
_EMBEDDING_DIM = 1024


class RAGService:
    """RAG Service for pattern retrieval from pgvector (Supabase).

    Retrieves similar F&B patterns from the `fb_patterns` pgvector table.
    Falls back gracefully to a zero-vector when MISTRAL_API_KEY is absent
    (dev/test mode) — pgvector cosine distance on zero vectors degrades to
    unordered results rather than crashing.
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

    async def find_similar_patterns(
        self,
        query_text: str,
        service_type: str,
        tenant_id: Optional[str] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Returns up to *limit* patterns ordered by cosine similarity to *query_text*.

        Filters:
          - service_type must match exactly
          - tenant_id, when provided, restricts to that hotel's patterns plus
            global patterns (tenant_id IS NULL)
          - feedback_status != 'rejected' (exclude patterns managers disliked)

        When running against SQLite (tests), the `<=>` operator is unavailable;
        the query falls back to a plain SELECT ordered by creation date.
        """
        if self._db is None:
            return []

        embedding = await self._embedding.embed(query_text)

        try:
            params: Dict[str, Any] = {
                "service_type": service_type,
                "limit": limit,
                "embedding": str(embedding),
            }
            where_clauses = [
                "service_type = :service_type",
                "feedback_status != 'rejected'",
            ]
            if tenant_id:
                where_clauses.append("(tenant_id = :tenant_id OR tenant_id IS NULL)")
                params["tenant_id"] = tenant_id

            where_sql = " AND ".join(where_clauses)
            sql = text(
                f"""
                SELECT id, service_type, occupancy_band, day_of_week,
                       weather_condition, feedback_status, pattern_text,
                       outcome_description,
                       embedding <=> CAST(:embedding AS vector) AS similarity
                FROM fb_patterns
                WHERE {where_sql}
                ORDER BY similarity ASC
                LIMIT :limit
                """
            )
            result = await self._db.execute(sql, params)
            rows = result.mappings().all()
        except Exception as exc:
            if (
                "no such function" in str(exc).lower()
                or "no such column" in str(exc).lower()
                or "syntax error" in str(exc).lower()
                or "operator" in str(exc).lower()
            ):
                # SQLite fallback — return most-recently-added patterns
                logger.debug("pgvector operator unavailable (SQLite?), using fallback: %s", exc)
                rows = await self._fallback_select(service_type, tenant_id, limit)
            else:
                logger.error("RAGService.find_similar_patterns error: %s", exc)
                return []

        results = [
            {
                "id": str(row["id"]),
                "score": float(row.get("similarity", 1.0)),
                "payload": {
                    "service_type": row["service_type"],
                    "occupancy_band": row["occupancy_band"],
                    "day_of_week": row["day_of_week"],
                    "weather_condition": row["weather_condition"],
                    "feedback_status": row["feedback_status"],
                    "pattern_text": row["pattern_text"],
                    "outcome_description": row["outcome_description"],
                },
            }
            for row in rows
        ]
        # Demo board: highlight pgvector RAG node after pattern retrieval
        asyncio.create_task(demo_emit("rag"))
        return results

    async def find_similar_patterns_by_embedding(
        self,
        embedding: List[float],
        tenant_id: Optional[str] = None,
        limit: int = 5,
        service_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Pre-embedded variant of find_similar_patterns — used by MemoryRecallService
        cold-start (ADR 0002 D6) when private memory is empty and we already hold
        a query vector (no need to re-embed).

        Returns patterns in the same shape as find_similar_patterns, shaped for
        MemoryHit construction. Cross-hotel global patterns (tenant_id IS NULL)
        are included; private memory is never cross-tenant.
        """
        if self._db is None:
            return []

        params: Dict[str, Any] = {
            "limit": limit,
            "embedding": str(embedding),
        }
        where_clauses = ["feedback_status != 'rejected'"]
        if service_type:
            where_clauses.append("service_type = :service_type")
            params["service_type"] = service_type
        if tenant_id:
            where_clauses.append("(tenant_id = :tenant_id OR tenant_id IS NULL)")
            params["tenant_id"] = tenant_id

        where_sql = " AND ".join(where_clauses)
        sql = text(
            f"""
            SELECT id, service_type, pattern_text, outcome_description,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM fb_patterns
            WHERE {where_sql}
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector) ASC
            LIMIT :limit
            """
        )
        try:
            result = await self._db.execute(sql, params)
            rows = result.mappings().all()
        except Exception as exc:
            logger.warning(
                "find_similar_patterns_by_embedding failed (cold-start fallback): %s", exc
            )
            return []

        return [
            {
                "id": str(row["id"]),
                "similarity": float(row["similarity"]),
                "description": row["pattern_text"] or "",
                "context_summary": row["outcome_description"] or "",
                "service_type": row["service_type"],
            }
            for row in rows
        ]

    async def _fallback_select(
        self,
        service_type: str,
        tenant_id: Optional[str],
        limit: int,
    ) -> List[Any]:
        """Plain SELECT without vector ops — used when pgvector is unavailable."""
        params: Dict[str, Any] = {"service_type": service_type, "limit": limit}
        where_clauses = [
            "service_type = :service_type",
            "feedback_status != 'rejected'",
        ]
        if tenant_id:
            where_clauses.append("(tenant_id = :tenant_id OR tenant_id IS NULL)")
            params["tenant_id"] = tenant_id
        where_sql = " AND ".join(where_clauses)
        sql = text(
            f"""
            SELECT id, service_type, occupancy_band, day_of_week,
                   weather_condition, feedback_status, pattern_text,
                   outcome_description, NULL AS similarity
            FROM fb_patterns
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        result = await self._db.execute(sql, params)
        return result.mappings().all()

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def build_context_string(
        self, target_date: date, service_type: str, context: Dict[str, Any]
    ) -> str:
        """Build a standardised context string for embedding query generation.
        An absent value is written as unknown, never as a default (HOS-358)."""
        weather = context.get("weather") or {}
        events = context.get("events") or []
        events_str = ", ".join(e.get("type", "Event") for e in events) or "None"
        occupancy = context.get("occupancy")
        return (
            f"Date: {target_date.isoformat()}\n"
            f"Service: {service_type}\n"
            f"Weather: {weather.get('condition') or 'Unknown'}\n"
            f"Events: {events_str}\n"
            f"Hotel Occupancy: {occupancy if occupancy is not None else 'unknown'}\n"
        )

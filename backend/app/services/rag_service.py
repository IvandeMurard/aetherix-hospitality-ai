"""
RAG Service — pgvector retrieval layer (HOS-99).

Replaces the old Qdrant + Mistral stack with a single SQL query against
the `fb_patterns` table in Supabase (PostgreSQL + pgvector extension).

Embedding generation is delegated to an injected ``EmbeddingProvider``.
Zero-vector fallback is preserved via ``MistralEmbeddingProvider`` when no
API key is configured (dev mode).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider

logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieves similar F&B patterns from the `fb_patterns` pgvector table.

    Accepts an injected AsyncSession so callers control the DB transaction.
    Falls back gracefully when no DB session is provided (returns empty list).
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
            # Build the cosine-distance ORDER BY.  pgvector registers the <=>
            # operator; on SQLite this will raise an OperationalError which we
            # catch below and fall back to a simple date-ordered query.
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
            if "no such function" in str(exc).lower() or "no such column" in str(exc).lower() \
                    or "syntax error" in str(exc).lower() or "operator" in str(exc).lower():
                # SQLite fallback — return most-recently-added patterns
                logger.debug("pgvector operator unavailable (SQLite?), using fallback: %s", exc)
                rows = await self._fallback_select(service_type, tenant_id, limit)
            else:
                logger.error("RAGService.find_similar_patterns error: %s", exc)
                return []

        return [
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
        self,
        target_date: date,
        service_type: str,
        context: Dict[str, Any],
    ) -> str:
        """Builds a standardised natural-language string for embedding lookup."""
        weather = context.get("weather", {})
        events = context.get("events", [])
        events_str = ", ".join([e.get("type", "Event") for e in events]) or "None"
        return (
            f"Date: {target_date.isoformat()}\n"
            f"Service: {service_type}\n"
            f"Weather: {weather.get('condition', 'Unknown')}\n"
            f"Events: {events_str}\n"
            f"Hotel Occupancy: {context.get('occupancy', 0.8)}\n"
        )

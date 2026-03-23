from __future__ import annotations

import asyncio
import logging
import os
from datetime import date
from typing import Any, Dict, List

from mistralai import Mistral
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG Service for pattern retrieval from pgvector (Supabase).

    Replaces the previous Qdrant-based implementation. A single SQL query
    with the pgvector cosine-distance operator (<=>)  replaces the two-hop
    Qdrant → embedding round-trip, keeping p95 latency well within the
    500 ms MCP target.
    """

    def __init__(self) -> None:
        mistral_key = os.getenv("MISTRAL_API_KEY")
        self._mistral = Mistral(api_key=mistral_key) if mistral_key else None

    async def get_embedding(self, text_: str) -> List[float]:
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

    async def find_similar_patterns(
        self,
        query_text: str,
        service_type: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Search fb_patterns in pgvector for semantically similar F&B patterns.

        Returns a list of dicts with keys: id, score (cosine similarity 0–1),
        payload (JSONB from the patterns table).
        """
        embedding = await self.get_embedding(query_text)
        vec = self._vec_literal(embedding)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id,
                        payload,
                        1 - (embedding <=> CAST(:vec AS vector)) AS score
                    FROM fb_patterns
                    WHERE service_type = :service_type
                    ORDER BY embedding <=> CAST(:vec AS vector)
                    LIMIT :limit
                    """
                ),
                {"vec": vec, "service_type": service_type, "limit": limit},
            )
            rows = result.fetchall()

        return [
            {"id": str(row.id), "score": float(row.score), "payload": row.payload}
            for row in rows
        ]

    def build_context_string(
        self, target_date: date, service_type: str, context: Dict[str, Any]
    ) -> str:
        """Build a standardised context string for embedding query generation."""
        weather = context.get("weather", {})
        events = context.get("events", [])
        events_str = ", ".join(e.get("type", "Event") for e in events) or "None"
        return (
            f"Date: {target_date.isoformat()}\n"
            f"Service: {service_type}\n"
            f"Weather: {weather.get('condition', 'Unknown')}\n"
            f"Events: {events_str}\n"
            f"Hotel Occupancy: {context.get('occupancy', 0.8)}\n"
        )

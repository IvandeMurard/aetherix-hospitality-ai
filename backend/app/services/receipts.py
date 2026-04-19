"""Phase 2 — Agent Receipts daily composer (P2-1 + P2-2).

P2-1: `ReceiptsService.daily_receipt` reads `agent_action_log` for a (hotel_id, date)
      and returns a typed `ReceiptPayload`.
P2-2: Enriches each `ReceiptLine` with `memory_hits` — `operational_memory` rows
      written during that same tool call, linked via `request_id` backlink.

Memory-hits enrichment uses a single second SELECT (batch by request_id set),
not N+1 queries.

Intentionally not in scope here: narrative prose composition (P2-3 / OQ4 tone),
WhatsApp/email dispatch (P2-3 / P2-5), web drill-down (P2-6).

Phase 2 spec: docs/planning/phase-2-agent-receipts.md
PM-locked decisions: CLAUDE.md Decision #15.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timezone
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentActionLog, OperationalMemory


class MemoryHitSummary(BaseModel):
    """Condensed view of an `operational_memory` row linked to a Receipt line."""

    memory_id: str
    reflection_snippet: str  # first 200 chars
    manager_feedback: Optional[str] = None
    memory_type: str
    created_at: datetime


class ReceiptLine(BaseModel):
    """One row of an agent's daily action log, in Receipt-friendly form."""

    timestamp: datetime
    tool_name: str
    status: str  # ok | auth_error | tool_error | rate_limited | rate_limit_fallback
    request_id: str
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    dedup_hit: Optional[bool] = None
    top_similarity: Optional[float] = None
    # P2-2: memory rows written during this call (empty for non-write calls)
    memory_hits: list[MemoryHitSummary] = Field(default_factory=list)


class ReceiptPayload(BaseModel):
    """Full Receipt for a hotel on a single UTC date.

    P2-1 returns log-only data. P2-2 enriches with memory_hits via request_id.
    P2-3 wraps this in narrative + dispatch. P2-6 renders the web view.
    """

    hotel_id: str
    receipt_date: date
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    total_actions: int
    counts_by_status: dict[str, int]
    counts_by_tool: dict[str, int]
    lines: list[ReceiptLine]


class ReceiptsService:
    """Daily Receipt composer. Stateless beyond the injected DB session."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def daily_receipt(
        self, hotel_id: str, target_date: date
    ) -> ReceiptPayload:
        """Build a `ReceiptPayload` for `hotel_id` on `target_date`.

        Date boundaries are inclusive UTC (00:00:00 → 23:59:59.999999).
        Memory enrichment uses one additional batch SELECT (P2-2).
        """
        day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

        result = await self.db.execute(
            select(AgentActionLog)
            .where(AgentActionLog.hotel_id == hotel_id)
            .where(AgentActionLog.created_at >= day_start)
            .where(AgentActionLog.created_at <= day_end)
            .order_by(AgentActionLog.created_at.asc())
        )
        rows = result.scalars().all()

        lines = [
            ReceiptLine(
                timestamp=r.created_at,
                tool_name=r.tool_name,
                status=r.status,
                request_id=r.request_id or "",
                latency_ms=r.latency_ms,
                error_code=r.error_code,
                dedup_hit=r.dedup_hit,
                top_similarity=r.top_similarity,
            )
            for r in rows
        ]

        # P2-2: batch-fetch memory rows linked to these tool calls
        await self._attach_memory_hits(hotel_id, lines)

        return ReceiptPayload(
            hotel_id=hotel_id,
            receipt_date=target_date,
            total_actions=len(lines),
            counts_by_status=dict(Counter(line.status for line in lines)),
            counts_by_tool=dict(Counter(line.tool_name for line in lines)),
            lines=lines,
        )

    async def _attach_memory_hits(
        self, hotel_id: str, lines: list[ReceiptLine]
    ) -> None:
        """Enrich each ReceiptLine with memory rows sharing its request_id.

        Single batch query — no N+1. Lines with empty request_id or no matching
        memory rows keep their default empty list.
        """
        request_ids = {line.request_id for line in lines if line.request_id}
        if not request_ids:
            return

        mem_result = await self.db.execute(
            select(OperationalMemory)
            .where(OperationalMemory.hotel_id == hotel_id)
            .where(OperationalMemory.request_id.in_(request_ids))
            .order_by(OperationalMemory.created_at.asc())
        )
        memory_rows = mem_result.scalars().all()

        hits_by_rid: dict[str, list[MemoryHitSummary]] = defaultdict(list)
        for m in memory_rows:
            hits_by_rid[m.request_id].append(
                MemoryHitSummary(
                    memory_id=str(m.id),
                    reflection_snippet=(m.reflection or "")[:200],
                    manager_feedback=m.manager_feedback,
                    memory_type=m.memory_type,
                    created_at=m.created_at,
                )
            )

        for line in lines:
            if line.request_id in hits_by_rid:
                line.memory_hits = hits_by_rid[line.request_id]

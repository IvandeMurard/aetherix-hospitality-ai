"""Decision Ledger — read-only consolidation of the decision loop (HOS-317).

This module builds **nothing new**. Every leg of the loop was already persisted
across five tables; what was missing was the edge letting them be read as one
object (Finding C5/F6, external adversarial review 2026-07-20). HOS-317 added
``operational_memory.recommendation_id``; this service is the query that spends
it.

    demand_anomalies          → source context + data quality
      staffing_recommendations → recommendation emitted, dispatch, outcome value
        operational_memory     → manager answer (WhatsApp) + ground-truth outcome
          agent_action_log     → abstention / guardrail trip for that turn

Deliberately read-only: no write path, no side effect, no LLM. The write paths
stay where they are (``mcp_server.tool_submit_feedback_to_memory``,
``ReceiptsService.persist_actual_covers``, ``action_logger``).

Two surfaces, one shape:
  * this service — runtime source of truth, portable SQLAlchemy (tests run on
    SQLite, which has no LATERAL),
  * the ``decision_ledger`` SQL view (migration 20260801100000) — analyst and
    demo surface (HOS-310).

Vocabulary (AC4): this is an **outcome-tracked operational history**. It records
what was recommended, what the manager answered and what actually happened. It
does not claim the agent learns from it — see docs/context/decision-ledger.md §5
for what the ledger closes today and what it does not.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentActionLog,
    DemandAnomaly,
    OperationalMemory,
    StaffingRecommendation,
)

logger = logging.getLogger(__name__)

# Memory rows that carry the manager's answer vs the measured outcome.
_FEEDBACK_TYPE = "feedback"
_GROUND_TRUTH_TYPE = "ground_truth"


@dataclass(frozen=True)
class DecisionRecord:
    """One decision, end to end. Every field may be None — a recommendation
    that was never answered is a legitimate (and interesting) ledger row."""

    # Identity
    recommendation_id: UUID
    tenant_id: str
    property_id: Optional[UUID]

    # 1. Source context + data quality
    anomaly_id: Optional[UUID] = None
    triggering_factors: Any = None
    deviation_pct: Optional[float] = None
    direction: Optional[str] = None
    context_detected_at: Optional[datetime] = None

    # 2. Recommendation emitted
    recommended_at: Optional[datetime] = None
    message_text: Optional[str] = None
    recommended_headcount: Optional[int] = None
    predicted_covers: Optional[float] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    dispatch_channel: Optional[str] = None

    # 3. Manager response — dashboard column, else WhatsApp memory row
    manager_response: Optional[str] = None
    manager_responded_at: Optional[datetime] = None
    manager_response_channel: Optional[str] = None   # dashboard | whatsapp
    feedback_memory_id: Optional[UUID] = None
    feedback_reflection: Optional[str] = None

    # 4. Measured outcome
    actual_covers: Optional[float] = None
    actual_covers_source: Optional[str] = None
    actual_covers_at: Optional[datetime] = None
    outcome_memory_id: Optional[UUID] = None

    # 5. Confidence / abstention telemetry (ADR-0003 · ADR-0007 §D6)
    request_id: Optional[str] = None
    abstention_reason: Optional[str] = None
    abstention_layer: Optional[str] = None
    agent_status: Optional[str] = None
    agent_error_code: Optional[str] = None

    # Rows that fed this record, for auditability.
    memory_ids: list[UUID] = field(default_factory=list)

    @property
    def abs_pct_error(self) -> Optional[float]:
        """|predicted − actual| / actual, in %. None until both legs exist.

        Single-decision error, not a MAPE: the Level-1 KPI is aggregated
        elsewhere (`ReceiptsService.weekly_digest`, `kpi_daily`).
        """
        if self.predicted_covers is None or not self.actual_covers:
            return None
        return round(
            abs(float(self.predicted_covers) - float(self.actual_covers))
            / float(self.actual_covers) * 100,
            2,
        )

    @property
    def is_closed(self) -> bool:
        """True when the loop is complete: answered *and* measured."""
        return self.manager_response is not None and self.actual_covers is not None


class DecisionLedgerService:
    """Read-only queries over the consolidated decision loop."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_decision(
        self,
        recommendation_id: UUID | str,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[DecisionRecord]:
        """AC3 — "for recommendation X, what did the manager answer and what
        actually happened".

        ``tenant_id`` is an optional isolation guard: pass it on any path where
        the caller's tenant is known, so a mis-supplied id cannot read another
        property's decision.
        """
        rec_uuid = recommendation_id if isinstance(recommendation_id, UUID) else UUID(str(recommendation_id))

        stmt = (
            select(StaffingRecommendation, DemandAnomaly)
            .outerjoin(DemandAnomaly, DemandAnomaly.id == StaffingRecommendation.anomaly_id)
            .where(StaffingRecommendation.id == rec_uuid)
        )
        if tenant_id is not None:
            stmt = stmt.where(StaffingRecommendation.tenant_id == tenant_id)

        row = (await self._db.execute(stmt)).first()
        if row is None:
            return None

        rec, anomaly = row
        memories = await self._memories_for(rec.id)
        return await self._assemble(rec, anomaly, memories)

    async def list_decisions(
        self,
        tenant_id: str,
        *,
        limit: int = 50,
        closed_only: bool = False,
    ) -> list[DecisionRecord]:
        """Most recent decisions for a property, newest first.

        ``closed_only`` keeps only loops that were both answered and measured —
        the population any honest claim about decision quality has to be built
        on.
        """
        limit = max(1, min(500, int(limit)))

        stmt = (
            select(StaffingRecommendation, DemandAnomaly)
            .outerjoin(DemandAnomaly, DemandAnomaly.id == StaffingRecommendation.anomaly_id)
            .where(StaffingRecommendation.tenant_id == tenant_id)
            .order_by(StaffingRecommendation.created_at.desc())
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).all()
        if not rows:
            return []

        memories_by_rec = await self._memories_for_many([rec.id for rec, _ in rows])

        records = [
            await self._assemble(rec, anomaly, memories_by_rec.get(rec.id, []))
            for rec, anomaly in rows
        ]
        return [r for r in records if r.is_closed] if closed_only else records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _memories_for(self, rec_id: UUID) -> list[OperationalMemory]:
        result = await self._db.execute(
            select(OperationalMemory)
            .where(OperationalMemory.recommendation_id == rec_id)
            .order_by(OperationalMemory.created_at.desc())
        )
        return list(result.scalars().all())

    async def _memories_for_many(
        self, rec_ids: list[UUID]
    ) -> dict[UUID, list[OperationalMemory]]:
        """One query for the whole page — avoids N+1 on list_decisions."""
        if not rec_ids:
            return {}
        result = await self._db.execute(
            select(OperationalMemory)
            .where(OperationalMemory.recommendation_id.in_(rec_ids))
            .order_by(OperationalMemory.created_at.desc())
        )
        grouped: dict[UUID, list[OperationalMemory]] = {}
        for mem in result.scalars().all():
            grouped.setdefault(mem.recommendation_id, []).append(mem)
        return grouped

    async def _assemble(
        self,
        rec: StaffingRecommendation,
        anomaly: Optional[DemandAnomaly],
        memories: list[OperationalMemory],
    ) -> DecisionRecord:
        # Memories arrive newest-first, so the first match of each type is the
        # latest one.
        feedback = next((m for m in memories if m.memory_type == _FEEDBACK_TYPE), None)
        ground_truth = next((m for m in memories if m.memory_type == _GROUND_TRUTH_TYPE), None)

        # The dashboard column wins over the WhatsApp memory row: it is the
        # explicit accept/reject, whereas the memory row also covers "modified".
        if rec.action is not None:
            manager_response = rec.action
            manager_responded_at = rec.actioned_at
            channel: Optional[str] = "dashboard"
        elif feedback is not None:
            manager_response = feedback.manager_feedback
            manager_responded_at = feedback.created_at
            channel = "whatsapp"
        else:
            manager_response = manager_responded_at = channel = None

        request_id = (feedback.request_id if feedback else None) or (
            ground_truth.request_id if ground_truth else None
        ) or None

        action_log = await self._action_log_for(rec.tenant_id, request_id)

        return DecisionRecord(
            recommendation_id=rec.id,
            tenant_id=rec.tenant_id,
            property_id=rec.property_id,
            anomaly_id=anomaly.id if anomaly else None,
            triggering_factors=anomaly.triggering_factors if anomaly else None,
            deviation_pct=_as_float(anomaly.deviation_pct) if anomaly else None,
            direction=anomaly.direction if anomaly else None,
            context_detected_at=anomaly.detected_at if anomaly else None,
            recommended_at=rec.created_at,
            message_text=rec.message_text,
            recommended_headcount=rec.recommended_headcount,
            predicted_covers=_as_float(rec.predicted_covers),
            window_start=rec.window_start,
            window_end=rec.window_end,
            dispatched_at=rec.dispatched_at,
            dispatch_channel=rec.dispatch_channel,
            manager_response=manager_response,
            manager_responded_at=manager_responded_at,
            manager_response_channel=channel,
            feedback_memory_id=feedback.id if feedback else None,
            feedback_reflection=feedback.reflection if feedback else None,
            actual_covers=_as_float(rec.actual_covers),
            actual_covers_source=rec.actual_covers_source,
            actual_covers_at=rec.actual_covers_at,
            outcome_memory_id=ground_truth.id if ground_truth else None,
            request_id=request_id,
            abstention_reason=action_log.abstention_reason if action_log else None,
            abstention_layer=action_log.abstention_layer if action_log else None,
            agent_status=action_log.status if action_log else None,
            agent_error_code=action_log.error_code if action_log else None,
            memory_ids=[m.id for m in memories],
        )

    async def _action_log_for(
        self, tenant_id: str, request_id: Optional[str]
    ) -> Optional[AgentActionLog]:
        """Latest agent call for this turn — carries the typed abstention /
        guardrail reason (NFR2, Décision #27). Non-blocking: telemetry is
        supporting evidence, never the reason a ledger read fails."""
        if not request_id:
            return None
        try:
            result = await self._db.execute(
                select(AgentActionLog)
                .where(AgentActionLog.request_id == request_id)
                .where(AgentActionLog.hotel_id == tenant_id)
                .order_by(AgentActionLog.created_at.desc())
                .limit(1)
            )
            return result.scalars().first()
        except Exception as exc:  # noqa: BLE001 — partitioned table, best effort
            logger.warning("decision_ledger: action-log lookup failed: %s", exc)
            return None


def _as_float(value: Any) -> Optional[float]:
    """Numeric columns come back as Decimal on Postgres, float on SQLite."""
    return None if value is None else float(value)

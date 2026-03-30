"""Recommendation Formatter Service.

Converts ROI-positive demand anomalies into plain-text staffing directives
that are ready to dispatch to hotel F&B managers.

Story 3.3c (HOS-23): Format Staffing Recommendations for Dispatch.

Status transitions:
    roi_positive  →  (format)  →  ready_to_push

Architecture constraints:
- All business logic lives here (Fat Backend).
- Routes and workers delegate to this service; no logic in route handlers.
- Uses AsyncSession (sqlalchemy.ext.asyncio) with raw text() queries to match
  the existing codebase pattern established in stories 3.3a/3.3b.
- Idempotent: INSERT with unique anomaly_id constraint prevents duplicates
  on re-runs (AC #8).
[Source: architecture.md#Architectural-Boundaries, story 3.3c HOS-23]
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.roi_calculator import ROICalculatorService

logger = logging.getLogger(__name__)

_FALLBACK_FACTOR = "demand anomaly detected"

# ---------------------------------------------------------------------------
# Pure formatting helpers (stateless, easily unit-testable)
# ---------------------------------------------------------------------------


def _extract_triggering_factor(triggering_factors: Any) -> str:
    """Pick the highest-weight factor label from a triggering_factors payload.

    Expected shape: list of dicts with at least a ``label`` key and an
    optional numeric ``weight`` key, e.g.::

        [{"label": "Tech conference nearby", "weight": 0.9}]

    Falls back to *_FALLBACK_FACTOR* when nothing useful is found.
    """
    if not triggering_factors:
        return _FALLBACK_FACTOR

    candidates: List[Dict[str, Any]] = []
    if isinstance(triggering_factors, list):
        candidates = triggering_factors
    elif isinstance(triggering_factors, dict):
        candidates = [triggering_factors]

    if not candidates:
        return _FALLBACK_FACTOR

    best = max(candidates, key=lambda f: float(f.get("weight", 0)))
    return best.get("label") or _FALLBACK_FACTOR


def format_message(
    direction: str,
    headcount: int,
    revenue_opp: float,
    labor_cost: float,
    window_start: datetime,
    window_end: datetime,
    factor: str,
) -> str:
    """Build the plain-text staffing directive.

    For **surges** (direction == "surge"):
        "Add {headcount} staff to capture an estimated £{revenue:.0f} in
        additional covers between {HH:MM}–{HH:MM}. Est. additional labour
        cost: £{labor:.0f}. Trigger: {factor}."

    For **lulls**:
        "Consider reducing staffing by {abs(headcount)} for the
        {HH:MM}–{HH:MM} window due to below-average demand.
        Trigger: {factor}."
    """
    start_str = window_start.strftime("%H:%M")
    end_str = window_end.strftime("%H:%M")

    if direction == "surge":
        return (
            f"Add {headcount} staff to capture an estimated "
            f"£{revenue_opp:.0f} in additional covers between "
            f"{start_str}–{end_str}. "
            f"Est. additional labour cost: £{labor_cost:.0f}. "
            f"Trigger: {factor}."
        )
    else:
        # lull — recommend reducing headcount; revenue_opp not applicable
        abs_hc = abs(headcount)
        return (
            f"Consider reducing staffing by {abs_hc} for the "
            f"{start_str}–{end_str} window due to below-average demand. "
            f"Trigger: {factor}."
        )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class RecommendationFormatterService:
    """Formats ROI-positive anomalies into ready-to-push recommendations.

    Designed to run either:
    * After the ROI calculator (auto-chain in the worker — AC #6), or
    * On demand via POST /api/v1/anomalies/format (manual trigger — AC #7).
    """

    _roi_service = ROICalculatorService()

    # ------------------------------------------------------------------
    # Single-property entry point
    # ------------------------------------------------------------------

    async def run_for_property(
        self, db: AsyncSession, property_id: uuid.UUID
    ) -> int:
        """Fetch all *roi_positive* anomalies for *property_id*, format them,
        upsert a StaffingRecommendation row, and transition the anomaly status
        to *ready_to_push*.

        Returns:
            Number of recommendations created (skips already-existing ones
            to preserve idempotency).
        """
        result = await db.execute(
            text(
                """
                SELECT id, tenant_id, property_id,
                       direction, triggering_factors,
                       roi_revenue_opp, roi_labor_cost, roi_net,
                       window_start, window_end,
                       deviation_pct
                FROM demand_anomalies
                WHERE property_id = :property_id
                  AND status = 'roi_positive'
                ORDER BY window_start
                """
            ),
            {"property_id": str(property_id)},
        )
        rows = result.fetchall()

        if not rows:
            logger.debug(
                "recommendation_formatter: no roi_positive anomalies for "
                "property %s",
                property_id,
            )
            return 0

        created = 0
        for row in rows:
            did_create = await self._format_and_upsert(db, row)
            if did_create:
                created += 1

        await db.commit()
        logger.info(
            "recommendation_formatter: created %d recommendations for "
            "property %s",
            created,
            property_id,
        )
        return created

    # ------------------------------------------------------------------
    # Full cross-tenant scan
    # ------------------------------------------------------------------

    async def run_full_scan(self, db: AsyncSession) -> int:
        """Process every *roi_positive* anomaly across all properties.

        Used by the worker's scheduled/chained invocation (AC #6).

        Returns:
            Total number of recommendations created in this run.
        """
        result = await db.execute(
            text(
                """
                SELECT id, tenant_id, property_id,
                       direction, triggering_factors,
                       roi_revenue_opp, roi_labor_cost, roi_net,
                       window_start, window_end,
                       deviation_pct
                FROM demand_anomalies
                WHERE status = 'roi_positive'
                ORDER BY window_start
                """
            )
        )
        rows = result.fetchall()

        if not rows:
            logger.info("recommendation_formatter: no roi_positive anomalies to format")
            return 0

        created = 0
        for row in rows:
            did_create = await self._format_and_upsert(db, row)
            if did_create:
                created += 1

        await db.commit()
        logger.info(
            "recommendation_formatter: full scan complete — %d recommendations created",
            created,
        )
        return created

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _format_and_upsert(self, db: AsyncSession, row: Any) -> bool:
        """Format one anomaly row and upsert its recommendation.

        Args:
            db:  Async SQLAlchemy session.
            row: Row tuple from the SELECT query in run_for_property /
                 run_full_scan.

        Returns:
            True if a new recommendation was created, False if it already
            existed (idempotency guard).
        """
        (
            anomaly_id,
            tenant_id,
            property_id,
            direction,
            triggering_factors_raw,
            roi_revenue_opp,
            roi_labor_cost,
            roi_net,
            window_start,
            window_end,
            deviation_pct,
        ) = row

        # Guard: window times are required
        if window_start is None or window_end is None:
            logger.warning(
                "recommendation_formatter: anomaly %s has no window — skipping",
                anomaly_id,
            )
            return False

        # Idempotency check: skip if recommendation already exists
        existing = await db.execute(
            text(
                "SELECT id FROM staffing_recommendations WHERE anomaly_id = :anomaly_id LIMIT 1"
            ),
            {"anomaly_id": str(anomaly_id)},
        )
        if existing.fetchone():
            logger.debug(
                "recommendation_formatter: recommendation already exists for "
                "anomaly %s — skipping",
                anomaly_id,
            )
            return False

        # Derive values
        # triggering_factors may be a Python list (asyncpg) or a JSON string
        if isinstance(triggering_factors_raw, str):
            try:
                triggering_factors = json.loads(triggering_factors_raw)
            except (ValueError, TypeError):
                triggering_factors = []
        else:
            triggering_factors = triggering_factors_raw or []

        factor = _extract_triggering_factor(triggering_factors)

        headcount = self._roi_service.recommended_headcount(
            float(deviation_pct) if deviation_pct is not None else 0.0
        )
        revenue_opp_f = float(roi_revenue_opp) if roi_revenue_opp is not None else 0.0
        labor_cost_f = float(roi_labor_cost) if roi_labor_cost is not None else 0.0
        roi_net_f = float(roi_net) if roi_net is not None else 0.0

        # Normalise window datetimes to plain datetime for strftime
        ws = window_start if isinstance(window_start, datetime) else datetime.fromisoformat(str(window_start))
        we = window_end if isinstance(window_end, datetime) else datetime.fromisoformat(str(window_end))

        message = format_message(
            direction=direction,
            headcount=headcount,
            revenue_opp=revenue_opp_f,
            labor_cost=labor_cost_f,
            window_start=ws,
            window_end=we,
            factor=factor,
        )

        rec_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)

        # Insert recommendation
        await db.execute(
            text(
                """
                INSERT INTO staffing_recommendations
                    (id, tenant_id, property_id, anomaly_id,
                     message_text, triggering_factor, recommended_headcount,
                     window_start, window_end,
                     roi_net, roi_labor_cost,
                     status, created_at, updated_at)
                VALUES
                    (:id, :tenant_id, :property_id, :anomaly_id,
                     :message_text, :triggering_factor, :recommended_headcount,
                     :window_start, :window_end,
                     :roi_net, :roi_labor_cost,
                     'ready_to_push', :now, :now)
                ON CONFLICT (anomaly_id) DO NOTHING
                """
            ),
            {
                "id": rec_id,
                "tenant_id": str(tenant_id),
                "property_id": str(property_id),
                "anomaly_id": str(anomaly_id),
                "message_text": message,
                "triggering_factor": factor,
                "recommended_headcount": headcount,
                "window_start": ws.isoformat(),
                "window_end": we.isoformat(),
                "roi_net": roi_net_f,
                "roi_labor_cost": labor_cost_f,
                "now": now.isoformat(),
            },
        )

        # Transition anomaly status: roi_positive → ready_to_push (AC #5)
        await db.execute(
            text(
                """
                UPDATE demand_anomalies
                SET status = 'ready_to_push',
                    recommendation_text = :message_text
                WHERE id = :anomaly_id
                """
            ),
            {"message_text": message, "anomaly_id": str(anomaly_id)},
        )

        logger.info(
            "recommendation_formatter: formatted recommendation for anomaly %s "
            "(property %s, direction=%s, headcount=%d)",
            anomaly_id,
            property_id,
            direction,
            headcount,
        )
        return True

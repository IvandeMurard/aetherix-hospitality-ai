"""ROI Calculator Service.

Implements Story 3.3b: Calculate Financial ROI for Detected Anomalies.

Business logic:
  revenue_opportunity = captation_rate × expected_additional_covers × avg_spend_per_cover
  labor_cost          = recommended_headcount × hourly_rate × window_duration_hours
  net_roi             = revenue_opportunity - labor_cost

  If net_roi > 0  → anomaly status updated to 'roi_positive'
  Otherwise       → anomaly status remains 'detected'

For lulls (direction == 'lull'):
  revenue_opp = 0, labor_cost = 0, net_roi = 0  (no staffing action required)

Headcount scale (deviation_pct from baseline):
  20 – 35 %  →  1 extra head
  35 – 55 %  →  2 extra heads
  55 – 80 %  →  3 extra heads
  > 80 %     →  4 extra heads (max)
  lull / ≤ 0 →  0

Architecture constraints:
- All business logic lives here (Fat Backend).
- Routes and workers delegate to this service; no logic in route handlers.
- Uses AsyncSession (sqlalchemy.ext.asyncio) throughout.
- Idempotent: re-running updates existing ROI fields without creating
  duplicates (AC 8).
[Source: story 3.3b, architecture.md#Architectural-Boundaries]
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    DEFAULT_AVG_SPEND_PER_COVER,
    DEFAULT_CAPTATION_RATE,
    DEFAULT_STAFF_HOURLY_RATE,
)

logger = logging.getLogger(__name__)

# Window duration used for labor cost calculation (hours)
_WINDOW_HOURS: float = 4.0


class ROICalculatorService:
    """Financial ROI calculator for demand anomalies.

    All public methods accept an AsyncSession.  The session is NOT committed
    inside helpers; callers are responsible for committing or the top-level
    ``run_for_property`` / ``run_full_scan`` methods handle it.
    """

    # ------------------------------------------------------------------
    # Headcount Scale (AC: Headcount Scale table)
    # ------------------------------------------------------------------
    @staticmethod
    def recommended_headcount(deviation_pct: float) -> int:
        """Map a deviation percentage to additional headcount required.

        Args:
            deviation_pct: Signed deviation from baseline (positive = surge,
                           negative or zero = lull).

        Returns:
            Number of additional staff members required (0 for lulls).
        """
        if deviation_pct <= 0:
            # Lull — no additional staffing action
            return 0
        if deviation_pct < 35:
            return 1
        if deviation_pct < 55:
            return 2
        if deviation_pct < 80:
            return 3
        return 4  # > 80 % — capped at 4

    # ------------------------------------------------------------------
    # Core calculation
    # ------------------------------------------------------------------
    def calculate_for_anomaly(
        self,
        *,
        direction: str,
        deviation_pct: float,
        expected_demand: float,
        baseline_demand: float,
        avg_spend_per_cover: float,
        staff_hourly_rate: float,
        captation_rate: float = DEFAULT_CAPTATION_RATE,
        window_hours: float = _WINDOW_HOURS,
    ) -> Dict[str, float]:
        """Calculate ROI metrics for a single anomaly.

        Args:
            direction:          'surge' or 'lull'.
            deviation_pct:      (expected - baseline) / baseline * 100.
            expected_demand:    Projected demand for the window.
            baseline_demand:    Historical baseline demand for the window.
            avg_spend_per_cover: Average revenue per cover (£).
            staff_hourly_rate:  Hourly cost per additional staff member (£).
            captation_rate:     Fraction of extra demand the property can capture.
            window_hours:       Duration of the anomaly window in hours (default 4).

        Returns:
            dict with keys: revenue_opp, labor_cost, net_roi
        """
        if direction == "lull":
            return {"revenue_opp": 0.0, "labor_cost": 0.0, "net_roi": 0.0}

        # Surge: calculate additional covers above baseline
        expected_additional_covers = max(0.0, expected_demand - baseline_demand)

        revenue_opp = captation_rate * expected_additional_covers * avg_spend_per_cover

        headcount = self.recommended_headcount(deviation_pct)
        labor_cost = headcount * staff_hourly_rate * window_hours

        net_roi = revenue_opp - labor_cost

        return {
            "revenue_opp": round(revenue_opp, 2),
            "labor_cost": round(labor_cost, 2),
            "net_roi": round(net_roi, 2),
        }

    # ------------------------------------------------------------------
    # Property-level runner
    # ------------------------------------------------------------------
    async def run_for_property(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
    ) -> int:
        """Calculate ROI for all 'detected' anomalies for a single property.

        Fetches the property's rate overrides (or uses system defaults) then
        iterates every anomaly with status='detected', computes ROI, writes
        back roi_revenue_opp, roi_labor_cost, roi_net, and updates status to
        'roi_positive' when net_roi > 0.

        Args:
            db:          Async SQLAlchemy session.
            property_id: UUID of the property to process.

        Returns:
            Number of anomaly rows updated.
        """
        # 1. Resolve property rate config
        avg_spend, hourly_rate = await self._get_property_rates(db, property_id)

        # 2. Fetch detected anomalies for this property
        result = await db.execute(
            text(
                """
                SELECT id, direction, deviation_pct, expected_demand, baseline_demand
                FROM demand_anomalies
                WHERE property_id = :property_id
                  AND status = 'detected'
                ORDER BY window_start
                """
            ),
            {"property_id": str(property_id)},
        )
        rows = result.fetchall()

        if not rows:
            logger.debug(
                "roi_calculator: no 'detected' anomalies for property %s", property_id
            )
            return 0

        updated = 0
        for row in rows:
            anomaly_id = row[0]
            direction = row[1]
            deviation_pct = float(row[2]) if row[2] is not None else 0.0
            expected_demand = float(row[3]) if row[3] is not None else 0.0
            baseline_demand = float(row[4]) if row[4] is not None else 0.0

            metrics = self.calculate_for_anomaly(
                direction=direction,
                deviation_pct=deviation_pct,
                expected_demand=expected_demand,
                baseline_demand=baseline_demand,
                avg_spend_per_cover=avg_spend,
                staff_hourly_rate=hourly_rate,
            )

            new_status = (
                "roi_positive" if metrics["net_roi"] > 0 else "detected"
            )

            await db.execute(
                text(
                    """
                    UPDATE demand_anomalies
                    SET roi_revenue_opp = :revenue_opp,
                        roi_labor_cost  = :labor_cost,
                        roi_net         = :net_roi,
                        status          = :status
                    WHERE id = :id
                    """
                ),
                {
                    "revenue_opp": metrics["revenue_opp"],
                    "labor_cost": metrics["labor_cost"],
                    "net_roi": metrics["net_roi"],
                    "status": new_status,
                    "id": str(anomaly_id),
                },
            )
            updated += 1

        await db.commit()
        logger.info(
            "roi_calculator: updated %d anomalies for property %s",
            updated,
            property_id,
        )
        return updated

    # ------------------------------------------------------------------
    # Full cross-tenant scan
    # ------------------------------------------------------------------
    async def run_full_scan(self, db: AsyncSession) -> None:
        """Run ROI calculation for all active properties in parallel.

        Uses asyncio.gather to match the parallelism pattern of the anomaly
        detection service (NFR5).

        Args:
            db: Async SQLAlchemy session.
        """
        try:
            result = await db.execute(
                text("SELECT id FROM properties WHERE is_active = TRUE")
            )
            property_ids = [row[0] for row in result.fetchall()]
        except Exception:
            logger.exception(
                "roi_calculator: failed to fetch active properties"
            )
            return

        if not property_ids:
            logger.info("roi_calculator: no active properties, skipping")
            return

        tasks = [
            self.run_for_property(db, property_id=pid)
            for pid in property_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        error_count = sum(1 for r in results if isinstance(r, Exception))
        if error_count:
            logger.warning(
                "roi_calculator: %d/%d property runs raised exceptions",
                error_count,
                len(tasks),
            )
        for exc in results:
            if isinstance(exc, Exception):
                logger.error("roi_calculator property error: %s", exc)

        total_updated = sum(r for r in results if isinstance(r, int))
        logger.info(
            "roi_calculator: full scan complete — %d anomalies updated across "
            "%d properties",
            total_updated,
            len(property_ids),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    async def _get_property_rates(
        self,
        db: AsyncSession,
        property_id: uuid.UUID,
    ) -> tuple[float, float]:
        """Return (avg_spend_per_cover, staff_hourly_rate) for a property.

        Falls back to system defaults (from config.py) when the columns are
        NULL or when the properties table cannot be queried.
        """
        try:
            result = await db.execute(
                text(
                    """
                    SELECT avg_spend_per_cover, staff_hourly_rate
                    FROM properties
                    WHERE id = :property_id
                    LIMIT 1
                    """
                ),
                {"property_id": str(property_id)},
            )
            row = result.fetchone()
            if row:
                avg_spend = (
                    float(row[0])
                    if row[0] is not None
                    else DEFAULT_AVG_SPEND_PER_COVER
                )
                hourly_rate = (
                    float(row[1])
                    if row[1] is not None
                    else DEFAULT_STAFF_HOURLY_RATE
                )
                return avg_spend, hourly_rate
        except Exception:
            logger.debug(
                "roi_calculator: properties rate lookup failed for %s — "
                "using defaults",
                property_id,
            )

        return DEFAULT_AVG_SPEND_PER_COVER, DEFAULT_STAFF_HOURLY_RATE

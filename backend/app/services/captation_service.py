"""Captation rate baseline calculator.

Story 2.4 — Calculate Baseline Captation Rates (FR3).

Captation rate = F&B revenue per occupied room.

The service:
1. Loads all PMSSyncLog rows for a tenant where occupancy > 0.
2. Computes the overall average captation rate.
3. Computes day-of-week adjustment factors (ratio of each DoW's average
   to the overall average).
4. Computes monthly (seasonal) adjustment factors.
5. Upserts the result into CaptationBaseline.
6. Exposes a lightweight ``get_baseline`` helper for Story 3.3a.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import CaptationBaseline, PMSSyncLog

logger = logging.getLogger(__name__)

# Minimum number of data points before we attempt a calculation.
MIN_DATA_POINTS = 7


class InsufficientDataError(ValueError):
    """Raised when there are not enough non-zero occupancy records."""


class CaptationService:
    """Calculates and stores captation rate baselines per tenant."""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def calculate_baseline(
        self, tenant_id: str, db: AsyncSession
    ) -> CaptationBaseline:
        """Calculate (or recalculate) the captation baseline for *tenant_id*.

        Fetches all PMSSyncLog rows with occupancy > 0, runs the stats, then
        upserts a single ``CaptationBaseline`` row for the tenant.

        Raises:
            InsufficientDataError: if fewer than MIN_DATA_POINTS valid rows exist.
        """
        rows = await self._load_sync_logs(tenant_id, db)

        if len(rows) < MIN_DATA_POINTS:
            raise InsufficientDataError(
                f"Tenant '{tenant_id}' has only {len(rows)} valid PMS sync records "
                f"(minimum required: {MIN_DATA_POINTS})."
            )

        df = self._to_dataframe(rows)
        avg_rate = self._compute_overall_avg(df)
        dow_factors = self._compute_dow_factors(df, avg_rate)
        monthly_factors = self._compute_monthly_factors(df, avg_rate)

        period_start = df["sync_date"].min().date()
        period_end = df["sync_date"].max().date()

        baseline = await self._upsert_baseline(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            avg_fb_revenue_per_room=avg_rate,
            dow_factors=dow_factors,
            monthly_factors=monthly_factors,
            data_points_count=len(df),
            db=db,
        )

        logger.info(
            "Captation baseline computed for tenant=%s  avg=%.2f  points=%d",
            tenant_id,
            avg_rate,
            len(df),
        )
        return baseline

    async def get_baseline(
        self, tenant_id: str, db: AsyncSession
    ) -> Optional[CaptationBaseline]:
        """Return the most recently computed baseline for *tenant_id*, or None."""
        result = await db.execute(
            select(CaptationBaseline)
            .where(CaptationBaseline.tenant_id == tenant_id)
            .order_by(CaptationBaseline.computed_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_sync_logs(
        self, tenant_id: str, db: AsyncSession
    ) -> list[PMSSyncLog]:
        """Fetch all PMSSyncLog rows for the tenant that have occupancy > 0."""
        result = await db.execute(
            select(PMSSyncLog)
            .where(
                PMSSyncLog.tenant_id == tenant_id,
                PMSSyncLog.occupancy > 0,
                PMSSyncLog.fb_revenue.isnot(None),
            )
            .order_by(PMSSyncLog.sync_date)
        )
        return list(result.scalars().all())

    def _to_dataframe(self, rows: list[PMSSyncLog]) -> pd.DataFrame:
        """Convert ORM rows to a pandas DataFrame with derived columns."""
        data = [
            {
                "sync_date": pd.Timestamp(row.sync_date),
                "occupancy": row.occupancy,
                "fb_revenue": row.fb_revenue,
            }
            for row in rows
        ]
        df = pd.DataFrame(data)
        # Core metric per record
        df["captation_rate"] = df["fb_revenue"] / df["occupancy"]
        # Calendar helpers
        df["dow"] = df["sync_date"].dt.dayofweek  # 0=Monday … 6=Sunday
        df["month"] = df["sync_date"].dt.month     # 1–12
        return df

    def _compute_overall_avg(self, df: pd.DataFrame) -> float:
        return float(df["captation_rate"].mean())

    def _compute_dow_factors(
        self, df: pd.DataFrame, overall_avg: float
    ) -> dict[str, float]:
        """Return day-of-week multipliers keyed by weekday number as a string."""
        if overall_avg == 0:
            return {str(d): 1.0 for d in range(7)}

        dow_avg = df.groupby("dow")["captation_rate"].mean()
        factors: dict[str, float] = {}
        for d in range(7):
            if d in dow_avg.index:
                factors[str(d)] = round(float(dow_avg[d]) / overall_avg, 4)
            else:
                # No data for this weekday — use neutral factor
                factors[str(d)] = 1.0
        return factors

    def _compute_monthly_factors(
        self, df: pd.DataFrame, overall_avg: float
    ) -> dict[str, float]:
        """Return monthly multipliers keyed by month number as a string."""
        if overall_avg == 0:
            return {str(m): 1.0 for m in range(1, 13)}

        month_avg = df.groupby("month")["captation_rate"].mean()
        factors: dict[str, float] = {}
        for m in range(1, 13):
            if m in month_avg.index:
                factors[str(m)] = round(float(month_avg[m]) / overall_avg, 4)
            else:
                factors[str(m)] = 1.0
        return factors

    async def _upsert_baseline(
        self,
        *,
        tenant_id: str,
        period_start: date,
        period_end: date,
        avg_fb_revenue_per_room: float,
        dow_factors: dict,
        monthly_factors: dict,
        data_points_count: int,
        db: AsyncSession,
    ) -> CaptationBaseline:
        """Insert or update the single baseline row for this tenant."""
        result = await db.execute(
            select(CaptationBaseline)
            .where(CaptationBaseline.tenant_id == tenant_id)
            .limit(1)
        )
        existing = result.scalars().first()

        if existing:
            existing.period_start = period_start
            existing.period_end = period_end
            existing.avg_fb_revenue_per_room = avg_fb_revenue_per_room
            existing.dow_factors = dow_factors
            existing.monthly_factors = monthly_factors
            existing.data_points_count = data_points_count
            existing.computed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(existing)
            return existing

        baseline = CaptationBaseline(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            avg_fb_revenue_per_room=avg_fb_revenue_per_room,
            dow_factors=dow_factors,
            monthly_factors=monthly_factors,
            data_points_count=data_points_count,
        )
        db.add(baseline)
        await db.commit()
        await db.refresh(baseline)
        return baseline

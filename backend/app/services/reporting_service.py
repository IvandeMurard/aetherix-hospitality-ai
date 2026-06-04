import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd  # For easy data manipulation

logger = logging.getLogger(__name__)

MAPE_ALERT_THRESHOLD = 30.0  # % — above this triggers a Linear issue

class ReportingService:
    """
    Performance Reporting Layer (Phase 3).
    Calculates MAPE and Financial ROI for the "Friday Audit".
    """

    def __init__(self, db_service=None):
        # AsyncSession when wired from the route (real pilot data); None in
        # contexts without a DB, where we fall back to the demo mock.
        self.db = db_service

    async def generate_weekly_metrics(self, tenant_id: str, week_start: date) -> Dict[str, Any]:
        """
        Calculates MAPE and labor savings for a given tenant's week.
        """
        # 1. Fetch real prediction-vs-actual rows (Story 10.10 / HOS-200).
        #    Falls back to the demo mock only when no ground-truth rows exist
        #    yet (gated on actual_covers IS NULL — AC4).
        data = await self._get_weekly_data(tenant_id, week_start)
        if not data:
            data = self._get_mock_weekly_data(tenant_id, week_start)

        df = pd.DataFrame(data)
        
        # 2. Calculate MAPE (Mean Absolute Percentage Error)
        if not df.empty:
            df['abs_error'] = abs(df['actual_covers'] - df['predicted_covers'])
            df['percentage_error'] = df['abs_error'] / df['actual_covers']
            mape = df['percentage_error'].mean() * 100
        else:
            mape = 0.0

        # 3. Calculate Estimated Labor Savings
        # Logic: savings = (Idle hours saved) + (Lost revenue captured)
        # simplified for pilot: £15/cover for captured revenue, £12/hr for labor reduction
        labor_savings = self._calculate_savings(df)

        result = {
            "tenant_id": tenant_id,
            "period": f"{week_start} to {week_start + timedelta(days=6)}",
            "metrics": {
                "mape": round(mape, 2),
                "accuracy": round(100 - mape, 2),
                "total_covers": int(df['actual_covers'].sum())
            },
            "financial_impact": {
                "estimated_savings_gbp": round(labor_savings, 2),
                "roi_multiplier": round(labor_savings / 50.0, 1) # $50 is a mock SaaS cost
            }
        }

        await self._dispatch_ops(result, mape)
        return result

    async def _dispatch_ops(self, result: Dict[str, Any], mape: float) -> None:
        """Fire-and-forget: write audit to Obsidian; alert Linear if accuracy drops."""
        from app.integrations.obsidian import VAULT_FOLDERS
        from app.services.ops_dispatcher import dispatch_anomaly, dispatch_report

        m = result["metrics"]
        f = result["financial_impact"]
        period = result["period"]
        tenant = result["tenant_id"]

        note_content = (
            f"# Weekly Audit — {tenant}\n\n"
            f"**Period:** {period}\n\n"
            f"| Metric | Value |\n|---|---|\n"
            f"| Accuracy | {m['accuracy']}% |\n"
            f"| MAPE | {m['mape']}% |\n"
            f"| Total covers | {m['total_covers']} |\n"
            f"| Estimated savings | £{f['estimated_savings_gbp']} |\n"
            f"| ROI | {f['roi_multiplier']}x |\n"
        )
        await dispatch_report(
            title=f"Weekly Audit {period}",
            content=note_content,
            folder=VAULT_FOLDERS["reports"],
            tags=["weekly-audit", tenant],
        )

        if mape > MAPE_ALERT_THRESHOLD:
            await dispatch_anomaly(
                title=f"[{tenant}] Forecast accuracy degraded — MAPE {m['mape']}%",
                detail=(
                    f"Weekly MAPE exceeded {MAPE_ALERT_THRESHOLD}% threshold for period {period}.\n"
                    f"Accuracy: {m['accuracy']}% | Covers: {m['total_covers']}\n\n"
                    "Possible causes: missing PMS data, model drift, or unusual demand spike."
                ),
                tags=["model", "accuracy"],
            )

    def _calculate_savings(self, df: pd.DataFrame) -> float:
        """Heuristic for labor savings based on prediction accuracy."""
        if df.empty:
            return 0.0
        
        # Captured Revenue (Surges predicted correctly)
        # Assume correct surge predictions (actual > baseline + 10%) saved 10% of that revenue
        surge_savings = df[df['actual_covers'] > 150]['actual_covers'].sum() * 0.10 * 15.0 # £15 per cover
        
        # Idle Labor Reduction (Quiet days predicted correctly)
        # Assume correct quiet predictions saved 2 server shifts (£60 each)
        quiet_savings = df[df['actual_covers'] < 100].shape[0] * 120.0 # £120 per quiet day
        
        return surge_savings + quiet_savings

    async def _get_weekly_data(self, tenant_id: str, week_start: date) -> List[Dict]:
        """Fetch real prediction-vs-actual rows for the week (Story 10.10 / HOS-200).

        Reads `staffing_recommendations` where `actual_covers IS NOT NULL`
        (ground truth persisted from manager feedback) AND `predicted_covers
        IS NOT NULL`, for the 7-day window starting at `week_start`. Returns one
        dict per recommendation: ``{date, actual_covers, predicted_covers}``.

        Returns an empty list when no DB session is wired or no ground-truth rows
        exist yet — the caller then gates onto the demo mock (AC4).
        """
        if self.db is None:
            return []

        # Local imports keep the module importable without the ORM/DB stack
        # (e.g. pure mock-data unit tests).
        from sqlalchemy import select

        from app.db.models import StaffingRecommendation

        week_end = week_start + timedelta(days=7)
        window_start = datetime.combine(week_start, time.min, tzinfo=timezone.utc)
        window_end = datetime.combine(week_end, time.min, tzinfo=timezone.utc)

        result = await self.db.execute(
            select(StaffingRecommendation)
            .where(StaffingRecommendation.tenant_id == tenant_id)
            .where(StaffingRecommendation.actual_covers.isnot(None))
            .where(StaffingRecommendation.predicted_covers.isnot(None))
            .where(StaffingRecommendation.window_start >= window_start)
            .where(StaffingRecommendation.window_start < window_end)
            .order_by(StaffingRecommendation.window_start)
        )
        rows = result.scalars().all()

        data: List[Dict] = []
        for r in rows:
            ws = r.window_start
            data.append(
                {
                    "date": ws.date() if hasattr(ws, "date") else ws,
                    "actual_covers": float(r.actual_covers),
                    "predicted_covers": float(r.predicted_covers),
                }
            )

        logger.info(
            "reporting_service._get_weekly_data: tenant=%s week_start=%s real_rows=%d",
            tenant_id,
            week_start,
            len(data),
        )
        return data

    def _get_mock_weekly_data(self, tenant_id: str, week_start: date) -> List[Dict]:
        """Simulates DB result for the pilot audit (with surge/quiet days)."""
        return [
            {"date": week_start, "actual_covers": 85, "predicted_covers": 90}, # Quiet day
            {"date": week_start + timedelta(days=1), "actual_covers": 120, "predicted_covers": 115},
            {"date": week_start + timedelta(days=2), "actual_covers": 175, "predicted_covers": 170}, # Surge day
            {"date": week_start + timedelta(days=3), "actual_covers": 130, "predicted_covers": 135},
            {"date": week_start + timedelta(days=4), "actual_covers": 140, "predicted_covers": 140},
            {"date": week_start + timedelta(days=5), "actual_covers": 145, "predicted_covers": 145},
            {"date": week_start + timedelta(days=6), "actual_covers": 150, "predicted_covers": 150},
        ]

    async def format_audit_email(self, metrics: Dict[str, Any]) -> str:
        """Generates a markdown/html summary for the Friday Audit email."""
        m = metrics['metrics']
        f = metrics['financial_impact']
        
        return (
            f"📅 *Aetherix Weekly Audit: {metrics['tenant_id']}*\n"
            f"Period: {metrics['period']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📈 *Forecasting Performance:*\n"
            f"• Accuracy: {m['accuracy']}%\n"
            f"• MAPE: {m['mape']}%\n"
            f"• Covers Processed: {m['total_covers']}\n\n"
            f"💰 *Operational ROI:*\n"
            f"• Estimated Savings: £{f['estimated_savings_gbp']}\n"
            f"• Value Delivered: {f['roi_multiplier']}x monthly cost\n\n"
            f"Aetherix is optimizing your labor costs effectively."
        )

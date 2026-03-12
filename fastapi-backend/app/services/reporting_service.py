import logging
from datetime import date, timedelta
from typing import List, Dict, Any
import pandas as pd # For easy data manipulation

logger = logging.getLogger(__name__)

class ReportingService:
    """
    Performance Reporting Layer (Phase 3).
    Calculates MAPE and Financial ROI for the "Friday Audit".
    """
    
    def __init__(self, db_service=None):
        self.db = db_service # Mocking DB access for now

    async def generate_weekly_metrics(self, tenant_id: str, week_start: date) -> Dict[str, Any]:
        """
        Calculates MAPE and labor savings for a given tenant's week.
        """
        # 1. Fetch historical predictions vs actuals
        # In a real scenario, this would query Supabase/PostgreSQL
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

        return {
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

    def _calculate_savings(self, df: pd.DataFrame) -> float:
        """Heuristic for labor savings based on prediction accuracy."""
        if df.empty: return 0.0
        
        # Captured Revenue (Surges predicted correctly)
        # Assume correct surge predictions (actual > baseline + 10%) saved 10% of that revenue
        surge_savings = df[df['actual_covers'] > 150]['actual_covers'].sum() * 0.10 * 15.0 # £15 per cover
        
        # Idle Labor Reduction (Quiet days predicted correctly)
        # Assume correct quiet predictions saved 2 server shifts (£60 each)
        quiet_savings = df[df['actual_covers'] < 100].shape[0] * 120.0 # £120 per quiet day
        
        return surge_savings + quiet_savings

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

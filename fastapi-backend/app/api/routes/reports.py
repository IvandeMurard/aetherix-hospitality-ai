from fastapi import APIRouter, Depends, Query
from datetime import date, timedelta
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["insights"])

@router.get("/weekly")
async def get_weekly_audit(
    tenant_id: str = Query(..., example="pilot_hotel"),
    week_start: date = Query(None)
):
    """
    Triggers the "Friday Audit" weekly performance report.
    Defaults to the start of the current week (Monday).
    """
    if not week_start:
        # Default to previous Monday
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        
    service = ReportingService()
    metrics = await service.generate_weekly_metrics(tenant_id, week_start)
    email_summary = await service.format_audit_email(metrics)
    
    return {
        "report": metrics,
        "summary_markdown": email_summary
    }

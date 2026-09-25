"""Weekly report — GET /api/v1/reports/weekly (ADR-0007 §17.1).

Returns the deterministic weekly recap (``decision_recap``) for the tenant the
bearer token is bound to. Until 24/09/2026 this route had no authentication,
took ``tenant_id`` from the query string, and served hard-coded demo covers,
invented savings and a mock ROI when no data existed.

Auth: MCP bearer token with ``receipts:read`` (same as the Receipt drill-down
and the KPIs); ``tenant_id`` must be the token's hotel.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant_scope import require_token_hotel
from app.db.session import get_db
from app.mcp_core import MCPAuthError, RECEIPTS_READ_SCOPE
from app.mcp_server import verify_bearer
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["insights"])


def _require_receipts_scope():
    async def _dep(
        authorization: Optional[str] = Header(None),
        db: AsyncSession = Depends(get_db),
    ):
        try:
            tok = await verify_bearer(authorization, db)
        except MCPAuthError as exc:
            raise HTTPException(
                status_code=exc.status,
                headers={"WWW-Authenticate": "Bearer"},
                detail=exc.detail,
            )
        if RECEIPTS_READ_SCOPE not in (tok.scopes or []):
            raise HTTPException(
                status_code=403,
                detail=f"Token missing required scope: {RECEIPTS_READ_SCOPE}",
            )
        return tok
    return _dep


# Named at module level so tests can apply dependency_overrides
_reports_auth = _require_receipts_scope()


@router.get("/weekly")
async def get_weekly_audit(
    tenant_id: str = Query(..., example="pilot_hotel"),
    week_start: date = Query(None),
    locale: Literal["fr", "en"] = Query("fr"),
    token=Depends(_reports_auth),
    db: AsyncSession = Depends(get_db),
):
    """Weekly recap, Monday ``week_start`` (default: this week's Monday)."""
    require_token_hotel(token, tenant_id)
    if not week_start:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

    service = ReportingService(db_service=db)
    metrics = await service.generate_weekly_metrics(tenant_id, week_start, locale=locale)
    return {
        "report": metrics,
        "summary_markdown": metrics["summary_text"],
    }

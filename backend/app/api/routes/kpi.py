"""Trust-KPI read endpoint — HOS-177 (P3-3).

GET /api/v1/kpi/{hotel_id}/recommendation_acceptance?days=7
  → Returns 7-day rolling acceptance rate, trend arrow, and daily timeseries.
  → Auth: MCP bearer token with receipts:read scope (same as Receipt drill-down).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.mcp_core import MCPAuthError, RECEIPTS_READ_SCOPE
from app.mcp_server import verify_bearer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kpi", tags=["kpi"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DailyRate(BaseModel):
    date: date
    rate: Optional[float]


class RecommendationAcceptanceResponse(BaseModel):
    rolling_rate: Optional[float]
    trend: str  # "up" | "down" | "flat"
    daily: list[DailyRate]


# ---------------------------------------------------------------------------
# Auth — same bearer + receipts:read scope as receipts route
# ---------------------------------------------------------------------------

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


_kpi_auth = _require_receipts_scope()


# ---------------------------------------------------------------------------
# Trend calculation (pure — testable)
# ---------------------------------------------------------------------------

def _compute_trend(daily: list[DailyRate]) -> str:
    """Compare last half vs first half of the window. Flat if |delta| < 2 pp."""
    rates = [d.rate for d in daily if d.rate is not None]
    if len(rates) < 2:
        return "flat"
    mid = len(rates) // 2
    prior = rates[:mid]
    recent = rates[mid:]
    if not prior or not recent:
        return "flat"
    avg_recent = sum(recent) / len(recent)
    avg_prior = sum(prior) / len(prior)
    delta = avg_recent - avg_prior
    if delta > 0.02:
        return "up"
    if delta < -0.02:
        return "down"
    return "flat"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get(
    "/{hotel_id}/recommendation_acceptance",
    response_model=RecommendationAcceptanceResponse,
)
async def get_recommendation_acceptance(
    hotel_id: str,
    days: int = Query(default=7, ge=1, le=90),
    token=Depends(_kpi_auth),
    db: AsyncSession = Depends(get_db),
) -> RecommendationAcceptanceResponse:
    """Return rolling recommendation acceptance rate for `hotel_id` over the last `days` days.

    Fetches 2× the window from kpi_daily to compute the trend (last half vs prior half).
    """
    today = date.today()
    trend_window = days * 2
    trend_start = today - timedelta(days=trend_window - 1)

    result = await db.execute(
        text("""
            SELECT kpi_date, value
            FROM kpi_daily
            WHERE tenant_id = :tenant_id
              AND kpi_name  = :kpi_name
              AND kpi_date BETWEEN :trend_start AND :today
            ORDER BY kpi_date ASC
        """),
        {
            "tenant_id": hotel_id,
            "kpi_name": "recommendation_acceptance_rate",
            "trend_start": trend_start,
            "today": today,
        },
    )
    rows = result.fetchall()
    date_map: dict[date, Optional[float]] = {row.kpi_date: row.value for row in rows}

    # Requested window (most recent `days` days)
    window_start = today - timedelta(days=days - 1)
    daily = [
        DailyRate(date=window_start + timedelta(days=i), rate=date_map.get(window_start + timedelta(days=i)))
        for i in range(days)
    ]

    values = [r.rate for r in daily if r.rate is not None]
    rolling_rate = sum(values) / len(values) if values else None

    # Trend over the full 2× window
    full_window = [
        DailyRate(date=trend_start + timedelta(days=i), rate=date_map.get(trend_start + timedelta(days=i)))
        for i in range(trend_window)
    ]
    trend = _compute_trend(full_window)

    logger.info(
        "kpi_route: hotel_id=%s rolling_rate=%s trend=%s days=%d",
        hotel_id,
        rolling_rate,
        trend,
        days,
    )
    return RecommendationAcceptanceResponse(
        rolling_rate=rolling_rate,
        trend=trend,
        daily=daily,
    )


# ---------------------------------------------------------------------------
# Décision #38 — manager decision capture metrics
# ---------------------------------------------------------------------------

class DecisionCaptureResponse(BaseModel):
    days: int
    replies: int
    decision_seeking_replies: int
    decisions_written: int
    capture_rate: Optional[float]
    by_source: dict[str, int]
    source_share: dict[str, float]
    confirmations_requested: int
    confirmations_confirmed: int
    confirmations_declined: int
    confirmations_expired: int
    confirmation_rate: Optional[float]
    confirmation_timeout_rate: Optional[float]
    not_recorded_by_why: dict[str, int]
    reasons_captured: int
    reasons_routed: int


@router.get("/{hotel_id}/decision_capture", response_model=DecisionCaptureResponse)
async def get_decision_capture(
    hotel_id: str,
    days: int = Query(default=7, ge=1, le=90),
    token=Depends(_kpi_auth),
    db: AsyncSession = Depends(get_db),
) -> DecisionCaptureResponse:
    """Capture rate, decisions by source, confirmation and timeout rates over the
    last `days` days (ADR-0007 §16.8). Source: `inbound_reply_events`.

    Arm C should read `by_source` before trusting a decision count: a
    `bare_ack_rule` acceptance is weaker evidence than a `button` one.
    """
    from datetime import datetime, timezone

    from app.services.inbound_decision import InboundDecisionService

    if getattr(token, "hotel_id", hotel_id) != hotel_id:
        raise HTTPException(status_code=403, detail="Token not scoped to this hotel")
    until = datetime.now(tz=timezone.utc)
    metrics = await InboundDecisionService(db).capture_metrics(
        hotel_id, until - timedelta(days=days), until
    )
    return DecisionCaptureResponse(days=days, **metrics.as_dict())

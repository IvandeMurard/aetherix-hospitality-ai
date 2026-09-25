"""Trust-KPI read endpoint — HOS-177 (P3-3).

GET /api/v1/kpi/{hotel_id}/recommendation_acceptance?days=7
  → Returns the rolling acceptance rate, trend arrow, and daily timeseries.
  → Auth: MCP bearer token with receipts:read scope, bound to `hotel_id`.

Definition (ADR-0007 §17.6): `decision_recap.acceptance_rate`, computed live
from `staffing_recommendations` — the table where the decision, its source and
who decided now live — human decisions only. Until 24/09/2026 this read
`kpi_daily`, fed by a materialized view joining feedback memory rows to
recommendation/prediction tool calls on request_id: feedback rows carry the
request_id of the feedback call itself, so WhatsApp and MCP decisions were
essentially never counted.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tenant_scope import require_token_hotel
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
    rolling_rate: Optional[float]      # pooled over the window, human decisions only
    trend: str  # "up" | "down" | "flat"
    daily: list[DailyRate]
    decided: int = 0                   # human decisions in the window
    accepted: int = 0
    no_reply: int = 0
    by_decided_by: dict[str, int] = {}
    agent_decided: int = 0             # host agent alone — never in the rate
    override_rate: Optional[float] = None
    median_response_minutes: Optional[float] = None  # latency, not effort
    definition: str = ""


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
    The token must be bound to `hotel_id` (tenant isolation, ADR-0007 §17.7).
    """
    require_token_hotel(token, hotel_id)
    from datetime import datetime, timezone

    from app.services.decision_recap import (
        ACCEPTANCE_DEFINITION,
        _tz,
        acceptance_rate,
        load_rows,
        summarize,
        utc_window,
    )
    from app.services.decision_provenance import HUMAN_DECIDERS

    tz = _tz()
    today = datetime.now(tz=timezone.utc).astimezone(tz).date()
    trend_start = today - timedelta(days=days * 2 - 1)
    window_start = today - timedelta(days=days - 1)
    lo, hi = utc_window(trend_start, today, tz)
    rows = await load_rows(db, hotel_id, lo, hi)

    def _day_rate(d: date) -> Optional[float]:
        human = [r for r in rows
                 if r.received_at.astimezone(tz).date() == d and r.decided_by in HUMAN_DECIDERS]
        return acceptance_rate(sum(1 for r in human if r.status == "accepted"), len(human))

    full_window = [
        DailyRate(date=trend_start + timedelta(days=i), rate=_day_rate(trend_start + timedelta(days=i)))
        for i in range(days * 2)
    ]
    daily = full_window[days:]
    in_window = [r for r in rows if r.received_at.astimezone(tz).date() >= window_start]
    summary = summarize(in_window, "window", window_start, today, tz)
    trend = _compute_trend(full_window)

    logger.info(
        "kpi_route: hotel_id=%s rolling_rate=%s decided=%d trend=%s days=%d",
        hotel_id, summary.human.acceptance_rate, summary.human.decided, trend, days,
    )
    return RecommendationAcceptanceResponse(
        rolling_rate=summary.human.acceptance_rate,
        trend=trend,
        daily=daily,
        decided=summary.human.decided,
        accepted=summary.human.accepted,
        no_reply=summary.no_reply,
        by_decided_by=summary.by_decided_by,
        agent_decided=summary.agent.decided,
        override_rate=summary.human.override_rate,
        median_response_minutes=summary.human.median_response_minutes,
        definition=ACCEPTANCE_DEFINITION,
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
    revisions: int = 0


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

    require_token_hotel(token, hotel_id)
    until = datetime.now(tz=timezone.utc)
    metrics = await InboundDecisionService(db).capture_metrics(
        hotel_id, until - timedelta(days=days), until
    )
    return DecisionCaptureResponse(days=days, **metrics.as_dict())

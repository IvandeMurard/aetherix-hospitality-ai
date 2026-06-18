"""Epic 12 G-4 (HOS-251) — confidence-tiered forecast guardrail at dispatch.

The ADR-0005 cold-start auto-disable does not *cut* the forecast — it
**degrades** to a safer baseline. G-4 generalizes that principle to the runtime
dispatch path. **Decision SM/PM (18/06): never a binary suppression.** A
low-confidence day still owes the manager a staffing number; delivering *nothing*
is worse than delivering a figure with a caveat (Décision #6 HITL-always, and
consistent with the inbound parser's `confidence < 0.6 → degrade, not blank`).

So this guardrail produces a **confidence indicator, not a switch**, in two tiers:

  * **Tier 1 — low but usable** (``confidence < WARN``): the recommendation is
    dispatched anyway, tagged with an ``AgentAbstention`` *flag carrier*
    (HOS-206) the manager can weigh. Never blanked.
  * **Tier 2 — catastrophic** (``confidence < CATASTROPHE`` **or**
    ``live_mape > MAPE_CATASTROPHE``): fall back to a simpler baseline (tagged as
    such), recommendation still delivered — mirrors the ADR-0005 degradation.

Every non-nominal verdict is logged to ``agent_action_log`` with a typed reason
(AC5 / NFR2) — populating the abstention columns so it feeds the Epic 11
abstention metrics. A Tier-2 fallback also raises an ops anomaly alert (Linear).
Thresholds live in ``app.core.config`` and are documented in
``eval/FAILURE_THRESHOLDS.md``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core import config
from app.db.models import AgentActionLog
from app.db.session import AsyncSessionLocal
from app.i18n.abstention_messages import localized_message
from app.services.abstention import AgentAbstention

logger = logging.getLogger(__name__)

# Tiers.
NOMINAL = "nominal"
TIER1_FLAG = "tier1_flag"
TIER2_FALLBACK = "tier2_fallback"

# Abstention reason codes (must be members of the HOS-206 reason set — the i18n
# coverage test enforces the mapping). Tier 1 reuses the confidence reason; Tier 2
# reuses the ADR-0005 cold-start degradation reason (same "degrade, don't cut"
# semantics).
REASON_TIER1 = "confidence_below_threshold"
REASON_TIER2 = "cold_start_meta_learner_drift"

# agent_action_log.tool_name for forecast-guardrail trip rows.
GUARDRAIL_TOOL = "forecast.guardrail"


@dataclass(frozen=True)
class ForecastVerdict:
    """Outcome of the confidence-tiering decision on one forecast.

    ``effective_covers`` is what staffing must be computed on: the Prophet point
    estimate for nominal/Tier-1, the baseline for Tier-2. ``abstention`` is the
    manager-facing flag carrier (None when nominal) — it does NOT blank the
    result; the recommendation is always delivered.
    """

    tier: str
    effective_covers: int
    confidence: float
    baseline_used: bool
    abstention: Optional[AgentAbstention] = None
    reason: Optional[str] = None
    detail: Optional[str] = None

    @property
    def is_nominal(self) -> bool:
        return self.tier == NOMINAL


def simple_baseline(context: Optional[dict], predicted_covers: float) -> tuple[int, bool]:
    """Resolve a Tier-2 baseline. Returns (covers, is_real_baseline).

    Prefers a caller-supplied historical baseline (``baseline_covers`` then
    ``recent_avg_covers`` in context), else a configured constant prior, else
    degrades to the Prophet point estimate (still delivered + tagged — never
    silent). ``is_real_baseline`` is False for the degraded/constant fallbacks.
    """
    ctx = context or {}
    for key in ("baseline_covers", "recent_avg_covers"):
        val = ctx.get(key)
        if val is not None and float(val) > 0:
            return int(round(float(val))), True
    if config.FORECAST_BASELINE_DEFAULT_COVERS > 0:
        return int(round(config.FORECAST_BASELINE_DEFAULT_COVERS)), False
    return int(round(predicted_covers)), False


def evaluate(
    predicted_covers: float,
    confidence: float,
    *,
    context: Optional[dict] = None,
    live_mape: Optional[float] = None,
    locale: Optional[str] = None,
) -> ForecastVerdict:
    """Pure tiering decision. Never returns a blank/abstaining result."""
    warn = config.FORECAST_CONFIDENCE_WARN
    catastrophe = config.FORECAST_CONFIDENCE_CATASTROPHE
    mape_ceiling = config.FORECAST_MAPE_CATASTROPHE
    predicted_int = int(round(predicted_covers))

    catastrophic = confidence < catastrophe or (
        live_mape is not None and live_mape > mape_ceiling
    )
    if catastrophic:
        baseline, real = simple_baseline(context, predicted_covers)
        trigger = (
            f"live MAPE {live_mape:.0f}% > {mape_ceiling:.0f}%"
            if (live_mape is not None and live_mape > mape_ceiling)
            else f"confidence {confidence:.2f} < {catastrophe:.2f}"
        )
        detail = (
            f"Catastrophic forecast breach ({trigger}); degraded to "
            f"{'historical baseline' if real else 'fallback prior'} "
            f"{baseline} covers (was {predicted_int}). Recommendation still delivered."
        )
        return ForecastVerdict(
            tier=TIER2_FALLBACK,
            effective_covers=baseline,
            confidence=confidence,
            baseline_used=True,
            abstention=AgentAbstention(
                reason=REASON_TIER2,
                layer="forecast",
                context={
                    "forecast_confidence": confidence,
                    "live_mape": live_mape,
                    "prophet_covers": predicted_int,
                    "baseline_covers": baseline,
                    "real_baseline": real,
                },
                human_message=localized_message(REASON_TIER2, locale),
            ),
            reason=REASON_TIER2,
            detail=detail,
        )

    if confidence < warn:
        detail = (
            f"Low forecast confidence {confidence:.2f} < {warn:.2f}; recommendation "
            f"dispatched with a confidence caveat ({predicted_int} covers)."
        )
        return ForecastVerdict(
            tier=TIER1_FLAG,
            effective_covers=predicted_int,
            confidence=confidence,
            baseline_used=False,
            abstention=AgentAbstention(
                reason=REASON_TIER1,
                layer="forecast",
                context={"forecast_confidence": confidence, "prophet_covers": predicted_int},
                human_message=localized_message(REASON_TIER1, locale),
            ),
            reason=REASON_TIER1,
            detail=detail,
        )

    return ForecastVerdict(
        tier=NOMINAL,
        effective_covers=predicted_int,
        confidence=confidence,
        baseline_used=False,
    )


async def record_forecast_trip(hotel_id: str, verdict: ForecastVerdict) -> None:
    """Log a typed trip (AC5/NFR2) + (Tier-2 only) raise an ops anomaly alert.

    Fire-and-forget: guardrail instrumentation never breaks the dispatch path.
    Populates the abstention columns so the trip feeds Epic 11 metrics.
    """
    if verdict.is_nominal:
        return

    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AgentActionLog(
                    hotel_id=hotel_id or "_system",
                    tool_name=GUARDRAIL_TOOL,
                    status="tool_error",
                    error_code=verdict.reason,
                    payload={
                        "kind": "trip",
                        "tier": verdict.tier,
                        "detail": verdict.detail,
                        "baseline_used": verdict.baseline_used,
                    },
                    abstention_reason=verdict.reason,
                    abstention_layer="forecast",
                    abstention_context=(
                        verdict.abstention.context if verdict.abstention else None
                    ),
                    request_id="",
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("forecast_guardrail: agent_action_log write failed: %s", exc)

    # Tier 1 is a routine manager-facing caveat (no ops noise); Tier 2 is a
    # catastrophic degrade worth an ops anomaly.
    if verdict.tier == TIER2_FALLBACK:
        try:
            from app.services.ops_dispatcher import dispatch_anomaly

            await dispatch_anomaly(
                title=f"forecast guardrail Tier-2 fallback: {hotel_id}",
                detail=verdict.detail or "Catastrophic forecast breach — baseline delivered.",
                tags=["forecast_guardrail", verdict.reason or "tier2", hotel_id],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("forecast_guardrail: dispatch_anomaly failed: %s", exc)

    logger.warning(
        "forecast_guardrail: %s hotel_id=%s — %s", verdict.tier, hotel_id, verdict.detail
    )


async def apply(
    hotel_id: str,
    predicted_covers: float,
    confidence: float,
    *,
    context: Optional[dict] = None,
    live_mape: Optional[float] = None,
    locale: Optional[str] = None,
) -> ForecastVerdict:
    """Evaluate the tiering and log the trip in one call. Returns the verdict."""
    verdict = evaluate(
        predicted_covers, confidence, context=context, live_mape=live_mape, locale=locale
    )
    await record_forecast_trip(hotel_id, verdict)
    return verdict

"""Epic 12 G-3 (HOS-250) — input bounds on the feedback→training loop.

HOS-200 opened an unguarded write path: a manager-reported ``actual_covers`` is
persisted and later re-injected into retraining without a plausibility check. An
aberrant value (manager typo, faulty POS sensor) silently poisons the model.

This module bounds the value at the ingestion chokepoint
(``ReceiptsService.persist_actual_covers``):

  * lower bound (``FEEDBACK_COVERS_MIN``) — catches negative / zero,
  * capacity ceiling — ``total_seats × turns × multiplier`` (AC1),
  * historical soft sanity — far above the property's historical max → *flag*
    only (a real surge inside capacity must not be rejected).

On an implausible value the policy (``FEEDBACK_BOUNDS_POLICY``) is either
``reject`` (value not ingested) or ``flag`` (ingested but tagged). Either way a
typed trip is logged to ``agent_action_log`` (AC3) and an ops alert is raised via
``ops_dispatcher`` (Linear sink — no Slack, consistent with HOS-248).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core import config
from app.db.models import AgentActionLog
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Typed trip reason (AC3 / NFR2). Stored in agent_action_log.error_code.
REASON_IMPLAUSIBLE = "implausible_feedback"
# agent_action_log.tool_name for feedback-ingestion guard rows.
FEEDBACK_TOOL = "feedback.ingestion"


@dataclass(frozen=True)
class BoundsVerdict:
    """Outcome of a plausibility check on an actual_covers value."""

    plausible: bool
    severity: str  # "ok" | "reject" | "flag"
    reason: Optional[str] = None
    detail: Optional[str] = None


def _policy() -> str:
    pol = config.FEEDBACK_BOUNDS_POLICY
    return pol if pol in ("reject", "flag") else "reject"


def capacity_ceiling(total_seats: float, turns_sum: float) -> float:
    """Physical daily covers ceiling for a property (AC1, AC4)."""
    return float(total_seats) * float(turns_sum) * config.FEEDBACK_COVERS_CAPACITY_MULTIPLIER


def evaluate(
    actual_value: float,
    *,
    total_seats: Optional[float] = None,
    turns_sum: Optional[float] = None,
    historical_max: Optional[float] = None,
) -> BoundsVerdict:
    """Bound an actual_covers value. Capacity is enforced whenever seats are
    known (default turns used when the turn config is missing)."""
    # Lower bound — negative / zero / sub-minimum.
    if actual_value < config.FEEDBACK_COVERS_MIN:
        return BoundsVerdict(
            False,
            _policy(),
            REASON_IMPLAUSIBLE,
            f"actual_covers={actual_value} below minimum {config.FEEDBACK_COVERS_MIN}.",
        )

    # Capacity ceiling — enforced whenever the property's seats are known. Turns
    # may be NULL on an incompletely-onboarded property (turns_sum == 0); a falsy
    # turns_sum must NOT silently skip the ceiling (that lets an aberrant value
    # through), so fall back to a default service count to keep the bound live.
    if total_seats:
        effective_turns = turns_sum if turns_sum else config.FEEDBACK_COVERS_DEFAULT_TURNS
        ceiling = capacity_ceiling(total_seats, effective_turns)
        if ceiling > 0 and actual_value > ceiling:
            return BoundsVerdict(
                False,
                _policy(),
                REASON_IMPLAUSIBLE,
                (
                    f"actual_covers={actual_value} exceeds capacity ceiling "
                    f"{ceiling:.0f} (seats={total_seats} × turns={effective_turns} × "
                    f"{config.FEEDBACK_COVERS_CAPACITY_MULTIPLIER})."
                ),
            )

    # Historical soft sanity — never rejects (legit surge can beat history).
    if historical_max and actual_value > historical_max * config.FEEDBACK_HISTORICAL_MULTIPLIER:
        return BoundsVerdict(
            False,
            "flag",
            REASON_IMPLAUSIBLE,
            (
                f"actual_covers={actual_value} is "
                f"{actual_value / historical_max:.1f}× the historical max "
                f"{historical_max} (within capacity — flagged, not rejected)."
            ),
        )

    return BoundsVerdict(True, "ok")


async def record_feedback_trip(
    hotel_id: str,
    reason: str,
    detail: str,
    severity: str,
    *,
    db=None,
) -> None:
    """Log a typed trip (AC3) + raise an ops alert. Fire-and-forget.

    When ``db`` is provided the log row joins the caller's transaction; otherwise
    a short-lived session is opened and committed independently.
    """
    row = AgentActionLog(
        hotel_id=hotel_id,
        tool_name=FEEDBACK_TOOL,
        status="tool_error",
        error_code=reason,
        payload={"severity": severity, "detail": detail},
        request_id="",
    )
    try:
        if db is not None:
            db.add(row)
            await db.flush()
        else:
            async with AsyncSessionLocal() as session:
                session.add(row)
                await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("feedback_guard: agent_action_log write failed: %s", exc)

    try:
        from app.services.ops_dispatcher import dispatch_anomaly, dispatch_error

        title = f"feedback bounds [{severity}]: {hotel_id} — {reason}"
        tags = ["feedback_guard", reason, hotel_id]
        if severity == "reject":
            await dispatch_error(title=title, detail=detail, tags=tags)
        else:
            await dispatch_anomaly(title=title, detail=detail, tags=tags)
    except Exception as exc:  # noqa: BLE001
        logger.warning("feedback_guard: ops alert failed: %s", exc)

    from app.core.observability import guardrail_trip

    guardrail_trip(FEEDBACK_TOOL, hotel_id, reason, detail)
    logger.warning(
        "feedback_guard: TRIP hotel_id=%s severity=%s reason=%s — %s",
        hotel_id, severity, reason, detail,
    )

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

Rule B (PO 14/11/2026, HOS-366, audit of silences case 10): when the check
itself cannot run (its capacity / history lookup fails, or it crashes), the
verdict is ``unverified`` — it used to be ``BoundsVerdict(True, "ok")``, so the
value reached training unbounded. An unverified value is recorded with
``actual_covers_source = "manager_feedback_unverified"`` and **no**
``actual_covers``: every reader of measured actuals (learning loop, live error,
ledger, weekly MAPE) filters on ``actual_covers IS NOT NULL``, so it is held out
by construction, not by a filter each reader must remember. The figure itself
stays in the ground-truth memory row and the trip row, for a human to verify.
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
# Rule B (HOS-366): the bounds check could not run. Same reason as the forecast
# guardrail's not-verified verdict — one reason for "a guardrail did not run".
REASON_NOT_VERIFIED = "guardrail_not_verified"
SEVERITY_UNVERIFIED = "unverified"
# actual_covers_source of a manager figure the check could not verify.
SOURCE_UNVERIFIED = "manager_feedback_unverified"
# agent_action_log.tool_name for feedback-ingestion guard rows.
FEEDBACK_TOOL = "feedback.ingestion"


@dataclass(frozen=True)
class BoundsVerdict:
    """Outcome of a plausibility check on an actual_covers value."""

    plausible: bool
    severity: str  # "ok" | "reject" | "flag" | "unverified"
    reason: Optional[str] = None
    detail: Optional[str] = None


def not_verified(detail: str) -> BoundsVerdict:
    """Rule B verdict: the bounds check could not run on this value."""
    return BoundsVerdict(
        False,
        SEVERITY_UNVERIFIED,
        REASON_NOT_VERIFIED,
        f"feedback bounds check could not run ({detail[:200]}); value held as unverified.",
    )


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
    known (default turns used when the turn config is missing).

    Fails closed (rule B, HOS-366): a crash inside the check is an
    ``unverified`` verdict, never ``ok``."""
    try:
        return _evaluate(
            actual_value, total_seats=total_seats, turns_sum=turns_sum,
            historical_max=historical_max,
        )
    except Exception as exc:  # noqa: BLE001 — rule B: typed verdict, never "ok"
        logger.error("feedback_guard: bounds evaluation failed: %s", exc)
        return not_verified(f"{type(exc).__name__}: {exc}")


def _evaluate(
    actual_value: float,
    *,
    total_seats: Optional[float] = None,
    turns_sum: Optional[float] = None,
    historical_max: Optional[float] = None,
) -> BoundsVerdict:
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
        # A check that did not run is an error (P1), like a rejected value.
        if severity in ("reject", SEVERITY_UNVERIFIED):
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

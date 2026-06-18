"""Epic 12 G-5 (HOS-252) — output sanity bounds on recommendations.

Before a staffing recommendation is dispatched it must be *physically sane*: the
recommended covers must fit the property's capacity, the headcount must not be an
absurd multiple of the baseline, and the labor cost must respect the budget. Today
only a partial budget-alert check lives in ``staffing_service``; this module is the
single centralized guard that **absorbs** that check (AC5) and adds the capacity +
delta bounds.

Out-of-bounds outputs are **clamped/flagged and routed to a human** — never
dropped silently (AC2, consistent with the G-4 never-blank principle). Every trip
is logged to ``agent_action_log`` with a typed reason (AC3 / NFR2) and raises an
ops anomaly alert (Linear). The property-capacity ceiling is shared with G-3
(``feedback_guard.capacity_ceiling``) — one definition of "capacity", not two.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core import config
from app.db.models import AgentActionLog
from app.db.session import AsyncSessionLocal
from app.services.feedback_guard import capacity_ceiling

logger = logging.getLogger(__name__)

# Typed trip reasons (AC3 / NFR2). Stored in agent_action_log.error_code.
REASON_OVER_CAPACITY = "output_over_capacity"     # covers exceed property capacity
REASON_ABSURD_DELTA = "output_absurd_delta"       # headcount >> baseline
REASON_BUDGET = "labor_budget_exceeded"           # cost over daily budget (absorbed)

# agent_action_log.tool_name for output-sanity trip rows.
SANITY_TOOL = "output.sanity"


@dataclass
class SanityVerdict:
    """Outcome of the sanity-bounds check on a recommendation output."""

    within_bounds: bool = True
    clamped_covers: Optional[int] = None  # set when covers were clamped to capacity
    route_to_human: bool = False          # a physical-sanity breach (not just budget)
    flags: list[tuple[str, str]] = field(default_factory=list)  # (reason, detail)

    @property
    def warnings(self) -> list[str]:
        return [detail for _, detail in self.flags]


def evaluate(
    covers: float,
    headcount: int,
    *,
    total_seats: Optional[float] = None,
    turns_sum: Optional[float] = None,
    baseline_headcount: Optional[int] = None,
    labor_cost: Optional[float] = None,
    labor_budget: Optional[float] = None,
) -> SanityVerdict:
    """Bound a recommendation's covers/headcount/cost. Pure — no side effects.

    Capacity uses the shared G-3 ceiling whenever the property's seats are known.
    A capacity breach clamps the covers (and signals a human review); an absurd
    headcount delta or a budget overrun flag without clamping.
    """
    verdict = SanityVerdict()

    # 1. Capacity ceiling (shared with G-3). Clamp covers down to the ceiling.
    if total_seats:
        ceiling = capacity_ceiling(total_seats, turns_sum or config.FEEDBACK_COVERS_DEFAULT_TURNS)
        if ceiling > 0 and covers > ceiling:
            verdict.within_bounds = False
            verdict.route_to_human = True
            verdict.clamped_covers = int(ceiling)
            verdict.flags.append((
                REASON_OVER_CAPACITY,
                (
                    f"recommended covers {covers:.0f} exceed property capacity "
                    f"{ceiling:.0f} — clamped to capacity, routed for review."
                ),
            ))

    # 2. Absurd headcount delta vs baseline.
    if baseline_headcount and baseline_headcount > 0:
        ceiling_hc = baseline_headcount * config.OUTPUT_SANITY_MAX_HEADCOUNT_DELTA_MULT
        if headcount > ceiling_hc:
            verdict.within_bounds = False
            verdict.route_to_human = True
            verdict.flags.append((
                REASON_ABSURD_DELTA,
                (
                    f"recommended headcount {headcount} is "
                    f"{headcount / baseline_headcount:.1f}× the baseline "
                    f"{baseline_headcount} (max {config.OUTPUT_SANITY_MAX_HEADCOUNT_DELTA_MULT}×) "
                    "— flagged for review."
                ),
            ))

    # 3. Labor budget (absorbed from staffing_service — single source now).
    if labor_cost is not None and labor_budget and labor_cost > labor_budget:
        verdict.within_bounds = False
        verdict.flags.append((
            REASON_BUDGET,
            (
                f"projected daily labor cost £{labor_cost:.0f} exceeds daily budget "
                f"£{labor_budget:.0f} (overage £{labor_cost - labor_budget:.0f})."
            ),
        ))

    return verdict


async def record_sanity_trip(hotel_id: str, verdict: SanityVerdict) -> None:
    """Log one typed trip row per flag (AC3) + raise an ops anomaly. Fire-and-forget."""
    if verdict.within_bounds:
        return

    try:
        async with AsyncSessionLocal() as db:
            for reason, detail in verdict.flags:
                db.add(
                    AgentActionLog(
                        hotel_id=hotel_id or "_system",
                        tool_name=SANITY_TOOL,
                        status="tool_error",
                        error_code=reason,
                        payload={"kind": "trip", "reason": reason, "detail": detail},
                        request_id="",
                    )
                )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("output_sanity: agent_action_log write failed: %s", exc)

    try:
        from app.services.ops_dispatcher import dispatch_anomaly

        reasons = ", ".join(r for r, _ in verdict.flags)
        await dispatch_anomaly(
            title=f"output sanity breach: {hotel_id} [{reasons}]",
            detail="\n".join(verdict.warnings),
            tags=["output_sanity", hotel_id] + [r for r, _ in verdict.flags],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("output_sanity: dispatch_anomaly failed: %s", exc)

    logger.warning("output_sanity: TRIP hotel_id=%s flags=%s", hotel_id, verdict.flags)

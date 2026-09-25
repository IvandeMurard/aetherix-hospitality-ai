import asyncio
import math
from typing import Dict, Optional, Union

from pydantic import BaseModel

from app.core.demo_events import demo_emit
from app.i18n.abstention_messages import localized_message
from app.services.abstention import AgentAbstention

# Below this forecast confidence the recommendation abstains (ADR-0007 §D6).
_CONFIDENCE_ABSTAIN_THRESHOLD = 0.5


class StaffingConfig(BaseModel):
    covers_per_server: int = 18
    covers_per_host: int = 70
    covers_per_kitchen: int = 50
    usual_servers: int = 7
    usual_hosts: int = 2
    usual_kitchen: int = 3
    usual_sommeliers: int = 1

    # Daily budget; compare against total_shifts * avg_shift_cost for one service
    # Field name kept (R6 test pins it); the amount is in config.CURRENCY.
    labor_budget_gbp_per_day: float = 1200.0
    avg_shift_cost: float = 80.0

class StaffingService:
    """Calculates staffing requirements based on demand."""

    @staticmethod
    def _staff_for(covers: float, cfg: StaffingConfig) -> tuple[int, int, int, int]:
        """Role headcounts for a covers level (pure ratio math)."""
        servers = math.ceil(covers / cfg.covers_per_server)
        hosts = math.ceil(covers / cfg.covers_per_host)
        kitchen = math.ceil(covers / cfg.covers_per_kitchen)
        sommeliers = 2 if covers > 160 else 1
        return servers, hosts, kitchen, sommeliers

    async def calculate_recommendation(
        self,
        predicted_covers: int,
        config: Optional[StaffingConfig] = None,
        confidence: Optional[float] = None,
        *,
        hotel_id: Optional[str] = None,
        total_seats: Optional[float] = None,
        turns_sum: Optional[float] = None,
    ) -> Union[Dict, AgentAbstention]:
        # ADR-0007 §D6 — graceful degradation: when the upstream forecast is too
        # uncertain, abstain rather than emit a confident-looking staffing number.
        # `confidence` is optional/additive: existing callers that don't pass it
        # keep the previous behaviour (no abstention).
        if confidence is not None and confidence < _CONFIDENCE_ABSTAIN_THRESHOLD:
            return AgentAbstention(
                reason="confidence_below_threshold",
                layer="recommendation",
                context={
                    "forecast_confidence": confidence,
                    "covers_predicted": predicted_covers,
                },
                human_message=localized_message("confidence_below_threshold"),
            )

        cfg = config or StaffingConfig()

        servers, hosts, kitchen, sommeliers = self._staff_for(predicted_covers, cfg)
        total_shifts = servers + hosts + kitchen + sommeliers
        current_cost = total_shifts * cfg.avg_shift_cost
        baseline_headcount = (
            cfg.usual_servers + cfg.usual_hosts + cfg.usual_kitchen + cfg.usual_sommeliers
        )

        # Epic 12 G-5 (HOS-252) — centralized output sanity bounds. Absorbs the
        # former ad-hoc budget alert: covers/headcount must fit property capacity
        # and sane deltas, cost must respect budget. Out of bounds → clamp/flag +
        # route to human (never silent), one typed trip per flag.
        from app.services import output_sanity

        verdict = output_sanity.evaluate(
            predicted_covers,
            total_shifts,
            total_seats=total_seats,
            turns_sum=turns_sum,
            baseline_headcount=baseline_headcount,
            labor_cost=current_cost,
            labor_budget=cfg.labor_budget_gbp_per_day,
        )

        # A capacity breach clamps the *delivered* covers down to capacity and
        # recomputes the headcount on the clamped value (still delivered, flagged).
        effective_covers = predicted_covers
        if verdict.clamped_covers is not None:
            effective_covers = verdict.clamped_covers
            servers, hosts, kitchen, sommeliers = self._staff_for(effective_covers, cfg)

        if not verdict.within_bounds:
            await output_sanity.record_sanity_trip(hotel_id or "_system", verdict)

        result = {
            "servers": servers,
            "hosts": hosts,
            "kitchen": kitchen,
            "deltas": {
                "servers": servers - cfg.usual_servers,
                "hosts": hosts - cfg.usual_hosts,
                "kitchen": kitchen - cfg.usual_kitchen,
                "sommeliers": sommeliers - cfg.usual_sommeliers,
            },
            "warnings": verdict.warnings,
            "sanity": {
                "within_bounds": verdict.within_bounds,
                "route_to_human": verdict.route_to_human,
                "clamped_covers": verdict.clamped_covers,
                "flags": [r for r, _ in verdict.flags],
            },
            "rationale": f"Staffing suggestion based on {effective_covers} covers. Optimized for role-ratios.",
        }
        # Demo board: highlight Staffing Service node after recommendation
        asyncio.create_task(demo_emit("staffing"))
        return result

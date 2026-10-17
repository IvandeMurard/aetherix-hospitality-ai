import asyncio
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel

from app.core.demo_events import demo_emit
from app.i18n.abstention_messages import localized_message
from app.services.abstention import AgentAbstention

logger = logging.getLogger(__name__)

# Below this forecast confidence the recommendation abstains (ADR-0007 §D6).
_CONFIDENCE_ABSTAIN_THRESHOLD = 0.5


class StaffingConfig(BaseModel):
    """System defaults. A hotel's own rules (hotel_parameters) take precedence
    role by role; a value taken from here is labelled ``default``, never
    presented as the hotel's (HOS-343)."""

    covers_per_server: int = 18
    covers_per_host: int = 70
    covers_per_kitchen: int = 50
    usual_servers: int = 7
    usual_hosts: int = 2
    usual_kitchen: int = 3
    usual_sommeliers: int = 1

    # Daily budget; compare against total_shifts * avg_shift_cost for one service
    # Field name kept (R6 test pins it); the amount is in config.CURRENCY.
    # HOS-348: no default. A budget nobody set must not raise an alert
    # (Décision #40: missing cost -> no money; #43: no default posing as the
    # hotel's constraint). None -> no budget check.
    labor_budget_gbp_per_day: Optional[float] = None
    avg_shift_cost: float = 80.0


# Ratio-staffed roles -> (hotel ratio parameter, hotel usual-team parameter).
# Runners have no system default: staffed only when the hotel sets a ratio.
_ROLE_PARAMS = {
    "servers": ("covers_per_server", "usual_servers"),
    "hosts": ("covers_per_host", "usual_hosts"),
    "runners": ("covers_per_runner", "usual_runners"),
    "kitchen": ("covers_per_kitchen_staff", "usual_kitchen_staff"),
}
_SOMMELIER_RULE = "1, or 2 above 160 covers"


@dataclass(frozen=True)
class RoleRule:
    covers_per: Optional[float]  # None -> role not staffed
    covers_per_source: str       # "hotel" | "default" | "none"
    usual: int
    usual_source: str            # "hotel" | "default"

    def as_dict(self) -> dict:
        return {
            "covers_per": self.covers_per, "covers_per_source": self.covers_per_source,
            "usual": self.usual, "usual_source": self.usual_source,
        }


@dataclass(frozen=True)
class StaffingRules:
    """The staffing rules one recommendation used, with where each came from."""

    roles: Dict[str, RoleRule]
    version: Optional[str] = None  # HotelParameters.version() when read from the hotel

    @classmethod
    def defaults(cls, cfg: Optional[StaffingConfig] = None) -> "StaffingRules":
        cfg = cfg or StaffingConfig()
        default_ratio = {"servers": cfg.covers_per_server, "hosts": cfg.covers_per_host,
                         "runners": None, "kitchen": cfg.covers_per_kitchen}
        default_usual = {"servers": cfg.usual_servers, "hosts": cfg.usual_hosts,
                         "runners": 0, "kitchen": cfg.usual_kitchen}
        return cls(roles={
            role: RoleRule(
                covers_per=default_ratio[role],
                covers_per_source="default" if default_ratio[role] is not None else "none",
                usual=default_usual[role], usual_source="default",
            )
            for role in _ROLE_PARAMS
        })

    @classmethod
    def from_parameters(cls, params: Any, cfg: Optional[StaffingConfig] = None) -> "StaffingRules":
        """Hotel values where set, system defaults elsewhere. ``params`` is a
        ``hotel_parameters.HotelParameters`` (anything with ``get``/``version``)."""
        base = cls.defaults(cfg)
        roles = {}
        for role, (ratio_name, usual_name) in _ROLE_PARAMS.items():
            d = base.roles[role]
            ratio, usual = params.get(ratio_name), params.get(usual_name)
            roles[role] = RoleRule(
                covers_per=ratio if ratio is not None else d.covers_per,
                covers_per_source="hotel" if ratio is not None else d.covers_per_source,
                usual=int(usual) if usual is not None else d.usual,
                usual_source="hotel" if usual is not None else d.usual_source,
            )
        return cls(roles=roles, version=params.version())

    def staffed(self) -> list[str]:
        return [r for r, rule in self.roles.items() if rule.covers_per is not None]

    def as_dict(self) -> dict:
        out = {role: rule.as_dict() for role, rule in self.roles.items()}
        out["sommeliers"] = {"rule": _SOMMELIER_RULE, "source": "default"}
        return out


class StaffingService:
    """Calculates staffing requirements based on demand."""

    @staticmethod
    def _staff_for(covers: float, rules: StaffingRules) -> tuple[Dict[str, int], int]:
        """Headcount per staffed role (ceil of covers / ratio) + sommeliers."""
        counts = {r: math.ceil(covers / rules.roles[r].covers_per) for r in rules.staffed()}
        sommeliers = 2 if covers > 160 else 1
        return counts, sommeliers

    async def rules_for(self, tenant_id: str, cfg: Optional[StaffingConfig] = None) -> StaffingRules:
        """The hotel's rules in force. Degrade-open: a read failure falls back
        to system defaults, labelled ``default``, and never blocks."""
        try:
            from app.db.session import AsyncSessionLocal
            from app.services import hotel_parameters

            async with AsyncSessionLocal() as db:
                params = await hotel_parameters.load(db, str(tenant_id))
            return StaffingRules.from_parameters(params, cfg)
        except Exception:  # noqa: BLE001 — degrade-open
            logger.warning("staffing: hotel rules unreadable for %s, using defaults", tenant_id)
            return StaffingRules.defaults(cfg)

    async def calculate_recommendation(
        self,
        predicted_covers: int,
        config: Optional[StaffingConfig] = None,
        confidence: Optional[float] = None,
        *,
        tenant_id: Optional[str] = None,
        rules: Optional[StaffingRules] = None,
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
        # HOS-343: the hotel's own rules when we know the hotel; explicit
        # `rules` win (demo, tests); otherwise system defaults, labelled so.
        if rules is None:
            rules = await self.rules_for(tenant_id, cfg) if tenant_id else StaffingRules.defaults(cfg)

        counts, sommeliers = self._staff_for(predicted_covers, rules)
        total_shifts = sum(counts.values()) + sommeliers
        current_cost = total_shifts * cfg.avg_shift_cost
        baseline_headcount = (
            sum(rules.roles[r].usual for r in rules.staffed()) + cfg.usual_sommeliers
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
            counts, sommeliers = self._staff_for(effective_covers, rules)

        if not verdict.within_bounds:
            await output_sanity.record_sanity_trip(hotel_id or tenant_id or "_system", verdict)

        sources = {rules.roles[r].covers_per_source for r in rules.staffed()}
        basis = ("the hotel's own ratios" if sources == {"hotel"}
                 else "default ratios" if sources == {"default"}
                 else "the hotel's ratios where set, defaults elsewhere")
        result = {
            "servers": counts.get("servers", 0),
            "hosts": counts.get("hosts", 0),
            "runners": counts.get("runners", 0),
            "kitchen": counts.get("kitchen", 0),
            "deltas": {
                **{r: counts[r] - rules.roles[r].usual for r in rules.staffed()},
                "sommeliers": sommeliers - cfg.usual_sommeliers,
            },
            "rules": rules.as_dict(),
            "rules_version": rules.version,
            "warnings": verdict.warnings,
            "sanity": {
                "within_bounds": verdict.within_bounds,
                "route_to_human": verdict.route_to_human,
                "clamped_covers": verdict.clamped_covers,
                "flags": [r for r, _ in verdict.flags],
            },
            "rationale": f"Staffing suggestion based on {effective_covers} covers, using {basis}.",
        }
        # Demo board: highlight Staffing Service node after recommendation
        asyncio.create_task(demo_emit("staffing"))
        return result

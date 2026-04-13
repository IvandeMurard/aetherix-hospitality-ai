import math
from typing import Dict, Optional
from pydantic import BaseModel

class StaffingConfig(BaseModel):
    covers_per_server: int = 18
    covers_per_host: int = 70
    covers_per_kitchen: int = 50
    usual_servers: int = 7
    usual_hosts: int = 2
    usual_kitchen: int = 3
    usual_sommeliers: int = 1

    # Daily budget; compare against total_shifts * avg_shift_cost for one service
    labor_budget_gbp_per_day: float = 1200.0
    avg_shift_cost: float = 80.0

class StaffingService:
    """Calculates staffing requirements based on demand."""

    async def calculate_recommendation(self, predicted_covers: int, config: Optional[StaffingConfig] = None) -> Dict:
        cfg = config or StaffingConfig()

        servers = math.ceil(predicted_covers / cfg.covers_per_server)
        hosts = math.ceil(predicted_covers / cfg.covers_per_host)
        kitchen = math.ceil(predicted_covers / cfg.covers_per_kitchen)

        # Role-specific: Sommelier required for high-volume/premium days
        sommeliers = 1
        if predicted_covers > 160:
            sommeliers = 2

        total_shifts = servers + hosts + kitchen + sommeliers
        current_cost = total_shifts * cfg.avg_shift_cost

        warnings = []
        if current_cost > cfg.labor_budget_gbp_per_day:
            msg = (
                f"Budget Alert: Projected daily labor cost £{current_cost:.0f} "
                f"exceeds daily budget of £{cfg.labor_budget_gbp_per_day:.0f}"
            )
            warnings.append(msg)
            await self._dispatch_budget_alert(predicted_covers, current_cost, cfg.labor_budget_gbp_per_day)

        return {
            "servers": servers,
            "hosts": hosts,
            "kitchen": kitchen,
            "deltas": {
                "servers": servers - cfg.usual_servers,
                "hosts": hosts - cfg.usual_hosts,
                "kitchen": kitchen - cfg.usual_kitchen,
                "sommeliers": sommeliers - cfg.usual_sommeliers
            },
            "warnings": warnings,
            "rationale": f"Staffing suggestion based on {predicted_covers} covers. Optimized for role-ratios."
        }

    @staticmethod
    async def _dispatch_budget_alert(covers: int, cost: float, budget: float) -> None:
        from app.services.ops_dispatcher import dispatch_anomaly
        await dispatch_anomaly(
            title=f"Labor budget exceeded — £{cost:.0f} vs £{budget:.0f} daily limit",
            detail=(
                f"Predicted covers: {covers}\n"
                f"Estimated daily cost: £{cost:.2f} | Daily budget: £{budget:.2f} | Overage: £{cost - budget:.2f}\n\n"
                "Review staffing ratios or adjust the labor budget in StaffingConfig."
            ),
            tags=["budget", "staffing"],
        )

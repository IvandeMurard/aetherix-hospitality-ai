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
    
    # Constraints
    labor_budget_gbp: float = 1200.0 # Weekly or daily target
    avg_shift_cost: float = 80.0

class StaffingService:
    """Calculates staffing requirements based on demand."""
    
    def calculate_recommendation(self, predicted_covers: int, config: Optional[StaffingConfig] = None) -> Dict:
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
        if current_cost > cfg.labor_budget_gbp:
            warnings.append(f"Budget Alert: Estimated cost £{current_cost} exceeds limit £{cfg.labor_budget_gbp}")
        
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

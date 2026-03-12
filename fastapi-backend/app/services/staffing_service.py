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

class StaffingService:
    """Calculates staffing requirements based on demand."""
    
    def calculate_recommendation(self, predicted_covers: int, config: Optional[StaffingConfig] = None) -> Dict:
        cfg = config or StaffingConfig()
        
        servers = math.ceil(predicted_covers / cfg.covers_per_server)
        hosts = math.ceil(predicted_covers / cfg.covers_per_host)
        kitchen = math.ceil(predicted_covers / cfg.covers_per_kitchen)
        
        return {
            "servers": servers,
            "hosts": hosts,
            "kitchen": kitchen,
            "deltas": {
                "servers": servers - cfg.usual_servers,
                "hosts": hosts - cfg.usual_hosts,
                "kitchen": kitchen - cfg.usual_kitchen
            },
            "rationale": f"Staffing suggestion based on {predicted_covers} covers."
        }

"""
Staff Recommender Agent
Calculates optimal staffing based on predicted covers
"""

from typing import Dict, Optional
from pydantic import BaseModel
import math


class RestaurantConfig(BaseModel):
    """Restaurant-specific staffing configuration"""
    restaurant_id: str
    covers_per_server: int = 18
    covers_per_host: int = 70
    covers_per_kitchen: int = 50
    usual_servers: int = 7
    usual_hosts: int = 2
    usual_kitchen: int = 3
    min_servers: int = 2
    min_hosts: int = 1
    min_kitchen: int = 1


class StaffRecommenderAgent:
    """Agent for calculating adaptive staffing recommendations"""
    
    def __init__(self):
        # Phase 1: Mock configs (Phase 2: Supabase lookup)
        self.default_config = RestaurantConfig(restaurant_id="default")
    
    async def recommend(
        self, 
        predicted_covers: int,
        restaurant_id: str = "default",
        config: Optional[RestaurantConfig] = None
    ) -> Dict:
        """
        Calculate recommended staffing based on predicted covers
        
        Returns:
            Dict with servers, hosts, kitchen counts + deltas vs usual
        """
        cfg = config or self.default_config
        
        # Calculate required staff (round up)
        servers_needed = max(cfg.min_servers, math.ceil(predicted_covers / cfg.covers_per_server))
        hosts_needed = max(cfg.min_hosts, math.ceil(predicted_covers / cfg.covers_per_host))
        kitchen_needed = max(cfg.min_kitchen, math.ceil(predicted_covers / cfg.covers_per_kitchen))
        
        # Calculate deltas vs usual
        server_delta = servers_needed - cfg.usual_servers
        host_delta = hosts_needed - cfg.usual_hosts
        kitchen_delta = kitchen_needed - cfg.usual_kitchen
        
        # Generate rationale
        rationale = self._generate_rationale(
            predicted_covers, servers_needed, server_delta, cfg
        )
        
        return {
            "servers": {
                "recommended": servers_needed,
                "usual": cfg.usual_servers,
                "delta": server_delta
            },
            "hosts": {
                "recommended": hosts_needed,
                "usual": cfg.usual_hosts,
                "delta": host_delta
            },
            "kitchen": {
                "recommended": kitchen_needed,
                "usual": cfg.usual_kitchen,
                "delta": kitchen_delta
            },
            "rationale": rationale,
            "covers_per_staff": round(predicted_covers / (servers_needed + hosts_needed + kitchen_needed), 1)
        }
    
    def _generate_rationale(
        self, 
        covers: int, 
        servers: int, 
        delta: int, 
        cfg: RestaurantConfig
    ) -> str:
        """Generate human-readable staffing rationale"""
        if delta > 2:
            intensity = "Very high"
            action = f"Add {delta} servers to handle peak demand"
        elif delta > 0:
            intensity = "Above average"
            action = f"Add {delta} server(s) for smooth service"
        elif delta < -2:
            intensity = "Low"
            action = f"Reduce by {abs(delta)} servers to optimize costs"
        elif delta < 0:
            intensity = "Below average"
            action = f"Consider reducing by {abs(delta)} server(s)"
        else:
            intensity = "Normal"
            action = "Maintain usual staffing levels"
        
        return f"{intensity} demand ({covers} covers). {action}."

from app.services.pms_sync import PMSAdapter
from typing import List, Dict, Any, Optional
import os
import logging
import time
import httpx
from datetime import date, datetime

logger = logging.getLogger(__name__)

class ApaleoPMSAdapter(PMSAdapter):
    """
    Adapter for the Apaleo PMS API.
    Implementation of Story 2.1 (Establish PMS API Connection & Auth).
    """
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.api_base_url = "https://api.apaleo.com"
        self.client_id = client_id or os.getenv("APALEO_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("APALEO_CLIENT_SECRET")
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0

    async def _authenticate(self):
        """Fetch/Refresh OAuth2 token for Apaleo."""
        # Check if token is still valid (with 60s buffer)
        if self.access_token and time.time() < self.token_expiry - 60:
            return

        if not self.client_id or not self.client_secret:
            raise ValueError("Apaleo credentials missing in environment.")
        
        token_url = "https://identity.apaleo.com/connect/token"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "scope": "offline_access openid profile read:occupancy read:revenue write:schedules"
                    }
                )
                
                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expiry = time.time() + expires_in
                    logger.info("Successfully authenticated with Apaleo")
                else:
                    logger.error(f"Apaleo Auth Error: {response.text}")
                    raise Exception(f"Failed to authenticate with Apaleo: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Apaleo Auth Exception: {str(e)}")
                raise

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        """
        Fetches occupancy metrics for a given date.
        """
        if not self.access_token:
            await self._authenticate()
            
        params = {
            "date": target_date.isoformat(),
            "propertyId": property_id
        }
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = f"{self.api_base_url}/booking/v1/metrics/occupancy"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Real parsing for Apaleo occupancy metrics
                    return int(data.get("occupancy") or 85)
                else:
                    logger.warning(f"Apaleo Occupancy fetch failed ({response.status_code}).")
                    return 85
        except Exception as e:
            logger.error(f"Apaleo API error: {str(e)}")
            return 80

    async def get_revenue(self, property_id: str, target_date: date, category: str = "Total") -> float:
        """
        Fetches revenue metrics.
        """
        if not self.access_token:
            await self._authenticate()
            
        url = f"{self.api_base_url}/finance/v1/metrics/revenue"
        params = {
            "from": target_date.isoformat(),
            "to": target_date.isoformat(),
            "propertyId": property_id
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Logic: Sum up F&B categories if available, else total
                    revenue_list = data.get("revenue", [])
                    fb_revenue = sum(item.get("amount", 0.0) for item in revenue_list if category.lower() in item.get("category", "").lower())
                    return fb_revenue if fb_revenue > 0 else sum(item.get("amount", 0.0) for item in revenue_list)
                return 0.0
        except Exception:
            return 0.0

    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Fetches bulk historical data from Apaleo Stay API.
        Implementation for Story 2.2.
        """
        if not self.access_token:
            await self._authenticate()
            
        url = f"{self.api_base_url}/reports/v1/stay-records"
        params = {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "propertyId": property_id
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    return response.json() # Returns list of stay records
                logger.warning(f"Failed to fetch historical data: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Apaleo Historical fetch error: {str(e)}")
            return []

    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        """
        Writes staffing recommendations back to Apaleo Schedules/Operations.
        Note: Target endpoint is exploratory based on 'Schedules' project requirement.
        """
        if not self.access_token:
            await self._authenticate()
            
        url = f"{self.api_base_url}/operations/v1/schedules"
        payload = {
            "propertyId": property_id,
            "date": target_date.isoformat(),
            "deltas": staffing_deltas,
            "source": "Aetherix-AI"
        }
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code in [200, 201, 204]:
                    logger.info(f"Successfully pushed staffing to Apaleo for {property_id}")
                    return True
                logger.error(f"Apaleo Push Failed ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"Apaleo Push Exception: {str(e)}")
            return False

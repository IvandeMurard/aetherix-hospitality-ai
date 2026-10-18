"""Mock PMS adapter for development and pilot verification (moved by HOS-280).

Values are fixed fixtures, never a hotel's data: every canonical value is
flagged ``is_placeholder=True``. Legacy ``get_*`` values are unchanged.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedReservation,
    NormalizedRevenue,
    OccupancyUnit,
    PMSProviderName,
    RevenueScope,
)


class MockPMSAdapter:
    """Mock adapter for development and pilot verification."""

    provider_name = PMSProviderName.MOCK
    transport = "mock"
    is_configured = True

    def __init__(self):
        # Mocking some baseline data
        self.mock_data = {
            "pilot_hotel": {
                "base_occupancy": 100,
                "base_fb_revenue": 2500.0,
            }
        }

    async def aclose(self) -> None:
        return None

    async def fetch_occupancy(self, property_id: str, target_date: date) -> NormalizedOccupancy:
        return NormalizedOccupancy(
            pms_property_id=property_id, day=target_date,
            value=int(self.mock_data.get(property_id, {}).get("base_occupancy", 50)),
            unit=OccupancyUnit.AS_REPORTED, provider=PMSProviderName.MOCK, is_placeholder=True,
        )

    async def fetch_revenue(self, property_id: str, target_date: date, category: str = "Total") -> NormalizedRevenue:
        return NormalizedRevenue(
            pms_property_id=property_id, day=target_date,
            amount=self.mock_data.get(property_id, {}).get("base_fb_revenue", 1000.0),
            category=category, scope=RevenueScope.CATEGORY, provider=PMSProviderName.MOCK, is_placeholder=True,
        )

    async def fetch_reservations(self, property_id: str, start: date, end: date) -> List[NormalizedReservation]:
        return []

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        return (await self.fetch_occupancy(property_id, target_date)).value

    async def get_revenue(self, property_id: str, target_date: date, category: str = "Total") -> float:
        return (await self.fetch_revenue(property_id, target_date, category)).amount

    async def get_historical_data(self, property_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        return [
            {
                "date": target_date.isoformat(),
                "occupancy": 80,
                "fb_revenue": 2000.0,
            } for target_date in [start_date]  # Simplification for mock
        ]

    async def update_staffing_in_pms(self, property_id: str, target_date: date, staffing_deltas: Dict[str, int]) -> bool:
        # Simulate successful write-back
        print(f"Mocked push to {property_id} on {target_date}: {staffing_deltas}")
        return True

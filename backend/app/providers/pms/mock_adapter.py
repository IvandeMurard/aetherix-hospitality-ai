"""Mock PMS adapter for development and pilot verification (moved by HOS-280).

Values are fixed fixtures, never a hotel's data: every canonical value has
status ``fixture`` (HOS-352), so nothing downstream learns from it.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedReservation,
    NormalizedRevenue,
    PMSDataStatus,
    PMSProviderName,
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
                "rooms_sold": 100,
                "rooms_available": 120,
                "fb_revenue": 2500.0,
            }
        }

    def _fixture(self, property_id: str) -> Dict[str, Any]:
        return self.mock_data.get(property_id, {"rooms_sold": 50, "rooms_available": 80, "fb_revenue": 1000.0})

    async def aclose(self) -> None:
        return None

    async def fetch_occupancy(self, property_id: str, target_date: date) -> NormalizedOccupancy:
        f = self._fixture(property_id)
        return NormalizedOccupancy(
            pms_property_id=property_id, day=target_date, provider=PMSProviderName.MOCK,
            status=PMSDataStatus.FIXTURE, rooms_sold=f["rooms_sold"], rooms_available=f["rooms_available"],
        )

    async def fetch_fb_revenue(self, property_id: str, target_date: date) -> NormalizedRevenue:
        return NormalizedRevenue(
            pms_property_id=property_id, day=target_date, provider=PMSProviderName.MOCK,
            status=PMSDataStatus.FIXTURE, amount=self._fixture(property_id)["fb_revenue"], currency="EUR",
        )

    async def fetch_reservations(self, property_id: str, start: date, end: date) -> List[NormalizedReservation]:
        return []

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

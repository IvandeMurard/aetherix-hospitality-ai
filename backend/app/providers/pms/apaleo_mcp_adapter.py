"""
Apaleo PMS adapter backed by Apaleo's MCP Server (direct, bearer mode).

Drop-in replacement for ``ApaleoPMSAdapter`` — same interface via MCP tool
calls instead of raw REST. Decision HOS-101: MCP > API raw. Moved to the
vendor-neutral PMS layer by HOS-280 (Décision #28).

Requires APALEO_MCP_SERVER_URL to be set (provided by Apaleo on alpha access).
Falls back to placeholder values when not configured or on error, so the
pipeline is never blocked. Since HOS-280 those values are **flagged**
(``is_placeholder=True``): occupancy 80 and revenue 0.0 never came from the PMS.
The values themselves are unchanged by this story.

MCP tool mapping (Apaleo native PascalCase naming):
    fetch_occupancy      → ListPropertyPerformanceReport  (soldCount/houseCount → percent)
    fetch_revenue        → ListRevenuesReport              (grossAmount.amount, all revenue)
    fetch_reservations   → ListReservations                (reservations[])
    update_staffing      → not available in Apaleo MCP     (returns False)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.providers.pms.apaleo_adapter import map_stay_record
from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedReservation,
    NormalizedRevenue,
    OccupancyUnit,
    PMSProviderName,
    RevenueScope,
)

logger = logging.getLogger(__name__)

PLACEHOLDER_OCCUPANCY = 80
PLACEHOLDER_REVENUE = 0.0


class ApaleoMCPAdapter:
    """
    PMS adapter using Apaleo's MCP Server.

    Inject a custom client for testing::

        adapter = ApaleoMCPAdapter(mcp_client=FakeClient())
    """

    provider_name = PMSProviderName.APALEO
    transport = "mcp"

    def __init__(self, mcp_client: ApaleoMCPClient | None = None) -> None:
        self._client = mcp_client or ApaleoMCPClient()

    @property
    def is_configured(self) -> bool:
        return bool(self._client.is_configured)

    async def aclose(self) -> None:
        return None

    # --- canonical (providers/pms/base.py) -----------------------------------------

    def _placeholder_occupancy(self, property_id: str, day: date) -> NormalizedOccupancy:
        return NormalizedOccupancy(
            pms_property_id=property_id, day=day, value=PLACEHOLDER_OCCUPANCY,
            unit=OccupancyUnit.PERCENT, provider=PMSProviderName.APALEO, is_placeholder=True,
        )

    async def fetch_occupancy(self, property_id: str, target_date: date) -> NormalizedOccupancy:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — placeholder occupancy (80)")
            return self._placeholder_occupancy(property_id, target_date)
        try:
            data = await self._client.call_tool(
                "ListPropertyPerformanceReport",
                {"property_id": property_id, "from_": target_date.isoformat(), "to": target_date.isoformat()},
            )
            report = data.get("data", {}) if isinstance(data, dict) else {}
            house = int(report.get("houseCount", 0))
            sold = int(report.get("soldCount", 0))
            if house > 0:
                return NormalizedOccupancy(
                    pms_property_id=property_id, day=target_date, value=round(sold / house * 100),
                    unit=OccupancyUnit.PERCENT, provider=PMSProviderName.APALEO,
                    rooms_sold=sold, rooms_available=house,
                )
            return self._placeholder_occupancy(property_id, target_date)
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.fetch_occupancy failed: %s", exc)
            return self._placeholder_occupancy(property_id, target_date)

    async def fetch_revenue(
        self, property_id: str, target_date: date, category: str = "Total"
    ) -> NormalizedRevenue:
        def placeholder() -> NormalizedRevenue:
            return NormalizedRevenue(
                pms_property_id=property_id, day=target_date, amount=PLACEHOLDER_REVENUE, category=category,
                scope=RevenueScope.ALL_REVENUE, provider=PMSProviderName.APALEO, is_placeholder=True,
            )

        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — placeholder revenue (0.0)")
            return placeholder()
        try:
            data = await self._client.call_tool(
                "ListRevenuesReport",
                {
                    "property_id": property_id,
                    "from_": target_date.isoformat(),
                    "to": target_date.isoformat(),
                },
            )
            report = data.get("data", data) if isinstance(data, dict) else {}
            if isinstance(report, list):
                amount = sum(float(r.get("grossAmount", {}).get("amount", 0.0)) for r in report)
            else:
                amount = float(report.get("grossAmount", {}).get("amount", 0.0))
            # The MCP report ignores the category: labelled, not fixed here.
            return NormalizedRevenue(
                pms_property_id=property_id, day=target_date, amount=amount, category=category,
                scope=RevenueScope.ALL_REVENUE, provider=PMSProviderName.APALEO,
            )
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.fetch_revenue failed: %s", exc)
            return placeholder()

    async def fetch_reservations(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[NormalizedReservation]:
        return [map_stay_record(r) for r in await self.get_historical_data(property_id, start_date, end_date)]

    # --- legacy interface (values identical to before HOS-280) ------------------------

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        return (await self.fetch_occupancy(property_id, target_date)).value

    async def get_revenue(
        self, property_id: str, target_date: date, category: str = "Total"
    ) -> float:
        return (await self.fetch_revenue(property_id, target_date, category)).amount

    async def get_historical_data(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Raw reservations, for the forecast pipeline until it reads
        ``fetch_reservations`` (HOS-281)."""
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning empty history")
            return []
        try:
            data = await self._client.call_tool(
                "ListReservations",
                {
                    "property_ids": [property_id],
                    "date_filter": "Stay",
                    "from_": f"{start_date.isoformat()}T00:00:00Z",
                    "to": f"{end_date.isoformat()}T23:59:59Z",
                    "status": ["Confirmed", "InHouse", "CheckedOut"],
                    "page_size": 200,
                },
            )
            if isinstance(data, list):
                return data
            inner = data.get("data", data) if isinstance(data, dict) else data
            if isinstance(inner, list):
                return inner
            return inner.get("reservations", [])
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.get_historical_data failed: %s", exc)
            return []

    async def update_staffing_in_pms(
        self, property_id: str, target_date: date, staffing_deltas: dict[str, int]
    ) -> bool:
        # Apaleo MCP does not expose a staffing/schedule update tool.
        # Writes are also blocked in Phase 0 (APALEO_READONLY=true, HOS-107).
        logger.warning(
            "ApaleoMCPAdapter.update_staffing_in_pms: no staffing tool available "
            "in Apaleo MCP — property=%s date=%s",
            property_id, target_date,
        )
        return False

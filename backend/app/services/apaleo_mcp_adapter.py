"""
Apaleo PMS adapter backed by Apaleo's MCP Server (direct, bearer mode).

Drop-in replacement for ``ApaleoPMSAdapter`` — implements the same
``PMSAdapter`` interface via MCP tool calls instead of raw REST.

Decision HOS-101: MCP > API raw.

Requires APALEO_MCP_SERVER_URL to be set (provided by Apaleo on alpha access).
Falls back to safe defaults when not configured, so the pipeline is never blocked.

MCP tool mapping (Apaleo native PascalCase naming):
    get_occupancy        → ListPropertyPerformanceReport  (soldCount/houseCount)
    get_revenue          → ListRevenuesReport              (grossAmount.amount)
    get_historical_data  → ListReservations                (reservations[])
    update_staffing      → not available in Apaleo MCP     (returns False)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.integrations.apaleo_logger import ApaleoWriteBlockedError
from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.services.pms_sync import PMSAdapter

logger = logging.getLogger(__name__)


class ApaleoMCPAdapter(PMSAdapter):
    """
    PMSAdapter implementation using Apaleo's MCP Server.

    Inject a custom client for testing::

        adapter = ApaleoMCPAdapter(mcp_client=FakeClient())
    """

    def __init__(self, mcp_client: ApaleoMCPClient | None = None) -> None:
        self._client = mcp_client or ApaleoMCPClient()

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning mock occupancy (80)")
            return 80
        try:
            data = await self._client.call_tool(
                "ListPropertyPerformanceReport",
                {"property_id": property_id, "from_": target_date.isoformat(), "to": target_date.isoformat()},
            )
            report = data.get("data", {}) if isinstance(data, dict) else {}
            house = int(report.get("houseCount", 0))
            sold = int(report.get("soldCount", 0))
            if house > 0:
                return round(sold / house * 100)
            return 80
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.get_occupancy failed: %s", exc)
            return 80

    async def get_revenue(
        self, property_id: str, target_date: date, category: str = "Total"
    ) -> float:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning 0.0 revenue")
            return 0.0
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
                return sum(
                    float(r.get("grossAmount", {}).get("amount", 0.0)) for r in report
                )
            return float(report.get("grossAmount", {}).get("amount", 0.0))
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.get_revenue failed: %s", exc)
            return 0.0

    async def get_historical_data(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
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

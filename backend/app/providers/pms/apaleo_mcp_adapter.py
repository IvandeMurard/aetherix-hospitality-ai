"""
Apaleo PMS adapter backed by Apaleo's MCP Server (direct, bearer mode).

Same canonical interface as ``ApaleoPMSAdapter``, via MCP tool calls instead
of raw REST. Decision HOS-101: MCP > API raw. Moved to the vendor-neutral PMS
layer by HOS-280 (Décision #28).

Requires APALEO_MCP_SERVER_URL to be set (provided by Apaleo on alpha access).
Since HOS-352 a figure is true or absent: not configured, on error, or with
nothing usable in the report, the adapter returns an absent value with its
status. It used to return occupancy 80 and revenue 0.0 as if the PMS had
said so.

MCP tool mapping (Apaleo native PascalCase naming):
    fetch_occupancy      → ListPropertyPerformanceReport  (soldCount / houseCount − outOfOrderCount)
    fetch_fb_revenue     → ListPropertyPerformanceReport  (netFoodAndBeveragesRevenue)
    fetch_reservations   → ListReservations                (reservations[])
    update_staffing      → not available in Apaleo MCP     (returns False)

``ListRevenuesReport`` is no longer used: probed on 18/10/2026 it returns the
"Revenues" account total (not F&B), and 422 when ``to`` equals ``from``.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.providers.pms.apaleo_adapter import map_performance_report, map_stay_record
from app.providers.pms.base import (
    NormalizedOccupancy,
    NormalizedReservation,
    NormalizedRevenue,
    PMSDataStatus,
    PMSProviderName,
)

logger = logging.getLogger(__name__)


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

    async def _performance(self, property_id: str, target_date: date) -> tuple[NormalizedOccupancy, NormalizedRevenue]:
        apaleo = PMSProviderName.APALEO

        def absent(status: PMSDataStatus, detail: str | None = None):
            return (NormalizedOccupancy.absent(property_id, target_date, apaleo, status, detail),
                    NormalizedRevenue.absent(property_id, target_date, apaleo, status, detail))

        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — occupancy and F&B revenue absent")
            return absent(PMSDataStatus.NOT_CONFIGURED)
        try:
            data = await self._client.call_tool(
                "ListPropertyPerformanceReport",
                {"property_id": property_id, "from_": target_date.isoformat(), "to": target_date.isoformat()},
            )
        except Exception as exc:  # noqa: BLE001 — any failure is a pms_error, never a made-up figure
            logger.error("ApaleoMCPAdapter: performance report failed: %s", exc)
            return absent(PMSDataStatus.PMS_ERROR, str(exc)[:200])
        # The MCP server returns Apaleo's HTTP errors as a payload, not an exception.
        if isinstance(data, dict) and int(data.get("status_code") or 200) >= 400:
            logger.error("ApaleoMCPAdapter: performance report HTTP %s", data.get("status_code"))
            return absent(PMSDataStatus.PMS_ERROR, f"HTTP {data.get('status_code')}: {str(data.get('message'))[:160]}")
        report = data.get("data", {}) if isinstance(data, dict) else {}
        return map_performance_report(report, property_id, target_date)

    async def fetch_occupancy(self, property_id: str, target_date: date) -> NormalizedOccupancy:
        return (await self._performance(property_id, target_date))[0]

    async def fetch_fb_revenue(self, property_id: str, target_date: date) -> NormalizedRevenue:
        return (await self._performance(property_id, target_date))[1]

    async def fetch_reservations(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[NormalizedReservation]:
        return [map_stay_record(r) for r in await self.get_historical_data(property_id, start_date, end_date)]

    # --- legacy interface ------------------------------------------------------------

    async def get_historical_data(
        self, property_id: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Raw reservations; ``fetch_reservations`` maps them to the canonical
        schema (HOS-281)."""
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

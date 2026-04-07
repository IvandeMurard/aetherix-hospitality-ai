"""
Apaleo PMS adapter backed by Apaleo's MCP Server (direct, bearer mode).

Drop-in replacement for ``ApaleoPMSAdapter`` — implements the same
``PMSAdapter`` interface via MCP tool calls instead of raw REST.

Decision HOS-101: MCP > API raw.

Requires APALEO_MCP_SERVER_URL to be set (provided by Apaleo on alpha access).
Falls back to safe defaults when not configured, so the pipeline is never blocked.

MCP tool mapping (Apaleo Core API — 237 endpoints):
    get_occupancy        → APALEO_GET_OCCUPANCY_METRICS
    get_revenue          → APALEO_GET_REVENUE_METRICS
    get_historical_data  → APALEO_GET_RESERVATIONS
    update_staffing      → APALEO_UPDATE_SCHEDULE
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
                "APALEO_GET_OCCUPANCY_METRICS",
                {"propertyId": property_id, "date": target_date.isoformat()},
            )
            return int(data.get("occupancyPercent", data.get("occupancy", 80)))
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
                "APALEO_GET_REVENUE_METRICS",
                {
                    "propertyId": property_id,
                    "from": target_date.isoformat(),
                    "to": target_date.isoformat(),
                    "category": category,
                },
            )
            items: list[dict[str, Any]] = data.get("revenue", [])
            if not items:
                return float(data.get("totalRevenue", 0.0))
            matched = [
                float(i.get("amount", 0.0))
                for i in items
                if category.lower() in i.get("category", "").lower()
            ]
            return sum(matched) if matched else sum(float(i.get("amount", 0.0)) for i in items)
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
                "APALEO_GET_RESERVATIONS",
                {
                    "propertyId": property_id,
                    "from": start_date.isoformat(),
                    "to": end_date.isoformat(),
                    "pageSize": 500,
                },
            )
            if isinstance(data, list):
                return data
            return data.get("reservations", [])
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.get_historical_data failed: %s", exc)
            return []

    async def update_staffing_in_pms(
        self, property_id: str, target_date: date, staffing_deltas: dict[str, int]
    ) -> bool:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — staffing push skipped")
            return False
        try:
            data = await self._client.call_tool(
                "APALEO_UPDATE_SCHEDULE",
                {
                    "propertyId": property_id,
                    "date": target_date.isoformat(),
                    "deltas": staffing_deltas,
                    "source": "Aetherix-AI",
                },
            )
            success = bool(
                data.get("success")
                or data.get("status") in ("ok", "created", "updated", "accepted")
            )
            logger.info(
                "ApaleoMCPAdapter.update_staffing: property=%s date=%s success=%s",
                property_id, target_date, success,
            )
            return success
        except ApaleoWriteBlockedError:
            # Write-guard (HOS-107): re-raise so callers are explicitly aware
            # that writes are disabled in Phase 0 — do not silently return False.
            raise
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.update_staffing_in_pms failed: %s", exc)
            return False

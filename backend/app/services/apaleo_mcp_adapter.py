"""
Apaleo PMS adapter backed by Apaleo's MCP Server.

Drop-in replacement for ``ApaleoPMSAdapter`` — implements the same
``PMSAdapter`` interface but fetches data via MCP tool calls instead
of raw REST API calls.

Decision HOS-101: MCP > API raw.

Auth-mode scope (30/03/2026)
----------------------------
The available MCP path depends on ``ApaleoMCPClient.auth_mode``:

  ``"apikey"`` — Composio Tool Router (available now)
    Exposes **Inventory API** tools only: properties, units, unit groups.
    PMSAdapter methods (occupancy / revenue / reservations) are NOT
    available → they fall back to safe defaults.
    Use ``ApaleoInventoryMCPService`` below for Composio-specific calls.

  ``"bearer"`` — Apaleo direct alpha (invite required)
    Exposes the full Core API (237 endpoints), including:
      get_occupancy       → APALEO_GET_OCCUPANCY_METRICS
      get_revenue         → APALEO_GET_REVENUE_METRICS
      get_reservations    → APALEO_GET_RESERVATIONS
      update_schedule     → APALEO_UPDATE_SCHEDULE
    PMSAdapter methods are fully operational.

Routing
-------
- F&B operational data  → ``ApaleoPMSAdapter`` (raw REST, always works)
                          OR ``ApaleoMCPAdapter`` in bearer mode (alpha)
- Property setup        → ``ApaleoInventoryMCPService`` in apikey mode
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from app.integrations.apaleo_mcp_client import ApaleoMCPClient
from app.services.pms_sync import PMSAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Composio tool names (Inventory API — apikey mode)
# ---------------------------------------------------------------------------
# All tool names as exposed by Composio Apaleo toolkit (confirmed 30/03/2026).
# These are UPPERCASE snake_case identifiers, unlike hypothetical bearer names.

_TOOL_GET_PROPERTIES_LIST = "APALEO_GET_A_PROPERTIES_LIST"
_TOOL_GET_PROPERTY = "APALEO_GET_A_PROPERTY"
_TOOL_CREATE_PROPERTY = "APALEO_CREATES_A_PROPERTY"
_TOOL_ARCHIVE_PROPERTY = "APALEO_ARCHIVE_A_PROPERTY"
_TOOL_CLONE_PROPERTY = "APALEO_CLONES_A_PROPERTY"
_TOOL_MOVE_TO_LIVE = "APALEO_MOVE_PROPERTY_TO_LIVE"
_TOOL_RESET_DATA = "APALEO_RESET_PROPERTY_DATA"
_TOOL_GET_UNITS_LIST = "APALEO_GET_A_UNITS_LIST"
_TOOL_GET_UNIT = "APALEO_GET_A_UNIT"
_TOOL_CREATE_UNIT = "APALEO_CREATE_A_UNIT"
_TOOL_CREATE_MULTIPLE_UNITS = "APALEO_CREATE_MULTIPLE_UNITS"
_TOOL_DELETE_UNIT = "APALEO_DELETE_A_UNIT"
_TOOL_LIST_UNIT_GROUPS = "APALEO_LIST_UNIT_GROUPS"
_TOOL_GET_UNIT_GROUP = "APALEO_GET_A_UNIT_GROUP"
_TOOL_CREATE_UNIT_GROUP = "APALEO_CREATE_A_UNIT_GROUP"
_TOOL_REPLACE_UNIT_GROUP = "APALEO_REPLACE_A_UNIT_GROUP"
_TOOL_DELETE_UNIT_GROUP = "APALEO_DELETE_A_UNIT_GROUP"

# ---------------------------------------------------------------------------
# Bearer/direct tool names (full Core API — Apaleo alpha)
# ---------------------------------------------------------------------------

_TOOL_GET_OCCUPANCY = "APALEO_GET_OCCUPANCY_METRICS"
_TOOL_GET_REVENUE = "APALEO_GET_REVENUE_METRICS"
_TOOL_GET_RESERVATIONS = "APALEO_GET_RESERVATIONS"
_TOOL_UPDATE_SCHEDULE = "APALEO_UPDATE_SCHEDULE"


# ===========================================================================
# ApaleoMCPAdapter — PMSAdapter implementation (bearer / direct mode)
# ===========================================================================

class ApaleoMCPAdapter(PMSAdapter):
    """
    PMSAdapter backed by Apaleo MCP (bearer/direct mode — alpha).

    Fully functional for F&B operational data once Apaleo direct alpha
    access is granted. Falls back to safe defaults until then.

    Inject a custom client for testing::

        adapter = ApaleoMCPAdapter(mcp_client=FakeClient())
    """

    def __init__(self, mcp_client: ApaleoMCPClient | None = None) -> None:
        self._client = mcp_client or ApaleoMCPClient(auth_mode="bearer")

    async def get_occupancy(self, property_id: str, target_date: date) -> int:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning mock occupancy (80)")
            return 80
        try:
            data = await self._client.call_tool(
                _TOOL_GET_OCCUPANCY,
                {"propertyId": property_id, "date": target_date.isoformat()},
            )
            return int(data.get("occupancyPercent", data.get("occupancy", 80)))
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.get_occupancy failed: %s", exc)
            return 80

    async def get_revenue(
        self,
        property_id: str,
        target_date: date,
        category: str = "Total",
    ) -> float:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning 0.0 revenue")
            return 0.0
        try:
            data = await self._client.call_tool(
                _TOOL_GET_REVENUE,
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
        self,
        property_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — returning empty history")
            return []
        try:
            data = await self._client.call_tool(
                _TOOL_GET_RESERVATIONS,
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
        self,
        property_id: str,
        target_date: date,
        staffing_deltas: dict[str, int],
    ) -> bool:
        if not self._client.is_configured:
            logger.warning("ApaleoMCPAdapter: not configured — staffing push skipped")
            return False
        try:
            data = await self._client.call_tool(
                _TOOL_UPDATE_SCHEDULE,
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
        except Exception as exc:
            logger.error("ApaleoMCPAdapter.update_staffing_in_pms failed: %s", exc)
            return False


# ===========================================================================
# ApaleoInventoryMCPService — property/unit management via Composio
# ===========================================================================

class ApaleoInventoryMCPService:
    """
    Property and unit management via Composio Apaleo MCP (apikey mode).

    Wraps the Inventory API tools that Composio exposes today.
    Not part of PMSAdapter — this is a separate service for property
    setup operations (onboarding, unit management, cloning).

    Usage::

        svc = ApaleoInventoryMCPService()
        props = await svc.list_properties()
        await svc.create_unit(property_id="MUC", unit_name="101")
    """

    def __init__(self, mcp_client: ApaleoMCPClient | None = None) -> None:
        self._client = mcp_client or ApaleoMCPClient(auth_mode="apikey")

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured

    async def list_properties(self) -> list[dict[str, Any]]:
        """Return the list of properties accessible in this Apaleo account."""
        data = await self._client.call_tool(_TOOL_GET_PROPERTIES_LIST, {})
        if isinstance(data, list):
            return data
        return data.get("properties", [])

    async def get_property(self, property_id: str) -> dict[str, Any]:
        return await self._client.call_tool(_TOOL_GET_PROPERTY, {"id": property_id})

    async def create_property(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._client.call_tool(_TOOL_CREATE_PROPERTY, payload)

    async def clone_property(self, property_id: str) -> dict[str, Any]:
        return await self._client.call_tool(_TOOL_CLONE_PROPERTY, {"id": property_id})

    async def archive_property(self, property_id: str) -> dict[str, Any]:
        return await self._client.call_tool(_TOOL_ARCHIVE_PROPERTY, {"id": property_id})

    async def move_to_live(self, property_id: str) -> dict[str, Any]:
        return await self._client.call_tool(_TOOL_MOVE_TO_LIVE, {"id": property_id})

    async def list_units(self, property_id: str) -> list[dict[str, Any]]:
        data = await self._client.call_tool(_TOOL_GET_UNITS_LIST, {"propertyId": property_id})
        if isinstance(data, list):
            return data
        return data.get("units", [])

    async def create_unit(self, property_id: str, unit_name: str, **kwargs: Any) -> dict[str, Any]:
        return await self._client.call_tool(
            _TOOL_CREATE_UNIT,
            {"propertyId": property_id, "name": unit_name, **kwargs},
        )

    async def create_multiple_units(
        self, property_id: str, naming_rule: str, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        return await self._client.call_tool(
            _TOOL_CREATE_MULTIPLE_UNITS,
            {"propertyId": property_id, "namingRule": naming_rule, "count": count, **kwargs},
        )

    async def list_unit_groups(self, property_id: str) -> list[dict[str, Any]]:
        data = await self._client.call_tool(_TOOL_LIST_UNIT_GROUPS, {"propertyId": property_id})
        if isinstance(data, list):
            return data
        return data.get("unitGroups", [])

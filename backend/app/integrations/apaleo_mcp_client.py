"""
ApaleoMCPClient — wraps Apaleo REST API as MCP-compatible tools.

Designed for direct use inside the FastAPI backend (no subprocess/stdio).
Provides list_tools() and call_tool() to satisfy the MCP probe contract.

Required env vars:
    APALEO_CLIENT_ID      OAuth2 client ID
    APALEO_CLIENT_SECRET  OAuth2 client secret
    APALEO_PROPERTY_ID    Property code (e.g. "IIQJ")
"""

import base64
import os
import time
from datetime import date, timedelta
from typing import Any

import httpx

APALEO_TOKEN_URL = "https://identity.apaleo.com/connect/token"
APALEO_API_BASE = "https://api.apaleo.com"

TOOL_REGISTRY: list[dict] = [
    {
        "name": "APALEO_GET_OCCUPANCY_METRICS",
        "description": (
            "Return today's reservation count and occupancy for the configured "
            "Apaleo property. Returns an empty dataset if the sandbox has no "
            "reservations — a 2xx response is the success criterion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (defaults to today)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "APALEO_LIST_RESERVATIONS",
        "description": "List reservations for a date range from the Apaleo PMS.",
        "input_schema": {
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
            },
            "required": ["from_date", "to_date"],
        },
    },
]


class ApaleoMCPClient:
    def __init__(self) -> None:
        self.client_id = os.getenv("APALEO_CLIENT_ID", "")
        self.client_secret = os.getenv("APALEO_CLIENT_SECRET", "")
        self.property_id = os.getenv("APALEO_PROPERTY_ID", "")
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def has_credentials(self) -> bool:
        return bool(
            self.client_id
            and self.client_secret
            and self.client_id not in ("...", "")
            and self.client_secret not in ("...", "")
        )

    async def authenticate(self) -> float:
        """Acquire OAuth2 bearer token. Returns elapsed ms."""
        t0 = time.monotonic()
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                APALEO_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        return (time.monotonic() - t0) * 1000

    async def _ensure_token(self) -> None:
        if not self._token or time.time() >= self._token_expires_at - 30:
            await self.authenticate()

    def list_tools(self) -> list[dict]:
        return TOOL_REGISTRY

    async def call_tool(self, name: str, args: dict[str, Any] | None = None) -> dict:
        await self._ensure_token()
        args = args or {}

        if name == "APALEO_GET_OCCUPANCY_METRICS":
            return await self._get_occupancy_metrics(
                args.get("target_date", date.today().isoformat())
            )
        if name == "APALEO_LIST_RESERVATIONS":
            return await self._list_reservations(
                args["from_date"], args["to_date"]
            )
        raise ValueError(f"Unknown tool: {name}")

    async def _get_occupancy_metrics(self, target_date: str) -> dict:
        # Apaleo requires ISO date-time with timezone and from < to.
        day = date.fromisoformat(target_date)
        frm = f"{day.isoformat()}T00:00:00Z"
        to = f"{(day + timedelta(days=1)).isoformat()}T00:00:00Z"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{APALEO_API_BASE}/booking/v1/reservations",
                headers={"Authorization": f"Bearer {self._token}"},
                params={
                    "propertyIds": self.property_id or None,
                    "dateFilter": "Stay",
                    "from": frm,
                    "to": to,
                    "pageSize": 1,
                },
            )
            resp.raise_for_status()
            # 204 No Content -> no reservations for the range.
            data = resp.json() if resp.status_code != 204 and resp.content else {}
        return {
            "date": target_date,
            "total_count": data.get("count", 0),
            "source": "apaleo",
            "property_id": self.property_id,
        }

    async def _list_reservations(self, from_date: str, to_date: str) -> dict:
        # Apaleo requires ISO date-time with timezone for from/to.
        frm = f"{date.fromisoformat(from_date).isoformat()}T00:00:00Z"
        to = f"{date.fromisoformat(to_date).isoformat()}T00:00:00Z"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{APALEO_API_BASE}/booking/v1/reservations",
                headers={"Authorization": f"Bearer {self._token}"},
                params={
                    "propertyIds": self.property_id or None,
                    "dateFilter": "Arrival",
                    "from": frm,
                    "to": to,
                    "pageSize": 100,
                },
            )
            resp.raise_for_status()
            return resp.json() if resp.status_code != 204 and resp.content else {"reservations": []}

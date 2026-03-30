"""
Async MCP client for Apaleo's MCP Server (direct, OAuth2 bearer).

Connects to Apaleo's MCP Server via streamable-HTTP transport,
authenticating with OAuth2 client credentials — same flow as the raw API.

Required env vars:
    APALEO_CLIENT_ID        — OAuth2 client ID from Apaleo developer portal
    APALEO_CLIENT_SECRET    — OAuth2 client secret
    APALEO_MCP_SERVER_URL   — Apaleo MCP endpoint (provided on alpha access)

Usage::

    client = ApaleoMCPClient()
    data = await client.call_tool("APALEO_GET_OCCUPANCY_METRICS",
                                  {"propertyId": "MUC", "date": "2026-03-29"})
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_APALEO_TOKEN_URL = "https://identity.apaleo.com/connect/token"


class ApaleoMCPClient:
    """
    Thin async wrapper around Apaleo's MCP Server.

    Handles OAuth2 token lifecycle and exposes a single ``call_tool``
    coroutine. Falls back gracefully: if ``is_configured`` is False,
    ``call_tool`` raises ``RuntimeError`` — the adapter layer converts
    that to mock/default data.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        server_url: str | None = None,
    ) -> None:
        self.client_id: str = client_id or os.getenv("APALEO_CLIENT_ID", "")
        self.client_secret: str = client_secret or os.getenv("APALEO_CLIENT_SECRET", "")
        self.server_url: str = server_url or os.getenv("APALEO_MCP_SERVER_URL", "")
        self._token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def is_configured(self) -> bool:
        """True when all required credentials and server URL are present."""
        return bool(self.client_id and self.client_secret and self.server_url)

    async def _get_token(self) -> str:
        """Fetch or reuse a valid OAuth2 bearer token (30s buffer)."""
        if self._token and time.time() < self._token_expiry - 30:
            return self._token

        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(
                _APALEO_TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        logger.debug("Apaleo MCP token refreshed (expires in %ss)", data.get("expires_in", 3600))
        return self._token  # type: ignore[return-value]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call an Apaleo MCP tool and return its decoded result.

        Args:
            tool_name:  MCP tool name (e.g. ``"APALEO_GET_OCCUPANCY_METRICS"``).
            arguments:  JSON-serialisable tool input dict.

        Returns:
            Parsed JSON dict/list, or raw text if response is not JSON.

        Raises:
            RuntimeError: credentials not configured.
            httpx.HTTPStatusError: OAuth2 / transport failure.
            mcp.McpError: MCP protocol error.
        """
        if not self.is_configured:
            raise RuntimeError(
                "ApaleoMCPClient: not configured. "
                "Set APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, APALEO_MCP_SERVER_URL."
            )

        from mcp import ClientSession  # noqa: PLC0415
        from mcp.client.streamable_http import streamablehttp_client  # noqa: PLC0415

        token = await self._get_token()

        async with streamablehttp_client(
            self.server_url,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.debug("Calling Apaleo MCP tool %r with args %r", tool_name, arguments)
                result = await session.call_tool(tool_name, arguments)

        if result.content and result.content[0].type == "text":
            raw = result.content[0].text
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        return result

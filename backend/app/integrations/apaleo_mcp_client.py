"""
Async MCP client for Apaleo's MCP Server.

Connects to Apaleo's MCP Server via the streamable-HTTP transport,
authenticating with OAuth2 client credentials (same flow as the raw API).

Required env vars:
    APALEO_CLIENT_ID        — OAuth2 client ID from Apaleo developer portal
    APALEO_CLIENT_SECRET    — OAuth2 client secret
    APALEO_MCP_SERVER_URL   — Apaleo MCP endpoint
                              (default: https://mcp.apaleo.com)

Usage::

    client = ApaleoMCPClient()
    data = await client.call_tool("apaleo_get_occupancy_metrics",
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
_DEFAULT_MCP_SERVER_URL = "https://mcp.apaleo.com"


class ApaleoMCPClient:
    """
    Thin async wrapper around Apaleo's MCP Server.

    Handles OAuth2 token lifecycle and exposes a single ``call_tool``
    coroutine so callers never need to touch MCP transport details.

    Falls back gracefully: if ``is_configured`` is False, ``call_tool``
    raises ``RuntimeError`` immediately without attempting any network call —
    the adapter layer converts that to mock/default data.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        server_url: str | None = None,
    ) -> None:
        self.client_id: str = client_id or os.getenv("APALEO_CLIENT_ID", "")
        self.client_secret: str = client_secret or os.getenv("APALEO_CLIENT_SECRET", "")
        self.server_url: str = (
            server_url
            or os.getenv("APALEO_MCP_SERVER_URL", _DEFAULT_MCP_SERVER_URL)
        )
        self._token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def is_configured(self) -> bool:
        """True when all required credentials and the server URL are present."""
        return bool(self.client_id and self.client_secret and self.server_url)

    async def _refresh_token(self) -> str:
        """Fetch or reuse a valid OAuth2 bearer token.

        Uses a 30-second buffer so the token is never sent when it is
        about to expire mid-request.
        """
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
        logger.debug(
            "Apaleo MCP OAuth2 token refreshed (expires in %ss)",
            data.get("expires_in", 3600),
        )
        return self._token  # type: ignore[return-value]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call an Apaleo MCP tool and return its decoded result.

        Opens a short-lived MCP session per call using the streamable-HTTP
        transport. Suitable for the low-frequency sync operations in
        ApaleoMCPAdapter. Persistent sessions can be added if needed.

        Args:
            tool_name:  Name of the MCP tool to invoke (e.g.
                        ``"apaleo_get_occupancy_metrics"``).
            arguments:  Tool input as a plain dict (JSON-serialisable).

        Returns:
            Parsed JSON dict/list, or the raw text string if the response
            is not valid JSON.

        Raises:
            RuntimeError: when credentials are not configured.
            httpx.HTTPStatusError: on OAuth2 or transport-level failures.
            mcp.McpError: on MCP protocol errors (tool not found, etc.).
        """
        if not self.is_configured:
            raise RuntimeError(
                "ApaleoMCPClient: credentials not configured. "
                "Set APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, "
                "and APALEO_MCP_SERVER_URL."
            )

        from mcp import ClientSession  # noqa: PLC0415 — lazy import to keep startup fast
        from mcp.client.streamable_http import streamablehttp_client  # noqa: PLC0415

        token = await self._refresh_token()

        async with streamablehttp_client(
            self.server_url,
            headers={"Authorization": f"Bearer {token}"},
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.debug("Calling Apaleo MCP tool %r with args %r", tool_name, arguments)
                result = await session.call_tool(tool_name, arguments)

        # MCP returns a list of content blocks; extract the first text block.
        if result.content and result.content[0].type == "text":
            raw = result.content[0].text
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        return result

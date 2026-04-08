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

from app.integrations.apaleo_logger import (
    ApaleoAgentLogger,
    ApaleoWriteBlockedError,
    is_readonly_mode,
    is_write_tool,
)

logger = logging.getLogger(__name__)
_agent_logger = ApaleoAgentLogger()

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

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user: str | None = None,
    ) -> Any:
        """
        Call an Apaleo MCP tool and return its decoded result.

        Args:
            tool_name:  MCP tool name (e.g. ``"APALEO_GET_OCCUPANCY_METRICS"``).
        Opens a short-lived MCP session per call (streamable-HTTP transport).

        Write-guard (HOS-107)
        ---------------------
        When ``APALEO_READONLY`` is not explicitly set to ``"false"``,
        any call to a known write tool raises ``ApaleoWriteBlockedError``
        before opening a network connection.  The blocked attempt is logged
        at WARNING level.

        Args:
            tool_name:  MCP tool name.
                        Composio mode  → ``"APALEO_GET_A_PROPERTIES_LIST"`` etc.
                        Direct mode    → ``"APALEO_GET_OCCUPANCY_METRICS"`` etc.
            arguments:  JSON-serialisable tool input dict.
            user:       Optional caller identity for the agent action log.

        Returns:
            Parsed JSON dict/list, or raw text if response is not JSON.

        Raises:
            ApaleoWriteBlockedError: write operation attempted in read-only mode.
            RuntimeError: credentials not configured.
            httpx.HTTPStatusError: OAuth2 / transport failure.
            mcp.McpError: MCP protocol error.
        """
        if not self.is_configured:
            raise RuntimeError(
                "ApaleoMCPClient: not configured. "
                "Set APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, APALEO_MCP_SERVER_URL."
            )

        # ── Write-guard ────────────────────────────────────────────────────
        write = is_write_tool(tool_name)
        if write and is_readonly_mode():
            _agent_logger.log(
                tool_name,
                arguments,
                user=user,
                mode="blocked",
                error="read-only mode active (Phase 0) — set APALEO_READONLY=false to enable writes",
            )
            raise ApaleoWriteBlockedError(
                f"ApaleoMCPClient: write operation '{tool_name}' blocked — "
                "Apaleo is in read-only mode (Phase 0). "
                "Set APALEO_READONLY=false to enable writes."
            )

        from mcp import ClientSession  # noqa: PLC0415
        from mcp.client.streamable_http import streamablehttp_client  # noqa: PLC0415

        token = await self._get_token()
        mode = "write" if write else "read"
        t0 = time.monotonic()

        try:
            async with streamablehttp_client(
                self.server_url,
                headers={"Authorization": f"Bearer {token}"},
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.debug("Calling Apaleo MCP tool %r with args %r", tool_name, arguments)
                    result = await session.call_tool(tool_name, arguments)

            duration_ms = (time.monotonic() - t0) * 1000

            if result.content and result.content[0].type == "text":
                raw = result.content[0].text
                try:
                    decoded = json.loads(raw)
                except json.JSONDecodeError:
                    decoded = raw
            else:
                decoded = result

            _agent_logger.log(
                tool_name,
                arguments,
                user=user,
                mode=mode,
                duration_ms=duration_ms,
                result_summary=str(decoded)[:200],
            )
            return decoded

        except ApaleoWriteBlockedError:
            raise
        except Exception as exc:
            duration_ms = (time.monotonic() - t0) * 1000
            _agent_logger.log(
                tool_name,
                arguments,
                user=user,
                mode=mode,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise

"""
Async MCP client for Apaleo's MCP Server.

Supports two authentication modes:

  1. **Composio managed** (``auth_mode="apikey"``) — recommended for now.
     The MCP URL is generated dynamically via Composio Tool Router
     (see ``scripts/generate_composio_mcp_url.py``).
     Auth: ``X-API-Key: <COMPOSIO_API_KEY>`` header.

     ⚠️  Scope: Composio exposes the Apaleo *Inventory API* only
     (properties, units, unit groups). Not suitable for occupancy /
     revenue / reservations — use ``ApaleoPMSAdapter`` for those.

  2. **Apaleo direct** (``auth_mode="bearer"``) — alpha programme.
     Standard OAuth2 client-credentials flow against
     ``identity.apaleo.com``. URL provided by Apaleo on invitation.

Required env vars by mode:

  Composio (apikey):
    APALEO_MCP_SERVER_URL   — Composio Tool Router URL (from generate script)
    COMPOSIO_API_KEY        — Composio API key

  Apaleo direct (bearer):
    APALEO_MCP_SERVER_URL   — Direct Apaleo MCP endpoint (alpha)
    APALEO_CLIENT_ID        — OAuth2 client ID
    APALEO_CLIENT_SECRET    — OAuth2 client secret

Usage::

    # Composio mode (default when COMPOSIO_API_KEY is set)
    client = ApaleoMCPClient()
    props = await client.call_tool("APALEO_GET_A_PROPERTIES_LIST", {})

    # Direct mode
    client = ApaleoMCPClient(auth_mode="bearer")
    data = await client.call_tool("apaleo_get_occupancy_metrics",
                                  {"propertyId": "MUC", "date": "2026-03-29"})
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Literal

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

AuthMode = Literal["apikey", "bearer"]


def _detect_auth_mode() -> AuthMode:
    """Infer auth mode from available env vars.

    Composio API key takes priority when present — it is the currently
    available path. Falls back to bearer (Apaleo direct alpha).
    """
    if os.getenv("COMPOSIO_API_KEY"):
        return "apikey"
    return "bearer"


class ApaleoMCPClient:
    """
    Thin async MCP client for Apaleo, supporting both Composio and direct auth.

    Auth modes
    ----------
    ``"apikey"``  — Composio. Auth embedded in URL query params
                    (``?api_key=...&user_id=...``). No extra header needed.
                    Exposes Inventory API tools (properties / units).
    ``"bearer"``  — Apaleo direct alpha. OAuth2 client-credentials token.
                    Exposes full Core API (occupancy, revenue, reservations).

    Pass ``auth_mode`` explicitly or let it be auto-detected from env vars
    (``COMPOSIO_API_KEY`` present → apikey, otherwise bearer).
    """

    def __init__(
        self,
        server_url: str | None = None,
        auth_mode: AuthMode | None = None,
        # apikey mode
        composio_api_key: str | None = None,
        # bearer mode
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.auth_mode: AuthMode = auth_mode or _detect_auth_mode()
        self.server_url: str = server_url or os.getenv("APALEO_MCP_SERVER_URL", "")

        # apikey (Composio)
        self.composio_api_key: str = (
            composio_api_key or os.getenv("COMPOSIO_API_KEY", "")
        )

        # bearer (Apaleo direct)
        self.client_id: str = client_id or os.getenv("APALEO_CLIENT_ID", "")
        self.client_secret: str = client_secret or os.getenv("APALEO_CLIENT_SECRET", "")
        self._bearer_token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def is_configured(self) -> bool:
        """True when server URL and the relevant credentials are all present.

        Composio (apikey): auth is embedded in the URL; we just check the URL
        is set and contains ``api_key`` (set by generate_composio_mcp_url.py).
        """
        if not self.server_url:
            return False
        if self.auth_mode == "apikey":
            return "api_key=" in self.server_url or bool(self.composio_api_key)
        return bool(self.client_id and self.client_secret)

    async def _auth_headers(self) -> dict[str, str]:
        """Return auth headers for the configured mode.

        Composio (apikey): auth is embedded in the URL query params
        (``?api_key=...&user_id=...``) — no extra header required.
        """
        if self.auth_mode == "apikey":
            return {}  # auth already in URL — see generate_composio_mcp_url.py

        # bearer — fetch/refresh OAuth2 token
        if not (self._bearer_token and time.time() < self._token_expiry - 30):
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
            self._bearer_token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600)
            logger.debug(
                "Apaleo MCP OAuth2 token refreshed (expires in %ss)",
                data.get("expires_in", 3600),
            )
        return {"Authorization": f"Bearer {self._bearer_token}"}

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        user: str | None = None,
    ) -> Any:
        """
        Call an Apaleo MCP tool and return its decoded result.

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
            mcp.McpError: MCP protocol error (tool not found, etc.).
        """
        if not self.is_configured:
            missing = (
                "COMPOSIO_API_KEY and APALEO_MCP_SERVER_URL"
                if self.auth_mode == "apikey"
                else "APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, and APALEO_MCP_SERVER_URL"
            )
            raise RuntimeError(
                f"ApaleoMCPClient ({self.auth_mode} mode): not configured. "
                f"Set {missing}."
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

        headers = await self._auth_headers()
        mode = "write" if write else "read"
        t0 = time.monotonic()

        try:
            async with streamablehttp_client(self.server_url, headers=headers) as (
                read_stream,
                write_stream,
                _,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    logger.debug(
                        "ApaleoMCPClient (%s) calling %r with %r",
                        self.auth_mode,
                        tool_name,
                        arguments,
                    )
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

"""
Apaleo MCP stdio proxy for Claude Code.

Bridges Claude Code (stdio MCP client) ↔ Apaleo MCP server (streamable HTTP).
Handles OAuth2 client_credentials token refresh automatically.

Configure in Claude Code (project settings or global):
    claude mcp add apaleo -- python path/to/apaleo_mcp_proxy.py

Or in .claude/settings.json:
    {
      "mcpServers": {
        "apaleo": {
          "command": "python",
          "args": ["scripts/apaleo_mcp_proxy.py"]
        }
      }
    }

Required env vars (auto-loaded from backend/.env):
    APALEO_CLIENT_ID, APALEO_CLIENT_SECRET
Optional:
    APALEO_MCP_SERVER_URL  (default: https://mcp.apaleo.com/mcp/)
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

try:
    from dotenv import load_dotenv
    for _p in [
        Path(__file__).parent.parent / "backend" / ".env",
        Path(".env"),
    ]:
        if _p.exists():
            load_dotenv(_p, override=False)
            break
except ImportError:
    pass

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("apaleo-proxy")

_TOKEN_URL = "https://identity.apaleo.com/connect/token"
_token: str | None = None
_token_expiry: float = 0.0


async def _get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry - 60:
        return _token

    client_id = os.environ.get("APALEO_CLIENT_ID", "")
    client_secret = os.environ.get("APALEO_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "APALEO_CLIENT_ID and APALEO_CLIENT_SECRET must be set "
            "(hint: run from backend/ so .env is loaded)"
        )

    async with httpx.AsyncClient(timeout=10) as http:
        resp = await http.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()

    data = resp.json()
    _token = data["access_token"]
    _token_expiry = time.time() + data.get("expires_in", 3600)
    logger.debug("Token refreshed, expires in %ss", data.get("expires_in", 3600))
    return _token  # type: ignore[return-value]


def _server_url() -> str:
    return os.environ.get("APALEO_MCP_SERVER_URL", "https://mcp.apaleo.com/mcp/")


async def _list_tools() -> list[Tool]:
    token = await _get_token()
    async with streamablehttp_client(
        _server_url(), headers={"Authorization": f"Bearer {token}"}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools or []


async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
    token = await _get_token()
    async with streamablehttp_client(
        _server_url(), headers={"Authorization": f"Bearer {token}"}
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(name, arguments)


async def run_proxy() -> None:
    server = Server("apaleo-proxy")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return await _list_tools()

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        result = await _call_tool(name, arguments or {})
        if result.content:
            return result.content
        return [TextContent(type="text", text=str(result))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run_proxy())

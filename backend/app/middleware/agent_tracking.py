"""Agent call tracking middleware (P1-5 · HOS-72).

Purely observational — never blocks requests, never writes to DB.

Detection heuristics (OR-logic):
  - User-Agent contains "mcp-client" | "claude" | "agent" (case-insensitive)
  - X-Agent-Id header is present
  - X-Aetherix-MCP-Version header is present

On every detected agent call:
  - Logs: agent_call: path=<path> agent_id=<...> latency_ms=<...> status=<...>
  - Attaches X-Request-Id response header (uuid4) when not already set.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Case-insensitive substrings that classify a User-Agent as an agent caller.
_AGENT_UA_KEYWORDS = ("mcp-client", "claude", "agent")


def is_agent_request(request: Request) -> bool:
    """Return True when the request looks like it originates from an agent."""
    # Check X-Agent-Id and X-Aetherix-MCP-Version headers first (definitive).
    if request.headers.get("x-agent-id") or request.headers.get("x-aetherix-mcp-version"):
        return True

    # Inspect User-Agent substring (case-insensitive).
    ua = request.headers.get("user-agent", "").lower()
    return any(kw in ua for kw in _AGENT_UA_KEYWORDS)


def extract_agent_id(request: Request) -> str:
    """Return a best-effort agent identifier from the request headers."""
    agent_id = request.headers.get("x-agent-id")
    if agent_id:
        return agent_id
    mcp_version = request.headers.get("x-aetherix-mcp-version")
    if mcp_version:
        return f"mcp-v{mcp_version}"
    ua = request.headers.get("user-agent", "")
    if ua:
        return ua[:80]  # truncate long UA strings
    return "unknown"


class AgentTrackingMiddleware(BaseHTTPMiddleware):
    """Lightweight observability middleware for agent-originated requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.monotonic()
        response: Response = await call_next(request)
        latency_ms = round((time.monotonic() - start) * 1000)

        # Attach X-Request-Id if absent (useful for distributed tracing).
        if "x-request-id" not in response.headers:
            response.headers["x-request-id"] = str(uuid.uuid4())

        # Log only if the caller looks like an agent.
        if is_agent_request(request):
            logger.info(
                "agent_call: path=%s agent_id=%s latency_ms=%d status=%d",
                request.url.path,
                extract_agent_id(request),
                latency_ms,
                response.status_code,
            )

        return response

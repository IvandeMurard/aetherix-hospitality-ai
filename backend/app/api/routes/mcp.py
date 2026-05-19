"""MCP Server HTTP shim — minimal JSON-RPC 2.0 over HTTP (ADR 0001 · P1-2 · ADR-0004).

This is a deliberately thin router that speaks the subset of MCP's JSON-RPC
methods needed for v0 and v1:
  - initialize
  - tools/list
  - tools/call

The full `mcp` SDK (FastMCP) will replace this if/when we need progress
notifications and capability negotiation. For now, a bare router keeps the
dependency surface small and is trivially testable without a transport layer.

Mounted twice by `app/main.py`:
  - `/mcp/v0/` — original 3-tool surface (ADR-0001)
  - `/mcp/v1/` — adds `recall_memory` (ADR-0004 · HOS-184 PR-A)

In PR-B, `/mcp/v1/` will drop `get_recommendations_with_memory_context` in favor
of the atomic recall_memory + get_operational_predictions composition. Until then,
both versions advertise the same TOOLS_MANIFEST — v1 is purely additive.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.mcp_core import TOOLS_MANIFEST, MCPAuthError
from app.mcp_server import dispatch_tool, verify_bearer

logger = logging.getLogger(__name__)


def _rpc_error(request_id: Any, status: int, title: str, detail: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32000 - status,
            "message": title,
            "data": {"type": "about:blank", "title": title, "status": status, "detail": detail},
        },
    }


def _rpc_result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _make_router(version: str) -> APIRouter:
    """Factory for an MCP JSON-RPC router pinned to a protocol version.

    Both v0 and v1 currently share the same TOOLS_MANIFEST and dispatch.
    The version header lets clients pin to a specific surface and lets us
    diverge schemas in future versions without breaking existing consumers.
    """
    router = APIRouter(prefix=f"/mcp/v{version}", tags=["mcp"])

    @router.post(
        "/",
        summary=f"MCP JSON-RPC endpoint v{version} (initialize, tools/list, tools/call)",
        openapi_extra={"x-agent-callable": True, "x-mcp-compatible": True},
    )
    async def mcp_rpc(
        request: Request,
        response: Response,
        authorization: Optional[str] = Header(None),
        db: AsyncSession = Depends(get_db),
    ) -> dict[str, Any]:
        response.headers["x-aetherix-mcp-version"] = version

        try:
            body = await request.json()
        except json.JSONDecodeError as exc:
            return _rpc_error(None, 400, "invalid_input", f"Malformed JSON: {exc}")

        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params") or {}

        if method == "initialize":
            return _rpc_result(req_id, {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "aetherix", "version": f"0.{version}.0"},
                "capabilities": {"tools": {"listChanged": False}},
            })

        if method == "tools/list":
            try:
                await verify_bearer(authorization, db)
            except MCPAuthError as exc:
                return _rpc_error(req_id, exc.status, exc.title, exc.detail)
            return _rpc_result(req_id, {"tools": TOOLS_MANIFEST})

        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}
            embedding_provider = getattr(request.app.state, "embedding", None)
            engine = getattr(request.app.state, "engine", None)
            # Generate request_id here — middleware sets x-request-id POST call_next,
            # so reading it from response headers at this point always returns "".
            request_id = str(uuid.uuid4())
            response.headers["x-request-id"] = request_id
            try:
                result = await dispatch_tool(
                    tool_name, arguments, authorization, db,
                    embedding_provider=embedding_provider,
                    engine=engine,
                    request_id=request_id,
                )
                await db.commit()
            except MCPAuthError as exc:
                await db.rollback()
                return _rpc_error(req_id, exc.status, exc.title, exc.detail)
            except Exception as exc:
                await db.rollback()
                logger.exception("MCP tool dispatch failed: %s", exc)
                return _rpc_error(req_id, 500, "internal_error", str(exc))
            return _rpc_result(req_id, {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "isError": False,
            })

        return _rpc_error(req_id, 400, "invalid_input", f"Unknown method: {method}")

    return router


# Build both routers at import time so they can be mounted by app/main.py.
router_v0 = _make_router("0")
router_v1 = _make_router("1")

# Backward-compatible alias — existing app.main imports `router` for v0.
router = router_v0

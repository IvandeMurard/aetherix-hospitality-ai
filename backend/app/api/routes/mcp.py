"""MCP Server HTTP shim — minimal JSON-RPC 2.0 over HTTP (ADR 0001 · P1-2).

This is a deliberately thin router that speaks the subset of MCP's JSON-RPC
methods needed for v0:
  - initialize
  - tools/list
  - tools/call

The full `mcp` SDK (FastMCP) will replace this in v1 once we need progress
notifications and capability negotiation. For v0, a bare router keeps the
dependency surface small and is trivially testable without a transport layer.

Mounted at `/mcp/v0/` by `app/main.py`.
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

router = APIRouter(prefix="/mcp/v0", tags=["mcp"])


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


@router.post(
    "/",
    summary="MCP JSON-RPC endpoint (initialize, tools/list, tools/call)",
    openapi_extra={"x-agent-callable": True, "x-mcp-compatible": True},
)
async def mcp_rpc(
    request: Request,
    response: Response,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    response.headers["x-aetherix-mcp-version"] = "0"

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
            "serverInfo": {"name": "aetherix", "version": "0.0.0"},
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

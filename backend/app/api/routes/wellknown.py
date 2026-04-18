"""Agent discovery manifest (P1-5 · HOS-72).

GET /.well-known/agent.json — publicly accessible, no auth required.

Third-party agents crawl this path (analogous to robots.txt) to discover
Aetherix capabilities, MCP endpoint location, auth schemes, and rate limits.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["agent-seo"])

_AGENT_MANIFEST = {
    "schema_version": "1.0",
    "name": "Aetherix",
    "description": (
        "Agentic AI platform for F&B hotel operations — "
        "covers forecasting, staffing recommendations, and operational memory."
    ),
    "version": "0.1.0",
    "mcp_endpoint": "/mcp/v0/",
    "tools": [
        {
            "name": "get_operational_predictions",
            "description": "Forecast F&B covers and staffing for the authenticated property.",
            "endpoint": "/mcp/v0/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "get_recommendations_with_memory_context",
            "description": (
                "Contextualized recommendation pulling from "
                "operational_memory + fb_patterns."
            ),
            "endpoint": "/mcp/v0/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "submit_feedback_to_memory",
            "description": (
                "Record manager outcome for a past recommendation "
                "(self-improving loop)."
            ),
            "endpoint": "/mcp/v0/",
            "method": "POST",
            "x-mcp-tool": True,
        },
    ],
    "agent_callable_endpoints": [
        {
            "path": "/api/v1/predictions/predict",
            "method": "POST",
            "x-agent-callable": True,
            "x-mcp-compatible": True,
            "description": "Direct predict endpoint — F&B cover forecasting.",
        },
        {
            "path": "/api/v1/roi/simulate",
            "method": "POST",
            "x-agent-callable": True,
            "x-mcp-compatible": True,
            "description": "Public ROI simulator — stateless, no auth required.",
        },
        {
            "path": "/mcp/v0/",
            "method": "POST",
            "x-agent-callable": True,
            "x-mcp-compatible": True,
            "description": "MCP JSON-RPC 2.0 endpoint (initialize, tools/list, tools/call).",
        },
    ],
    "auth_schemes": [
        {
            "type": "bearer",
            "description": (
                "Pass an Aetherix API token (atx_…) in "
                "Authorization: Bearer <token>. "
                "Required for /mcp/v0/ and /api/v1/predictions/predict."
            ),
        },
        {
            "type": "none",
            "description": (
                "POST /api/v1/roi/simulate is public (no auth). "
                "Rate-limited at the edge."
            ),
        },
    ],
    "rate_limits": {
        "get_operational_predictions": "60 req/min per hotel",
        "get_recommendations_with_memory_context": "30 req/min per hotel",
        "submit_feedback_to_memory": "20 req/min per hotel",
        "default": "60 req/min",
    },
    "contact": {
        "name": "Aetherix",
        "email": "api@aetherix.ai",
        "docs": "https://aetherix.ai/docs",
    },
}


@router.get(
    "/.well-known/agent.json",
    summary="Agent discovery manifest",
    response_description="Machine-readable agent capability manifest",
    include_in_schema=True,
)
async def agent_manifest() -> JSONResponse:
    """Return the Aetherix agent discovery manifest.

    This endpoint is public (no auth) and is intended to be crawled by
    third-party agents and orchestrators discovering Aetherix capabilities.
    """
    return JSONResponse(content=_AGENT_MANIFEST, media_type="application/json")

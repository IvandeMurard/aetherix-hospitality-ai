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
    "mcp_endpoint": "/mcp/v1/",
    "tools": [
        {
            "name": "get_operational_predictions",
            "description": "Forecast F&B covers and staffing for the authenticated property.",
            "endpoint": "/mcp/v1/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "recall_memory",
            "description": (
                "Semantic recall from the property's operational memory — "
                "the k most relevant past observations for a free-text query."
            ),
            "endpoint": "/mcp/v1/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "submit_feedback_to_memory",
            "description": (
                "Record the decision on a recommendation with who decided "
                "(human relayed by the host, or host agent alone — refused by the "
                "default human-validation policy) and a structured reason."
            ),
            "endpoint": "/mcp/v1/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "get_decision_recap",
            "description": (
                "Deterministic recap of recommendations and decisions over a day, "
                "week or month. No estimated figure."
            ),
            "endpoint": "/mcp/v1/",
            "method": "POST",
            "x-mcp-tool": True,
        },
        {
            "name": "get_pending_recommendations",
            "description": (
                "Undecided recommendations with typed consequences per option "
                "(accept / refuse), correction window and decision rule."
            ),
            "endpoint": "/mcp/v1/",
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
            "path": "/mcp/v1/",
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
                "Required for /mcp/v1/ and /api/v1/predictions/predict."
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
        "recall_memory": "60 req/min per hotel",
        "submit_feedback_to_memory": "20 req/min per hotel",
        "get_decision_recap": "30 req/min per hotel",
        "get_pending_recommendations": "30 req/min per hotel",
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

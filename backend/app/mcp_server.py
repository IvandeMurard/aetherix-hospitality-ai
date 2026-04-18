"""Aetherix MCP Server v0 — inbound, agent-callable (ADR 0001 · HOS-71 · P1-2).

Exposes three tools to third-party agents (Claude Desktop, enterprise hubs):
  - get_operational_predictions
  - get_recommendations_with_memory_context
  - submit_feedback_to_memory

Mounted by `app/main.py` at `/mcp/v0`. Single-process, shared lifespan with
the main FastAPI app (ADR D2).

hotel_id is resolved from the bearer token server-side — **never** from tool
input (ADR D4, multi-tenant isolation). Tool schemas do not expose it.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MCPApiToken, OperationalMemory
from app.mcp_core import (
    TOOLS_MANIFEST,
    MCPAuthError,
    check_rate_limit,
    hash_token,
    require_scope,
    sanitize_notes,
)
from app.services.aetherix_engine import AetherixEngine

logger = logging.getLogger(__name__)

_engine = AetherixEngine()


# ---------------------------------------------------------------------------
# Auth — opaque bearer, hotel_id bound to token (ADR D3, D4)
# ---------------------------------------------------------------------------

async def verify_bearer(authorization: Optional[str], db: AsyncSession) -> MCPApiToken:
    """Extract and validate a bearer token → return the MCPApiToken row."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise MCPAuthError(401, "unauthorized", "Missing Bearer token")
    raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        raise MCPAuthError(401, "unauthorized", "Empty Bearer token")
    token_hash = hash_token(raw)
    result = await db.execute(
        select(MCPApiToken).where(MCPApiToken.token_hash == token_hash)
    )
    tok = result.scalars().first()
    if tok is None:
        raise MCPAuthError(401, "unauthorized", "Invalid token")
    if tok.revoked_at is not None:
        raise MCPAuthError(401, "unauthorized", "Token revoked")
    if tok.expires_at is not None and tok.expires_at < datetime.now(timezone.utc):
        raise MCPAuthError(401, "unauthorized", "Token expired")
    tok.last_used_at = datetime.now(timezone.utc)
    return tok


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def tool_get_operational_predictions(
    hotel_id: str,
    target_date: str,
    service_type: str = "dinner",
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    try:
        tdate = date.fromisoformat(target_date)
    except ValueError as exc:
        raise MCPAuthError(400, "invalid_input", f"Bad target_date: {exc}") from exc
    if service_type not in ("breakfast", "lunch", "dinner"):
        raise MCPAuthError(400, "invalid_input", "service_type must be breakfast|lunch|dinner")
    ctx = context or {"weather": {"condition": "Unknown"}, "events": [], "occupancy": None}
    try:
        return await _engine.get_forecast(hotel_id, tdate, service_type, ctx)
    except Exception as exc:
        logger.exception("tool_get_operational_predictions failed: %s", exc)
        raise MCPAuthError(503, "upstream_unavailable", str(exc)) from exc


async def tool_get_recommendations_with_memory_context(
    hotel_id: str,
    query: str,
    db: AsyncSession,
    target_date: Optional[str] = None,
    k_memory: int = 5,
) -> dict[str, Any]:
    query = sanitize_notes(query, max_len=500)
    if not query:
        raise MCPAuthError(400, "invalid_input", "query is required")
    k = max(1, min(20, int(k_memory)))

    # Retrieve recent reflections for the tenant — simple ordering by recency.
    # Semantic search (cosine on embedding) deferred to v1 once Mistral embedding
    # integration is wired through the provider lifespan.
    result = await db.execute(
        select(OperationalMemory)
        .where(OperationalMemory.hotel_id == hotel_id)
        .order_by(OperationalMemory.created_at.desc())
        .limit(k)
    )
    rows = result.scalars().all()
    memory_hits = [
        {
            "pattern_id": str(r.id),
            "summary": (r.reflection or "")[:200],
            "feedback": r.manager_feedback,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    try:
        if target_date:
            tdate = date.fromisoformat(target_date)
            forecast = await _engine.get_forecast(
                hotel_id, tdate, "dinner",
                {"weather": {}, "events": [], "occupancy": None},
            )
            reasoning_summary = forecast.get("reasoning", "")
            confidence = forecast.get("prediction", {}).get("confidence", 0.0)
        else:
            reasoning_summary = f"Retrieved {len(memory_hits)} memory hits for query: {query}"
            confidence = 0.5
    except Exception as exc:
        logger.warning("forecast enrichment failed, returning memory-only: %s", exc)
        reasoning_summary = f"Retrieved {len(memory_hits)} memory hits for query: {query}"
        confidence = 0.3

    return {
        "recommendation": reasoning_summary,
        "confidence": confidence,
        "memory_hits": memory_hits,
        "reasoning_summary": reasoning_summary,
    }


async def tool_submit_feedback_to_memory(
    hotel_id: str,
    recommendation_id: str,
    outcome: str,
    db: AsyncSession,
    actual_value: Optional[float] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    if outcome not in ("accepted", "rejected", "modified", "ignored"):
        raise MCPAuthError(400, "invalid_input",
                           "outcome must be accepted|rejected|modified|ignored")
    try:
        rec_uuid = UUID(recommendation_id)
    except ValueError as exc:
        raise MCPAuthError(400, "invalid_input", f"Bad recommendation_id: {exc}") from exc

    clean_notes = sanitize_notes(notes or "", max_len=1000)

    feedback_map = {"accepted": "followed", "rejected": "rejected",
                    "modified": "neutral", "ignored": "neutral"}

    reflection = f"[rec={rec_uuid}] outcome={outcome}"
    if actual_value is not None:
        reflection += f" actual={actual_value}"
    if clean_notes:
        reflection += f" notes={clean_notes}"

    # Embedding stub — real Mistral embedding wired via provider singleton in v1.
    # For v0 we write a deterministic zero-vector placeholder; dedup relies on
    # (hotel_id, recommendation_id, outcome) tuple instead of cosine.
    existing = await db.execute(
        select(OperationalMemory)
        .where(OperationalMemory.hotel_id == hotel_id)
        .where(OperationalMemory.memory_type == "feedback")
        .where(OperationalMemory.reflection.like(f"[rec={rec_uuid}]%outcome={outcome}%"))
        .limit(1)
    )
    if existing.scalars().first():
        return {"memory_id": None, "status": "deduplicated", "embedding_dim": 1024}

    mem = OperationalMemory(
        hotel_id=hotel_id,
        reflection=reflection,
        manager_feedback=feedback_map[outcome],
        outcome=outcome,
        memory_type="feedback",
        embedding=[0.0] * 1024,
    )
    db.add(mem)
    await db.flush()
    return {
        "memory_id": str(mem.id),
        "status": "stored",
        "embedding_dim": 1024,
    }


# ---------------------------------------------------------------------------
# Dispatcher — used by the HTTP shim and integration tests
# ---------------------------------------------------------------------------

async def dispatch_tool(
    tool_name: str,
    arguments: dict[str, Any],
    authorization: Optional[str],
    db: AsyncSession,
) -> dict[str, Any]:
    """Validate auth + scope + rate limit, then route to the tool body."""
    if tool_name not in {t["name"] for t in TOOLS_MANIFEST}:
        raise MCPAuthError(404, "not_found", f"Unknown tool: {tool_name}")
    tok = await verify_bearer(authorization, db)
    require_scope(tok.scopes, tool_name)
    check_rate_limit(tok.hotel_id, tool_name)

    # hotel_id comes from the token — never from arguments
    args = {k: v for k, v in (arguments or {}).items() if k != "hotel_id"}

    if tool_name == "get_operational_predictions":
        return await tool_get_operational_predictions(tok.hotel_id, **args)
    if tool_name == "get_recommendations_with_memory_context":
        return await tool_get_recommendations_with_memory_context(
            tok.hotel_id, db=db, **args,
        )
    if tool_name == "submit_feedback_to_memory":
        return await tool_submit_feedback_to_memory(
            tok.hotel_id, db=db, **args,
        )
    raise MCPAuthError(500, "internal_error", "Dispatcher inconsistency")

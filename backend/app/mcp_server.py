"""Aetherix MCP Server — inbound, agent-callable (ADR 0001 · HOS-71 · P1-2).

Exposes tools to third-party agents (Claude Desktop, enterprise hubs):
  - get_operational_predictions
  - get_recommendations_with_memory_context
  - submit_feedback_to_memory  (a host's decision: who decided + why, ADR-0007 §17.4)
  - get_decision_recap          (deterministic recap, read-only, ADR-0007 §17.2)

Backs the `/mcp/v1/` route (ADR-0004). The `/mcp/v0/` route was retired on
2026-08-01 (HOS-315); `get_recommendations_with_memory_context` stays
dispatchable here for the stdio surface but is no longer advertised.
Single-process, shared lifespan with the main FastAPI app (ADR D2).

hotel_id is resolved from the bearer token server-side — **never** from tool
input (ADR D4, multi-tenant isolation). Tool schemas do not expose it.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MCPApiToken, OperationalMemory
from app.db.session import AsyncSessionLocal
from app.mcp_core import (
    TOOLS_MANIFEST,
    V1_TOOLS_MANIFEST,
    MCPAuthError,
    hash_token,
    require_scope,
    sanitize_notes,
)
from app.services.agent_event import AgentEvent, emit_agent_event
from app.services.memory_recall_service import MemoryRecallService
from app.services.rate_limit import check_rate_limit_async

logger = logging.getLogger(__name__)

_ALL_TOOL_NAMES: frozenset[str] = frozenset(
    {t["name"] for t in TOOLS_MANIFEST} | {t["name"] for t in V1_TOOLS_MANIFEST}
)


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
    engine: Optional[Any] = None,
) -> dict[str, Any]:
    try:
        tdate = date.fromisoformat(target_date)
    except ValueError as exc:
        raise MCPAuthError(400, "invalid_input", f"Bad target_date: {exc}") from exc
    if service_type not in ("breakfast", "lunch", "dinner"):
        raise MCPAuthError(400, "invalid_input", "service_type must be breakfast|lunch|dinner")
    if engine is None:
        raise MCPAuthError(503, "upstream_unavailable", "Prediction engine not initialized")
    ctx = context or {"weather": {"condition": "Unknown"}, "events": [], "occupancy": None}
    try:
        return await engine.get_forecast(hotel_id, tdate, service_type, ctx)
    except Exception as exc:
        logger.exception("tool_get_operational_predictions failed: %s", exc)
        raise MCPAuthError(503, "upstream_unavailable", str(exc)) from exc


async def tool_get_recommendations_with_memory_context(
    hotel_id: str,
    query: str,
    db: AsyncSession,
    embedding_provider: Any = None,
    target_date: Optional[str] = None,
    k_memory: int = 5,
    engine: Optional[Any] = None,
) -> dict[str, Any]:
    query = sanitize_notes(query, max_len=500)
    if not query:
        raise MCPAuthError(400, "invalid_input", "query is required")
    k = max(1, min(20, int(k_memory)))

    # Semantic recall via MemoryRecallService (ADR 0002 D4 / P1-3)
    memory_hits_raw = []
    if embedding_provider is not None:
        try:
            query_vec = await embedding_provider.embed(query)
            recall_svc = MemoryRecallService(db)
            hits = await recall_svc.recall(hotel_id, query_vec, k=k)
            memory_hits_raw = [
                {
                    "pattern_id": str(h.id),
                    "summary": h.reflection[:200],
                    "feedback": h.manager_feedback,
                    "similarity": round(h.similarity, 4),
                    "source": h.source,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                }
                for h in hits
            ]
        except Exception as exc:
            logger.warning("semantic recall failed, falling back to recency: %s", exc)

    # Recency fallback if embedding unavailable or recall failed
    if not memory_hits_raw:
        result = await db.execute(
            select(OperationalMemory)
            .where(OperationalMemory.hotel_id == hotel_id)
            .order_by(OperationalMemory.created_at.desc())
            .limit(k)
        )
        rows = result.scalars().all()
        memory_hits_raw = [
            {
                "pattern_id": str(r.id),
                "summary": (r.reflection or "")[:200],
                "feedback": r.manager_feedback,
                "similarity": None,
                "source": "recency_fallback",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    try:
        if target_date and engine is not None:
            tdate = date.fromisoformat(target_date)
            forecast = await engine.get_forecast(
                hotel_id, tdate, "dinner",
                {"weather": {}, "events": [], "occupancy": None},
            )
            reasoning_summary = forecast.get("reasoning", "")
            confidence = forecast.get("prediction", {}).get("confidence", 0.0)
        else:
            reasoning_summary = f"Retrieved {len(memory_hits_raw)} memory hits for query: {query}"
            confidence = 0.5
    except Exception as exc:
        logger.warning("forecast enrichment failed: %s", exc)
        reasoning_summary = f"Retrieved {len(memory_hits_raw)} memory hits for query: {query}"
        confidence = 0.3

    return {
        "recommendation": reasoning_summary,
        "confidence": confidence,
        "memory_hits": memory_hits_raw,
        "reasoning_summary": reasoning_summary,
    }


async def tool_recall_memory(
    hotel_id: str,
    query: str,
    db: AsyncSession,
    embedding_provider: Any = None,
    k: int = 5,
) -> dict[str, Any]:
    """Atomic memory recall — replaces the recall step of get_recommendations_with_memory_context."""
    query = sanitize_notes(query, max_len=500)
    if not query:
        raise MCPAuthError(400, "invalid_input", "query is required")
    k = max(1, min(20, int(k)))

    memory_hits: list[dict[str, Any]] = []
    source = "recency_fallback"

    if embedding_provider is not None:
        try:
            query_vec = await embedding_provider.embed(query)
            recall_svc = MemoryRecallService(db)
            hits = await recall_svc.recall(hotel_id, query_vec, k=k)
            if hits:
                source = "private"
                memory_hits = [
                    {
                        "pattern_id": str(h.id),
                        "summary": h.reflection[:200],
                        "feedback": h.manager_feedback,
                        "similarity": round(h.similarity, 4),
                        "source": h.source,
                        "created_at": h.created_at.isoformat() if h.created_at else None,
                    }
                    for h in hits
                ]
        except Exception as exc:
            logger.warning("recall_memory embedding failed, falling back to recency: %s", exc)

    if not memory_hits:
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
                "similarity": None,
                "source": "recency_fallback",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    return {"memory_hits": memory_hits, "source": source, "count": len(memory_hits)}


async def tool_submit_feedback_to_memory(
    hotel_id: str,
    recommendation_id: str,
    outcome: str,
    db: AsyncSession,
    embedding_provider: Any = None,
    actual_value: Optional[float] = None,
    notes: Optional[str] = None,
    request_id: str = "",
    decided_by: str = "human_whatsapp",
) -> dict[str, Any]:
    """Feedback-memory write. Called after a decision was recorded: by the
    WhatsApp path directly, by MCP through ``tool_record_host_decision``.
    ``decided_by`` is written into the reflection so recall can tell a human's
    answer from a host agent's (ADR-0007 §17.5)."""
    if outcome not in ("accepted", "rejected", "modified", "ignored"):
        raise MCPAuthError(400, "invalid_input",
                           "outcome must be accepted|rejected|modified|ignored")
    try:
        rec_uuid = UUID(recommendation_id)
    except (ValueError, AttributeError) as exc:
        raise MCPAuthError(400, "invalid_input", f"Bad recommendation_id: {exc}") from exc

    clean_notes = sanitize_notes(notes or "", max_len=1000)
    feedback_map = {"accepted": "followed", "rejected": "rejected",
                    "modified": "neutral", "ignored": "neutral"}

    reflection = f"[rec={rec_uuid}] outcome={outcome} decided_by={decided_by}"
    if actual_value is not None:
        reflection += f" actual={actual_value}"
    if clean_notes:
        reflection += f" notes={clean_notes}"

    # Tuple dedup — fast, no embedding needed (ADR D7 first pass)
    existing = await db.execute(
        select(OperationalMemory)
        .where(OperationalMemory.hotel_id == hotel_id)
        .where(OperationalMemory.memory_type == "feedback")
        .where(OperationalMemory.reflection.like(f"[rec={rec_uuid}]%outcome={outcome}%"))
        .limit(1)
    )
    if existing.scalars().first():
        return {"memory_id": None, "status": "deduplicated", "embedding_dim": 1024}

    # Compute real embedding (ADR D1 / P1-3); fall back to pending-flag on failure (ADR D9)
    embedding_vec: list[float] | None = None
    embedding_pending = False
    embedding_status = "stored"

    if embedding_provider is not None:
        try:
            payload = MemoryRecallService.build_embedding_payload(
                memory_type="feedback",
                outcome=outcome,
                notes=clean_notes or None,
                actual_value=actual_value,
            )
            embedding_vec = await embedding_provider.embed(payload)

            # Cosine dedup second pass (ADR D7)
            recall_svc = MemoryRecallService(db)
            dup_id = await recall_svc.check_cosine_dedup(hotel_id, embedding_vec)
            if dup_id:
                return {"memory_id": str(dup_id), "status": "deduplicated", "embedding_dim": 1024}
        except Exception as exc:
            logger.warning("embedding failed, writing pending row (ADR D9): %s", exc)
            embedding_pending = True
            embedding_status = "stored_pending_embedding"
    else:
        # No embedding provider available — write pending (ADR D9)
        embedding_pending = True
        embedding_status = "stored_pending_embedding"

    mem = OperationalMemory(
        hotel_id=hotel_id,
        reflection=reflection,
        manager_feedback=feedback_map[outcome],
        outcome=outcome,
        memory_type="feedback",
        embedding=embedding_vec,
        embedding_pending=embedding_pending,
        request_id=request_id,
        # HOS-317 — joinable link, alongside the `[rec=...]` text marker the
        # dedup above still matches on (legacy rows have only the marker).
        recommendation_id=rec_uuid,
    )
    db.add(mem)
    await db.flush()
    return {
        "memory_id": str(mem.id),
        "status": embedding_status,
        "embedding_dim": len(embedding_vec) if embedding_vec else 0,
    }


# ---------------------------------------------------------------------------
# ADR-0007 §17.4 — decisions from host agents: provenance + reason + policy
# ---------------------------------------------------------------------------

# Recommendation states a host may still decide. `ready_to_push` covers a
# headless tenant whose recommendations never go through WhatsApp.
_HOST_DECIDABLE_STATUSES = ("ready_to_push", "dispatched")


async def tool_record_host_decision(
    hotel_id: str,
    db: AsyncSession,
    caller: str,
    recommendation_id: str,
    outcome: str,
    embedding_provider: Any = None,
    actual_value: Optional[float] = None,
    notes: Optional[str] = None,
    request_id: str = "",
    **provenance: Any,
) -> dict[str, Any]:
    """MCP ``submit_feedback_to_memory``: record a host's decision.

    Order: outcome + provenance/reason validation (400, typed) → the
    recommendation must belong to the token's hotel (404, never another
    tenant's) → the decision policy seam (403 ``autonomy_not_permitted`` for a
    host agent deciding alone under the default policy) → still undecided
    (409 ``already_decided``) → write decision + who + why on the
    recommendation → feedback memory (unchanged path).

    ``ignored`` records no decision on the recommendation (memory only).
    """
    from app.db.models import StaffingRecommendation
    from app.services.decision_policy import DecisionNotPermitted, authorize_decision
    from app.services.decision_provenance import ProvenanceError, parse_agent_decision
    from app.services.manager_decision import DecisionSource

    if outcome not in ("accepted", "rejected", "modified", "ignored"):
        raise MCPAuthError(400, "invalid_input",
                           "outcome must be accepted|rejected|modified|ignored")
    try:
        decision = parse_agent_decision(provenance)
    except ProvenanceError as exc:
        raise MCPAuthError(400, "invalid_input", f"{exc.code}: {exc.detail}") from exc
    try:
        rec_uuid = UUID(recommendation_id)
    except (ValueError, AttributeError) as exc:
        raise MCPAuthError(400, "invalid_input", f"Bad recommendation_id: {exc}") from exc

    rec = (await db.execute(
        select(StaffingRecommendation).where(
            StaffingRecommendation.id == rec_uuid,
            StaffingRecommendation.tenant_id == hotel_id,
        )
    )).scalars().first()
    if rec is None:
        raise MCPAuthError(404, "unknown_recommendation",
                           "No recommendation with this id for the authenticated property")

    now = datetime.now(timezone.utc)
    try:
        policy = authorize_decision(hotel_id, decision.decided_by, at=now)
    except DecisionNotPermitted as exc:
        logger.info("host_decision_refused hotel=%s rec=%s code=%s policy=%s caller=%s",
                    hotel_id, rec_uuid, exc.code, exc.policy.version, caller)
        raise MCPAuthError(403, exc.code, exc.detail) from exc

    if outcome != "ignored":
        if rec.status not in _HOST_DECIDABLE_STATUSES:
            raise MCPAuthError(409, "already_decided",
                               f"recommendation already decided ({rec.status})")
        rec.status = outcome
        rec.action = outcome
        rec.actioned_at = now
        rec.decision_source = (
            DecisionSource.host_relay.value if decision.decided_by == "human_via_host"
            else DecisionSource.host_agent.value
        )
        rec.decision_confidence = 1.0
        rec.decided_by = decision.decided_by
        rec.decided_by_caller = caller
        rec.reason_code = decision.reason_code
        rec.reason_detail = decision.reason_detail or None
        rec.reason_source = decision.reason_source
        rec.reason_evidence = [e.model_dump() for e in decision.evidence] or None
        rec.decision_policy_version = policy.version
        logger.info(
            "host_decision_recorded hotel=%s rec=%s outcome=%s decided_by=%s reason_code=%s "
            "reason_source=%s caller=%s policy=%s",
            hotel_id, rec_uuid, outcome, decision.decided_by, decision.reason_code,
            decision.reason_source, caller, policy.version,
        )

    memory = await tool_submit_feedback_to_memory(
        hotel_id, recommendation_id, outcome, db,
        embedding_provider=embedding_provider, actual_value=actual_value, notes=notes,
        request_id=request_id, decided_by=decision.decided_by,
    )
    return {
        **memory,
        "decision_recorded": outcome != "ignored",
        "decided_by": decision.decided_by,
        "decision_policy_version": policy.version,
    }


async def tool_get_decision_recap(
    hotel_id: str, db: AsyncSession, period: str = "week", locale: str = "fr",
) -> dict[str, Any]:
    """MCP ``get_decision_recap`` — same deterministic recap as WhatsApp."""
    from app.services.decision_recap import PERIODS, build_recap, render_text

    if period not in PERIODS:
        raise MCPAuthError(400, "invalid_input", f"period must be one of {', '.join(PERIODS)}")
    if locale not in ("fr", "en"):
        raise MCPAuthError(400, "invalid_input", "locale must be fr|en")
    summary = await build_recap(db, hotel_id, period)
    return {"recap": summary.as_dict(), "text": render_text(summary, locale)}


async def tool_get_pending_recommendations(
    hotel_id: str, db: AsyncSession, locale: str = "fr", limit: int = 20,
) -> dict[str, Any]:
    """MCP ``get_pending_recommendations`` (ADR-0007 §18.4) — the token's hotel
    only; typed consequences as stored at issue time, never recomputed."""
    from sqlalchemy import select as _select

    from app.db.models import StaffingRecommendation
    from app.services.risk_assessment import render_lines

    if locale not in ("fr", "en"):
        raise MCPAuthError(400, "invalid_input", "locale must be fr|en")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise MCPAuthError(400, "invalid_input", "limit must be an integer") from None
    if not 1 <= limit <= 50:
        raise MCPAuthError(400, "invalid_input", "limit must be within [1, 50]")
    rows = (
        await db.execute(
            _select(StaffingRecommendation)
            .where(
                StaffingRecommendation.tenant_id == hotel_id,
                StaffingRecommendation.status.in_(("ready_to_push", "dispatched")),
            )
            .order_by(StaffingRecommendation.window_start)
            .limit(limit)
        )
    ).scalars().all()
    items = []
    for r in rows:
        ra = r.risk_assessment if isinstance(r.risk_assessment, dict) else None
        items.append({
            "recommendation_id": str(r.id),
            "status": r.status,
            "window_start": r.window_start.isoformat() if r.window_start else None,
            "window_end": r.window_end.isoformat() if r.window_end else None,
            "task_class": r.task_class,
            "recommended_delta_staff": r.recommended_headcount,
            "decision_rule": r.decision_rule,
            "correction_window": r.correction_window,
            "risk": ra,
            "lines": render_lines(ra, locale) if ra else [],
        })
    return {"hotel_id": hotel_id, "recommendations": items}


# ---------------------------------------------------------------------------
# Dispatcher — used by the HTTP shim and integration tests
# ---------------------------------------------------------------------------

async def dispatch_tool(
    tool_name: str,
    arguments: dict[str, Any],
    authorization: Optional[str],
    db: AsyncSession,
    embedding_provider: Any = None,
    engine: Any = None,
    request_id: str = "",
) -> dict[str, Any]:
    """Validate auth + scope + rate limit, then route to the tool body.

    embedding_provider and engine are injected from app.state by the HTTP shim.
    If None (test env / missing creds), tools fall back gracefully (ADR D9).
    Emits one agent_action_log row per call (ADR 0003 D2), including auth_error
    and rate_limited paths — every served request produces exactly one row.
    """
    if tool_name not in _ALL_TOOL_NAMES:
        raise MCPAuthError(404, "not_found", f"Unknown tool: {tool_name}")

    # Pre-tool event: hotel_id + scopes unknown until verify_bearer succeeds.
    # We build the event lazily and emit it in the outer finally block so that
    # any status transition (auth_error, rate_limited, tool_error, ok) produces
    # exactly one agent_action_log row.
    event = AgentEvent(
        hotel_id="<unauthenticated>",
        tool_name=tool_name,
        scopes=[],
        status="ok",
        request_id=request_id,
    )
    t0 = time.monotonic()

    try:
        try:
            tok = await verify_bearer(authorization, db)
        except MCPAuthError as exc:
            event.status = "auth_error"
            event.error_code = exc.title
            raise
        event.hotel_id = tok.hotel_id
        event.scopes = tok.scopes or []

        try:
            require_scope(tok.scopes, tool_name)
        except MCPAuthError as exc:
            event.status = "auth_error"
            event.error_code = exc.title
            raise

        try:
            redis_used = await check_rate_limit_async(tok.hotel_id, tool_name)
        except MCPAuthError as exc:
            event.status = "rate_limited"
            event.error_code = exc.title
            raise

        if not redis_used:
            logger.warning(
                "rate_limit_fallback hotel=%s tool=%s (Redis unavailable)",
                tok.hotel_id, tool_name,
            )

        # hotel_id, request_id, engine come from the server — never from arguments (ADR D4 / P2-2)
        args = {k: v for k, v in (arguments or {}).items() if k not in ("hotel_id", "request_id", "engine")}

        try:
            if tool_name == "get_operational_predictions":
                result = await tool_get_operational_predictions(tok.hotel_id, engine=engine, **args)
            elif tool_name == "get_recommendations_with_memory_context":
                result = await tool_get_recommendations_with_memory_context(
                    tok.hotel_id, db=db, embedding_provider=embedding_provider, engine=engine, **args,
                )
            elif tool_name == "recall_memory":
                result = await tool_recall_memory(
                    tok.hotel_id, db=db, embedding_provider=embedding_provider, **args,
                )
            elif tool_name == "submit_feedback_to_memory":
                result = await tool_record_host_decision(
                    tok.hotel_id, db=db, caller=tok.label or tok.token_prefix or str(tok.id),
                    embedding_provider=embedding_provider,
                    request_id=event.request_id, **args,
                )
            elif tool_name == "get_decision_recap":
                result = await tool_get_decision_recap(tok.hotel_id, db=db, **args)
            elif tool_name == "get_pending_recommendations":
                result = await tool_get_pending_recommendations(tok.hotel_id, db=db, **args)
            else:
                raise MCPAuthError(500, "internal_error", "Dispatcher inconsistency")
        except MCPAuthError as exc:
            event.status = "tool_error"
            event.error_code = exc.title
            raise
        except Exception:
            event.status = "tool_error"
            event.error_code = "internal_error"
            raise
    finally:
        event.latency_ms = round((time.monotonic() - t0) * 1000)
        try:
            async with AsyncSessionLocal() as isolated_db:
                await emit_agent_event(event, isolated_db)
                await isolated_db.commit()
        except Exception as exc:
            logger.warning("audit log isolated session failed: %s", exc)

    return result

"""Agent observability — AgentEvent model + emit_agent_event() (ADR 0003 · HOS-73b).

One row per MCP tool call, written synchronously in dispatch_tool before
db.commit(). Never raises — logging failures are warnings, not tool errors.

PII policy (ADR 0003 D9):
- Bearer token: never logged
- Raw query text: never logged (only tool_name + status)
- hotel_id: logged (non-personally-identifying internal ID)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    hotel_id: str
    tool_name: str
    scopes: list[str]
    status: str                               # "ok" | "auth_error" | "tool_error" | "rate_limited"
    request_id: str = ""
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    embedding_latency_ms: Optional[int] = None
    dedup_hit: Optional[bool] = None
    top_similarity: Optional[float] = None


async def emit_agent_event(event: AgentEvent, db: AsyncSession) -> None:
    """Append one row to agent_action_log. Silently swallows DB errors (ADR 0003 D2)."""
    sql = text("""
        INSERT INTO agent_action_log (
            hotel_id, tool_name, scopes, status, error_code,
            latency_ms, embedding_latency_ms, dedup_hit, top_similarity,
            request_id
        ) VALUES (
            :hotel_id, :tool_name, :scopes, :status, :error_code,
            :latency_ms, :embedding_latency_ms, :dedup_hit, :top_similarity,
            :request_id
        )
    """)
    try:
        await db.execute(sql, {
            "hotel_id": event.hotel_id,
            "tool_name": event.tool_name,
            "scopes": event.scopes,
            "status": event.status,
            "error_code": event.error_code,
            "latency_ms": event.latency_ms,
            "embedding_latency_ms": event.embedding_latency_ms,
            "dedup_hit": event.dedup_hit,
            "top_similarity": event.top_similarity,
            "request_id": event.request_id or "",
        })
    except Exception as exc:
        logger.warning("emit_agent_event failed (non-blocking): %s", exc)
        return
    logger.info("agent_event %s", json.dumps({
        "hotel_id": event.hotel_id,
        "tool": event.tool_name,
        "status": event.status,
        "latency_ms": event.latency_ms,
        "dedup_hit": event.dedup_hit,
    }))

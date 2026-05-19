"""Pure-logic primitives for the Aetherix MCP Server (ADR 0001 · P1-2).

Kept deliberately free of DB / ORM / engine imports so that:
  - Tier 1 unit tests (hashing, sanitization, rate limit, scope, manifest)
    run in any environment without the full backend stack.
  - Import cycles are impossible (this module is a leaf).

Import this module from `app.mcp_server` — never the reverse.
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

_MCP_VERSION = "0"

_TOOL_RATE_LIMITS = {
    "get_operational_predictions": 60,
    "get_recommendations_with_memory_context": 30,
    "submit_feedback_to_memory": 20,
    # v1 atomic tools
    "recall_memory": 60,
}

_TOOL_SCOPE = {
    "get_operational_predictions": "predict",
    "get_recommendations_with_memory_context": "recommend",
    "submit_feedback_to_memory": "feedback",
    # v1 atomic tools
    "recall_memory": "memory:read",
}

# Separate admin scope for destructive / model-mutating operations (HOS-149 AC4)
ADMIN_TRAIN_SCOPE = "admin:train"

# P2-6: Receipt drill-down read scope (HOS-172 OQ3)
RECEIPTS_READ_SCOPE = "receipts:read"

# In-memory fallback bucket; prod uses Redis (ADR D6) wired in v1.
_LOCAL_BUCKETS: dict[str, tuple[int, int]] = {}


class MCPAuthError(Exception):
    def __init__(self, status: int, title: str, detail: str):
        self.status = status
        self.title = title
        self.detail = detail
        super().__init__(f"{status} {title}: {detail}")


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sanitize_notes(text: str | None, max_len: int = 1000) -> str:
    """Strip all control chars including newlines/CR, trim, enforce max length.

    Strips 0x00-0x1f + 0x7f (entire C0 range). This intentionally removes
    \n (0x0a) and \r (0x0d) because notes are returned to calling agents via
    memory_hits[].summary — newlines are a prompt-injection vector.
    """
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return cleaned.strip()[:max_len]


def check_rate_limit(hotel_id: str, tool_name: str) -> None:
    limit = _TOOL_RATE_LIMITS.get(tool_name, 60)
    minute_bucket = int(time.time() // 60)
    key = f"{hotel_id}:{tool_name}:{minute_bucket}"
    count, bucket = _LOCAL_BUCKETS.get(key, (0, minute_bucket))
    count += 1
    _LOCAL_BUCKETS[key] = (count, bucket)
    if len(_LOCAL_BUCKETS) > 10_000:
        for k in list(_LOCAL_BUCKETS):
            if _LOCAL_BUCKETS[k][1] < minute_bucket - 2:
                _LOCAL_BUCKETS.pop(k, None)
    if count > limit:
        raise MCPAuthError(
            429,
            "rate_limited",
            f"{limit} req/min exceeded for tool={tool_name}",
        )


def require_scope(scopes: list[str] | None, tool_name: str) -> None:
    required = _TOOL_SCOPE[tool_name]
    if required not in (scopes or []):
        raise MCPAuthError(
            403, "forbidden", f"Token missing required scope: {required}",
        )


RECALL_MEMORY_TOOL: dict[str, Any] = {
    "name": "recall_memory",
    "description": (
        "Semantic recall from the property's operational memory. "
        "Returns the k most relevant past observations for a free-text query. "
        "Atomic replacement for the memory-recall step of "
        "get_recommendations_with_memory_context (deprecated in v0)."
    ),
    "inputSchema": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "maxLength": 500},
            "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
        },
    },
}

TOOLS_MANIFEST: list[dict[str, Any]] = [
    {
        "name": "get_operational_predictions",
        "description": "Forecast F&B covers and staffing for the authenticated property.",
        "inputSchema": {
            "type": "object",
            "required": ["target_date"],
            "properties": {
                "target_date": {"type": "string", "format": "date"},
                "service_type": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner"],
                    "default": "dinner",
                },
                "context": {
                    "type": "object",
                    "properties": {
                        "weather": {"type": "object"},
                        "events": {"type": "array"},
                        "occupancy": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
        },
    },
    {
        "name": "get_recommendations_with_memory_context",
        "description": "Contextualized recommendation pulling from operational_memory + fb_patterns.",
        "inputSchema": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "maxLength": 500},
                "target_date": {"type": "string", "format": "date"},
                "k_memory": {"type": "integer", "default": 5, "maximum": 20},
            },
        },
    },
    {
        "name": "submit_feedback_to_memory",
        "description": "Record manager outcome for a past recommendation (self-improving loop).",
        "inputSchema": {
            "type": "object",
            "required": ["recommendation_id", "outcome"],
            "properties": {
                "recommendation_id": {"type": "string", "format": "uuid"},
                "outcome": {
                    "type": "string",
                    "enum": ["accepted", "rejected", "modified", "ignored"],
                },
                "actual_value": {"type": "number"},
                "notes": {"type": "string", "maxLength": 1000},
            },
        },
    },
]

# v1 manifest: get_recommendations_with_memory_context replaced by recall_memory
V1_TOOLS_MANIFEST: list[dict[str, Any]] = [
    next(t for t in TOOLS_MANIFEST if t["name"] == "get_operational_predictions"),
    RECALL_MEMORY_TOOL,
    next(t for t in TOOLS_MANIFEST if t["name"] == "submit_feedback_to_memory"),
]

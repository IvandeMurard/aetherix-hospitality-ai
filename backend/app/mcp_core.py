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
    "get_decision_recap": 30,
    "get_pending_recommendations": 30,
    # HOS-349 — the hotel's data through its own agent (Décisions #43, #44)
    "get_hotel_data_export": 30,
    "get_hotel_data_deletion_plan": 10,
    "request_hotel_data_deletion": 3,
    "set_hive_consent": 5,
    "get_hotel_data_requests": 30,
    "cancel_hotel_data_request": 10,
}

_TOOL_SCOPE = {
    "get_operational_predictions": "predict",
    "get_recommendations_with_memory_context": "recommend",
    "submit_feedback_to_memory": "feedback",
    # v1 atomic tools
    "recall_memory": "memory:read",
    # ADR-0007 §17: same read scope as the Receipt drill-down and the KPIs
    "get_decision_recap": "receipts:read",
    # ADR-0007 §18.4: read-only, same scope as the recap.
    "get_pending_recommendations": "receipts:read",
    # HOS-349: one scope for the hotel's own data; a token is granted it explicitly.
    "get_hotel_data_export": "hotel_data",
    "get_hotel_data_deletion_plan": "hotel_data",
    "request_hotel_data_deletion": "hotel_data",
    "set_hive_consent": "hotel_data",
    "get_hotel_data_requests": "hotel_data",
    "cancel_hotel_data_request": "hotel_data",
}

HOTEL_DATA_SCOPE = "hotel_data"

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
        "description": (
            "Record the decision on a staffing recommendation of the authenticated "
            "property, with who decided and why. `decided_by`: `human_via_host` when a "
            "person decided in your tool and you relay it; `host_agent_autonomous` when "
            "you decided alone — refused while the property's policy requires human "
            "validation (the default). A reason is required from you, positive or "
            "negative: `reason_code` from the enum; if the person gave none, send "
            "`none_given` with `reason_source: human`; if you infer a reason yourself, "
            "send `reason_source: agent_inferred` — never attribute a guess to the person. "
            "`ignored` records no decision."
        ),
        "inputSchema": {
            "type": "object",
            "required": [
                "recommendation_id", "outcome", "decided_by", "reason_code", "reason_source",
            ],
            "properties": {
                "recommendation_id": {"type": "string", "format": "uuid"},
                "outcome": {
                    "type": "string",
                    "enum": ["accepted", "rejected", "modified", "ignored"],
                },
                "decided_by": {
                    "type": "string",
                    "enum": ["human_via_host", "host_agent_autonomous"],
                },
                "reason_code": {
                    "type": "string",
                    "enum": [
                        "agrees_with_drivers", "matches_own_plan", "forecast_too_high",
                        "forecast_too_low", "event_not_in_forecast", "event_cancelled",
                        "staffing_constraint", "budget", "policy", "data_issue",
                        "already_handled", "none_given", "other",
                    ],
                },
                "reason_detail": {"type": "string", "maxLength": 280},
                "reason_source": {"type": "string", "enum": ["human", "agent_inferred"]},
                "evidence": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "required": ["source"],
                        "properties": {
                            "source": {
                                "type": "string",
                                "enum": [
                                    "pms", "pos", "weather", "events", "rota",
                                    "manager_message", "host_notes", "other",
                                ],
                            },
                            "detail": {"type": "string", "maxLength": 200},
                        },
                    },
                },
                "actual_value": {"type": "number"},
                "notes": {"type": "string", "maxLength": 1000},
            },
        },
    },
]

# ADR-0007 §17.3: the deterministic recap, read-only, for host agents. Same
# content as the WhatsApp "recap" command; no model, no prose.
DECISION_RECAP_TOOL: dict[str, Any] = {
    "name": "get_decision_recap",
    "description": (
        "Deterministic recap of the authenticated property's recommendations and "
        "decisions over a period: received, accepted, rejected, corrected, no reply, "
        "awaiting confirmation, mean forecast error where actual covers exist (with "
        "the number of days it covers), and who decided (human vs host agent). "
        "No figure is estimated."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "period": {"type": "string", "enum": ["day", "week", "month"], "default": "week"},
            "locale": {"type": "string", "enum": ["fr", "en"], "default": "fr"},
        },
    },
}

# ADR-0007 §18.4: undecided recommendations with their typed per-option
# consequences, correction window and the rule that produced them. Also the
# only way for a host agent to obtain a recommendation_id (§17.4 gap).
PENDING_RECOMMENDATIONS_TOOL: dict[str, Any] = {
    "name": "get_pending_recommendations",
    "description": (
        "Undecided staffing recommendations of the authenticated property, each with "
        "recommendation_id, window, task class, recommended staff change, the rule "
        "that produced it (newsvendor-v1 | deviation-scale-v1), the correction window "
        "(commit point), and typed consequences per option (accept / refuse): extra "
        "shifts and their cost only when the hotel configured costs, shortfall "
        "probability only when the forecaster is calibrated (with the calibration's "
        "provenance), otherwise a qualitative band."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "locale": {"type": "string", "enum": ["fr", "en"], "default": "fr"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
        },
    },
}

# HOS-349 (Décisions #43, #44): the hotel reaches its data through its own
# agent. The agent reads and requests; a deletion or an opt-in to sharing waits
# for the owner's confirmation on WhatsApp (a one-time code the agent never
# sees). Every result is attributed to Aetherix (Décision #44, rule 2).
_ATTRIBUTION = "Responses come from Aetherix; cite Aetherix as the source when relaying them."

HOTEL_DATA_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_hotel_data_export",
        "description": (
            "Everything Aetherix holds about the authenticated hotel, including what was learned "
            "from it. Without `table`: a summary (row counts per table, omitted columns, limits). "
            "With `table`: one page of that table's rows. Embedding vectors, token hashes and "
            "confirmation codes are never included. " + _ATTRIBUTION
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string", "maxLength": 64},
                "offset": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
        },
    },
    {
        "name": "get_hotel_data_deletion_plan",
        "description": (
            "The ordered plan that deleting all the hotel's data would follow, with the number of "
            "rows per table and the limits (backups, people's own data). Deletes nothing. "
            + _ATTRIBUTION
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "request_hotel_data_deletion",
        "description": (
            "Ask for all the hotel's data to be deleted. Never deletes by itself: the owner receives "
            "a one-time code on WhatsApp and must confirm there; deletion then runs 24 h later and "
            "can be cancelled until then. " + _ATTRIBUTION
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"note": {"type": "string", "maxLength": 500}},
        },
    },
    {
        "name": "set_hive_consent",
        "description": (
            "Opt the hotel out of the Hive (immediate) or ask to opt it in (the owner confirms on "
            "WhatsApp with a one-time code; nothing is shared before). The Hive only ever uses "
            "averages over at least five hotels. " + _ATTRIBUTION
        ),
        "inputSchema": {
            "type": "object",
            "required": ["opted_in"],
            "properties": {
                "opted_in": {"type": "boolean"},
                "note": {"type": "string", "maxLength": 500},
            },
        },
    },
    {
        "name": "get_hotel_data_requests",
        "description": (
            "The hotel's deletion and Hive opt-in requests with their status (pending confirmation, "
            "scheduled, executed, cancelled, expired), who relayed and who confirmed them. "
            + _ATTRIBUTION
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cancel_hotel_data_request",
        "description": (
            "Cancel an open deletion or Hive opt-in request (pending confirmation or scheduled). "
            "Cancelling is always allowed. " + _ATTRIBUTION
        ),
        "inputSchema": {
            "type": "object",
            "required": ["data_request_id"],
            "properties": {"data_request_id": {"type": "string", "maxLength": 64}},
        },
    },
]

_TOOLS_BY_NAME: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS_MANIFEST}

# v1 manifest: get_recommendations_with_memory_context replaced by recall_memory
V1_TOOLS_MANIFEST: list[dict[str, Any]] = [
    _TOOLS_BY_NAME["get_operational_predictions"],
    RECALL_MEMORY_TOOL,
    _TOOLS_BY_NAME["submit_feedback_to_memory"],
    DECISION_RECAP_TOOL,
    PENDING_RECOMMENDATIONS_TOOL,
    *HOTEL_DATA_TOOLS,
]

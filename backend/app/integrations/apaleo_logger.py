"""
Apaleo write-guard and agent action logger — HOS-107.

Read-only mode (Phase 0 default)
---------------------------------
All write operations are blocked unless ``APALEO_READONLY=false`` is set.
Every tool call (read or blocked-write) is logged as a structured JSON line
to the ``apaleo.agent_actions`` logger.

The write-guard is applied at the transport chokepoint
(``ApaleoMCPClient.call_tool``) so it covers all MCP paths automatically.
The REST adapter (``ApaleoPMSAdapter``) applies it explicitly on its own
write method.

Usage::

    from app.integrations.apaleo_logger import (
        ApaleoAgentLogger,
        ApaleoWriteBlockedError,
        is_readonly_mode,
        is_write_tool,
    )
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger("apaleo.agent_actions")

# ---------------------------------------------------------------------------
# Known write tools (both Composio/Inventory and bearer/Core API)
# ---------------------------------------------------------------------------

#: Tool names that mutate state in Apaleo.
#: Extend this set when new write capabilities are added.
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        # Core API — bearer/direct mode
        "APALEO_UPDATE_SCHEDULE",
        # Inventory API — Composio apikey mode
        "APALEO_CREATES_A_PROPERTY",
        "APALEO_ARCHIVE_A_PROPERTY",
        "APALEO_CLONES_A_PROPERTY",
        "APALEO_MOVE_PROPERTY_TO_LIVE",
        "APALEO_RESET_PROPERTY_DATA",
        "APALEO_CREATE_A_UNIT",
        "APALEO_CREATE_MULTIPLE_UNITS",
        "APALEO_DELETE_A_UNIT",
        "APALEO_CREATE_A_UNIT_GROUP",
        "APALEO_REPLACE_A_UNIT_GROUP",
        "APALEO_DELETE_A_UNIT_GROUP",
        # Raw REST adapter sentinel (used by ApaleoPMSAdapter)
        "REST_UPDATE_STAFFING",
    }
)


def is_readonly_mode() -> bool:
    """Return True when the write-guard is active (default in Phase 0).

    Controlled by the ``APALEO_READONLY`` env var:

    - unset / ``"true"`` / ``"1"`` / ``"yes"``  → read-only (default)
    - ``"false"`` / ``"0"`` / ``"no"``           → writes allowed
    """
    return os.getenv("APALEO_READONLY", "true").lower() not in ("false", "0", "no")


def is_write_tool(tool_name: str) -> bool:
    """Return True when *tool_name* is a known write operation."""
    return tool_name in WRITE_TOOLS


class ApaleoWriteBlockedError(RuntimeError):
    """Raised when a write operation is attempted while in read-only mode.

    Phase 0 policy (HOS-107): Apaleo is read-only by default.
    Set ``APALEO_READONLY=false`` to enable writes once the integration
    is mature enough.
    """


# ---------------------------------------------------------------------------
# Structured agent action log
# ---------------------------------------------------------------------------

ActionMode = Literal["read", "write", "blocked"]


@dataclass
class AgentActionRecord:
    """Immutable snapshot of a single Apaleo agent action."""

    timestamp: str
    tool: str
    params: dict[str, Any]
    user: str | None
    mode: ActionMode
    duration_ms: float | None = None
    result_summary: str | None = None
    error: str | None = None


class ApaleoAgentLogger:
    """Emit a structured JSON log line for every Apaleo agent action.

    Log levels:

    - ``WARNING`` for blocked write attempts (``mode="blocked"``)
    - ``INFO``    for executed reads and (allowed) writes

    All records are prefixed with ``APALEO_AGENT_ACTION`` for easy
    log-aggregator filtering.

    Example output::

        INFO  apaleo.agent_actions APALEO_AGENT_ACTION {"timestamp": "...",
            "tool": "APALEO_GET_A_PROPERTIES_LIST", "params": {}, "user": null,
            "mode": "read", "duration_ms": 123.4, ...}

        WARNING apaleo.agent_actions APALEO_AGENT_ACTION {"timestamp": "...",
            "tool": "APALEO_UPDATE_SCHEDULE", "params": {...}, "user": "agent",
            "mode": "blocked", "error": "read-only mode active (Phase 0)"}
    """

    def log(
        self,
        tool: str,
        params: dict[str, Any],
        *,
        user: str | None = None,
        mode: ActionMode = "read",
        duration_ms: float | None = None,
        result_summary: str | None = None,
        error: str | None = None,
    ) -> AgentActionRecord:
        """Log one agent action and return its record.

        Args:
            tool:           Tool/method name (e.g. ``"APALEO_GET_A_PROPERTIES_LIST"``).
            params:         Input parameters passed to the tool (must be JSON-safe).
            user:           Caller identity — agent name, user ID, or ``None``.
            mode:           ``"read"``, ``"write"``, or ``"blocked"``.
            duration_ms:    Round-trip latency in milliseconds (omit for blocked calls).
            result_summary: Short summary of the result (first 200 chars recommended).
            error:          Exception message if the call failed or was blocked.

        Returns:
            The ``AgentActionRecord`` that was logged.
        """
        record = AgentActionRecord(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            tool=tool,
            params=params,
            user=user,
            mode=mode,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            result_summary=result_summary,
            error=error,
        )
        payload = json.dumps(
            {
                "timestamp": record.timestamp,
                "tool": record.tool,
                "params": record.params,
                "user": record.user,
                "mode": record.mode,
                "duration_ms": record.duration_ms,
                "result_summary": record.result_summary,
                "error": record.error,
            },
            default=str,
        )
        if mode == "blocked":
            logger.warning("APALEO_AGENT_ACTION %s", payload)
        else:
            logger.info("APALEO_AGENT_ACTION %s", payload)
        return record

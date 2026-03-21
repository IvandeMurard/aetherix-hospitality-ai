"""
Ops Dispatcher — central router between internal events and external ops tools.

Rules:
  - Critical errors / service failures  → Linear issue (priority 2 = high)
  - Anomalies / threshold breaches      → Linear issue (priority 3 = medium) + Obsidian alert
  - Routine reports / audit logs        → Obsidian note only (no Linear issue)

All functions are fire-and-forget: failures are logged but never re-raised,
so a broken Linear/Obsidian config never disrupts the main request path.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Linear priority constants (0=none, 1=urgent, 2=high, 3=medium, 4=low)
P_ERROR = 2
P_ANOMALY = 3


async def dispatch_error(
    title: str,
    detail: str,
    priority: int = P_ERROR,
    tags: Optional[list[str]] = None,
) -> None:
    """Create a Linear issue for service errors or failures."""
    try:
        from app.integrations.linear import create_issue
        await create_issue(title=title, description=detail, priority=priority)
        logger.info(f"ops_dispatcher: Linear issue created — {title!r}")
    except Exception as exc:
        logger.warning(f"ops_dispatcher: Linear issue failed: {exc}")

    # Mirror into Obsidian Alerts folder
    try:
        from app.integrations.obsidian import write_note, VAULT_FOLDERS
        content = f"## {title}\n\n{detail}\n\n> Linear issue created (priority {priority})"
        write_note(title, content, folder=VAULT_FOLDERS["alerts"], tags=["error"] + (tags or []))
    except Exception as exc:
        logger.warning(f"ops_dispatcher: Obsidian alert write failed: {exc}")


async def dispatch_anomaly(
    title: str,
    detail: str,
    tags: Optional[list[str]] = None,
) -> None:
    """Create a medium-priority Linear issue for anomalies and threshold breaches."""
    await dispatch_error(title, detail, priority=P_ANOMALY, tags=tags)


async def dispatch_report(
    title: str,
    content: str,
    folder: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> None:
    """Write a report or operational log to the Obsidian vault only."""
    try:
        from app.integrations.obsidian import write_note, VAULT_FOLDERS
        write_note(
            title=title,
            content=content,
            folder=folder or VAULT_FOLDERS["reports"],
            tags=tags or [],
        )
        logger.info(f"ops_dispatcher: Obsidian note written — {title!r}")
    except Exception as exc:
        logger.warning(f"ops_dispatcher: Obsidian report write failed: {exc}")

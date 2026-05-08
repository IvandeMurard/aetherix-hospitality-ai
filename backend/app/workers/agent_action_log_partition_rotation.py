"""HOS-150 AC4 — APScheduler job that keeps `agent_action_log` partitions ahead.

`agent_action_log` is PARTITION BY RANGE (created_at) with one partition per
calendar month. If we don't keep creating future partitions ahead of `now()`,
every MCP tool-call INSERT will fail with `no partition of relation "..." found
for row` — which would take the MCP server down (the INSERT runs in the finally
of the dispatcher).

This job runs at 02:00 UTC on the 1st of every month and ensures the partition
for `<current month + 2>` exists (idempotent — `CREATE TABLE IF NOT EXISTS`).
On failure, `dispatch_error` is invoked so we get a Linear issue + Obsidian
alert.
"""
from __future__ import annotations

import logging
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


def _next_month(d: date) -> date:
    """Return the first day of the month after `d`."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _partition_bounds(target: date) -> tuple[str, str, str]:
    """Compute (table_name, lower_bound, upper_bound) for the month of `target`."""
    start = date(target.year, target.month, 1)
    end = _next_month(start)
    table_name = f"agent_action_log_{start.year:04d}_{start.month:02d}"
    return table_name, start.isoformat(), end.isoformat()


async def ensure_partition_exists(target: date) -> str:
    """Create (idempotent) the agent_action_log partition that covers `target`.

    Returns the partition table name. Raises on SQL error.
    """
    table_name, lower, upper = _partition_bounds(target)
    stmt = (
        f'CREATE TABLE IF NOT EXISTS "{table_name}" '
        f"PARTITION OF agent_action_log "
        f"FOR VALUES FROM ('{lower}') TO ('{upper}')"
    )
    async with engine.begin() as conn:
        await conn.execute(text(stmt))
    logger.info("partition_rotation: ensured %s [%s, %s)", table_name, lower, upper)
    return table_name


async def rotate_partitions(today: date | None = None) -> None:
    """Entry point for APScheduler. Ensures partition for month+2 exists."""
    today = today or date.today()
    target = _next_month(_next_month(date(today.year, today.month, 1)))
    try:
        await ensure_partition_exists(target)
    except Exception as exc:
        logger.exception("partition_rotation: failed to create partition for %s", target)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="agent_action_log partition rotation failed",
                detail=(
                    f"Failed to create monthly partition for {target.isoformat()}. "
                    f"Without this partition, MCP tool-call INSERTs on "
                    f"agent_action_log will start failing on "
                    f"{target.isoformat()}. Error: {exc!r}"
                ),
                tags=["partition", "agent_action_log", "schema"],
            )
        except Exception as inner:
            logger.warning("partition_rotation: dispatch_error itself failed: %s", inner)
        raise


def register_partition_rotation_job(scheduler: AsyncIOScheduler) -> None:
    """Register the monthly cron — 1st of each month at 02:00 UTC."""
    scheduler.add_job(
        rotate_partitions,
        trigger="cron",
        day=1,
        hour=2,
        minute=0,
        id="agent_action_log_partition_rotation",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "partition_rotation: cron registered (1st of month, 02:00 UTC, ensures month+2)"
    )

"""APScheduler job — refreshes memory_instrumentation_daily MV at 02:00 UTC (ADR 0003 D8)."""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


async def refresh_memory_instrumentation_mv() -> None:
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY memory_instrumentation_daily")
            )
        logger.info("memory_instrumentation_daily MV refreshed")
    except Exception as exc:
        logger.warning("MV refresh failed (non-blocking): %s", exc)


def register_memory_metrics_job(scheduler) -> None:
    scheduler.add_job(
        refresh_memory_instrumentation_mv,
        trigger="cron",
        hour=2,
        minute=0,
        id="memory_metrics_refresh",
        replace_existing=True,
    )

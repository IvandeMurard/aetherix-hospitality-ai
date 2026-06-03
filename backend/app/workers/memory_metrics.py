"""APScheduler job — refreshes memory_instrumentation_daily MV at 02:00 UTC (ADR 0003 D8)."""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


async def refresh_memory_instrumentation_mv() -> None:
    job_id = str(uuid.uuid4())[:8]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY memory_instrumentation_daily")
            )
        logger.info("memory_metrics: MV refreshed  job_id=%s", job_id)
    except Exception as exc:
        logger.warning(
            "memory_metrics: MV refresh failed (non-blocking)  job_id=%s  error=%s",
            job_id,
            exc,
        )


def register_memory_metrics_job(scheduler) -> None:
    scheduler.add_job(
        refresh_memory_instrumentation_mv,
        trigger="cron",
        hour=2,
        minute=0,
        id="memory_metrics_refresh",
        replace_existing=True,
    )

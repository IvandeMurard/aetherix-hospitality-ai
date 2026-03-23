"""APScheduler background worker for anomaly detection.

Runs AnomalyDetectionService.run_full_scan() every 4 hours (cron: 0 */4 * * *).
Registered on FastAPI startup in main.py alongside weather/event sync jobs.

Architecture constraints:
- Cron job is registered on startup; no state is kept in this module.
- Session is opened per job execution and closed cleanly on exit.
[Source: story 3.3a Task 4, architecture.md#Infrastructure-Deployment]
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.anomaly_detection import AnomalyDetectionService

logger = logging.getLogger(__name__)

_service = AnomalyDetectionService()


async def _run_anomaly_scan_job() -> None:
    """Entry point called by APScheduler every 4 hours."""
    logger.info("anomaly_scan: starting scheduled run")
    async with AsyncSessionLocal() as db:
        await _service.run_full_scan(db)
    logger.info("anomaly_scan: scheduled run complete")


def register_anomaly_scan_job(scheduler: AsyncIOScheduler) -> None:
    """Register the 4-hour anomaly scan cron job on the provided scheduler.

    Args:
        scheduler: The application-level AsyncIOScheduler instance.
    """
    scheduler.add_job(
        _run_anomaly_scan_job,
        trigger="cron",
        hour="*/4",
        minute=0,
        id="anomaly_scan",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("anomaly_scan: cron job registered (every 4 hours)")

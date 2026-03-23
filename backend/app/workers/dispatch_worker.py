"""Dispatch Worker — Story 4.2 (HOS-25).

APScheduler cron job that polls for ready_to_push staffing recommendations
every 2 minutes (*/2 * * * *) and dispatches them to hotel managers.

NFR2: Alerts must be delivered within 3 minutes of anomaly detection.
A 2-minute poll interval guarantees worst-case delivery within that window.

Register via register_dispatch_job() on the application-level scheduler
in main.py (shared with anomaly_scan and other background jobs).

Architecture constraints:
- Job is registered on startup; no state is kept in this module.
- Session is opened per job execution and closed cleanly on exit.
[Source: story 4.2 HOS-25, architecture.md#Infrastructure-Deployment]
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.alert_dispatcher import AlertDispatcherService

logger = logging.getLogger(__name__)

_service = AlertDispatcherService()


async def _run_dispatch_job() -> None:
    """Entry point called by APScheduler every 2 minutes."""
    logger.info("dispatch_worker: starting dispatch run")
    async with AsyncSessionLocal() as db:
        try:
            await _service.run_pending(db)
            logger.info("dispatch_worker: dispatch run complete")
        except Exception:
            logger.exception("dispatch_worker: unhandled error during dispatch run")


def register_dispatch_job(scheduler: AsyncIOScheduler) -> None:
    """Register the 2-minute dispatch cron job on the provided scheduler.

    Args:
        scheduler: The application-level AsyncIOScheduler instance.
    """
    scheduler.add_job(
        _run_dispatch_job,
        trigger="cron",
        minute="*/2",
        id="dispatch_worker",
        replace_existing=True,
        misfire_grace_time=60,
    )
    logger.info("dispatch_worker: cron job registered (every 2 minutes)")

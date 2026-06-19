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
- On non-recoverable failure: dispatch_error() is called and exception re-raises.
[Source: story 4.2 HOS-25, architecture.md#Infrastructure-Deployment]
"""
from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.alert_dispatcher import AlertDispatcherService
from app.workers.heartbeat import JOB_DISPATCH_WORKER, record_heartbeat

logger = logging.getLogger(__name__)

_service = AlertDispatcherService()


async def _run_dispatch_job() -> None:
    """Entry point called by APScheduler every 2 minutes."""
    job_id = str(uuid.uuid4())[:8]
    logger.info("dispatch_worker: started  job_id=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            await _service.run_pending(db)
        logger.info("dispatch_worker: complete  job_id=%s", job_id)
        # AC2 — heartbeat marks a completed run for the dead-man's switch.
        await record_heartbeat(JOB_DISPATCH_WORKER)
    except Exception as exc:
        logger.exception("dispatch_worker: error  job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="dispatch_worker job failed",
                detail=(
                    f"Unrecoverable error in 2-minute dispatch run. "
                    f"job_id={job_id}. Error: {exc!r}"
                ),
                tags=["dispatch_worker", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("dispatch_worker: dispatch_error failed: %s", inner)
        raise


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

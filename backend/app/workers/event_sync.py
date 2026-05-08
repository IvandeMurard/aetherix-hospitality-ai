"""APScheduler background worker — PredictHQ event sync daily at 06:00 UTC (HOS-84 Story 3.2).

The job is registered on the application-level scheduler (main.py lifespan) via
`start_event_scheduler(scheduler)` — no separate AsyncIOScheduler is created here.

Each job iteration:
  1. Fetches all RestaurantProfile rows that have GPS coordinates.
  2. Calls EventIngestionService.sync_for_tenant for each profile.
  3. Logs per-tenant success / failure; a per-tenant failure does NOT
     abort the remaining tenants (SC #6).
  4. On any non-recoverable outer exception: calls dispatch_error() and re-raises.
"""
from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select

from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.services.event_ingestion import EventIngestionService

logger = logging.getLogger(__name__)


async def _run_event_sync_for_all_tenants() -> None:
    """Iterate every property with GPS coords and sync PredictHQ events."""
    job_id = str(uuid.uuid4())[:8]
    service = EventIngestionService()

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(RestaurantProfile).where(
                    RestaurantProfile.latitude.isnot(None),
                    RestaurantProfile.longitude.isnot(None),
                )
            )
            profiles = result.scalars().all()

        logger.info(
            "event_sync: started  job_id=%s  properties=%d", job_id, len(profiles)
        )

        for profile in profiles:
            try:
                async with AsyncSessionLocal() as session:
                    rows = await service.sync_for_tenant(session, profile)
                logger.info(
                    "event_sync: OK  job_id=%s  tenant=%s  new_rows=%d",
                    job_id,
                    profile.tenant_id,
                    rows,
                )
            except Exception as exc:  # noqa: BLE001
                # Per-tenant failure must NOT affect other tenants (SC #6)
                logger.error(
                    "event_sync: FAILED  job_id=%s  tenant=%s  error=%s",
                    job_id,
                    profile.tenant_id,
                    exc,
                    exc_info=True,
                )

        logger.info("event_sync: job finished  job_id=%s", job_id)

    except Exception as exc:
        logger.exception("event_sync: job failed  job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="event_sync job failed",
                detail=(
                    f"Unrecoverable error in daily event sync. "
                    f"job_id={job_id}. Error: {exc!r}"
                ),
                tags=["event_sync", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("event_sync: dispatch_error failed: %s", inner)
        raise


def start_event_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Register the daily 06:00 UTC event sync job on the provided scheduler.

    The caller (main.py lifespan) is responsible for starting and stopping
    the scheduler — this function only adds the job.
    """
    scheduler.add_job(
        _run_event_sync_for_all_tenants,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="event_sync_daily_06utc",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("event_sync: job registered (cron=daily 06:00 UTC)")


def stop_event_scheduler() -> None:
    """No-op — lifecycle is managed by the application-level scheduler in main.py."""

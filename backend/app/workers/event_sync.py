"""APScheduler background worker — PredictHQ event sync daily at 06:00 UTC (HOS-84 Story 3.2).

The scheduler is started on FastAPI startup and stopped on shutdown.
Each job iteration:
  1. Fetches all RestaurantProfile rows that have GPS coordinates.
  2. Calls EventIngestionService.sync_for_tenant for each profile.
  3. Logs per-tenant success / failure; a per-tenant failure does NOT
     abort the remaining tenants (SC #6).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models import RestaurantProfile
from app.services.event_ingestion import EventIngestionService

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


async def _run_event_sync_for_all_tenants() -> None:
    """Iterate every property with GPS coords and sync PredictHQ events."""
    service = EventIngestionService()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.latitude.isnot(None),
                RestaurantProfile.longitude.isnot(None),
            )
        )
        profiles = result.scalars().all()

    logger.info("Event sync job started — %d properties with GPS", len(profiles))

    for profile in profiles:
        try:
            async with AsyncSessionLocal() as session:
                rows = await service.sync_for_tenant(session, profile)
            logger.info(
                "Event sync OK  tenant=%s  new_rows=%d",
                profile.tenant_id,
                rows,
            )
        except Exception as exc:  # noqa: BLE001
            # Per-tenant failure must NOT affect other tenants (SC #6)
            logger.error(
                "Event sync FAILED  tenant=%s  error=%s",
                profile.tenant_id,
                exc,
                exc_info=True,
            )


def start_event_scheduler() -> None:
    """Register the daily 06:00 UTC event sync job and start the scheduler."""
    _scheduler.add_job(
        _run_event_sync_for_all_tenants,
        trigger=CronTrigger(hour=6, minute=0, timezone="UTC"),
        id="event_sync_daily_06utc",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Event scheduler started (cron=daily 06:00 UTC)")


def stop_event_scheduler() -> None:
    """Gracefully shut down the scheduler on app shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Event scheduler stopped")

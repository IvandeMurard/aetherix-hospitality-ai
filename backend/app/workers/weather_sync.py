"""APScheduler background worker — weather sync every 12 hours (HOS-83 Story 3.1).

The scheduler is started on FastAPI startup and stopped on shutdown.
Each job iteration:
  1. Fetches all RestaurantProfile rows that have GPS coordinates.
  2. Calls WeatherIngestionService.sync_for_tenant for each profile.
  3. Logs per-tenant success / failure; a per-tenant failure does NOT
     abort the remaining tenants (SC #6).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models import RestaurantProfile
from app.services.weather_ingestion import WeatherIngestionService

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()


async def _run_weather_sync_for_all_tenants() -> None:
    """Iterate every property with GPS coords and sync weather."""
    service = WeatherIngestionService()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.latitude.isnot(None),
                RestaurantProfile.longitude.isnot(None),
            )
        )
        profiles = result.scalars().all()

    logger.info("Weather sync job started — %d properties with GPS", len(profiles))

    for profile in profiles:
        try:
            async with AsyncSessionLocal() as session:
                rows = await service.sync_for_tenant(session, profile)
            logger.info("Weather synced  tenant=%s  new_rows=%d", profile.tenant_id, rows)
        except Exception as exc:  # noqa: BLE001
            # Per-tenant failure must NOT affect other tenants (SC #6)
            logger.error(
                "Weather sync FAILED  tenant=%s  error=%s",
                profile.tenant_id,
                exc,
                exc_info=True,
            )


def start_weather_scheduler() -> None:
    """Register the 12-hour weather job and start the scheduler."""
    _scheduler.add_job(
        _run_weather_sync_for_all_tenants,
        trigger=IntervalTrigger(hours=12),
        id="weather_sync_12h",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Weather scheduler started (interval=12h)")


def stop_weather_scheduler() -> None:
    """Gracefully shut down the scheduler on app shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Weather scheduler stopped")

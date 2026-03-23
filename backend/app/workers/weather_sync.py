"""APScheduler 12-hour background worker for weather forecast ingestion.

Story 3.1: Ingest Localized Weather Data (HOS-83).

Schedule: every 12 hours (00:00 UTC and 12:00 UTC).
Behaviour:
- Queries all active restaurant profiles that have GPS coordinates configured.
- Calls WeatherIngestionService.sync_property() for each in sequence.
- Failures for one tenant are caught and logged; other tenants are not affected.
- The scheduler instance is created once and stored on the FastAPI app state
  so that it can be started/stopped with the application lifecycle.

Usage (in main.py):
    from app.workers.weather_sync import create_weather_scheduler
    scheduler = create_weather_scheduler()
    app.state.weather_scheduler = scheduler

    @app.on_event("startup")
    async def on_startup():
        scheduler.start()

    @app.on_event("shutdown")
    async def on_shutdown():
        scheduler.shutdown(wait=False)
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
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select

from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models import RestaurantProfile
from app.services.weather_ingestion import WeatherIngestionService

logger = logging.getLogger(__name__)

_service = WeatherIngestionService()


async def run_weather_sync_all_tenants() -> None:
    """Sync weather forecasts for every property with GPS coordinates.

    This coroutine is invoked by APScheduler every 12 hours.
    Errors for individual tenants are isolated — they do not abort the loop.
    """
    logger.info("Weather sync job started")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
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

    logger.info("Weather sync: %d properties to process", len(profiles))

    for profile in profiles:
        try:
            async with AsyncSessionLocal() as db:
                count = await _service.sync_property(profile.tenant_id, db)
                logger.info(
                    "Weather sync OK — tenant=%s rows=%d", profile.tenant_id, count
                )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Weather sync FAILED — tenant=%s error=%s",
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

    logger.info("Weather sync job finished")


def create_weather_scheduler() -> AsyncIOScheduler:
    """Build and return a configured AsyncIOScheduler.

    The scheduler is NOT started here — call scheduler.start() in the
    FastAPI startup event to bind it to the running event loop.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_weather_sync_all_tenants,
        trigger=CronTrigger(hour="0,12", minute=0, timezone="UTC"),
        id="weather_sync",
        name="Weather Forecast Sync (12h)",
        replace_existing=True,
        misfire_grace_time=300,  # 5-minute grace window
    )
    return scheduler

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

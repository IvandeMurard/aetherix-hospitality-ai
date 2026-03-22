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
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select

from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
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

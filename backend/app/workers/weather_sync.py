"""APScheduler 12-hour background worker for weather forecast ingestion.

Story 3.1: Ingest Localized Weather Data (HOS-83).

The job is registered on the application-level scheduler (main.py lifespan) via
`start_weather_scheduler(scheduler)` — no separate AsyncIOScheduler is created here.

Schedule: every 12 hours (interval trigger).
Behaviour:
- Queries all active restaurant profiles that have GPS coordinates configured.
- Calls WeatherIngestionService.sync_for_tenant() for each in sequence.
- Failures for one tenant are caught and logged; other tenants are not affected.
- On any non-recoverable outer exception: calls dispatch_error() and re-raises.
"""
from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.future import select

from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.services.weather_ingestion import WeatherIngestionService

logger = logging.getLogger(__name__)


async def _run_weather_sync_for_all_tenants() -> None:
    """Iterate every property with GPS coords and sync weather (interval scheduler)."""
    job_id = str(uuid.uuid4())[:8]
    service = WeatherIngestionService()

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
            "weather_sync: started  job_id=%s  properties=%d", job_id, len(profiles)
        )

        for profile in profiles:
            try:
                async with AsyncSessionLocal() as db:
                    rows = await service.sync_for_tenant(db, profile)
                logger.info(
                    "weather_sync: OK  job_id=%s  tenant=%s  new_rows=%d",
                    job_id,
                    profile.tenant_id,
                    rows,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "weather_sync: FAILED  job_id=%s  tenant=%s  error=%s",
                    job_id,
                    profile.tenant_id,
                    exc,
                    exc_info=True,
                )

        logger.info("weather_sync: job finished  job_id=%s", job_id)

    except Exception as exc:
        logger.exception("weather_sync: job failed  job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="weather_sync job failed",
                detail=(
                    f"Unrecoverable error in 12-hour weather sync. "
                    f"job_id={job_id}. Error: {exc!r}"
                ),
                tags=["weather_sync", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("weather_sync: dispatch_error failed: %s", inner)
        raise


def start_weather_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Register the 12-hour weather sync job on the provided scheduler.

    The caller (main.py lifespan) is responsible for starting and stopping
    the scheduler — this function only adds the job.
    """
    scheduler.add_job(
        _run_weather_sync_for_all_tenants,
        trigger=IntervalTrigger(hours=12),
        id="weather_sync_12h",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("weather_sync: job registered (interval=12h)")


def stop_weather_scheduler() -> None:
    """No-op — lifecycle is managed by the application-level scheduler in main.py."""

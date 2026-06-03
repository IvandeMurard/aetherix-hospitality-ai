"""APScheduler background worker for anomaly detection.

Runs AnomalyDetectionService.run_full_scan() every 4 hours (cron: 0 */4 * * *),
then immediately chains ROI calculation (Story 3.3b AC 9) and recommendation
formatting (Story 3.3c AC 6).

Registered on FastAPI startup in main.py alongside weather/event sync jobs.

Architecture constraints:
- Cron job is registered on startup; no state is kept in this module.
- Session is opened per job execution and closed cleanly on exit.
- ROI calculation is chained within the same job execution (AC 9).
- Recommendation formatting is chained after ROI calculation (Story 3.3c AC 6).
- On non-recoverable failure: dispatch_error() is called and exception re-raises.
[Source: story 3.3a Task 4, story 3.3b AC 9, story 3.3c AC 6,
         architecture.md#Infrastructure-Deployment]
"""
from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal
from app.services.anomaly_detection import AnomalyDetectionService
from app.services.recommendation_formatter import RecommendationFormatterService
from app.services.roi_calculator import ROICalculatorService

logger = logging.getLogger(__name__)

_service = AnomalyDetectionService()
_roi_service = ROICalculatorService()
_formatter_service = RecommendationFormatterService()


async def _run_anomaly_scan_job() -> None:
    """Entry point called by APScheduler every 4 hours.

    Phase 1 — Anomaly detection scan.
    Phase 2 — ROI calculation chain (AC 9: auto-chain after each scan cycle).
    Phase 3 — Recommendation formatting chain (Story 3.3c AC 6).
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info("anomaly_scan: started  job_id=%s", job_id)

    try:
        async with AsyncSessionLocal() as db:
            await _service.run_full_scan(db)
        logger.info("anomaly_scan: scan complete  job_id=%s", job_id)

        logger.info("roi_calculator: starting post-scan chain  job_id=%s", job_id)
        async with AsyncSessionLocal() as db:
            await _roi_service.run_full_scan(db)
        logger.info("roi_calculator: chain complete  job_id=%s", job_id)

        logger.info(
            "recommendation_formatter: starting post-ROI chain  job_id=%s", job_id
        )
        async with AsyncSessionLocal() as db:
            created = await _formatter_service.run_full_scan(db)
        logger.info(
            "recommendation_formatter: chain complete  job_id=%s  created=%d",
            job_id,
            created,
        )

    except Exception as exc:
        logger.exception("anomaly_scan: job failed  job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="anomaly_scan job failed",
                detail=(
                    f"Unrecoverable error in 4-hour anomaly scan chain. "
                    f"job_id={job_id}. Error: {exc!r}"
                ),
                tags=["anomaly_scan", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("anomaly_scan: dispatch_error failed: %s", inner)
        raise


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

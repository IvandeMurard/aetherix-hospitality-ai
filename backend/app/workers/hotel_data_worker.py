"""Hotel data requests worker — HOS-349 (Décisions #43, #44).

Every 15 minutes: expire confirmation codes nobody used, then execute the
deletions the owner confirmed whose 24 h delay has passed. Nothing runs that
an owner did not confirm on WhatsApp.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_hotel_data_pass() -> None:
    from app.services import hotel_data_requests as hdr

    try:
        async with AsyncSessionLocal() as db:
            expired = await hdr.expire_stale(db)
            reports = await hdr.run_due_deletions(db)
        if expired or reports:
            logger.info("hotel_data_worker: %d expired, %d deletions executed", expired, len(reports))
    except Exception:  # noqa: BLE001 — a failed pass retries at the next tick
        logger.exception("hotel_data_worker: pass failed")


def register_hotel_data_job(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_hotel_data_pass,
        trigger="interval",
        minutes=15,
        id="hotel_data_requests",
        replace_existing=True,
        misfire_grace_time=900,
    )

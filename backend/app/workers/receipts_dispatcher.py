"""Phase 2 — Daily Receipt dispatcher + Weekly KPI digest (P2-3 + P2-5).

APScheduler cron job that fires daily at RECEIPT_DISPATCH_HOUR (default 18:00)
in RECEIPT_TIMEZONE (default UTC). For each active hotel with a phone number:

  1. Builds ReceiptPayload via ReceiptsService.daily_receipt (P2-1 + P2-2).
  2. Composes OQ4-tone narrative via ReceiptsService.compose_narrative (P2-3).
  3. Sends WhatsApp via TwilioClient.
  4. Sends email via SendGridClient when SENDGRID_API_KEY is configured (opt-in).

Opt-out: hotels with is_active=False are skipped. A dedicated receipts_opted_out
column will be added in a future migration; for Phase 2 Sandbox is_active suffices.

Spec: docs/planning/phase-2-agent-receipts.md §4 P2-3
PM-locked tone decisions: CLAUDE.md Decision #15 OQ4
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core import config
from app.core.pii import pseudonymise
from app.core.exceptions import NotConfiguredError
from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient
from app.services.receipts import ReceiptsService
from app.workers.heartbeat import (
    JOB_RECEIPT_DISPATCHER,
    JOB_WEEKLY_DIGEST,
    REASON_PARTIAL,  # noqa: F401 — re-exported: tests and call sites assert against it
    evaluate_partial,
    record_heartbeat,
    record_trip,
)

logger = logging.getLogger(__name__)

_twilio = TwilioClient()
_sendgrid = SendGridClient()


async def _send_to_channels(
    hotel: RestaurantProfile,
    subject: str,
    narrative: str,
    *,
    log_ctx: str,
) -> None:
    """Send a composed narrative to a hotel's WhatsApp + email channels (HOS-272).

    WhatsApp is the required channel (OQ1); email is opt-in — sent only when the
    hotel has a notification_email. Each channel is independently guarded so one
    failing never blocks the other, and NotConfiguredError is downgraded to a log
    line (expected in envs without Twilio/SendGrid). Shared by the daily Receipt
    and weekly digest dispatchers — previously copy-pasted 3-except blocks in both.
    """
    hotel_id: str = hotel.tenant_id

    if hotel.phone_number:
        try:
            sid = await _twilio.send_whatsapp(hotel.phone_number, narrative)
            logger.info("%s: WhatsApp sent hotel_id=%s sid=%s", log_ctx, hotel_id, sid)
        except NotConfiguredError:
            logger.warning(
                "%s: Twilio not configured — skipping WhatsApp hotel_id=%s", log_ctx, hotel_id
            )
        except Exception:
            logger.exception("%s: WhatsApp send failed hotel_id=%s", log_ctx, hotel_id)

    if hotel.notification_email:
        try:
            await _sendgrid.send_email(hotel.notification_email, subject, narrative)
            logger.info(
                "%s: email sent hotel_id=%s to=%s",
                log_ctx,
                hotel_id,
                pseudonymise(hotel.notification_email),
            )
        except NotConfiguredError:
            logger.debug(
                "%s: SendGrid not configured — skipping email hotel_id=%s", log_ctx, hotel_id
            )
        except Exception:
            logger.exception("%s: email send failed hotel_id=%s", log_ctx, hotel_id)


async def _run_dispatch_loop(
    job_name: str,
    *,
    log_ctx: str,
    label: str,
    per_hotel: Callable[[ReceiptsService, RestaurantProfile], Awaitable[None]],
) -> None:
    """Shared scaffold for the per-hotel dispatch jobs (P2-3 / P2-5, HOS-272).

    Owns the active-hotel SELECT, the per-hotel loop with dispatched/skipped/failed
    counters, the aggregated partial-failure trip (AC1), the success heartbeat
    (AC2) and the fatal-error handler. Each job supplies only its registry
    ``job_name`` (for heartbeat/trip), a ``log_ctx``/``label`` for messages, and a
    ``per_hotel`` coroutine that builds & sends one hotel's message.

    Note: ``job_name`` is the heartbeat-registry id (e.g. "receipt_dispatcher");
    ``log_ctx`` is the human worker name used in logs + ops alerts (e.g.
    "receipts_dispatcher") — they intentionally differ.
    """
    job_id = str(uuid.uuid4())[:8]
    logger.info("%s: started job_id=%s", log_ctx, job_id)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RestaurantProfile).where(RestaurantProfile.is_active.is_(True))
            )
            hotels = result.scalars().all()

        dispatched = 0
        skipped = 0
        failed = 0
        for hotel in hotels:
            if not hotel.phone_number and not hotel.notification_email:
                skipped += 1
                continue
            async with AsyncSessionLocal() as db:
                service = ReceiptsService(db)
                try:
                    await per_hotel(service, hotel)
                    dispatched += 1
                except Exception:
                    failed += 1
                    logger.exception(
                        "%s: dispatch failed hotel_id=%s job_id=%s",
                        log_ctx,
                        hotel.tenant_id,
                        job_id,
                    )

        logger.info(
            "%s: complete job_id=%s dispatched=%d skipped=%d failed=%d",
            log_ctx,
            job_id,
            dispatched,
            skipped,
            failed,
        )

        # AC1 — per-hotel failures are otherwise silent; trip one aggregated alert.
        breach = evaluate_partial(failed, dispatched)
        if breach:
            reason, detail = breach
            await record_trip(job_name, reason, f"{label}: {detail} job_id={job_id}.")
        # AC2 — heartbeat marks a completed run (even with partial failures, the
        # job itself ran → the dead-man's switch should not trip).
        await record_heartbeat(job_name)

    except Exception as exc:
        logger.exception("%s: fatal error job_id=%s", log_ctx, job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title=f"{log_ctx} job failed",
                detail=f"{label} dispatch failed. job_id={job_id}. Error: {exc!r}",
                tags=[log_ctx, "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("%s: dispatch_error failed: %s", log_ctx, inner)
        raise


async def _dispatch_receipt_for_hotel(
    service: ReceiptsService,
    hotel: RestaurantProfile,
    target_date: date,
) -> None:
    """Build and send one Receipt for a single hotel."""
    hotel_id: str = hotel.tenant_id
    hotel_name: str = hotel.property_name or hotel.outlet_name or hotel_id

    payload = await service.daily_receipt(hotel_id, target_date)

    drill_down_url = (
        f"{config.FRONTEND_BASE_URL.rstrip('/')}"
        f"/receipts/{hotel_id}/{target_date.isoformat()}"
    )
    narrative = await service.compose_narrative(payload, hotel_name, drill_down_url)
    subject = f"Daily Receipt — {hotel_name} — {target_date.isoformat()}"

    await _send_to_channels(hotel, subject, narrative, log_ctx="receipts_dispatcher")


async def _run_receipt_dispatch_job() -> None:
    """Entry point called daily by APScheduler at RECEIPT_DISPATCH_HOUR (P2-3)."""
    target_date = date.today()

    async def _per_hotel(service: ReceiptsService, hotel: RestaurantProfile) -> None:
        await _dispatch_receipt_for_hotel(service, hotel, target_date)

    await _run_dispatch_loop(
        JOB_RECEIPT_DISPATCHER,
        log_ctx="receipts_dispatcher",
        label="Daily Receipt",
        per_hotel=_per_hotel,
    )


def register_receipt_dispatch_job(scheduler: AsyncIOScheduler) -> None:
    """Register the daily Receipt dispatch cron job on the shared scheduler.

    Fires at RECEIPT_DISPATCH_HOUR (default 18) in RECEIPT_TIMEZONE (default UTC).
    """
    scheduler.add_job(
        _run_receipt_dispatch_job,
        trigger="cron",
        hour=config.RECEIPT_DISPATCH_HOUR,
        minute=0,
        timezone=config.RECEIPT_TIMEZONE,
        id="receipt_dispatcher",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(
        "receipts_dispatcher: cron job registered (daily at %02d:00 %s)",
        config.RECEIPT_DISPATCH_HOUR,
        config.RECEIPT_TIMEZONE,
    )


async def _dispatch_weekly_digest_for_hotel(
    service: ReceiptsService,
    hotel: RestaurantProfile,
    week_end: date,
) -> None:
    """Build and send one weekly KPI digest for a single hotel (P2-5)."""
    hotel_id: str = hotel.tenant_id
    hotel_name: str = hotel.property_name or hotel.outlet_name or hotel_id

    payload = await service.weekly_digest(hotel_id, week_end)
    narrative = await service.compose_weekly_narrative(payload, hotel_name)
    subject = f"Weekly Digest — {hotel_name} — week of {payload.week_start}"

    await _send_to_channels(hotel, subject, narrative, log_ctx="weekly_digest")


async def _run_weekly_digest_job() -> None:
    """Entry point called every Sunday by APScheduler at RECEIPT_DISPATCH_HOUR (P2-5)."""
    week_end = date.today()

    async def _per_hotel(service: ReceiptsService, hotel: RestaurantProfile) -> None:
        await _dispatch_weekly_digest_for_hotel(service, hotel, week_end)

    await _run_dispatch_loop(
        JOB_WEEKLY_DIGEST,
        log_ctx="weekly_digest",
        label="Weekly Digest",
        per_hotel=_per_hotel,
    )


def register_weekly_digest_job(scheduler: AsyncIOScheduler) -> None:
    """Register the Sunday weekly KPI digest cron job on the shared scheduler (P2-5).

    Fires every Sunday at RECEIPT_DISPATCH_HOUR in RECEIPT_TIMEZONE.
    """
    scheduler.add_job(
        _run_weekly_digest_job,
        trigger="cron",
        day_of_week="sun",
        hour=config.RECEIPT_DISPATCH_HOUR,
        minute=0,
        timezone=config.RECEIPT_TIMEZONE,
        id="weekly_digest",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info(
        "weekly_digest: cron job registered (every Sunday at %02d:00 %s)",
        config.RECEIPT_DISPATCH_HOUR,
        config.RECEIPT_TIMEZONE,
    )

"""Phase 2 — Daily Receipt dispatcher (P2-3, HOS-169).

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
from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core import config
from app.core.exceptions import NotConfiguredError
from app.db.models import RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient
from app.services.receipts import ReceiptsService

logger = logging.getLogger(__name__)

_twilio = TwilioClient()
_sendgrid = SendGridClient()


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

    # WhatsApp — required channel (OQ1)
    if hotel.phone_number:
        try:
            sid = await _twilio.send_whatsapp(hotel.phone_number, narrative)
            logger.info(
                "receipts_dispatcher: WhatsApp sent hotel_id=%s date=%s sid=%s",
                hotel_id,
                target_date,
                sid,
            )
        except NotConfiguredError:
            logger.warning(
                "receipts_dispatcher: Twilio not configured — skipping WhatsApp hotel_id=%s",
                hotel_id,
            )
        except Exception:
            logger.exception(
                "receipts_dispatcher: WhatsApp send failed hotel_id=%s date=%s",
                hotel_id,
                target_date,
            )

    # Email — opt-in (OQ1): only when hotel has notification_email + SendGrid configured
    if hotel.notification_email:
        subject = f"Daily Receipt — {hotel_name} — {target_date.isoformat()}"
        try:
            await _sendgrid.send_email(hotel.notification_email, subject, narrative)
            logger.info(
                "receipts_dispatcher: email sent hotel_id=%s date=%s to=%s",
                hotel_id,
                target_date,
                hotel.notification_email,
            )
        except NotConfiguredError:
            logger.debug(
                "receipts_dispatcher: SendGrid not configured — skipping email hotel_id=%s",
                hotel_id,
            )
        except Exception:
            logger.exception(
                "receipts_dispatcher: email send failed hotel_id=%s date=%s",
                hotel_id,
                target_date,
            )


async def _run_receipt_dispatch_job() -> None:
    """Entry point called daily by APScheduler at RECEIPT_DISPATCH_HOUR."""
    job_id = str(uuid.uuid4())[:8]
    target_date = date.today()
    logger.info(
        "receipts_dispatcher: started job_id=%s date=%s", job_id, target_date
    )

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RestaurantProfile).where(RestaurantProfile.is_active.is_(True))
            )
            hotels = result.scalars().all()

        dispatched = 0
        skipped = 0
        for hotel in hotels:
            if not hotel.phone_number and not hotel.notification_email:
                skipped += 1
                continue
            async with AsyncSessionLocal() as db:
                service = ReceiptsService(db)
                try:
                    await _dispatch_receipt_for_hotel(service, hotel, target_date)
                    dispatched += 1
                except Exception:
                    logger.exception(
                        "receipts_dispatcher: dispatch failed hotel_id=%s job_id=%s",
                        hotel.tenant_id,
                        job_id,
                    )

        logger.info(
            "receipts_dispatcher: complete job_id=%s dispatched=%d skipped=%d",
            job_id,
            dispatched,
            skipped,
        )

    except Exception as exc:
        logger.exception("receipts_dispatcher: fatal error job_id=%s", job_id)
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="receipts_dispatcher job failed",
                detail=(
                    f"Daily Receipt dispatch failed. "
                    f"job_id={job_id}. Error: {exc!r}"
                ),
                tags=["receipts_dispatcher", "worker"],
            )
        except Exception as inner:  # noqa: BLE001
            logger.warning("receipts_dispatcher: dispatch_error failed: %s", inner)
        raise


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

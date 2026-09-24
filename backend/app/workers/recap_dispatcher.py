"""Weekly recap push — opt-in only, WhatsApp 24 h rule respected (ADR-0007 §17.2–17.3).

Every Monday at RECEIPT_DISPATCH_HOUR (RECEIPT_TIMEZONE), for each active
hotel with ``weekly_recap_opt_in = true`` and a phone number, send the
deterministic recap of the previous week (``decision_recap``). No opt-in → no
push: the recap stays available on demand ("recap").

The push is **business-initiated**. WhatsApp refuses a free-form message
outside the 24 h customer-service window, so ``push_mode`` decides:

  * ``template`` — an approved Content template is configured
    (``TWILIO_CONTENT_SID_RECAP_{FR,EN}``, body ``{{1}}`` = the recap text):
    sent any time. Approval is an ops step, pending.
  * ``session``  — no template, but the manager wrote to us less than
    ``SESSION_WINDOW`` minus a safety margin ago: a free-form message is allowed.
  * ``outside_window`` — neither: **not sent**, logged with that typed reason.
    Deferral = the manager's next "recap" (on demand is always a reply, hence
    always inside the window). Nothing is queued to be pushed later.

Recap on demand, confirmations and reason requests are replies to the
manager's own message: always inside the window, no template needed.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select

from app.core import config
from app.core.exceptions import NotConfiguredError
from app.db.models import InboundReplyEvent, RestaurantProfile
from app.db.session import AsyncSessionLocal
from app.integrations.twilio_client import TwilioClient
from app.services.decision_recap import build_recap, period_bounds, render_text

logger = logging.getLogger(__name__)

SESSION_WINDOW = timedelta(hours=24)
# Keep clear of the edge: Twilio's clock and ours may differ, and a send can queue.
SESSION_SAFETY_MARGIN = timedelta(minutes=30)

PushMode = Literal["template", "session", "outside_window", "not_opted_in"]

_twilio = TwilioClient()


def recap_template_sid(locale: Optional[str]) -> str:
    en = (locale or "").lower().startswith("en")
    return config.TWILIO_CONTENT_SID_RECAP_EN if en else config.TWILIO_CONTENT_SID_RECAP_FR


def push_mode(
    opted_in: bool, template_sid: str, last_inbound_at: Optional[datetime], now: datetime
) -> PushMode:
    """Pure rule: may a business-initiated recap be sent now, and how."""
    if not opted_in:
        return "not_opted_in"
    if template_sid:
        return "template"
    if last_inbound_at is not None and now - last_inbound_at < SESSION_WINDOW - SESSION_SAFETY_MARGIN:
        return "session"
    return "outside_window"


async def _last_inbound_at(db, profile: RestaurantProfile) -> Optional[datetime]:
    """Latest reply from the manager (every inbound reply writes one event)."""
    value = (await db.execute(
        select(func.max(InboundReplyEvent.created_at)).where(
            InboundReplyEvent.property_id == uuid.UUID(str(profile.id)),
            InboundReplyEvent.channel.in_(["text", "button"]),
        )
    )).scalar()
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def dispatch_weekly_recap(db, profile: RestaurantProfile, now: datetime) -> PushMode:
    locale = profile.manager_locale or "fr"
    sid = recap_template_sid(locale)
    mode = push_mode(bool(profile.weekly_recap_opt_in), sid,
                     await _last_inbound_at(db, profile), now)
    if mode in ("not_opted_in", "outside_window") or not profile.phone_number:
        logger.info("weekly_recap: not sent hotel_id=%s reason=%s", profile.tenant_id,
                    mode if profile.phone_number else "no_phone_number")
        return mode

    last_week_end = period_bounds("week", now)[0] - timedelta(days=1)
    start = last_week_end - timedelta(days=6)
    summary = await build_recap(db, profile.tenant_id, "week", start=start, end=last_week_end)
    text = render_text(summary, locale)
    try:
        if mode == "template":
            await _twilio.send_whatsapp_content(profile.phone_number, sid, {"1": text})
        else:
            await _twilio.send_whatsapp(profile.phone_number, text)
        logger.info("weekly_recap: sent hotel_id=%s mode=%s", profile.tenant_id, mode)
    except NotConfiguredError:
        logger.warning("weekly_recap: Twilio not configured hotel_id=%s", profile.tenant_id)
    except Exception:
        logger.exception("weekly_recap: send failed hotel_id=%s mode=%s", profile.tenant_id, mode)
    return mode


async def run_weekly_recap_job() -> None:
    now = datetime.now(tz=timezone.utc)
    async with AsyncSessionLocal() as db:
        profiles = (await db.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.is_active.is_(True),
                RestaurantProfile.weekly_recap_opt_in.is_(True),
            )
        )).scalars().all()
        for profile in profiles:
            try:
                await dispatch_weekly_recap(db, profile, now)
            except Exception:  # noqa: BLE001 — one hotel never blocks the others
                logger.exception("weekly_recap: failed hotel_id=%s", profile.tenant_id)


def register_weekly_recap_job(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        run_weekly_recap_job,
        trigger="cron",
        day_of_week="mon",
        hour=config.RECEIPT_DISPATCH_HOUR,
        minute=5,
        timezone=config.RECEIPT_TIMEZONE,
        id="weekly_recap",
        replace_existing=True,
        misfire_grace_time=300,
    )

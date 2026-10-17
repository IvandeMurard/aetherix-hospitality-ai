"""One reminder before the point of no return — HOS-350 (Décisions #6, #43, #44).

On WhatsApp the Aetherix thread sinks under other conversations and the
evening recommendation gets missed. When a dispatched recommendation is still
unanswered N hours before its point of no return (``commit_at``), it gets
**one** reminder, through the hotel's own channel. Then nothing more.

* **At most one.** ``reminder_status`` is set once and never reset: sent, or
  why it was not (already answered, disabled, no compliant channel, failed,
  commit point already passed).
* **The hotel's timing.** N comes from the hotel parameter
  ``reminder_offset_hours.<task_class>``; unset, ``DEFAULT_OFFSET_HOURS``,
  labelled as a default (Décision #43). 0 = no reminder.
* **The hotel's channel, and WhatsApp's rule.** The preferred channel first.
  WhatsApp is used only inside the 24 h customer-service window, or with an
  approved template; otherwise the hotel's next channel (e-mail, then SMS).
  Never a non-compliant send. A hotel with an agent can also read the
  recommendation through MCP (``get_pending_recommendations``).
* **Silence stays silence.** A reminder never records a decision (Décision #6).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import config

logger = logging.getLogger(__name__)

DEFAULT_OFFSET_HOURS = 2.0
STATUSES = ("sent", "skipped_answered", "disabled", "no_compliant_channel", "failed", "missed")

Sender = Callable[[str, object, str, dict], Awaitable[object]]


def reminder_template_sid(locale: Optional[str]) -> str:
    en = (locale or "").lower().startswith("en")
    return config.TWILIO_CONTENT_SID_REMINDER_EN if en else config.TWILIO_CONTENT_SID_REMINDER_FR


@dataclass(frozen=True)
class Offset:
    hours: float
    source: str   # hotel | default


def offset_for(params, task_class: Optional[str]) -> Offset:
    """The hotel's reminder offset for this decision type, else the labelled default."""
    value = params.get(f"reminder_offset_hours.{task_class}") if (params is not None and task_class) else None
    return Offset(float(value), "hotel") if value is not None else Offset(DEFAULT_OFFSET_HOURS, "default")


def due(commit_at: datetime, offset_hours: float, now: datetime) -> bool:
    """Inside [commit_at - offset, commit_at)."""
    return commit_at - timedelta(hours=offset_hours) <= now < commit_at


def channel_plan(profile, *, whatsapp_mode: str) -> list[str]:
    """Channels to try, in order: the hotel's preferred one first, then its
    other usable channels. WhatsApp only when ``whatsapp_mode`` allows it
    (template or session); never otherwise."""
    preferred = (getattr(profile, "preferred_channel", None) or "whatsapp").lower()
    phone = getattr(profile, "phone_number", None)
    email = getattr(profile, "notification_email", None)
    usable = {
        "whatsapp": bool(phone) and whatsapp_mode in ("template", "session"),
        "email": bool(email),
        "sms": bool(phone),
    }
    order = [preferred] + [c for c in ("email", "sms", "whatsapp") if c != preferred]
    return [c for c in order if usable.get(c)]


_TEXT = {
    "fr": ("Rappel Aetherix : la recommandation pour {window} attend votre réponse. Elle reste "
           "modifiable jusqu'à {commit}. Sans réponse, rien n'est fait.\n\n{message}"),
    "en": ("Aetherix reminder: the recommendation for {window} is waiting for your reply. It can be "
           "changed until {commit}. Without a reply, nothing is done.\n\n{message}"),
}


def reminder_text(rec, locale: Optional[str], tz) -> tuple[str, dict]:
    loc = "en" if (locale or "").lower().startswith("en") else "fr"
    window = (rec.window_start.astimezone(tz).strftime("%d/%m %H:%M") if rec.window_start else "")
    commit = _aware(rec.commit_at).astimezone(tz).strftime("%d/%m %H:%M")
    text = _TEXT[loc].format(window=window, commit=commit, message=rec.message_text or "")
    return text, {"1": window, "2": commit}


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def _default_send(channel: str, profile, text: str, template: dict) -> object:
    """Real channels. ``template`` carries {"sid", "variables"} for a WhatsApp template send."""
    from app.integrations.sendgrid_client import SendGridClient
    from app.integrations.twilio_client import TwilioClient

    if channel == "whatsapp":
        client = TwilioClient()
        if template.get("sid"):
            return await client.send_whatsapp_content(profile.phone_number, template["sid"], template["variables"])
        return await client.send_whatsapp(profile.phone_number, text)
    if channel == "sms":
        return await TwilioClient().send_sms(profile.phone_number, text)
    if channel == "email":
        return await SendGridClient().send_email(profile.notification_email, "Aetherix: reminder", text)
    raise ValueError(f"unknown channel {channel}")


async def _answered(db: AsyncSession, rec) -> bool:
    """Any reply about this recommendation since it was sent (even one awaiting
    confirmation) means the manager saw it: no reminder."""
    from app.db.models import InboundReplyEvent

    if rec.status != "dispatched":
        return True
    q = select(InboundReplyEvent.id).where(InboundReplyEvent.recommendation_id == rec.id)
    if rec.dispatched_at is not None:
        q = q.where(InboundReplyEvent.created_at >= rec.dispatched_at)
    return (await db.execute(q.limit(1))).first() is not None


async def run_due(db: AsyncSession, now: Optional[datetime] = None, *, send: Optional[Sender] = None) -> dict:
    """Send the reminders that are due. Commits. Returns counts per status."""
    from app.db.models import RestaurantProfile, StaffingRecommendation as SR
    from app.services import hotel_parameters
    from app.services.decision_recap import _tz
    from app.workers.recap_dispatcher import _last_inbound_at, push_mode

    now = now or datetime.now(timezone.utc)
    send = send or _default_send
    tz = _tz()
    recs = (await db.execute(
        select(SR).where(SR.status == "dispatched", SR.commit_at.is_not(None), SR.reminder_status.is_(None))
    )).scalars().all()
    counts: dict[str, int] = {}
    params_cache: dict[str, object] = {}

    def mark(rec, status: str, channel: Optional[str] = None) -> None:
        rec.reminder_status, rec.reminder_channel = status, channel
        if status == "sent":
            rec.reminder_sent_at = now
        counts[status] = counts.get(status, 0) + 1
        logger.info("reminder: recommendation=%s status=%s channel=%s", rec.id, status, channel)

    for rec in recs:
        commit_at = _aware(rec.commit_at)
        if tenant := rec.tenant_id:
            if tenant not in params_cache:
                try:
                    params_cache[tenant] = await hotel_parameters.load(db, tenant)
                except Exception:  # noqa: BLE001 — unreadable parameters → labelled default
                    params_cache[tenant] = None
        offset = offset_for(params_cache.get(rec.tenant_id), rec.task_class)
        if now >= commit_at:
            mark(rec, "missed")
            continue
        if offset.hours <= 0:
            mark(rec, "disabled")
            continue
        if not due(commit_at, offset.hours, now):
            continue                                        # not yet: try again next tick
        if await _answered(db, rec):
            mark(rec, "skipped_answered")
            continue
        profile = (await db.execute(
            select(RestaurantProfile).where(RestaurantProfile.id == rec.property_id)
        )).scalars().first()
        if profile is None:
            mark(rec, "no_compliant_channel")
            continue
        locale = getattr(profile, "manager_locale", None) or "fr"
        sid = reminder_template_sid(locale)
        mode = push_mode(True, sid, await _last_inbound_at(db, profile), now)
        text, variables = reminder_text(rec, locale, tz)
        plan = channel_plan(profile, whatsapp_mode=mode)
        if not plan:
            mark(rec, "no_compliant_channel")
            continue
        sent_on = None
        for channel in plan:
            template = {"sid": sid, "variables": variables} if (channel == "whatsapp" and mode == "template") else {}
            try:
                await send(channel, profile, text, template)
                sent_on = channel
                break
            except Exception:  # noqa: BLE001 — try the hotel's next channel
                logger.warning("reminder: %s failed for recommendation %s", channel, rec.id)
        mark(rec, "sent" if sent_on else "failed", sent_on)
    await db.commit()
    return counts

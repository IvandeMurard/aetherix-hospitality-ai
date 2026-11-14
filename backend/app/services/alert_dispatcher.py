"""Alert Dispatcher Service — Story 4.2 (HOS-25).

Formats AI staffing recommendations into channel-appropriate messages
and dispatches them to hotel managers via their preferred notification channel.

Lifecycle: ready_to_push → dispatched   (terminal failures: config_error, dispatch_failed)

HOS-369 (16.48) — atomic claim. ``run_pending`` takes a per-row lease with
``UPDATE ... WHERE id=:id AND status='ready_to_push' AND (lease free or
expired)`` and checks the rowcount BEFORE any send, so two workers (several
Fly instances) never send the same alert. The row stays ``ready_to_push`` while
leased: a worker that dies after the claim leaves nothing stuck, the row is
re-claimed once ``CLAIM_LEASE`` has expired. The lease doubles as the retry
back-off. At-least-once, not exactly-once: a crash between the provider
accepting the message and our commit of ``dispatched`` can re-send after the
lease (no provider idempotency key exists). Retries are bounded by
``MAX_DISPATCH_ATTEMPTS``; the row then ends in ``dispatch_failed``.

Channels supported (from restaurant_profiles.preferred_channel):
  - whatsapp  — via TwilioClient.send_whatsapp()
  - sms       — via TwilioClient.send_sms()
  - email     — via SendGridClient.send_email()

Error handling contract:
  - NotConfiguredError  → log WARNING, status config_error (permanent, no retry)
  - Any other exception → logger.exception + guardrail_trip(send_failed), row
    stays ready_to_push and is retried after the lease, up to
    MAX_DISPATCH_ATTEMPTS; then status dispatch_failed + guardrail_trip
    (retries_exhausted) + dispatch_error (Linear/Obsidian, existing router).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotConfiguredError
from app.core.observability import guardrail_trip
from app.db.models import RestaurantProfile, StaffingRecommendation
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient
from app.services.decision_messaging import buttons_available, send_with_buttons

logger = logging.getLogger(__name__)

# HOS-369 — claim lease and retry bound. The lease is also the back-off between
# two attempts on the same row (the worker ticks every 2 minutes).
CLAIM_LEASE = timedelta(minutes=5)
MAX_DISPATCH_ATTEMPTS = 3

DISPATCH_TOOL = "alert_dispatcher"
REASON_SEND_FAILED = "send_failed"
REASON_RETRIES_EXHAUSTED = "retries_exhausted"
REASON_NO_PROFILE = "no_profile"


@dataclass
class DispatchSummary:
    """Counts of one ``run_pending`` pass (NFR2: failures are counted, never silent)."""

    candidates: int = 0
    claimed: int = 0
    dispatched: int = 0
    skipped: int = 0  # claimed but not sent (config_error, missing profile)
    failed: int = 0  # send raised
    exhausted: int = 0  # reached dispatch_failed


def _validate_phone(number: str) -> bool:
    """Return True if number is a non-empty E.164 string (starts with '+', length >= 8)."""
    return bool(number and number.startswith("+") and len(number) >= 8)


def _format_message(rec: StaffingRecommendation) -> str:
    """Build the final dispatch message from recommendation fields."""
    parts = [rec.message_text]
    # The formatter already writes "Trigger: <factor>" into the message: the
    # factor is appended only when the message does not already carry it.
    if rec.triggering_factor and rec.triggering_factor not in (rec.message_text or ""):
        parts.append(f"Context: {rec.triggering_factor}")
    return "\n".join(parts)


class AlertDispatcherService:
    """Formats and dispatches staffing alerts to hotel managers."""

    async def dispatch_one(
        self, recommendation: StaffingRecommendation, session: AsyncSession
    ) -> bool:
        """Dispatch a single recommendation to the manager's preferred channel.

        Returns True on successful dispatch, False if skipped (NotConfiguredError
        or missing profile). Raises on unexpected errors; run_pending records the
        failure (log + typed event + bounded retry). Does not claim: callers
        go through run_pending, which holds the lease.
        """
        # Idempotency guard — never re-send already dispatched recommendations
        if recommendation.status == "dispatched":
            logger.debug(
                "Skipping already-dispatched recommendation id=%s", recommendation.id
            )
            return False

        # Fetch the linked restaurant profile to determine channel + contact
        result = await session.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.id == uuid.UUID(str(recommendation.property_id))
            )
        )
        profile: RestaurantProfile | None = result.scalars().first()

        if profile is None:
            logger.error(
                "No restaurant profile for property_id=%s; skipping recommendation id=%s",
                recommendation.property_id,
                recommendation.id,
            )
            return False

        channel = (profile.preferred_channel or "whatsapp").lower()
        message = _format_message(recommendation)

        try:
            await self._send(channel, profile, message)
        except NotConfiguredError as exc:
            logger.warning(
                "Channel %r not configured for property %s (recommendation id=%s): %s",
                channel,
                recommendation.property_id,
                recommendation.id,
                exc,
            )
            recommendation.status = "config_error"
            await session.commit()
            return False
        except Exception:
            logger.exception(
                "Unexpected error dispatching recommendation id=%s via channel %r",
                recommendation.id,
                channel,
            )
            raise  # run_pending counts it, emits the typed event and retries (bounded)

        # Mark as dispatched
        recommendation.status = "dispatched"
        recommendation.dispatched_at = datetime.now(tz=timezone.utc)
        recommendation.dispatch_channel = channel
        await session.commit()

        logger.info(
            "Recommendation id=%s dispatched via %s for property %s",
            recommendation.id,
            channel,
            recommendation.property_id,
        )
        return True

    @staticmethod
    async def _claim(session: AsyncSession, rec_id, now: datetime) -> bool:
        """Atomically take the lease on one ready_to_push row (HOS-369 AC1).

        One conditional UPDATE: only the worker whose UPDATE matches the row
        (rowcount == 1) may send. Portable to Postgres and SQLite.
        """
        result = await session.execute(
            update(StaffingRecommendation)
            .where(
                StaffingRecommendation.id == rec_id,
                StaffingRecommendation.status == "ready_to_push",
                StaffingRecommendation.dispatch_attempts < MAX_DISPATCH_ATTEMPTS,
                or_(
                    StaffingRecommendation.dispatch_claimed_at.is_(None),
                    StaffingRecommendation.dispatch_claimed_at < now - CLAIM_LEASE,
                ),
            )
            .values(
                dispatch_claimed_at=now,
                dispatch_attempts=StaffingRecommendation.dispatch_attempts + 1,
            )
            .execution_options(synchronize_session=False)
        )
        await session.commit()  # publish the claim before sending
        return result.rowcount == 1

    @staticmethod
    async def _mark_failed(
        session: AsyncSession, rec_id, tenant_id: str, reason_detail: str
    ) -> None:
        """Terminal dispatch_failed (retry bound reached) + typed event + ops alert."""
        result = await session.execute(
            update(StaffingRecommendation)
            .where(
                StaffingRecommendation.id == rec_id,
                StaffingRecommendation.status == "ready_to_push",
            )
            .values(status="dispatch_failed")
            .execution_options(synchronize_session=False)
        )
        await session.commit()
        if result.rowcount != 1:
            return
        logger.error(
            "Recommendation id=%s ended dispatch_failed after %d attempts: %s",
            rec_id, MAX_DISPATCH_ATTEMPTS, reason_detail,
        )
        guardrail_trip(
            DISPATCH_TOOL, tenant_id, REASON_RETRIES_EXHAUSTED,
            f"recommendation={rec_id} attempts={MAX_DISPATCH_ATTEMPTS} last={reason_detail}",
        )
        try:
            from app.services.ops_dispatcher import dispatch_error

            await dispatch_error(
                title="Alert dispatch failed permanently",
                detail=(
                    f"Recommendation {rec_id} (tenant {tenant_id}) could not be sent after "
                    f"{MAX_DISPATCH_ATTEMPTS} attempts and is now dispatch_failed. "
                    f"Last error: {reason_detail}"
                ),
                tags=["alert_dispatcher", "dispatch_failed"],
            )
        except Exception:  # noqa: BLE001 - alerting must never break the loop
            logger.warning("alert_dispatcher: dispatch_error failed", exc_info=True)

    async def run_pending(self, session: AsyncSession) -> DispatchSummary:
        """Claim ready_to_push recommendations one by one, then send each.

        Sequential (one session, one send at a time), safe across workers
        because each row is claimed atomically before any send (HOS-369).
        """
        summary = DispatchSummary()
        result = await session.execute(
            select(StaffingRecommendation.id).where(
                StaffingRecommendation.status == "ready_to_push"
                # config_error / dispatch_failed are excluded — permanent problems
                # that must not be retried automatically
            )
        )
        pending_ids = list(result.scalars().all())
        summary.candidates = len(pending_ids)

        if not pending_ids:
            logger.debug("No pending recommendations to dispatch.")
            return summary

        logger.info("Found %d pending recommendation(s).", len(pending_ids))
        now = datetime.now(tz=timezone.utc)

        for rec_id in pending_ids:
            if not await self._claim(session, rec_id, now):
                continue  # another worker holds the lease, or retries exhausted
            summary.claimed += 1
            rec = (
                await session.execute(
                    select(StaffingRecommendation)
                    .where(StaffingRecommendation.id == rec_id)
                    .execution_options(populate_existing=True)
                )
            ).scalars().first()
            if rec is None:
                continue
            tenant_id = str(rec.tenant_id or "")
            attempts = int(rec.dispatch_attempts or 0)  # read now: rollback expires attributes
            try:
                sent = await self.dispatch_one(rec, session)
            except Exception as exc:  # noqa: BLE001 - recorded below, never swallowed
                await session.rollback()
                summary.failed += 1
                logger.exception(
                    "Dispatch failed for recommendation id=%s (attempt %s/%s)",
                    rec_id, attempts, MAX_DISPATCH_ATTEMPTS,
                )
                guardrail_trip(
                    DISPATCH_TOOL, tenant_id, REASON_SEND_FAILED,
                    f"recommendation={rec_id} attempt={attempts} error={exc!r}",
                )
                if attempts >= MAX_DISPATCH_ATTEMPTS:
                    await self._mark_failed(session, rec_id, tenant_id, repr(exc))
                    summary.exhausted += 1
                continue
            rec_status = rec.status
            if sent:
                summary.dispatched += 1
            else:
                summary.skipped += 1
                if rec_status == "ready_to_push":  # missing profile: counts as an attempt
                    guardrail_trip(
                        DISPATCH_TOOL, tenant_id, REASON_NO_PROFILE,
                        f"recommendation={rec_id} attempt={attempts}",
                    )
                    if attempts >= MAX_DISPATCH_ATTEMPTS:
                        await self._mark_failed(session, rec_id, tenant_id, REASON_NO_PROFILE)
                        summary.exhausted += 1

        logger.info(
            "Dispatch pass: candidates=%d claimed=%d dispatched=%d skipped=%d failed=%d exhausted=%d",
            summary.candidates, summary.claimed, summary.dispatched,
            summary.skipped, summary.failed, summary.exhausted,
        )
        return summary

    # ------------------------------------------------------------------
    # Private channel routing
    # ------------------------------------------------------------------

    @staticmethod
    async def _send_whatsapp_decision(client: TwilioClient, to: str, message: str) -> None:
        """Décision #38 (ADR-0007 §16.4): attach the Accepter / Refuser / Corriger
        quick replies when ``WHATSAPP_DECISION_BUTTONS`` is on and the approved
        template SID is set; otherwise (or if the Content send fails) send the
        text as before. The text path is unchanged when the flag is off."""
        if buttons_available("decision"):
            await send_with_buttons(client, to, message, "decision")
        else:
            await client.send_whatsapp(to=to, body=message)

    async def _send(
        self, channel: str, profile: RestaurantProfile, message: str
    ) -> None:
        if channel == "whatsapp":
            to = profile.phone_number or ""
            if not _validate_phone(to):
                raise NotConfiguredError(
                    f"Invalid or missing phone_number for profile {profile.id}"
                )
            client = TwilioClient()
            await self._send_whatsapp_decision(client, to, message)

        elif channel == "sms":
            to = profile.phone_number or ""
            if not _validate_phone(to):
                raise NotConfiguredError(
                    f"Invalid or missing phone_number for profile {profile.id}"
                )
            client = TwilioClient()
            await client.send_sms(to=to, body=message)

        elif channel == "email":
            client = SendGridClient()
            to = profile.notification_email or ""
            subject = "Aetherix Staffing Alert"
            await client.send_email(to=to, subject=subject, body=message)

        else:
            logger.warning(
                "Unknown notification channel %r — falling back to WhatsApp.", channel
            )
            to = profile.phone_number or ""
            if not _validate_phone(to):
                raise NotConfiguredError(
                    f"Invalid or missing phone_number for profile {profile.id}"
                )
            client = TwilioClient()
            await client.send_whatsapp(to=to, body=message)

"""Alert Dispatcher Service — Story 4.2 (HOS-25).

Formats AI staffing recommendations into channel-appropriate messages
and dispatches them to hotel managers via their preferred notification channel.

Lifecycle: ready_to_push → dispatched

Channels supported (from restaurant_profiles.preferred_channel):
  - whatsapp  — via TwilioClient.send_whatsapp()
  - sms       — via TwilioClient.send_sms()
  - email     — via SendGridClient.send_email()

Error handling contract:
  - NotConfiguredError  → log WARNING, skip recommendation (no status change)
  - Any other exception → log ERROR, leave status as ready_to_push for retry
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotConfiguredError
from app.db.models import RestaurantProfile, StaffingRecommendation
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient

logger = logging.getLogger(__name__)


def _format_message(rec: StaffingRecommendation) -> str:
    """Build the final dispatch message from recommendation fields."""
    parts = [rec.message_text]
    if rec.triggering_factor:
        parts.append(f"Context: {rec.triggering_factor}")
    return "\n".join(parts)


class AlertDispatcherService:
    """Formats and dispatches staffing alerts to hotel managers."""

    async def dispatch_one(
        self, recommendation: StaffingRecommendation, session: AsyncSession
    ) -> bool:
        """Dispatch a single recommendation to the manager's preferred channel.

        Returns True on successful dispatch, False if skipped (NotConfiguredError
        or missing profile). Raises on unexpected errors so run_pending can
        leave status unchanged.
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
                RestaurantProfile.tenant_id == str(recommendation.property_id)
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
            return False
        except Exception:
            logger.exception(
                "Unexpected error dispatching recommendation id=%s via channel %r",
                recommendation.id,
                channel,
            )
            raise  # re-raise so run_pending can leave status unchanged

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

    async def run_pending(self, session: AsyncSession) -> None:
        """Fetch all ready_to_push recommendations and dispatch in parallel."""
        result = await session.execute(
            select(StaffingRecommendation).where(
                StaffingRecommendation.status == "ready_to_push"
            )
        )
        pending = result.scalars().all()

        if not pending:
            logger.debug("No pending recommendations to dispatch.")
            return

        logger.info("Dispatching %d pending recommendation(s).", len(pending))

        async def _safe_dispatch(rec: StaffingRecommendation) -> None:
            try:
                await self.dispatch_one(rec, session)
            except Exception:
                # dispatch_one already logged the error; leave status unchanged
                pass

        await asyncio.gather(*[_safe_dispatch(rec) for rec in pending])

    # ------------------------------------------------------------------
    # Private channel routing
    # ------------------------------------------------------------------

    async def _send(
        self, channel: str, profile: RestaurantProfile, message: str
    ) -> None:
        if channel == "whatsapp":
            client = TwilioClient()
            to = profile.phone_number or ""
            await client.send_whatsapp(to=to, body=message)

        elif channel == "sms":
            client = TwilioClient()
            to = profile.phone_number or ""
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
            client = TwilioClient()
            to = profile.phone_number or ""
            await client.send_whatsapp(to=to, body=message)

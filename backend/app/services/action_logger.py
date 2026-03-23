"""Action Logger Service — Story 4.3 (HOS-26).

Parses Accept/Reject replies from F&B managers received via Twilio SMS/WhatsApp
and persists the decision against the most recent dispatched
StaffingRecommendation linked to the manager's phone number.

Lookup chain:
  inbound phone number
    → RestaurantProfile (phone_number column)
    → StaffingRecommendation (property_id = profile.tenant_id, status = dispatched)

Status lifecycle transition recorded here:
  dispatched → accepted | rejected
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RestaurantProfile, StaffingRecommendation
from app.schemas.webhook import ActionType

logger = logging.getLogger(__name__)


def parse_action(body: str) -> ActionType:
    """Case-insensitive parse of an inbound message body.

    Args:
        body: Raw text sent by the manager (may have leading/trailing whitespace).

    Returns:
        ``ActionType.accept`` if the trimmed body is "accept" (any case),
        ``ActionType.reject`` if it is "reject" (any case),
        ``ActionType.unknown`` otherwise.
    """
    normalised = body.strip().lower()
    if normalised == "accept":
        return ActionType.accept
    if normalised == "reject":
        return ActionType.reject
    return ActionType.unknown


class ActionLoggerService:
    """Records manager Accept/Reject decisions against StaffingRecommendations.

    All DB operations are async and use an SQLAlchemy ``AsyncSession`` passed
    in from the route layer (no session creation here — follows the thin-route
    / fat-service pattern mandated by the project architecture).
    """

    async def log_action(
        self,
        from_number: str,
        action: ActionType,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """Find the most recent dispatched recommendation and record the decision.

        Args:
            from_number: Manager's phone number as received from Twilio
                         (E.164 or ``whatsapp:+<number>`` prefix form).
            action:      Parsed ``ActionType`` — must be accept or reject.
            session:     Open async SQLAlchemy session (provided by FastAPI DI).

        Returns:
            ``{"status": "logged", "recommendation_id": <uuid>, "action": <str>}``
            on success, or ``{"status": "not_found"}`` when no profile /
            dispatched recommendation is matched.
        """
        # Strip WhatsApp prefix so we match both SMS and WA-origin numbers
        normalised_number = from_number.replace("whatsapp:", "")

        # 1. Resolve property from the manager's phone number
        profile_result = await session.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.phone_number == normalised_number
            )
        )
        profile: RestaurantProfile | None = profile_result.scalars().first()

        if profile is None:
            logger.warning(
                "action_logger: no profile found for phone_number=%s", from_number
            )
            return {"status": "not_found"}

        # 2. Find the most recent dispatched recommendation for this property.
        #    The dispatcher stores property_id as UUID; tenant_id on the profile
        #    is a plain string — we cast when comparing (mirrors alert_dispatcher.py).
        rec_result = await session.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == profile.id,
                StaffingRecommendation.status == "dispatched",
            )
            .order_by(
                StaffingRecommendation.dispatched_at.desc().nullslast(),
                StaffingRecommendation.created_at.desc(),
            )
            .limit(1)
        )
        recommendation: StaffingRecommendation | None = rec_result.scalars().first()

        if recommendation is None:
            logger.info(
                "action_logger: no dispatched recommendation for profile id=%s", profile.id
            )
            return {"status": "not_found"}

        # 3. Persist the decision
        new_status = "accepted" if action == ActionType.accept else "rejected"
        recommendation.status = new_status
        recommendation.action = new_status
        recommendation.actioned_at = datetime.now(tz=timezone.utc)

        await session.commit()

        logger.info(
            "action_logger: recommendation id=%s %s (profile id=%s)",
            recommendation.id,
            new_status,
            profile.id,
        )
        return {
            "status": "logged",
            "recommendation_id": str(recommendation.id),
            "action": new_status,
        }

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
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pii import pseudonymise
from app.db.models import RestaurantProfile, StaffingRecommendation
from app.schemas.webhook import ActionType
from app.services.manager_decision import DecisionSource, match_keyword
from app.services.decision_policy import authorize_decision
from app.services.decision_provenance import DecidedBy

logger = logging.getLogger(__name__)


def parse_action(body: str) -> ActionType:
    """Is the whole reply a lexicon reply (ADR-0007 §16.3, §19)?

    Delegates to ``manager_decision.match_keyword``. The label is coarse and
    proposal-independent (``KeywordMatch.summary``): the decision itself is
    derived later from the stance and what the recommendation proposed. A bare
    acknowledgement ("ok", "👍") is ``unknown`` here: it carries no decision and
    is resolved by rule (b) downstream.
    """
    match = match_keyword(body)
    if match is None or match.kind == "bare_ack":
        return ActionType.unknown
    return ActionType(match.summary())


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
        source: DecisionSource = DecisionSource.keyword,
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
                "action_logger: no profile found for phone_number=%s",
                pseudonymise(from_number),
            )
            return {"status": "not_found"}

        # 2. Find the most recent dispatched recommendation for this property.
        #    profile.id is a String column; cast explicitly to uuid.UUID so the
        #    comparison is type-safe against StaffingRecommendation.property_id
        #    (UUID column).  HOS-164.
        rec_result = await session.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == uuid.UUID(str(profile.id)),
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
        recommendation.decision_source = source.value
        recommendation.decision_confidence = 1.0
        recommendation.decided_by = DecidedBy.human_whatsapp.value
        recommendation.decision_policy_version = authorize_decision(
            profile.tenant_id, DecidedBy.human_whatsapp.value
        ).version

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

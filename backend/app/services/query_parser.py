"""Query Parser Service — Story 5.1 (HOS-28).

Routes non-action inbound messages (natural language queries like "Why?" or
"Explain this") to the AI reasoning engine by:
1. Resolving tenant_id and property_id from the sender's phone number.
2. Finding the most recent dispatched StaffingRecommendation for that property.
3. Persisting a ConversationalQuery row (idempotency: 60 s dedup window).

Called as a FastAPI BackgroundTask so the Twilio webhook can return a TwiML
acknowledgement within Twilio's 15 s deadline.

Lookup chain (mirrors ActionLoggerService):
  inbound phone number
    → RestaurantProfile.phone_number
    → StaffingRecommendation (most recent dispatched | accepted | rejected)
    → ConversationalQuery (persisted for downstream AI answering)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationalQuery, RestaurantProfile, StaffingRecommendation

logger = logging.getLogger(__name__)

# Idempotency window: duplicate (from_number, body) within this period is ignored.
_DEDUP_WINDOW_SECONDS = 60


class QueryParserService:
    """Identifies the tenant context for an inbound query and stores it for AI processing.

    All DB operations are async; the caller is responsible for providing an open
    ``AsyncSession`` (thin-route / fat-service pattern).
    """

    async def parse_and_store(
        self,
        from_number: str,
        body: str,
        session: AsyncSession,
    ) -> dict:
        """Parse an inbound conversational query and persist it.

        Args:
            from_number: Manager's phone number as received from Twilio
                         (E.164 or ``whatsapp:+<number>`` prefix form).
            body:        Raw message text from the manager.
            session:     Open async SQLAlchemy session.

        Returns:
            ``{"status": "stored", "query_id": <uuid>}`` on success.
            ``{"status": "not_found"}``  when no matching property is found.
            ``{"status": "duplicate"}``  when idempotency check fires.
        """
        normalised_number = from_number.replace("whatsapp:", "")

        # -----------------------------------------------------------------------
        # 1. Idempotency check — same message from same number within 60 s
        # -----------------------------------------------------------------------
        cutoff = datetime.now(tz=timezone.utc) - timedelta(seconds=_DEDUP_WINDOW_SECONDS)
        dedup_result = await session.execute(
            select(ConversationalQuery)
            .where(
                ConversationalQuery.from_number == normalised_number,
                ConversationalQuery.body == body,
                ConversationalQuery.created_at >= cutoff,
            )
            .limit(1)
        )
        existing = dedup_result.scalars().first()
        if existing is not None:
            logger.info(
                "query_parser: duplicate query suppressed from=%s body=%r (existing id=%s)",
                from_number,
                body,
                existing.id,
            )
            return {"status": "duplicate", "query_id": str(existing.id)}

        # -----------------------------------------------------------------------
        # 2. Resolve property from the manager's phone number
        # -----------------------------------------------------------------------
        profile_result = await session.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.phone_number == normalised_number
            )
        )
        profile: RestaurantProfile | None = profile_result.scalars().first()

        if profile is None:
            logger.warning(
                "query_parser: no profile found for phone_number=%s", from_number
            )
            return {"status": "not_found"}

        # -----------------------------------------------------------------------
        # 3. Find the most recent recommendation for this property
        #    (any actionable status — the manager may be asking about an already
        #    accepted/rejected one)
        # -----------------------------------------------------------------------
        rec_result = await session.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == profile.id,
                StaffingRecommendation.status.in_(
                    ["dispatched", "accepted", "rejected"]
                ),
            )
            .order_by(
                StaffingRecommendation.dispatched_at.desc().nullslast(),
                StaffingRecommendation.created_at.desc(),
            )
            .limit(1)
        )
        recommendation: StaffingRecommendation | None = rec_result.scalars().first()

        if recommendation is None:
            logger.warning(
                "query_parser: no recommendation found for profile id=%s phone=%s",
                profile.id,
                from_number,
            )
            # Still store the query — AC#5 polite response handled in the route
            recommendation_id = None
        else:
            recommendation_id = recommendation.id

        # -----------------------------------------------------------------------
        # 4. Persist the ConversationalQuery row
        # -----------------------------------------------------------------------
        query = ConversationalQuery(
            tenant_id=profile.tenant_id if _is_uuid(str(profile.tenant_id)) else None,
            property_id=profile.id,
            from_number=normalised_number,
            body=body,
            recommendation_id=recommendation_id,
            status="pending",
        )
        session.add(query)
        await session.commit()
        await session.refresh(query)

        logger.info(
            "query_parser: stored query id=%s tenant_id=%s recommendation_id=%s",
            query.id,
            query.tenant_id,
            query.recommendation_id,
        )
        return {
            "status": "stored",
            "query_id": str(query.id),
            "recommendation_id": str(recommendation_id) if recommendation_id else None,
        }


def _is_uuid(value: str) -> bool:
    """Return True if *value* is a valid UUID string."""
    import uuid as _uuid
    try:
        _uuid.UUID(value)
        return True
    except ValueError:
        return False

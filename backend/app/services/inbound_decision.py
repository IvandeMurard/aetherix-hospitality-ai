"""Inbound decision capture — DB side of ADR-0007 §16 (Décision #38).

Turns one manager reply into (a) at most one recorded decision on a
``StaffingRecommendation``, (b) at most one pending prompt (confirmation or
optional reason), (c) exactly one ``InboundReplyEvent`` row plus a structured
log line. The rules themselves live in ``manager_decision`` (pure).

Order in which a reply is read (first match wins):

1. quick-reply button payload (fixed IDs, no model);
2. answer to a pending confirmation ("oui" / "non" / buttons);
3. exact keyword (``match_keyword``): explicit → record, ambiguous → confirm,
   bare acknowledgement → rule (b);
4. answer to a pending reason request (never changes the decision);
5. free text: covers regex, then the model (``ReceiptsService.parse_inbound``),
   then ``resolve_feedback`` (threshold → record or confirm).

Steps 1-3 need no model and run synchronously in the webhook. Steps 4-5 run in
the background task. Nothing here reads ``actual_covers`` (§16.6).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    InboundReplyEvent,
    ManagerPrompt,
    RestaurantProfile,
    StaffingRecommendation,
)
from app.services.receipts import FeedbackIntent, resolve_feedback
from app.services.manager_decision import (
    BUTTON_CONFIRMATIONS,
    BUTTON_DECISIONS,
    CONFIRMED_SOURCE,
    PROMPT_WINDOW,
    CaptureMetrics,
    DecisionSource,
    PendingContext,
    Resolution,
    compute_capture_metrics,
    confirmation_question,
    match_confirmation_answer,
    match_keyword,
    recorded_message,
    resolve_keyword,
    routed_reason,
    text_for,
    wants_reason_prompt,
)

logger = logging.getLogger(__name__)

Buttons = Literal["decision", "confirm"]


@dataclass
class ReplyPlan:
    """What to send back. ``buttons`` names the quick-reply set to attach when
    the feature flag is on; the text alone is always a complete message."""

    text: Optional[str]
    buttons: Optional[Buttons] = None
    result: str = "not_recorded"
    decision: Optional[str] = None
    source: Optional[str] = None
    extras: dict = field(default_factory=dict)


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class InboundDecisionService:
    """Stateless beyond the injected session. ``locale`` defaults to FR (no
    ``locale`` column on ``RestaurantProfile`` yet — same as abstention copy)."""

    def __init__(self, db: AsyncSession, locale: str = "fr") -> None:
        self.db = db
        self.locale = locale

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def profile_for(self, from_number: str) -> Optional[RestaurantProfile]:
        normalised = from_number.replace("whatsapp:", "")
        result = await self.db.execute(
            select(RestaurantProfile).where(RestaurantProfile.phone_number == normalised)
        )
        return result.scalars().first()

    async def pending_recommendations(self, profile: RestaurantProfile) -> list[StaffingRecommendation]:
        result = await self.db.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == uuid.UUID(str(profile.id)),
                StaffingRecommendation.status == "dispatched",
            )
            .order_by(
                StaffingRecommendation.dispatched_at.desc().nullslast(),
                StaffingRecommendation.created_at.desc(),
            )
        )
        return list(result.scalars().all())

    async def latest_recommendation(self, profile: RestaurantProfile) -> Optional[StaffingRecommendation]:
        """Most recent dispatched-or-decided recommendation: the context a reason
        or a free-text note refers to."""
        result = await self.db.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == uuid.UUID(str(profile.id)),
                StaffingRecommendation.status.in_(["dispatched", "accepted", "rejected", "modified"]),
            )
            .order_by(
                StaffingRecommendation.dispatched_at.desc().nullslast(),
                StaffingRecommendation.created_at.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    def pending_context(recs: list[StaffingRecommendation], now: datetime) -> PendingContext:
        latest = _utc(recs[0].dispatched_at) if recs else None
        return PendingContext(pending_count=len(recs), latest_dispatched_at=latest, now=now)

    async def open_prompt(self, profile: RestaurantProfile, now: datetime) -> Optional[ManagerPrompt]:
        await self.expire_stale_prompts(now, property_id=uuid.UUID(str(profile.id)))
        result = await self.db.execute(
            select(ManagerPrompt)
            .where(
                ManagerPrompt.property_id == uuid.UUID(str(profile.id)),
                ManagerPrompt.status == "pending",
            )
            .order_by(ManagerPrompt.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    async def handle_deterministic(
        self,
        profile: RestaurantProfile,
        body: str,
        button_payload: str,
        now: datetime,
        request_id: str = "",
    ) -> Optional[ReplyPlan]:
        """Steps 1-3 (no model). ``None`` = the reply needs the free-text path."""
        prompt = await self.open_prompt(profile, now)
        channel = "button" if button_payload else "text"

        # 1. Button payload
        if button_payload:
            if button_payload in BUTTON_CONFIRMATIONS:
                return await self._answer_confirmation(
                    profile, prompt, BUTTON_CONFIRMATIONS[button_payload], now, channel, request_id
                )
            if button_payload in BUTTON_DECISIONS:
                await self._supersede(prompt, now)
                recs = await self.pending_recommendations(profile)
                return await self._record_or_explain(
                    profile, recs, BUTTON_DECISIONS[button_payload], DecisionSource.button,
                    1.0, now, channel, request_id,
                )
            return await self._not_recorded(profile, None, "unknown_button_payload", channel,
                                            request_id, text_for("not_understood", self.locale), "decision", now=now)

        # 2. Answer to a pending confirmation
        if prompt is not None and prompt.kind == "decision_confirmation":
            answer = match_confirmation_answer(body)
            if answer is not None:
                return await self._answer_confirmation(profile, prompt, answer, now, channel, request_id)

        # 3. Exact keyword
        match = match_keyword(body)
        if match is None:
            return None
        if match.kind == "bare_ack" and prompt is not None and prompt.kind == "reason_request":
            # "ok" after "Une raison ?" is not a reason and not a decision: close it.
            prompt.status = "answered"
            prompt.resolved_at = now
            await self._event(profile, prompt.recommendation_id, "reason_captured", channel,
                              request_id, prompt_id=prompt.id, why="no_reason_given", now=now)
            await self.db.commit()
            return ReplyPlan(text=text_for("ack", self.locale), result="reason_captured")

        await self._supersede(prompt, now)
        recs = await self.pending_recommendations(profile)
        ctx = self.pending_context(recs, now)
        res = resolve_keyword(match, ctx)
        return await self._apply(profile, recs, res, now, channel, request_id)

    async def handle_free_text(
        self,
        profile: RestaurantProfile,
        feedback: FeedbackIntent,
        now: datetime,
        request_id: str = "",
    ) -> tuple[ReplyPlan, Resolution, Optional[StaffingRecommendation]]:
        """Step 5 for an already-parsed reply. Returns the plan, the resolution
        and the recommendation a decision was written on (if any)."""
        prompt = await self.open_prompt(profile, now)
        await self._supersede(prompt, now)
        recs = await self.pending_recommendations(profile)
        ctx = self.pending_context(recs, now)
        res = resolve_feedback(feedback, ctx)
        plan = await self._apply(
            profile, recs, res, now, "text", request_id,
            corrected_value=feedback.actual_value,
            reason=feedback.reason,
            reason_route=routed_reason(feedback.reason_route, feedback.reason_route_confidence),
            reason_route_confidence=feedback.reason_route_confidence,
        )
        rec = recs[0] if (res.action == "record" and recs) else None
        return plan, res, rec

    async def handle_reason(
        self,
        profile: RestaurantProfile,
        prompt: ManagerPrompt,
        body: str,
        route: Optional[str],
        route_confidence: Optional[float],
        now: datetime,
        request_id: str = "",
    ) -> ReplyPlan:
        """Step 4: store the reason typed. Never touches the recorded decision."""
        prompt.status = "answered"
        prompt.resolved_at = now
        routed = routed_reason(route, route_confidence)
        await self._event(
            profile, prompt.recommendation_id, "reason_captured", "text", request_id,
            prompt_id=prompt.id, reason_text=body.strip()[:1000],
            reason_route=routed, reason_route_confidence=route_confidence, now=now)
        await self.db.commit()
        return ReplyPlan(text=text_for("reason_thanks", self.locale), result="reason_captured",
                         extras={"reason_route": routed})

    async def cancel_reason_prompt(self, profile: RestaurantProfile, now: datetime) -> None:
        await self.db.execute(
            update(ManagerPrompt)
            .where(
                ManagerPrompt.property_id == uuid.UUID(str(profile.id)),
                ManagerPrompt.kind == "reason_request",
                ManagerPrompt.status == "pending",
            )
            .values(status="superseded", resolved_at=now)
        )
        await self.db.commit()

    async def expire_stale_prompts(self, now: datetime, property_id: Optional[uuid.UUID] = None) -> int:
        """Pending prompts past ``expires_at`` → ``expired``. An expired
        confirmation is recorded as unconfirmed (one ``confirmation_expired``
        event), never as a decision. Called on every inbound reply for the
        property and by the dispatch worker sweep."""
        q = select(ManagerPrompt).where(ManagerPrompt.status == "pending")
        if property_id is not None:
            q = q.where(ManagerPrompt.property_id == property_id)
        stale = [p for p in (await self.db.execute(q)).scalars().all()
                 if _utc(p.expires_at) is not None and _utc(p.expires_at) <= now]
        for p in stale:
            p.status = "expired"
            p.resolved_at = now
            if p.kind == "decision_confirmation":
                self.db.add(InboundReplyEvent(
                    created_at=now,
                    tenant_id=p.tenant_id, property_id=p.property_id,
                    recommendation_id=p.recommendation_id, prompt_id=p.id,
                    channel="system", result="confirmation_expired",
                    decision=None, why="unconfirmed", confidence=p.confidence,
                ))
                logger.info(
                    "inbound_decision_event result=confirmation_expired tenant=%s prompt=%s proposed=%s origin=%s",
                    p.tenant_id, p.id, p.proposed_decision, p.origin,
                )
        if stale:
            await self.db.commit()
        return len(stale)

    async def capture_metrics(self, tenant_id: str, since: datetime, until: datetime) -> CaptureMetrics:
        rows = (await self.db.execute(
            select(InboundReplyEvent).where(
                InboundReplyEvent.tenant_id == tenant_id,
                InboundReplyEvent.created_at >= since,
                InboundReplyEvent.created_at < until,
            )
        )).scalars().all()
        return compute_capture_metrics(
            {"result": r.result, "decision_source": r.decision_source, "why": r.why,
             "reason_route": r.reason_route}
            for r in rows
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _apply(
        self,
        profile: RestaurantProfile,
        recs: list[StaffingRecommendation],
        res: Resolution,
        now: datetime,
        channel: str,
        request_id: str,
        corrected_value: Optional[float] = None,
        reason: Optional[str] = None,
        reason_route: Optional[str] = None,
        reason_route_confidence: Optional[float] = None,
    ) -> ReplyPlan:
        if res.action == "record":
            return await self._record_or_explain(
                profile, recs, res.decision, res.source, res.confidence, now, channel,
                request_id, reason=reason, reason_route=reason_route,
                reason_route_confidence=reason_route_confidence,
            )
        if res.action == "confirm":
            if not recs:
                return await self._not_recorded(profile, None, "no_pending_recommendation", channel,
                                                request_id, text_for("no_pending", self.locale), now=now)
            return await self._ask_confirmation(
                profile, recs[0], res.decision, res.origin, res.confidence, corrected_value,
                now, channel, request_id,
            )
        # none
        why = res.why or "no_decision"
        if why == "no_pending_recommendation" or why == "model_decision_none":
            reply = text_for("ack", self.locale)
            buttons = None
        else:  # model error / schema failure: ask for an explicit decision
            reply = text_for("not_understood", self.locale)
            buttons = "decision"
        rec_id = recs[0].id if recs else None
        return await self._not_recorded(profile, rec_id, why, channel, request_id, reply, buttons,
                                        confidence=res.confidence, now=now)

    async def _record_or_explain(
        self,
        profile: RestaurantProfile,
        recs: list[StaffingRecommendation],
        decision: str,
        source: DecisionSource,
        confidence: float,
        now: datetime,
        channel: str,
        request_id: str,
        prompt: Optional[ManagerPrompt] = None,
        reason: Optional[str] = None,
        reason_route: Optional[str] = None,
        reason_route_confidence: Optional[float] = None,
        result: str = "recorded",
    ) -> ReplyPlan:
        if not recs:
            return await self._not_recorded(profile, None, "no_pending_recommendation", channel,
                                            request_id, text_for("no_pending", self.locale), now=now)
        rec = recs[0]
        rec.status = decision
        rec.action = decision
        rec.actioned_at = now
        rec.decision_source = source.value
        rec.decision_confidence = round(float(confidence), 3)
        await self._event(
            profile, rec.id, result, channel, request_id,
            prompt_id=prompt.id if prompt else None, decision=decision,
            decision_source=source.value, confidence=confidence,
            reason_text=reason, reason_route=reason_route,
            reason_route_confidence=reason_route_confidence, now=now)
        text = recorded_message(decision, self.locale)
        if wants_reason_prompt(decision, reason_already_given=bool(reason)):
            key = "reason_after_reject" if decision == "rejected" else "reason_after_correct"
            self.db.add(ManagerPrompt(
                created_at=now,
                tenant_id=profile.tenant_id, property_id=uuid.UUID(str(profile.id)),
                recommendation_id=rec.id, kind="reason_request", origin=source.value,
                status="pending", expires_at=now + PROMPT_WINDOW, request_id=request_id,
            ))
            text = f"{text} {text_for(key, self.locale)}"
        await self.db.commit()
        return ReplyPlan(text=text, result=result, decision=decision, source=source.value)

    async def _ask_confirmation(
        self,
        profile: RestaurantProfile,
        rec: StaffingRecommendation,
        decision: str,
        origin: str,
        confidence: float,
        corrected_value: Optional[float],
        now: datetime,
        channel: str,
        request_id: str,
    ) -> ReplyPlan:
        prompt = ManagerPrompt(
            id=uuid.uuid4(),
            created_at=now,
            tenant_id=profile.tenant_id, property_id=uuid.UUID(str(profile.id)),
            recommendation_id=rec.id, kind="decision_confirmation",
            proposed_decision=decision, origin=origin,
            confidence=round(float(confidence), 3),
            corrected_value=corrected_value, status="pending",
            expires_at=now + PROMPT_WINDOW, request_id=request_id,
        )
        self.db.add(prompt)
        await self._event(profile, rec.id, "confirmation_requested", channel, request_id,
                          prompt_id=prompt.id, decision=decision, confidence=confidence,
                          why=origin, now=now)
        await self.db.commit()
        text = f"{confirmation_question(decision, self.locale)} {text_for('confirm_text_hint', self.locale)}"
        return ReplyPlan(text=text, buttons="confirm", result="confirmation_requested",
                         decision=decision, extras={"origin": origin})

    async def _answer_confirmation(
        self,
        profile: RestaurantProfile,
        prompt: Optional[ManagerPrompt],
        yes: bool,
        now: datetime,
        channel: str,
        request_id: str,
    ) -> ReplyPlan:
        if prompt is None or prompt.kind != "decision_confirmation":
            return await self._not_recorded(profile, None, "no_pending_confirmation", channel,
                                            request_id, text_for("not_understood", self.locale),
                                            "decision", now=now)
        prompt.resolved_at = now
        if not yes:
            prompt.status = "declined"
            await self._event(profile, prompt.recommendation_id, "declined", channel, request_id,
                              prompt_id=prompt.id, why=prompt.origin, now=now)
            await self.db.commit()
            return ReplyPlan(text=text_for("declined", self.locale), buttons="decision",
                             result="declined")
        prompt.status = "confirmed"
        rec = None
        if prompt.recommendation_id is not None:
            rec = (await self.db.execute(
                select(StaffingRecommendation).where(
                    StaffingRecommendation.id == prompt.recommendation_id,
                    StaffingRecommendation.status == "dispatched",
                )
            )).scalars().first()
        if rec is None:
            # Decided or withdrawn meanwhile: the confirmation has nothing to apply to.
            prompt.status = "superseded"
            return await self._not_recorded(profile, prompt.recommendation_id,
                                            "recommendation_no_longer_pending", channel,
                                            request_id, text_for("no_pending", self.locale), now=now)
        source = CONFIRMED_SOURCE.get(prompt.origin or "", DecisionSource.model_confirmed)
        return await self._record_or_explain(
            profile, [rec], prompt.proposed_decision, source,
            float(prompt.confidence) if prompt.confidence is not None else 1.0,
            now, channel, request_id, prompt=prompt, result="confirmed",
        )

    async def _supersede(self, prompt: Optional[ManagerPrompt], now: datetime) -> None:
        """A new decision-bearing reply replaces any open prompt (not counted as
        confirmed, declined or expired)."""
        if prompt is None:
            return
        await self.db.execute(
            update(ManagerPrompt)
            .where(ManagerPrompt.id == prompt.id, ManagerPrompt.status == "pending")
            .values(status="superseded", resolved_at=now)
        )

    async def _not_recorded(
        self,
        profile: RestaurantProfile,
        rec_id,
        why: str,
        channel: str,
        request_id: str,
        reply: Optional[str],
        buttons: Optional[Buttons] = None,
        confidence: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> ReplyPlan:
        await self._event(profile, rec_id, "not_recorded", channel, request_id, why=why,
                          confidence=confidence, now=now)
        await self.db.commit()
        return ReplyPlan(text=reply, buttons=buttons, result="not_recorded", extras={"why": why})

    async def _event(
        self,
        profile: RestaurantProfile,
        rec_id,
        result: str,
        channel: str,
        request_id: str,
        now: Optional[datetime] = None,
        **fields,
    ) -> None:
        conf = fields.get("confidence")
        if conf is not None:
            fields["confidence"] = round(float(conf), 3)
        rrc = fields.get("reason_route_confidence")
        if rrc is not None:
            fields["reason_route_confidence"] = round(float(rrc), 3)
        if now is not None:
            fields["created_at"] = now
        self.db.add(InboundReplyEvent(
            tenant_id=profile.tenant_id,
            property_id=uuid.UUID(str(profile.id)),
            recommendation_id=rec_id,
            request_id=request_id,
            channel=channel,
            result=result,
            **fields,
        ))
        # Structured event (typed fields only — never the raw reply body, PII).
        logger.info(
            "inbound_decision_event result=%s tenant=%s rec=%s channel=%s decision=%s "
            "source=%s confidence=%s why=%s reason_route=%s",
            result, profile.tenant_id, rec_id, channel, fields.get("decision"),
            fields.get("decision_source"), fields.get("confidence"), fields.get("why"),
            fields.get("reason_route"),
        )

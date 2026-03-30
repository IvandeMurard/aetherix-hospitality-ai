"""Explainability Service — Story 5.2 (HOS-29).

Generates a friendly, data-grounded explanation for a manager's inbound
question using Claude, then sends the reply back via Twilio.

Flow (called from the _bg_parse_query background task):
  ConversationalQuery (id)
    → StaffingRecommendation (linked via recommendation_id)
    → DemandAnomaly (linked via recommendation.anomaly_id)
    → Claude prompt assembled with anomaly maths + recommendation context
    → Claude generates plain-text explanation
    → Twilio sends reply to manager's phone number
    → ConversationalQuery.status updated to 'answered'

Performance target: P95 < 3 s from inbound webhook receipt (NFR6).
Claude Sonnet is used as it is the project's primary reasoning model (see CLAUDE.md).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationalQuery, DemandAnomaly, StaffingRecommendation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Twilio helpers (thin — avoids importing the heavyweight WhatsAppService)
# ---------------------------------------------------------------------------

_TWILIO_MSG_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)


async def _send_twilio_reply(to: str, body: str) -> None:
    """Send a Twilio SMS/WhatsApp reply back to the manager.

    Normalises the ``to`` number: if the original came in as bare E.164 we
    try whatsapp-prefix first (matching the property's preferred channel).
    If TWILIO_WHATSAPP_NUMBER is not set, falls back to plain SMS From.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", os.getenv("TWILIO_FROM_NUMBER", ""))

    if not account_sid or not auth_token or not from_number:
        logger.warning("explainability_service: Twilio env vars not set — skipping send")
        return

    # Mirror the channel: if manager used whatsapp prefix, reply on whatsapp
    if not to.startswith("whatsapp:") and from_number.startswith("whatsapp:"):
        to = f"whatsapp:{to}"

    url = _TWILIO_MSG_URL.format(account_sid=account_sid)
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                url,
                data={"To": to, "From": from_number, "Body": body},
                auth=(account_sid, auth_token),
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    "explainability_service: Twilio error status=%s body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.info("explainability_service: reply sent to=%s", to)
        except Exception as exc:
            logger.error("explainability_service: failed to send Twilio reply: %s", exc)


# ---------------------------------------------------------------------------
# Claude prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    query_body: str,
    recommendation: StaffingRecommendation,
    anomaly: DemandAnomaly | None,
) -> str:
    """Assemble the Claude prompt with the full recommendation context.

    We provide the underlying maths (deviation %, ROI, triggering factors) so
    Claude can give a data-grounded explanation — not a generic answer.
    """
    window = (
        f"{recommendation.window_start.strftime('%A %d %b, %H:%M')} – "
        f"{recommendation.window_end.strftime('%H:%M')}"
        if recommendation.window_start and recommendation.window_end
        else "unspecified window"
    )

    roi_net = (
        f"£{float(recommendation.roi_net):,.0f}" if recommendation.roi_net else "n/a"
    )
    roi_labor = (
        f"£{float(recommendation.roi_labor_cost):,.0f}"
        if recommendation.roi_labor_cost
        else "n/a"
    )

    anomaly_block = ""
    if anomaly:
        direction = anomaly.direction.upper()  # SURGE | LULL
        deviation = (
            f"{float(anomaly.deviation_pct):+.1f}%" if anomaly.deviation_pct else "n/a"
        )
        factors = anomaly.triggering_factors or []
        factor_list = (
            "\n".join(f"  • {f}" for f in factors) if factors else "  • (none recorded)"
        )
        anomaly_block = (
            f"\nDemand anomaly detected: {direction} ({deviation} vs baseline)\n"
            f"Triggering factors:\n{factor_list}\n"
        )

    return f"""You are Aetherix, an AI assistant for hotel F&B operations.
A manager replied to a staffing recommendation with the following question:

  "{query_body}"

Here is the full context behind that recommendation:

RECOMMENDATION
  Window : {window}
  Action : {recommendation.message_text or 'see below'}
  Headcount suggested: {recommendation.recommended_headcount or 'n/a'} staff
  Triggering factor : {recommendation.triggering_factor or 'n/a'}
  Estimated ROI net : {roi_net}
  Estimated labor cost delta: {roi_labor}
{anomaly_block}
TASK
Write a friendly, concise plain-text reply (3–5 sentences maximum) that directly
answers the manager's question using the data above.
- Use specific numbers (percentages, £ values) to build trust.
- Avoid jargon; write as if texting a busy hotel manager.
- Do NOT use markdown, bullet points, or headings — plain text only.
- End with a one-line next-step nudge (accept or reject).
"""


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

_FALLBACK_REPLY = (
    "I couldn't retrieve the full context for your question right now. "
    "Please reply ACCEPT or REJECT, or contact your operations team directly."
)


class ExplainabilityService:
    """Generates a Claude-powered explanation and dispatches it via Twilio.

    All DB operations use the provided ``AsyncSession``; all network calls are
    async. Designed to be called from a FastAPI BackgroundTask.
    """

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self._claude = AsyncAnthropic(api_key=api_key) if api_key else None

    async def generate_and_send(
        self,
        query_id: uuid.UUID,
        session: AsyncSession,
    ) -> dict:
        """End-to-end: fetch context → call Claude → send reply → mark answered.

        Args:
            query_id: PK of the ``ConversationalQuery`` row to process.
            session:  Open async SQLAlchemy session.

        Returns:
            ``{"status": "sent", "query_id": ..., "chars": N}`` on success.
            ``{"status": "error", "reason": ...}`` on any failure.
        """
        # ------------------------------------------------------------------
        # 1. Load the query row
        # ------------------------------------------------------------------
        cq_result = await session.execute(
            select(ConversationalQuery).where(ConversationalQuery.id == query_id)
        )
        cq: ConversationalQuery | None = cq_result.scalars().first()

        if cq is None:
            logger.error("explainability_service: query id=%s not found", query_id)
            return {"status": "error", "reason": "query_not_found"}

        # Mark as processing to prevent duplicate workers racing
        cq.status = "processing"
        await session.commit()

        # ------------------------------------------------------------------
        # 2. Load the linked recommendation
        # ------------------------------------------------------------------
        recommendation: StaffingRecommendation | None = None
        anomaly: DemandAnomaly | None = None

        if cq.recommendation_id:
            rec_result = await session.execute(
                select(StaffingRecommendation).where(
                    StaffingRecommendation.id == cq.recommendation_id
                )
            )
            recommendation = rec_result.scalars().first()

        if recommendation is None:
            logger.warning(
                "explainability_service: no recommendation linked to query id=%s — sending fallback",
                query_id,
            )
            await _send_twilio_reply(cq.from_number, _FALLBACK_REPLY)
            cq.status = "answered"
            await session.commit()
            return {"status": "sent_fallback", "query_id": str(query_id)}

        # ------------------------------------------------------------------
        # 3. Load the linked anomaly (best-effort)
        # ------------------------------------------------------------------
        if recommendation.anomaly_id:
            anomaly_result = await session.execute(
                select(DemandAnomaly).where(
                    DemandAnomaly.id == recommendation.anomaly_id
                )
            )
            anomaly = anomaly_result.scalars().first()

        # ------------------------------------------------------------------
        # 4. Call Claude
        # ------------------------------------------------------------------
        explanation = await self._call_claude(cq.body, recommendation, anomaly)

        # ------------------------------------------------------------------
        # 5. Send Twilio reply
        # ------------------------------------------------------------------
        await _send_twilio_reply(cq.from_number, explanation)

        # ------------------------------------------------------------------
        # 6. Mark query as answered
        # ------------------------------------------------------------------
        cq.status = "answered"
        await session.commit()

        logger.info(
            "explainability_service: answered query id=%s chars=%d",
            query_id,
            len(explanation),
        )
        return {"status": "sent", "query_id": str(query_id), "chars": len(explanation)}

    async def _call_claude(
        self,
        query_body: str,
        recommendation: StaffingRecommendation,
        anomaly: DemandAnomaly | None,
    ) -> str:
        """Call Claude Sonnet and return the plain-text explanation.

        Falls back to a static message if the API key is absent or the call fails.
        """
        if not self._claude:
            logger.warning("explainability_service: ANTHROPIC_API_KEY not set — using fallback")
            return _FALLBACK_REPLY

        prompt = _build_prompt(query_body, recommendation, anomaly)

        try:
            message = await self._claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception as exc:
            logger.error("explainability_service: Claude API error: %s", exc)
            return _FALLBACK_REPLY

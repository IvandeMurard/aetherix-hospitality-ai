"""Twilio Inbound Webhook — Story 4.3 (HOS-26) + Story 5.1 (HOS-28) + Story 5.2 (HOS-29) + P2-4 (HOS-170).

Public endpoint: POST /webhooks/twilio/inbound

Receives inbound SMS/WhatsApp messages forwarded by Twilio.
- Accept / Reject → persisted immediately via ActionLoggerService.
- Everything else  → P2-4 receipt feedback path (parse_inbound) first;
                     falls back to QueryParserService / ExplainabilityService
                     if no hotel profile found for the sender number.

Security model
--------------
* No ``get_current_user`` JWT dependency — the endpoint is public.
* Requests are authenticated via Twilio HMAC-SHA1 signature validation
  (X-Twilio-Signature header).
* Signature validation is bypassable in CI/test environments by setting
  ``TWILIO_SKIP_SIGNATURE_VALIDATION=true``.

Response
--------
Always returns TwiML XML with Content-Type ``application/xml``.
Twilio requires a response within 15 s; our target is < 200 ms for the
synchronous path (action logging) and < 50 ms for the async query path
(background task).

[Source: https://www.twilio.com/docs/usage/security#validating-signatures]
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.db.models import RestaurantProfile, StaffingRecommendation
from app.db.session import AsyncSessionLocal, get_db
from app.integrations.twilio_client import TwilioClient
from app.schemas.webhook import ActionType, TwilioInboundPayload
from app.services.action_logger import ActionLoggerService, parse_action
from app.services.explainability_service import ExplainabilityService
from app.services.query_parser import QueryParserService
from app.services.receipts import ReceiptsService, outcome_for_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# ---------------------------------------------------------------------------
# TwiML response templates
# ---------------------------------------------------------------------------

_TWIML_ACCEPT = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "\u2705 Staffing recommendation accepted. Good luck tonight!"
    "</Message></Response>"
)
_TWIML_REJECT = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "\u274c Recommendation rejected. No action will be taken."
    "</Message></Response>"
)
_TWIML_UNKNOWN = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "Reply ACCEPT or REJECT to action this recommendation."
    "</Message></Response>"
)

# Story 5.1 (HOS-28): conversational query acknowledgements
_TWIML_QUERY_ACK = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "Got your question, I'm looking into it... \U0001f9d0"
    "</Message></Response>"
)
_TWIML_QUERY_NO_CONTEXT = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "Sorry, I couldn't find an active recommendation linked to your number. "
    "Please contact your F&B manager directly."
    "</Message></Response>"
)

# P2-4 (HOS-170): receipt feedback acknowledgements
_TWIML_FEEDBACK_ACK = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "Noted. I've updated my records and will factor this into tomorrow's recommendations."
    "</Message></Response>"
)
_TWIML_FEEDBACK_CONFIRM_REQUEST = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "I've recorded your note with medium confidence. "
    "Reply with a thumbs-up to confirm, or ignore to discard."
    "</Message></Response>"
)
_TWIML_FEEDBACK_ACKNOWLEDGE = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<Response><Message>"
    "Understood."
    "</Message></Response>"
)

# Singleton Twilio client for outbound replies from background tasks
_twilio_client = TwilioClient()

_ACTION_TWIML: dict[ActionType, str] = {
    ActionType.accept: _TWIML_ACCEPT,
    ActionType.reject: _TWIML_REJECT,
    ActionType.unknown: _TWIML_UNKNOWN,
}


def _xml_response(twiml: str, status_code: int = 200) -> Response:
    return Response(content=twiml, media_type="application/xml", status_code=status_code)


# ---------------------------------------------------------------------------
# Reverse-proxy aware URL reconstruction for HMAC validation
# ---------------------------------------------------------------------------

def _get_webhook_url(request: Request) -> str:
    """Return the public-facing URL that Twilio signed.

    Behind a reverse proxy, ``request.url`` reflects the internal address
    (e.g. ``http://127.0.0.1:8000/...``). Twilio signed the original public
    URL, so we rebuild it in this priority order:
      1. ``TWILIO_WEBHOOK_BASE_URL`` env-var override (explicit production config)
      2. ``X-Forwarded-Proto`` + ``X-Forwarded-Host`` headers set by the proxy
      3. Raw ``request.url`` (local dev / direct access)
    """
    override = os.getenv("TWILIO_WEBHOOK_BASE_URL", "").rstrip("/")
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"

    if override:
        return override + path

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}{path}"


# ---------------------------------------------------------------------------
# Twilio HMAC-SHA1 signature validation
# ---------------------------------------------------------------------------

def _validate_twilio_signature(
    request_url: str,
    post_params: dict[str, str],
    twilio_signature: str,
    auth_token: str,
) -> bool:
    """Validate the X-Twilio-Signature header.

    Algorithm (RFC reference: https://www.twilio.com/docs/usage/security):
    1. Concatenate the full request URL with each POST param (key + value,
       alphabetically sorted by key name, no separator).
    2. HMAC-SHA1 sign the resulting string using TWILIO_AUTH_TOKEN as the key.
    3. Base64-encode and compare with the header value (constant-time compare).
    """
    s = request_url
    for key in sorted(post_params.keys()):
        s += key + post_params[key]

    mac = hmac.new(
        auth_token.encode("utf-8"),
        s.encode("utf-8"),
        hashlib.sha1,
    )
    computed = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(computed, twilio_signature)


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/twilio/inbound")
async def twilio_inbound_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    # Twilio always posts form-encoded data
    From: Annotated[str, Form()] = "",
    Body: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    # Optional signature header — absent in test mode
    x_twilio_signature: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Receive an inbound SMS/WhatsApp message and route it appropriately.

    Story 4.3 (HOS-26) — Accept / Reject path:
    AC#1  — Parses "Accept" / "Reject" (case-insensitive).
    AC#2  — Updates StaffingRecommendation status: accepted | rejected.
    AC#3  — Sets actioned_at timestamp.
    AC#4  — Returns help TwiML for unrecognised input (no error raised).
    AC#5  — Async DB path ensures < 200 ms response time under normal load.
    AC#6  — Returns TwiML XML; Content-Type: application/xml.
    AC#7  — No get_current_user dependency (public Twilio callback).
    AC#8  — Signature check skipped when TWILIO_SKIP_SIGNATURE_VALIDATION=true.

    Story 5.1 (HOS-28) — Conversational query path (FR13):
    AC#1  — Non-action text kicks off a BackgroundTask.
    AC#2  — BackgroundTask resolves tenant_id + recommendation from phone number.
    AC#3  — Webhook immediately returns a TwiML acknowledgement (< 50 ms).
    AC#4  — Query persisted in conversational_queries table.
    AC#5  — No matching recommendation → polite TwiML response.
    AC#6  — Idempotency: duplicate within 60 s is suppressed.
    """
    skip_validation = (
        os.getenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false").lower() == "true"
    )

    if not skip_validation:
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        signature = x_twilio_signature or ""
        form_data = dict(await request.form())
        full_url = _get_webhook_url(request)

        if not _validate_twilio_signature(
            full_url,
            {k: str(v) for k, v in form_data.items()},
            signature,
            auth_token,
        ):
            logger.warning("twilio_inbound: invalid signature from %s", From)
            return _xml_response(
                "<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
                status_code=403,
            )

    payload = TwilioInboundPayload(From=From, Body=Body, To=To)
    action = parse_action(payload.Body)

    if action != ActionType.unknown:
        # ---------------------------------------------------------------
        # Story 4.3 — synchronous Accept/Reject logging
        # ---------------------------------------------------------------
        service = ActionLoggerService()
        result = await service.log_action(payload.From_, action, db)
        logger.info("twilio_inbound: action log result=%s", result)
        return _xml_response(_ACTION_TWIML[action])

    # -------------------------------------------------------------------
    # P2-4 — receipt feedback path: parse intent, write to memory in bg
    # Falls back to legacy conversational query (Story 5.1) if hotel not found.
    # -------------------------------------------------------------------
    logger.info(
        "twilio_inbound: inbound from=%s body=%r — scheduling receipt feedback bg task",
        From,
        Body,
    )
    background_tasks.add_task(
        _bg_receipt_feedback,
        from_number=payload.From_,
        body=payload.Body,
    )
    return _xml_response(_TWIML_QUERY_ACK)


async def _bg_receipt_feedback(from_number: str, body: str) -> None:
    """P2-4: classify inbound WhatsApp reply and write to operational_memory.

    Routing:
      1. Normalize phone number, look up RestaurantProfile.
      2. If hotel not found → fall back to legacy _bg_parse_query path.
      3. classify intent via ReceiptsService.parse_inbound.
      4. acknowledge → send ack, no DB write.
      5. structured_correction / free_form with confidence ≥ 0.6
         → call tool_submit_feedback_to_memory, send confirmation.
      6. free_form with confidence < 0.6
         → write as outcome=modified, request thumbs-up confirmation.
    """
    import uuid as _uuid

    normalised = from_number.replace("whatsapp:", "")

    async with AsyncSessionLocal() as db:
        # Step 1: resolve hotel from phone number
        profile_result = await db.execute(
            select(RestaurantProfile).where(
                RestaurantProfile.phone_number == normalised
            )
        )
        profile: RestaurantProfile | None = profile_result.scalars().first()

        if profile is None:
            logger.info(
                "_bg_receipt_feedback: no profile for %s — falling back to conversational query",
                from_number,
            )
            # Fall back to old path (Phase 1 conversational queries)
            await _bg_parse_query(from_number=from_number, body=body)
            return

        hotel_id: str = profile.tenant_id

        # Step 2: find most recent recommendation for context (recommendation_id arg)
        rec_result = await db.execute(
            select(StaffingRecommendation)
            .where(
                StaffingRecommendation.property_id == _uuid.UUID(str(profile.id)),
                StaffingRecommendation.status.in_(["dispatched", "accepted", "rejected"]),
            )
            .order_by(
                StaffingRecommendation.dispatched_at.desc().nullslast(),
                StaffingRecommendation.created_at.desc(),
            )
            .limit(1)
        )
        recommendation: StaffingRecommendation | None = rec_result.scalars().first()
        recommendation_id: str = str(recommendation.id) if recommendation else ""

        # Step 3: classify intent
        service = ReceiptsService(db)
        feedback = await service.parse_inbound(body)
        # Shared with the parser eval (EVAL-4) so the eval grades what is written.
        outcome = outcome_for_feedback(feedback)

        if outcome is None:  # acknowledge — nothing recorded
            logger.info(
                "_bg_receipt_feedback: acknowledge hotel_id=%s — no DB write", hotel_id
            )
            try:
                await _twilio_client.send_whatsapp(from_number, "Understood.")
            except Exception:
                logger.warning("_bg_receipt_feedback: ack reply failed for %s", from_number)
            return

        # HOS-270: track whether the manager's numeric correction was rejected by
        # the G-3 plausibility guard, so Step 5 can tell them (not a silent drop).
        # Defined at function scope so the reply branch sees it on every path.
        covers_rejected = False

        # Step 4: write to operational_memory via tool_submit_feedback_to_memory
        if recommendation_id:
            from app.mcp_server import tool_submit_feedback_to_memory

            # Shared request_id links the feedback row and the P3-10 ground_truth
            # row for the same inbound correction.
            req_id = str(_uuid.uuid4())

            try:
                # HOS-250: run the plausibility guard FIRST. persist_actual_covers
                # bounds the value and returns None when it is rejected. The numeric
                # must clear the guard before it is allowed into the (embedded,
                # retrievable) feedback memory below — otherwise a rejected/aberrant
                # value still poisons the model via the feedback path even though
                # the ground-truth write was blocked.
                if (
                    feedback.intent == "structured_correction"
                    and feedback.actual_value is not None
                    and recommendation is not None
                ):
                    persisted = await service.persist_actual_covers(
                        recommendation,
                        feedback.actual_value,
                        request_id=req_id,
                    )
                    covers_rejected = persisted is None

                # Only carry the numeric correction into feedback memory when it
                # passed the guard. A rejected value still records the manager's
                # qualitative note, minus the implausible number.
                memory_actual = None if covers_rejected else feedback.actual_value
                notes_text = feedback.notes
                if memory_actual is not None:
                    notes_text = f"actual={memory_actual} {notes_text}".strip()

                result = await tool_submit_feedback_to_memory(
                    hotel_id=hotel_id,
                    recommendation_id=recommendation_id,
                    outcome=outcome,
                    db=db,
                    actual_value=memory_actual,
                    notes=notes_text,
                    request_id=req_id,
                )

                await db.commit()
                logger.info(
                    "_bg_receipt_feedback: memory written hotel_id=%s result=%s confidence=%.2f",
                    hotel_id,
                    result.get("status"),
                    feedback.confidence,
                )
            except Exception:
                logger.exception(
                    "_bg_receipt_feedback: memory write failed hotel_id=%s", hotel_id
                )
        else:
            logger.warning(
                "_bg_receipt_feedback: no recommendation found hotel_id=%s — skipping memory write",
                hotel_id,
            )

    # Step 5: Twilio reply based on confidence
    try:
        if covers_rejected:
            # HOS-270: the figure failed the plausibility guard — never drop it
            # silently. Tell the manager their note was kept but the number wasn't,
            # and invite a correction.
            reply = (
                "I've kept your note, but that covers figure looked outside the usual "
                "range for your venue, so I didn't record the number. If it's correct, "
                "please reply with the figure again to confirm."
            )
        elif feedback.requires_confirmation:
            reply = (
                "I've recorded your note with medium confidence. "
                "Reply with a thumbs-up to confirm, or ignore to discard."
            )
        else:
            reply = "Noted. I've updated my records and will factor this into tomorrow's recommendations."
        await _twilio_client.send_whatsapp(from_number, reply)
    except Exception:
        logger.warning(
            "_bg_receipt_feedback: reply send failed for %s", from_number
        )


async def _bg_parse_query(
    from_number: str,
    body: str,
) -> None:
    """Background task: parse, store, then generate & send explainability receipt.

    Opens an isolated AsyncSession so that commits here are independent of
    the request session (fixes silent rollback — same pattern as HOS-154).

    Story 5.1 (HOS-28) AC#2 — identifies tenant + recommendation.
    Story 5.2 (HOS-29)       — calls Claude and replies via Twilio.
    """
    async with AsyncSessionLocal() as db:
        # Step 1: store the query (Story 5.1)
        parser = QueryParserService()
        parse_result = await parser.parse_and_store(
            from_number=from_number, body=body, session=db
        )
        logger.info("twilio_inbound bg_parse_query: parse_result=%s", parse_result)

        if parse_result.get("status") not in ("stored",):
            # duplicate or not_found — QueryParserService already logged
            return

        # Step 2: generate explanation and send reply (Story 5.2)
        query_id = parse_result.get("query_id")
        if query_id:
            import uuid as _uuid
            explainer = ExplainabilityService()
            explain_result = await explainer.generate_and_send(
                query_id=_uuid.UUID(query_id), session=db
            )
            logger.info("twilio_inbound bg_parse_query: explain_result=%s", explain_result)

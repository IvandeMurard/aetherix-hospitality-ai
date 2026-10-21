"""Twilio Inbound Webhook — Story 4.3 (HOS-26) + Story 5.1 (HOS-28) + Story 5.2 (HOS-29) + P2-4 (HOS-170) + HOS-357.

Public endpoint: POST /webhooks/twilio/inbound

Receives inbound SMS/WhatsApp messages forwarded by Twilio.
- Button payload / confirmation answer / exact keyword / bare acknowledgement
  → decided synchronously, no model (InboundDecisionService, Décision #38).
- "prévision [jour] [service]" (HOS-358) → computed in the background like the
  MCP tool, on the hotel's stored context; never a decision.
- A question ("?", "pourquoi …", HOS-357) → answered in the background
  (ExplainabilityService); never a decision. A position stated in it is
  confirmed with the manager, never written.
- Everything else  → P2-4 receipt feedback path (parse_inbound + resolve_feedback)
                     in the background.
- A number with no hotel profile → "no context" reply, nothing else: there is
  no recommendation to explain or decide on, and no model is called.

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
synchronous path (deterministic decision capture) and < 50 ms for the async query path
(background task).

[Source: https://www.twilio.com/docs/usage/security#validating-signatures]
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, get_db
from app.integrations.twilio_client import TwilioClient
from app.core.pii import pseudonymise
from app.schemas.webhook import TwilioInboundPayload
from app.services.decision_messaging import (
    buttons_available,
    send_with_buttons,
    text_fallback,
)
from app.services.explainability_service import ExplainabilityService
from app.services.inbound_decision import InboundDecisionService, ReplyPlan
from app.services.manager_decision import ForecastCommand, is_question, match_forecast_command
from app.services.query_parser import QueryParserService
from app.services.receipts import ReceiptsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# ---------------------------------------------------------------------------
# TwiML response templates
# ---------------------------------------------------------------------------


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

# Singleton Twilio client for outbound replies from background tasks
_twilio_client = TwilioClient()


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

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _twiml_message(text: str) -> str:
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        f"<Response><Message>{xml_escape(text)}</Message></Response>"
    )


_TWIML_EMPTY = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"


async def _send_plan(to: str, plan: ReplyPlan) -> bool:
    """Send a reply out of band (REST), with quick replies when available.
    True once Twilio accepted it."""
    if not plan.text:
        return False
    try:
        await send_with_buttons(_twilio_client, to, plan.text, plan.buttons)
    except Exception:
        logger.warning("twilio_inbound: reply send failed for %s", pseudonymise(to))
        return False
    return True


@router.post("/twilio/inbound")
async def twilio_inbound_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    # Twilio always posts form-encoded data
    From: Annotated[str, Form()] = "",
    Body: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    # WhatsApp quick-reply tap (Décision #38): the button's fixed id. Empty for
    # a typed reply.
    ButtonPayload: Annotated[str, Form()] = "",
    # Optional signature header — absent in test mode
    x_twilio_signature: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Receive an inbound SMS/WhatsApp message and route it appropriately.

    Décision #38 / ADR-0007 §16 — manager decision capture:
      * Deterministic replies (button payload, answer to a pending confirmation,
        exact FR/EN keyword, bare acknowledgement) are decided synchronously by
        ``InboundDecisionService.handle_deterministic`` — no model. The reply is
        TwiML text, or sent via REST with quick replies when enabled.
      * A question (``is_question``, HOS-357) goes to ``_bg_question``: an
        answer, never a decision; a position stated in it is confirmed.
      * Everything else (free text, reason after a reject/correction) goes to
        the background task: covers regex → model → ``resolve_feedback``.
      * A decision the system is unsure of is confirmed, never written.

    Story 4.3 (HOS-26) — AC#3 actioned_at set, AC#6 TwiML XML, AC#7 public,
    AC#8 signature check skipped when TWILIO_SKIP_SIGNATURE_VALIDATION=true.
    Story 5.1 (HOS-28) — non-decision text kicks off a BackgroundTask.
    HOS-357 — an unknown sender gets the "no context" reply and nothing else.
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
            logger.warning("twilio_inbound: invalid signature from %s", pseudonymise(From))
            return _xml_response(_TWIML_EMPTY, status_code=403)

    payload = TwilioInboundPayload(From=From, Body=Body, To=To)
    decisions = InboundDecisionService(db)
    profile = await decisions.profile_for(payload.From_)

    if profile is not None:
        # HOS-349 (Décisions #43, #44): the owner confirms or cancels what the
        # hotel's agent requested (deletion, Hive opt-in) with a one-time code.
        # Exact whole-message commands, checked first, no model; only for the
        # hotel this verified number belongs to.
        from app.services import hotel_data_requests as hdr

        data_cmd = hdr.match_command(payload.Body)
        if data_cmd is not None:
            reply = await hdr.handle_command(db, profile, data_cmd, now=_now())
            logger.info("twilio_inbound: hotel data command action=%s", data_cmd.action)
            return _xml_response(_twiml_message(reply))

        # HOS-358: "prévision mardi" — computed like the MCP tool, in the
        # background (the engine runs Prophet). Never a decision.
        forecast_cmd = None if ButtonPayload else match_forecast_command(payload.Body)
        if forecast_cmd is not None:
            background_tasks.add_task(
                _bg_forecast, from_number=payload.From_, command=forecast_cmd,
                engine=getattr(request.app.state, "engine", None),
            )
            return _xml_response(_TWIML_EMPTY)

        plan = await decisions.handle_deterministic(
            profile, payload.Body, ButtonPayload.strip(), _now(), request_id=str(uuid.uuid4())
        )
        if plan is not None:
            logger.info("twilio_inbound: deterministic result=%s decision=%s source=%s",
                        plan.result, plan.decision, plan.source)
            if not plan.text:
                return _xml_response(_TWIML_EMPTY)
            if buttons_available(plan.buttons):
                background_tasks.add_task(_send_plan, payload.From_, plan)
                return _xml_response(_TWIML_EMPTY)
            return _xml_response(_twiml_message(text_fallback(plan.text, plan.buttons)))

        # HOS-357: a question is answered, never parsed as a decision.
        if is_question(payload.Body):
            logger.info("twilio_inbound: question from=%s — scheduling answer bg task",
                        pseudonymise(From))
            background_tasks.add_task(_bg_question, from_number=payload.From_, body=payload.Body)
            return _xml_response(_TWIML_EMPTY)
    else:
        # HOS-357: no hotel profile → no recommendation to decide on or explain.
        # (The legacy "Why?" fallback looked the number up the same way and could
        # never find one: the sender got "looking into it", then nothing.)
        return _xml_response(_TWIML_QUERY_NO_CONTEXT)

    # -------------------------------------------------------------------
    # Free text: model path in the background.
    # -------------------------------------------------------------------
    logger.info(
        "twilio_inbound: inbound from=%s — scheduling receipt feedback bg task",
        pseudonymise(From),
    )
    background_tasks.add_task(
        _bg_receipt_feedback,
        from_number=payload.From_,
        body=payload.Body,
    )
    return _xml_response(_TWIML_QUERY_ACK)


async def _bg_receipt_feedback(from_number: str, body: str) -> None:
    """Free-text reply (P2-4, ADR-0007 §16): reason or decision.

    1. Resolve the hotel from the phone number (the route already did; gone
       meanwhile → nothing).
    2. A pending reason request → the reply is the reason: routed (typed),
       stored, never changes the recorded decision.
    3. Otherwise ``parse_inbound`` (covers regex → model, shown the pending
       recommendation's proposal) → ``resolve_feedback`` (stance × proposal):
       record (≥ threshold), confirm (< threshold or two readings, nothing
       written), or nothing.
    4. A recorded decision with a note/figure → feedback memory + ground-truth
       covers (HOS-250 guard first, HOS-270 tells the manager if rejected).
    """
    request_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        decisions = InboundDecisionService(db)
        profile = await decisions.profile_for(from_number)

        if profile is None:
            logger.info("_bg_receipt_feedback: no profile for %s", pseudonymise(from_number))
            return

        hotel_id: str = profile.tenant_id
        service = ReceiptsService(db)
        now = _now()

        prompt = await decisions.open_prompt(profile, now)
        if prompt is not None and prompt.kind == "reason_request":
            route, route_conf = await service.route_reason(body)
            plan = await decisions.handle_reason(
                profile, prompt, body, route, route_conf, now, request_id
            )
            await _send_plan(from_number, plan)
            return

        # ADR-0007 §19: the model is shown what the pending recommendation
        # proposed; the decision is derived from its stance and that proposal.
        pending = await decisions.pending_recommendations(profile)
        proposal = decisions.proposal_of(pending[0] if pending else None)
        feedback = await service.parse_inbound(body, proposal)
        plan, resolution, recommendation = await decisions.handle_free_text(
            profile, feedback, now, request_id
        )

        # HOS-270: whether the manager's numeric correction failed the G-3
        # plausibility guard, so the reply can say so (not a silent drop).
        covers_rejected = False

        if resolution.action == "record" and recommendation is not None:
            from app.mcp_server import tool_submit_feedback_to_memory

            try:
                # HOS-250: plausibility guard FIRST, before the number can reach
                # the (embedded, retrievable) feedback memory.
                if (
                    feedback.intent == "structured_correction"
                    and feedback.actual_value is not None
                ):
                    persisted = await service.persist_actual_covers(
                        recommendation,
                        feedback.actual_value,
                        request_id=request_id,
                    )
                    covers_rejected = persisted is None

                memory_actual = None if covers_rejected else feedback.actual_value
                notes_text = feedback.notes
                if memory_actual is not None:
                    notes_text = f"actual={memory_actual} {notes_text}".strip()

                result = await tool_submit_feedback_to_memory(
                    hotel_id=hotel_id,
                    recommendation_id=str(recommendation.id),
                    outcome=resolution.decision,
                    db=db,
                    actual_value=memory_actual,
                    notes=notes_text,
                    request_id=request_id,
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

        if covers_rejected:
            # The reason prompt must not swallow the re-sent figure.
            await decisions.cancel_reason_prompt(profile, now)
            plan = ReplyPlan(text=_COVERS_REJECTED_REPLY)

    await _send_plan(from_number, plan)


_COVERS_REJECTED_REPLY = (
    "I've kept your note, but that covers figure looked outside the usual "
    "range for your venue, so I didn't record the number. If it's correct, "
    "please reply with the figure again to confirm."
)


async def _bg_forecast(from_number: str, command: ForecastCommand, engine) -> None:
    """Background task (HOS-358): "prévision mardi midi", answered.

    The same computation as the MCP tool ``get_operational_predictions``: the
    app's forecast engine (guardrail included) on the hotel's stored context
    (``forecast_context``). The answer (``forecast_reply``) is deterministic and
    goes to the manager's number. No decision is written, no prompt touched.
    """
    from app.services import forecast_context
    from app.services.decision_recap import _tz
    from app.services.forecast_reply import bad_date_reply, render_forecast

    request_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        decisions = InboundDecisionService(db)
        profile = await decisions.profile_for(from_number)
        if profile is None:
            return
        now = _now()
        locale = command.locale or getattr(profile, "manager_locale", None) or "fr"
        day = command.target_date(now.astimezone(_tz()).date())
        if day is None:
            await decisions.record_forecast_served(profile, None, "bad_date", now, request_id)
            await _send_plan(from_number, ReplyPlan(text=bad_date_reply(command.ref, locale)))
            return
        context = await forecast_context.build(db, profile, day, command.service)
        result = None
        if engine is not None:
            try:
                result = await engine.get_forecast(profile.tenant_id, day, command.service, dict(context))
            except Exception:
                logger.exception("twilio_inbound: forecast failed tenant=%s", profile.tenant_id)
        rec = await decisions.recommendation_for_day(profile, day)
        prediction = (result or {}).get("prediction") or {}
        why = ("unavailable" if result is None else "mock" if prediction.get("is_mock") else "served")
        await decisions.record_forecast_served(profile, rec.id if rec else None, why, now, request_id)
        text = render_forecast(result, context, day, command.service, locale, rec)
    logger.info("twilio_inbound: forecast served why=%s", why)
    await _send_plan(from_number, ReplyPlan(text=text, result="forecast_served"))


async def _bg_question(from_number: str, body: str) -> None:
    """Background task (HOS-357): a known manager's question, answered.

    Opens an isolated AsyncSession so that commits here are independent of
    the request session (fixes silent rollback — same pattern as HOS-154).

    1. The question is stored (``conversational_queries``, number as a digest);
       the same text from the same number within 60 s is a duplicate (a Twilio
       retry, a double send) and is not answered twice.
    2. ``ExplainabilityService`` writes the answer about the hotel's latest
       recommendation, in the manager's language, from stored fields only.
    3. ``InboundDecisionService.handle_question`` adds what the question needs:
       nothing, a confirmation of the position it states, or "2 quoi ?". It
       never writes a decision.
    4. The reply goes to the manager's number (not the stored digest); the
       question is marked answered only once Twilio accepted it.
    """
    request_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        decisions = InboundDecisionService(db)
        profile = await decisions.profile_for(from_number)
        if profile is None:
            return
        queries = QueryParserService()
        stored = await queries.parse_and_store(from_number=from_number, body=body, session=db)
        if stored.get("status") != "stored":
            return
        locale = getattr(profile, "manager_locale", None) or "fr"
        explanation = await ExplainabilityService().explain(
            body, await decisions.latest_recommendation(profile), db, locale
        )
        plan = await decisions.handle_question(
            profile, body, explanation, ReceiptsService(db).parse_inbound, _now(), request_id
        )
        logger.info("twilio_inbound: question result=%s decision=%s",
                    plan.result, plan.decision)
        if await _send_plan(from_number, plan):
            await queries.mark_answered(uuid.UUID(stored["query_id"]), db)

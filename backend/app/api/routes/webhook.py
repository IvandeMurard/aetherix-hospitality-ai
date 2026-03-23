"""Twilio Inbound Webhook — Story 4.3 (HOS-26).

Public endpoint: POST /webhooks/twilio/inbound

Receives inbound SMS/WhatsApp messages forwarded by Twilio, parses the
manager's Accept/Reject decision, and persists it via ActionLoggerService.

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
Twilio requires a response within 15 s; our target is < 200 ms because
all I/O (one DB query + one DB write) is async.

[Source: https://www.twilio.com/docs/usage/security#validating-signatures]
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.webhook import ActionType, TwilioInboundPayload
from app.services.action_logger import ActionLoggerService, parse_action

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

_ACTION_TWIML: dict[ActionType, str] = {
    ActionType.accept: _TWIML_ACCEPT,
    ActionType.reject: _TWIML_REJECT,
    ActionType.unknown: _TWIML_UNKNOWN,
}


def _xml_response(twiml: str, status_code: int = 200) -> Response:
    return Response(content=twiml, media_type="application/xml", status_code=status_code)


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
    # Twilio always posts form-encoded data
    From: Annotated[str, Form()] = "",
    Body: Annotated[str, Form()] = "",
    To: Annotated[str, Form()] = "",
    # Optional signature header — absent in test mode
    x_twilio_signature: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Receive an inbound SMS/WhatsApp message and log the manager decision.

    AC#1  — Parses "Accept" / "Reject" (case-insensitive).
    AC#2  — Updates StaffingRecommendation status: accepted | rejected.
    AC#3  — Sets actioned_at timestamp.
    AC#4  — Returns help TwiML for unrecognised input (no error raised).
    AC#5  — Async DB path ensures < 200 ms response time under normal load.
    AC#6  — Returns TwiML XML; Content-Type: application/xml.
    AC#7  — No get_current_user dependency (public Twilio callback).
    AC#8  — Signature check skipped when TWILIO_SKIP_SIGNATURE_VALIDATION=true.
    """
    skip_validation = (
        os.getenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false").lower() == "true"
    )

    if not skip_validation:
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        signature = x_twilio_signature or ""
        form_data = dict(await request.form())
        full_url = str(request.url)

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
        service = ActionLoggerService()
        result = await service.log_action(payload.From_, action, db)
        logger.info("twilio_inbound: action log result=%s", result)
    else:
        logger.info(
            "twilio_inbound: unknown action from %s body=%r", From, Body
        )

    return _xml_response(_ACTION_TWIML[action])

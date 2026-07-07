import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import Response

from app.api.routes.twilio_inbound import _validate_twilio_signature
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
whatsapp = WhatsAppService()


@router.post("/twilio/whatsapp")
async def twilio_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: Optional[str] = Header(None),
):
    """
    Inbound webhook for Twilio WhatsApp messages.

    Validates Twilio HMAC-SHA1 signature before processing (HOS-149 AC5).
    Set TWILIO_SKIP_SIGNATURE_VALIDATION=true in CI only — forbidden in production.
    """
    # Read form data once — Starlette caches it, safe to read before validation
    form_data = dict(await request.form())

    skip_validation = (
        os.getenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "false").lower() == "true"
    )

    if not skip_validation:
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        signature = x_twilio_signature or ""

        if not signature or not _validate_twilio_signature(
            str(request.url),
            {k: str(v) for k, v in form_data.items()},
            signature,
            auth_token,
        ):
            raise HTTPException(status_code=403, detail="Invalid or missing Twilio signature")

    # Process in background to respond to Twilio immediately (200 OK)
    background_tasks.add_task(whatsapp.handle_inbound_message, form_data)

    # Twilio expects TwiML from a Messaging webhook; returning a minimal,
    # empty <Response/> avoids webhook parsing issues.
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="text/xml",
    )

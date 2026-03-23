"""Notifications API routes.

POST /api/v1/notifications/test — dispatch a test message via the
requested channel (SMS, WhatsApp, or Email) and return the result.

Architecture constraints:
- Business logic lives in the integration clients, not here (thin router).
- RFC 7807 Problem Details errors via the global exception handler.
- No real messages are sent when the service credentials are absent
  (NotConfiguredError is surfaced as HTTP 503).
[Source: architecture.md#API-Contracts, architecture.md#Process-Patterns]
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.exceptions import NotConfiguredError
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient
from app.schemas.notifications import (
    NotificationChannel,
    TestNotificationRequest,
    TestNotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/test",
    response_model=TestNotificationResponse,
    summary="Send a test notification",
    description=(
        "Dispatches a single test message via the requested channel "
        "(sms, whatsapp, or email). Returns the provider message ID on success."
    ),
)
async def send_test_notification(
    body: TestNotificationRequest,
) -> TestNotificationResponse:
    """POST /api/v1/notifications/test

    Dispatches a test notification and returns success + provider reference ID.

    Raises:
        422: Validation error (invalid channel / missing fields).
        503: External service not configured (missing API keys).
        500: Unexpected provider error.
    """
    try:
        if body.channel == NotificationChannel.sms:
            client = TwilioClient()
            sid = await client.send_sms(to=body.to, body=body.message)
            return TestNotificationResponse(
                success=True,
                channel=body.channel,
                sidOrMessageId=sid,
            )

        elif body.channel == NotificationChannel.whatsapp:
            client = TwilioClient()
            sid = await client.send_whatsapp(to=body.to, body=body.message)
            return TestNotificationResponse(
                success=True,
                channel=body.channel,
                sidOrMessageId=sid,
            )

        else:  # email
            client = SendGridClient()
            await client.send_email(
                to=body.to,
                subject="Aetherix Test Notification",
                body=body.message,
            )
            return TestNotificationResponse(
                success=True,
                channel=body.channel,
                sidOrMessageId=None,
            )

    except NotConfiguredError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Notification delivery failed: {exc}",
        ) from exc

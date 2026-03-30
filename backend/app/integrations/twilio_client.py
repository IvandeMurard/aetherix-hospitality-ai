"""Twilio integration client for SMS and WhatsApp outbound messaging.

Uses httpx for all HTTP calls (no Twilio SDK dependency).
Twilio REST API reference: https://www.twilio.com/docs/messaging/api/message-resource

Architecture constraints:
- Raises NotConfiguredError if credentials are absent (lazy-init pattern).
- TwilioClient is stateless; instantiate per-request or as a singleton.
[Source: architecture.md#Integrations]
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core import config
from app.core.exceptions import NotConfiguredError

logger = logging.getLogger(__name__)

_MESSAGES_URL_TEMPLATE = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)


class TwilioClient:
    """Thin HTTP wrapper around the Twilio Messaging REST API.

    Raises ``NotConfiguredError`` on the first API call when
    ``TWILIO_ACCOUNT_SID`` or ``TWILIO_AUTH_TOKEN`` are empty strings.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        whatsapp_from: Optional[str] = None,
    ) -> None:
        self._account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self._auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        self._from_number = from_number or config.TWILIO_FROM_NUMBER
        self._whatsapp_from = whatsapp_from or config.TWILIO_WHATSAPP_FROM

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _assert_configured(self) -> None:
        if not self._account_sid or not self._auth_token:
            raise NotConfiguredError("Twilio")

    async def _post_message(self, to: str, from_: str, body: str) -> str:
        """Send a Twilio Messages.json POST and return the message SID."""
        self._assert_configured()

        url = _MESSAGES_URL_TEMPLATE.format(account_sid=self._account_sid)
        payload = {"To": to, "From": from_, "Body": body}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data=payload,
                auth=(self._account_sid, self._auth_token),
            )

        if response.status_code not in (200, 201):
            logger.error(
                "Twilio API error %s: %s", response.status_code, response.text
            )
            response.raise_for_status()

        data = response.json()
        sid: str = data.get("sid", "")
        logger.info("Twilio message sent: sid=%s to=%s", sid, to)
        return sid

    # ──────────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────────

    async def send_sms(self, to: str, body: str) -> str:
        """Send an SMS message.

        Args:
            to: Destination phone number in E.164 format (e.g. ``+33612345678``).
            body: Text content of the message.

        Returns:
            The Twilio message SID string.

        Raises:
            NotConfiguredError: If Twilio credentials are not set.
            httpx.HTTPStatusError: On non-2xx response from Twilio.
        """
        return await self._post_message(to=to, from_=self._from_number, body=body)

    async def send_whatsapp(self, to: str, body: str) -> str:
        """Send a WhatsApp message via the Twilio WhatsApp sandbox / approved number.

        The ``whatsapp:`` URI scheme prefix is automatically applied to ``to``
        if not already present.

        Args:
            to: Destination WhatsApp number, e.g. ``+33612345678`` or
                ``whatsapp:+33612345678``.
            body: Text content of the message.

        Returns:
            The Twilio message SID string.

        Raises:
            NotConfiguredError: If Twilio credentials are not set.
            httpx.HTTPStatusError: On non-2xx response from Twilio.
        """
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        whatsapp_from = self._whatsapp_from or self._from_number
        return await self._post_message(to=to, from_=whatsapp_from, body=body)

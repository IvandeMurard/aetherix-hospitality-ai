"""Twilio integration client for SMS and WhatsApp outbound messaging.

Uses httpx for all HTTP calls (no Twilio SDK dependency).
Twilio REST API reference: https://www.twilio.com/docs/messaging/api/message-resource

Architecture constraints:
- Raises NotConfiguredError if credentials are absent (lazy-init pattern).
- TwilioClient is stateless; instantiate per-request or as a singleton.
[Source: architecture.md#Integrations]
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx

from app.core import config
from app.core.exceptions import NotConfiguredError

logger = logging.getLogger(__name__)

_MESSAGES_URL_TEMPLATE = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)

_TWILIO_TIMEOUT = httpx.Timeout(10.0)
_TWILIO_MAX_RETRIES = 3


class TwilioClient:
    """Thin HTTP wrapper around the Twilio Messaging REST API.

    Raises ``NotConfiguredError`` on the first API call when
    ``TWILIO_ACCOUNT_SID`` or ``TWILIO_AUTH_TOKEN`` are empty strings.

    Outbound calls use a 10 s timeout and retry up to 3 times on 5xx or
    network errors with exponential back-off (1 s, 2 s). On definitive
    failure a structured ``twilio_dlq`` error is logged before re-raising.
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

    async def _post_message(
        self, to: str, from_: str, body: str, extra: Optional[dict[str, str]] = None
    ) -> str:
        """Send a Twilio Messages.json POST and return the message SID.

        Retries up to ``_TWILIO_MAX_RETRIES`` times on 5xx or transport errors
        with exponential back-off (2^(attempt-1) seconds). 4xx errors are
        raised immediately without retrying. After exhausting all attempts a
        structured ``twilio_dlq`` error is logged before the exception is
        re-raised.
        """
        self._assert_configured()

        url = _MESSAGES_URL_TEMPLATE.format(account_sid=self._account_sid)
        payload = {"To": to, "From": from_}
        if body:
            payload["Body"] = body
        if extra:
            payload.update(extra)

        last_exc: Exception | None = None
        for attempt in range(1, _TWILIO_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=_TWILIO_TIMEOUT) as client:
                    response = await client.post(
                        url,
                        data=payload,
                        auth=(self._account_sid, self._auth_token),
                    )

                if response.status_code in (200, 201):
                    data = response.json()
                    sid: str = data.get("sid", "")
                    logger.info(
                        "Twilio message sent: sid=%s to=%s attempt=%d", sid, to, attempt
                    )
                    return sid

                if response.status_code >= 500:
                    logger.warning(
                        "Twilio 5xx on attempt %d/%d status=%s",
                        attempt,
                        _TWILIO_MAX_RETRIES,
                        response.status_code,
                    )
                    last_exc = httpx.HTTPStatusError(
                        f"Server error {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                else:
                    # 4xx — permanent error, no point retrying
                    logger.error(
                        "Twilio API error %s: %s", response.status_code, response.text
                    )
                    response.raise_for_status()

            except httpx.TransportError as exc:
                logger.warning(
                    "Twilio network error on attempt %d/%d: %s",
                    attempt,
                    _TWILIO_MAX_RETRIES,
                    exc,
                )
                last_exc = exc

            if attempt < _TWILIO_MAX_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))

        # DLQ — all retries exhausted; log structured error for ops visibility
        logger.error(
            "twilio_dlq to=%s from=%s body=%r attempts=%d error=%r",
            to,
            from_,
            body,
            _TWILIO_MAX_RETRIES,
            last_exc,
        )
        raise last_exc or RuntimeError(
            f"Twilio: no successful response after {_TWILIO_MAX_RETRIES} attempts"
        )

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
            httpx.HTTPStatusError: On non-2xx response from Twilio after retries.
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
            httpx.HTTPStatusError: On non-2xx response from Twilio after retries.
        """
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        whatsapp_from = self._whatsapp_from or self._from_number
        return await self._post_message(to=to, from_=whatsapp_from, body=body)

    async def send_whatsapp_content(
        self, to: str, content_sid: str, variables: dict[str, str]
    ) -> str:
        """Send a WhatsApp message from a Twilio Content template (ContentSid).

        Used for quick-reply buttons (``twilio/quick-reply``, ADR-0007 §16.4).
        A business-initiated message needs a template approved by WhatsApp; a
        reply inside the 24 h customer-service window can use an unapproved
        (saved, not submitted) template, max 3 buttons. Twilio rejects the
        request (4xx) otherwise — callers fall back to plain text.

        Args:
            to: Destination WhatsApp number (``whatsapp:`` prefix optional).
            content_sid: ``HX…`` SID of the Content template.
            variables: Template variables, e.g. ``{"1": "Add 2 servers"}``.
        """
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"
        whatsapp_from = self._whatsapp_from or self._from_number
        return await self._post_message(
            to=to,
            from_=whatsapp_from,
            body="",
            extra={
                "ContentSid": content_sid,
                "ContentVariables": json.dumps(variables, ensure_ascii=False),
            },
        )

"""SendGrid integration client for outbound email delivery.

Uses httpx for all HTTP calls (no SendGrid SDK dependency).
SendGrid Mail Send API v3: https://docs.sendgrid.com/api-reference/mail-send/mail-send

Architecture constraints:
- Raises NotConfiguredError if the API key is absent (lazy-init pattern).
- All HTTP calls are performed with httpx (already a project dependency).
[Source: architecture.md#Integrations]
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.core import config
from app.core.exceptions import NotConfiguredError

logger = logging.getLogger(__name__)

_SENDGRID_MAIL_SEND_URL = "https://api.sendgrid.com/v3/mail/send"


class SendGridClient:
    """Thin HTTP wrapper around the SendGrid Mail Send v3 API.

    Raises ``NotConfiguredError`` on the first API call when
    ``SENDGRID_API_KEY`` is an empty string.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or config.SENDGRID_API_KEY
        self._from_email = from_email or config.SENDGRID_FROM_EMAIL

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _assert_configured(self) -> None:
        if not self._api_key:
            raise NotConfiguredError("SendGrid")

    # ──────────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────────

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send a transactional email via SendGrid.

        Args:
            to: Recipient email address (e.g. ``manager@hotel.com``).
            subject: Email subject line.
            body: Plain-text body of the email.

        Returns:
            ``True`` if the message was accepted by SendGrid (HTTP 202).

        Raises:
            NotConfiguredError: If ``SENDGRID_API_KEY`` is not set.
            httpx.HTTPStatusError: On non-2xx response from SendGrid.
        """
        self._assert_configured()

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self._from_email},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                _SENDGRID_MAIL_SEND_URL,
                json=payload,
                headers=headers,
            )

        if response.status_code not in (200, 202):
            logger.error(
                "SendGrid API error %s: %s", response.status_code, response.text
            )
            response.raise_for_status()

        logger.info("SendGrid email accepted: to=%s subject=%r", to, subject)
        return True

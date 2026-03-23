"""Tests for Story 4.1 (HOS-24): Twilio/WhatsApp/SendGrid outbound APIs.

All HTTP calls are mocked — no real messages are sent.
Covers: TwilioClient, SendGridClient, NotConfiguredError, and the
POST /api/v1/notifications/test route.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import NotConfiguredError
from app.integrations.sendgrid_client import SendGridClient
from app.integrations.twilio_client import TwilioClient
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_SID = "SM1234567890abcdef1234567890abcdef"

_TWILIO_OK_RESPONSE = MagicMock(
    status_code=201,
    json=MagicMock(return_value={"sid": FAKE_SID}),
    text="",
)

_SENDGRID_OK_RESPONSE = MagicMock(
    status_code=202,
    text="",
)


# ===========================================================================
# TwilioClient unit tests
# ===========================================================================


@pytest.mark.asyncio
async def test_twilio_client_send_sms_returns_sid():
    """TwilioClient.send_sms returns the Twilio message SID on success."""
    client = TwilioClient(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15005550006",
    )

    mock_response = MagicMock(
        status_code=201,
        json=MagicMock(return_value={"sid": FAKE_SID}),
        text="",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        sid = await client.send_sms(to="+33612345678", body="Hello from Aetherix")

    assert sid == FAKE_SID


@pytest.mark.asyncio
async def test_twilio_client_send_whatsapp_prefixes_number():
    """TwilioClient.send_whatsapp auto-prepends the 'whatsapp:' URI prefix."""
    client = TwilioClient(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15005550006",
        whatsapp_from="whatsapp:+14155238886",
    )

    captured: list[dict] = []

    async def fake_post(url, *, data, auth, **kwargs):
        captured.append({"url": url, "data": data})
        return MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": FAKE_SID}),
            text="",
        )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        sid = await client.send_whatsapp(to="+33612345678", body="WhatsApp test")

    assert sid == FAKE_SID
    # Verify the 'To' field has the whatsapp: prefix
    assert captured[0]["data"]["To"] == "whatsapp:+33612345678"


@pytest.mark.asyncio
async def test_twilio_client_send_whatsapp_already_prefixed_not_doubled():
    """send_whatsapp does not double-prefix an already-prefixed number."""
    client = TwilioClient(
        account_sid="ACtest",
        auth_token="token",
        from_number="+15005550006",
        whatsapp_from="whatsapp:+14155238886",
    )

    captured: list[dict] = []

    async def fake_post(url, *, data, auth, **kwargs):
        captured.append({"data": data})
        return MagicMock(
            status_code=201,
            json=MagicMock(return_value={"sid": FAKE_SID}),
            text="",
        )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=fake_post):
        await client.send_whatsapp(to="whatsapp:+33612345678", body="test")

    assert captured[0]["data"]["To"] == "whatsapp:+33612345678"


@pytest.mark.asyncio
async def test_twilio_not_configured_raises_error():
    """TwilioClient raises NotConfiguredError when credentials are empty."""
    client = TwilioClient(account_sid="", auth_token="", from_number="")

    with pytest.raises(NotConfiguredError) as exc_info:
        await client.send_sms(to="+33612345678", body="test")

    assert "Twilio" in str(exc_info.value)


@pytest.mark.asyncio
async def test_twilio_not_configured_whatsapp_raises_error():
    """NotConfiguredError is also raised for WhatsApp when creds are missing."""
    client = TwilioClient(account_sid="", auth_token="")

    with pytest.raises(NotConfiguredError):
        await client.send_whatsapp(to="+33612345678", body="test")


# ===========================================================================
# SendGridClient unit tests
# ===========================================================================


@pytest.mark.asyncio
async def test_sendgrid_client_send_email_success():
    """SendGridClient.send_email returns True on HTTP 202."""
    client = SendGridClient(
        api_key="SG.test_key",
        from_email="noreply@aetherix.io",
    )

    mock_response = MagicMock(status_code=202, text="")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.send_email(
            to="manager@hotel.com",
            subject="Test Subject",
            body="Hello manager",
        )

    assert result is True


@pytest.mark.asyncio
async def test_sendgrid_not_configured_raises_error():
    """SendGridClient raises NotConfiguredError when API key is empty."""
    client = SendGridClient(api_key="", from_email="noreply@aetherix.io")

    with pytest.raises(NotConfiguredError) as exc_info:
        await client.send_email(to="x@y.com", subject="S", body="B")

    assert "SendGrid" in str(exc_info.value)


@pytest.mark.asyncio
async def test_sendgrid_http_error_propagates():
    """SendGridClient propagates httpx.HTTPStatusError on non-2xx responses."""
    client = SendGridClient(api_key="SG.key", from_email="noreply@aetherix.io")

    bad_response = MagicMock(status_code=401, text="Unauthorized")
    bad_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=bad_response,
        )
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=bad_response):
        with pytest.raises(httpx.HTTPStatusError):
            await client.send_email(to="x@y.com", subject="S", body="B")


# ===========================================================================
# NotConfiguredError unit tests
# ===========================================================================


def test_not_configured_error_message_contains_service_name():
    """NotConfiguredError message includes the service name."""
    err = NotConfiguredError("MyService")
    assert "MyService" in str(err)
    assert err.service == "MyService"


# ===========================================================================
# POST /api/v1/notifications/test route tests
# ===========================================================================

_TEST_CLIENT = TestClient(app, raise_server_exceptions=False)


def test_test_notification_route_sms_returns_200():
    """Route returns 200 and a SID for SMS channel when Twilio is mocked."""
    mock_response = MagicMock(
        status_code=201,
        json=MagicMock(return_value={"sid": FAKE_SID}),
        text="",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        # Provide real-looking (non-empty) credentials via env override
        with patch("app.core.config.TWILIO_ACCOUNT_SID", "ACtest"), \
             patch("app.core.config.TWILIO_AUTH_TOKEN", "token"), \
             patch("app.core.config.TWILIO_FROM_NUMBER", "+15005550006"):
            resp = _TEST_CLIENT.post(
                "/api/v1/notifications/test",
                json={"channel": "sms", "to": "+33612345678", "message": "hello"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["channel"] == "sms"


def test_test_notification_route_whatsapp_returns_200():
    """Route returns 200 and a SID for WhatsApp channel when Twilio is mocked."""
    mock_response = MagicMock(
        status_code=201,
        json=MagicMock(return_value={"sid": FAKE_SID}),
        text="",
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with patch("app.core.config.TWILIO_ACCOUNT_SID", "ACtest"), \
             patch("app.core.config.TWILIO_AUTH_TOKEN", "token"), \
             patch("app.core.config.TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"):
            resp = _TEST_CLIENT.post(
                "/api/v1/notifications/test",
                json={"channel": "whatsapp", "to": "+33612345678", "message": "hello"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["channel"] == "whatsapp"


def test_test_notification_route_email_returns_200():
    """Route returns 200 for email channel when SendGrid is mocked."""
    mock_response = MagicMock(status_code=202, text="")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
        with patch("app.core.config.SENDGRID_API_KEY", "SG.test"):
            resp = _TEST_CLIENT.post(
                "/api/v1/notifications/test",
                json={
                    "channel": "email",
                    "to": "manager@hotel.com",
                    "message": "test email",
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["channel"] == "email"


def test_test_notification_route_invalid_channel_returns_422():
    """Route returns 422 for an unknown channel value."""
    resp = _TEST_CLIENT.post(
        "/api/v1/notifications/test",
        json={"channel": "telegram", "to": "+33612345678", "message": "hello"},
    )
    assert resp.status_code == 422


def test_test_notification_route_missing_to_field_returns_422():
    """Route returns 422 when the 'to' field is absent."""
    resp = _TEST_CLIENT.post(
        "/api/v1/notifications/test",
        json={"channel": "sms", "message": "hello"},
    )
    assert resp.status_code == 422


def test_test_notification_route_empty_message_returns_422():
    """Route returns 422 when 'message' is an empty string."""
    resp = _TEST_CLIENT.post(
        "/api/v1/notifications/test",
        json={"channel": "sms", "to": "+33612345678", "message": ""},
    )
    assert resp.status_code == 422


def test_test_notification_route_empty_to_returns_422():
    """Route returns 422 when 'to' is an empty string."""
    resp = _TEST_CLIENT.post(
        "/api/v1/notifications/test",
        json={"channel": "email", "to": "", "message": "hello"},
    )
    assert resp.status_code == 422


def test_test_notification_route_not_configured_returns_503():
    """Route returns 503 when Twilio credentials are not set (empty strings)."""
    with patch("app.core.config.TWILIO_ACCOUNT_SID", ""), \
         patch("app.core.config.TWILIO_AUTH_TOKEN", ""):
        resp = _TEST_CLIENT.post(
            "/api/v1/notifications/test",
            json={"channel": "sms", "to": "+33612345678", "message": "hello"},
        )

    assert resp.status_code == 503

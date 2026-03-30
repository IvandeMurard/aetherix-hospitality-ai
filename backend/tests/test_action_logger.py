"""Tests for Story 4.3 (HOS-26): Action Logging Accept/Reject via Twilio webhook.

Coverage:
- parse_action() — case-insensitive parsing (AC#1)
- ActionLoggerService — DB write, status transitions, not-found paths (AC#2, AC#3)
- POST /webhooks/twilio/inbound — TwiML responses, Content-Type (AC#4, AC#6)
- Signature validation bypass in test mode (AC#8)

All DB calls are mocked — no real database connection required.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.webhook import ActionType
from app.services.action_logger import ActionLoggerService, parse_action


# ===========================================================================
# parse_action — unit tests
# ===========================================================================

class TestParseAction:
    """AC#1: case-insensitive parsing of Accept / Reject."""

    # -- Accept variants --

    def test_parse_action_accept_uppercase(self):
        assert parse_action("ACCEPT") == ActionType.accept

    def test_parse_action_accept_titlecase(self):
        assert parse_action("Accept") == ActionType.accept

    def test_parse_action_accept_lowercase(self):
        assert parse_action("accept") == ActionType.accept

    def test_parse_action_accept_with_whitespace(self):
        assert parse_action("  ACCEPT  ") == ActionType.accept

    # -- Reject variants --

    def test_parse_action_reject_uppercase(self):
        assert parse_action("REJECT") == ActionType.reject

    def test_parse_action_reject_titlecase(self):
        assert parse_action("Reject") == ActionType.reject

    def test_parse_action_reject_lowercase(self):
        assert parse_action("reject") == ActionType.reject

    # -- Unknown variants --

    def test_parse_action_unknown_returns_unknown(self):
        assert parse_action("maybe") == ActionType.unknown

    def test_parse_action_empty_string_returns_unknown(self):
        assert parse_action("") == ActionType.unknown

    def test_parse_action_partial_word_returns_unknown(self):
        assert parse_action("acc") == ActionType.unknown


# ===========================================================================
# Helpers for ActionLoggerService tests
# ===========================================================================

def _make_profile(phone: str = "+33600000001"):
    profile = MagicMock()
    profile.id = uuid.uuid4()
    profile.tenant_id = "tenant-abc"
    profile.phone_number = phone
    return profile


def _make_recommendation(status: str = "dispatched"):
    rec = MagicMock()
    rec.id = uuid.uuid4()
    rec.status = status
    rec.action = None
    rec.actioned_at = None
    return rec


def _make_session(profile=None, recommendation=None):
    """Build an AsyncSession mock returning *profile* on first execute(),
    *recommendation* on second execute()."""
    session = AsyncMock()

    profile_result = MagicMock()
    profile_scalars = MagicMock()
    profile_scalars.first.return_value = profile
    profile_result.scalars.return_value = profile_scalars

    rec_result = MagicMock()
    rec_scalars = MagicMock()
    rec_scalars.first.return_value = recommendation
    rec_result.scalars.return_value = rec_scalars

    session.execute = AsyncMock(side_effect=[profile_result, rec_result])
    session.commit = AsyncMock()
    return session


# ===========================================================================
# ActionLoggerService — unit tests
# ===========================================================================

class TestActionLoggerService:

    @pytest.mark.asyncio
    async def test_log_action_accept_updates_status_to_accepted(self):
        profile = _make_profile()
        rec = _make_recommendation()
        session = _make_session(profile=profile, recommendation=rec)

        result = await ActionLoggerService().log_action("+33600000001", ActionType.accept, session)

        assert result["status"] == "logged"
        assert result["action"] == "accepted"
        assert rec.status == "accepted"

    @pytest.mark.asyncio
    async def test_log_action_reject_updates_status_to_rejected(self):
        profile = _make_profile()
        rec = _make_recommendation()
        session = _make_session(profile=profile, recommendation=rec)

        result = await ActionLoggerService().log_action("+33600000001", ActionType.reject, session)

        assert result["status"] == "logged"
        assert result["action"] == "rejected"
        assert rec.status == "rejected"

    @pytest.mark.asyncio
    async def test_log_action_sets_actioned_at(self):
        profile = _make_profile()
        rec = _make_recommendation()
        session = _make_session(profile=profile, recommendation=rec)

        await ActionLoggerService().log_action("+33600000001", ActionType.accept, session)

        assert rec.actioned_at is not None
        assert isinstance(rec.actioned_at, datetime)

    @pytest.mark.asyncio
    async def test_log_action_no_recommendation_returns_not_found(self):
        profile = _make_profile()
        session = _make_session(profile=profile, recommendation=None)

        result = await ActionLoggerService().log_action("+33600000001", ActionType.accept, session)

        assert result == {"status": "not_found"}
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_action_no_profile_returns_not_found(self):
        session = _make_session(profile=None, recommendation=None)

        result = await ActionLoggerService().log_action("+33600000001", ActionType.accept, session)

        assert result == {"status": "not_found"}

    @pytest.mark.asyncio
    async def test_log_action_strips_whatsapp_prefix(self):
        """Twilio WhatsApp numbers arrive prefixed with 'whatsapp:'."""
        profile = _make_profile(phone="+33600000001")
        rec = _make_recommendation()
        session = _make_session(profile=profile, recommendation=rec)

        result = await ActionLoggerService().log_action(
            "whatsapp:+33600000001", ActionType.accept, session
        )

        assert result["status"] == "logged"

    @pytest.mark.asyncio
    async def test_log_action_commits_session(self):
        profile = _make_profile()
        rec = _make_recommendation()
        session = _make_session(profile=profile, recommendation=rec)

        await ActionLoggerService().log_action("+33600000001", ActionType.accept, session)

        session.commit.assert_awaited_once()


# ===========================================================================
# Webhook route — integration tests with TestClient (mocked DB + service)
# ===========================================================================

def _make_webhook_app() -> FastAPI:
    from app.api.routes.webhook import router

    app = FastAPI()
    app.include_router(router)
    return app


async def _fake_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    yield session


@pytest.fixture(autouse=False)
def webhook_client(monkeypatch):
    """TestClient with TWILIO_SKIP_SIGNATURE_VALIDATION=true and no-op DB."""
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")

    from app.db.session import get_db

    app = _make_webhook_app()
    app.dependency_overrides[get_db] = _fake_db

    with patch(
        "app.api.routes.webhook.ActionLoggerService.log_action",
        new_callable=AsyncMock,
        return_value={"status": "logged", "recommendation_id": str(uuid.uuid4()), "action": "accepted"},
    ):
        with TestClient(app) as client:
            yield client


def test_webhook_accept_returns_twiml_accept_message(webhook_client):
    """AC#6 + AC#1: Accept reply → TwiML with acceptance confirmation."""
    resp = webhook_client.post(
        "/webhooks/twilio/inbound",
        data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
    )
    assert resp.status_code == 200
    assert "Good luck tonight" in resp.text or "accepted" in resp.text.lower()


def test_webhook_reject_returns_twiml_reject_message(webhook_client):
    """AC#6 + AC#1: Reject reply → TwiML with rejection message."""
    with patch(
        "app.api.routes.webhook.ActionLoggerService.log_action",
        new_callable=AsyncMock,
        return_value={"status": "logged", "recommendation_id": str(uuid.uuid4()), "action": "rejected"},
    ):
        resp = webhook_client.post(
            "/webhooks/twilio/inbound",
            data={"From": "+33600000001", "Body": "REJECT", "To": "+14155238886"},
        )
    assert resp.status_code == 200
    assert "No action will be taken" in resp.text or "rejected" in resp.text.lower()


def test_webhook_unknown_returns_query_ack(webhook_client):
    """Story 5.1: Unknown input (non-ACCEPT/REJECT) → conversational query-ack TwiML.

    Since Story 5.1, unknown messages are treated as conversational queries and
    receive a query-acknowledgement reply, not a help-message prompt.
    """
    with patch("app.api.routes.webhook.QueryParserService") as MockParser, \
         patch("app.api.routes.webhook.ExplainabilityService") as MockExplainer:
        mock_parser_instance = AsyncMock()
        mock_parser_instance.parse_and_store = AsyncMock(
            return_value={"status": "stored", "query_id": str(__import__("uuid").uuid4())}
        )
        MockParser.return_value = mock_parser_instance
        mock_explainer_instance = AsyncMock()
        mock_explainer_instance.generate_and_send = AsyncMock(return_value={"status": "sent"})
        MockExplainer.return_value = mock_explainer_instance

        resp = webhook_client.post(
            "/webhooks/twilio/inbound",
            data={"From": "+33600000001", "Body": "maybe", "To": "+14155238886"},
        )
    assert resp.status_code == 200
    assert "looking into it" in resp.text or "Got your question" in resp.text


def test_webhook_returns_xml_content_type(webhook_client):
    """AC#6: Content-Type must be application/xml."""
    resp = webhook_client.post(
        "/webhooks/twilio/inbound",
        data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
    )
    assert "application/xml" in resp.headers.get("content-type", "")


def test_webhook_response_is_valid_twiml(webhook_client):
    """AC#6: Response is parseable TwiML XML with a <Response> root."""
    import xml.etree.ElementTree as ET

    resp = webhook_client.post(
        "/webhooks/twilio/inbound",
        data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
    )
    root = ET.fromstring(resp.text)
    assert root.tag == "Response"


def test_webhook_signature_validation_skipped_in_test_mode(monkeypatch):
    """AC#8: When TWILIO_SKIP_SIGNATURE_VALIDATION=true, no X-Twilio-Signature required."""
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")

    from app.db.session import get_db

    app = _make_webhook_app()
    app.dependency_overrides[get_db] = _fake_db

    with patch(
        "app.api.routes.webhook.ActionLoggerService.log_action",
        new_callable=AsyncMock,
        return_value={"status": "not_found"},
    ):
        with TestClient(app) as client:
            # No X-Twilio-Signature header — should still succeed
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
            )
    assert resp.status_code == 200


def test_webhook_unknown_does_not_call_log_action(monkeypatch):
    """Story 5.1 + AC#4: Unknown action routes to conversational path; log_action NOT called."""
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")

    from app.db.session import get_db

    app = _make_webhook_app()
    app.dependency_overrides[get_db] = _fake_db

    mock_log = AsyncMock()
    mock_parser_instance = AsyncMock()
    mock_parser_instance.parse_and_store = AsyncMock(
        return_value={"status": "stored", "query_id": str(__import__("uuid").uuid4())}
    )
    mock_explainer_instance = AsyncMock()
    mock_explainer_instance.generate_and_send = AsyncMock(return_value={"status": "sent"})

    with patch("app.api.routes.webhook.ActionLoggerService.log_action", mock_log), \
         patch("app.api.routes.webhook.QueryParserService", return_value=mock_parser_instance), \
         patch("app.api.routes.webhook.ExplainabilityService", return_value=mock_explainer_instance):
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "helloworld", "To": "+14155238886"},
            )

    assert resp.status_code == 200
    mock_log.assert_not_called()

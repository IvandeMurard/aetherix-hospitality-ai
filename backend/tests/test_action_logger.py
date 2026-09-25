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
from datetime import datetime
from types import SimpleNamespace
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
    from app.api.routes.twilio_inbound import router

    app = FastAPI()
    app.include_router(router)
    return app


async def _fake_db():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    yield session


_PROFILE = SimpleNamespace(id=uuid.uuid4(), tenant_id="hotel_t", phone_number="+33600000001")


@pytest.fixture(autouse=False)
def webhook_client(monkeypatch):
    """TestClient with TWILIO_SKIP_SIGNATURE_VALIDATION=true, no-op DB, a known
    sender, and the decision service stubbed (its logic is covered in
    tests/services/test_inbound_decision.py)."""
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")

    from app.db.session import get_db

    app = _make_webhook_app()
    app.dependency_overrides[get_db] = _fake_db

    async def _deterministic(self, profile, body, button_payload, now, request_id=""):
        from app.services.inbound_decision import ReplyPlan

        action = parse_action(body)
        if action == ActionType.accept:
            return ReplyPlan(text="Validation enregistrée.", result="recorded", decision="accepted")
        if action == ActionType.reject:
            return ReplyPlan(text="Refus enregistré. Une raison ? (facultatif)",
                             result="recorded", decision="rejected")
        return None

    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=_PROFILE,
    ), patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.handle_deterministic",
        _deterministic,
    ):
        with TestClient(app) as client:
            yield client


def test_webhook_accept_returns_twiml_recorded_message(webhook_client):
    """AC#6 + AC#1: Accept reply → TwiML confirming the recorded decision."""
    resp = webhook_client.post(
        "/webhooks/twilio/inbound",
        data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
    )
    assert resp.status_code == 200
    assert "Validation enregistrée" in resp.text


def test_webhook_reject_returns_twiml_with_optional_reason(webhook_client):
    resp = webhook_client.post(
        "/webhooks/twilio/inbound",
        data={"From": "+33600000001", "Body": "REJECT", "To": "+14155238886"},
    )
    assert resp.status_code == 200
    assert "Refus enregistré" in resp.text and "facultatif" in resp.text


def test_webhook_unknown_returns_query_ack(webhook_client):
    """P2-4: free text → receipt-feedback background task → query-ack TwiML."""
    with patch("app.api.routes.twilio_inbound._bg_receipt_feedback", new_callable=AsyncMock):
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


def _no_profile_client(monkeypatch):
    monkeypatch.setenv("TWILIO_SKIP_SIGNATURE_VALIDATION", "true")
    from app.db.session import get_db

    app = _make_webhook_app()
    app.dependency_overrides[get_db] = _fake_db
    return app


def test_webhook_signature_validation_skipped_in_test_mode(monkeypatch):
    """AC#8: When TWILIO_SKIP_SIGNATURE_VALIDATION=true, no X-Twilio-Signature required."""
    app = _no_profile_client(monkeypatch)
    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=None,
    ):
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "Accept", "To": "+14155238886"},
            )
    assert resp.status_code == 200


def test_webhook_keyword_from_unknown_sender_is_not_recorded(monkeypatch):
    """A decision with no known sender has nothing to attach to — the old route
    replied "accepted" even when nothing was found."""
    app = _no_profile_client(monkeypatch)
    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=None,
    ), patch("app.api.routes.twilio_inbound._bg_receipt_feedback", new_callable=AsyncMock) as bg:
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000009", "Body": "oui", "To": "+14155238886"},
            )
    assert "couldn't find an active recommendation" in resp.text
    bg.assert_not_called()


def test_webhook_free_text_goes_to_background(monkeypatch):
    """P2-4 + AC#4: free text routes to the receipt-feedback path, not the
    deterministic one."""
    app = _no_profile_client(monkeypatch)
    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=_PROFILE,
    ), patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.handle_deterministic",
        new_callable=AsyncMock, return_value=None,
    ), patch("app.api.routes.twilio_inbound._bg_receipt_feedback", new_callable=AsyncMock) as bg:
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "helloworld", "To": "+14155238886"},
            )

    assert resp.status_code == 200
    bg.assert_called_once()


def test_webhook_confirmation_with_buttons_sent_out_of_band(monkeypatch):
    """With buttons enabled, a confirmation goes out via the Content API (REST)
    and the TwiML response is empty — TwiML cannot carry quick replies."""
    from app.core import config
    from app.services.inbound_decision import ReplyPlan

    monkeypatch.setattr(config, "WHATSAPP_DECISION_BUTTONS", True)
    monkeypatch.setattr(config, "TWILIO_CONTENT_SID_CONFIRM_FR", "HXconfirm")
    app = _no_profile_client(monkeypatch)
    plan = ReplyPlan(text="Je note un refus, c'est bien ça ? Répondez OUI ou NON.",
                     buttons="confirm", result="confirmation_requested", decision="rejected")
    content = AsyncMock(return_value="SM1")
    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=_PROFILE,
    ), patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.handle_deterministic",
        new_callable=AsyncMock, return_value=plan,
    ), patch("app.api.routes.twilio_inbound._twilio_client.send_whatsapp_content", content):
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "non merci", "To": "+14155238886"},
            )
    assert "<Message>" not in resp.text
    content.assert_awaited_once()
    assert content.await_args.args[1] == "HXconfirm"


def test_webhook_passes_button_payload_to_decision_service(monkeypatch):
    """Décision #38: a quick-reply tap reaches the deterministic path with its
    fixed payload id; the typed Body is not what decides."""
    from app.services.inbound_decision import ReplyPlan

    app = _no_profile_client(monkeypatch)
    handler = AsyncMock(return_value=ReplyPlan(text="Validation enregistrée.", result="recorded"))
    with patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.profile_for",
        new_callable=AsyncMock, return_value=_PROFILE,
    ), patch(
        "app.api.routes.twilio_inbound.InboundDecisionService.handle_deterministic", handler,
    ):
        with TestClient(app) as client:
            resp = client.post(
                "/webhooks/twilio/inbound",
                data={"From": "+33600000001", "Body": "Accepter", "To": "+14155238886",
                      "ButtonText": "Accepter", "ButtonPayload": "aetherix.decision.accept"},
            )
    assert "Validation enregistrée" in resp.text
    assert handler.await_args.args[2] == "aetherix.decision.accept"

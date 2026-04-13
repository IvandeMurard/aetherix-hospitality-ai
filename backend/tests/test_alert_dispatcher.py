"""Tests for Story 4.2 (HOS-25): Format & Dispatch Alerts.

All tests mock TwilioClient and SendGridClient — no real HTTP calls are made.

Minimum 13 tests required by the story spec.

Coverage:
  - test_dispatch_one_whatsapp_calls_send_whatsapp
  - test_dispatch_one_sms_calls_send_sms
  - test_dispatch_one_email_calls_send_email
  - test_dispatch_one_updates_status_to_dispatched
  - test_dispatch_one_sets_dispatched_at
  - test_dispatch_one_not_configured_skips_gracefully
  - test_dispatch_one_already_dispatched_skipped  (idempotency)
  - test_run_pending_processes_all_ready_to_push
  - test_run_pending_skips_dispatched
  - test_dispatch_route_returns_202
  - test_dispatch_failure_leaves_status_ready_to_push
  - test_dispatch_one_unknown_channel_falls_back_to_whatsapp  (edge)
  - test_dispatch_one_missing_profile_returns_false            (edge)
  - test_run_pending_no_recommendations_does_nothing           (edge)
  - test_dispatch_one_email_uses_correct_subject               (edge)
  - test_format_message_includes_triggering_factor
  - test_format_message_without_triggering_factor
  - test_dispatch_route_returns_accepted_status
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.models import RestaurantProfile, StaffingRecommendation
from app.services.alert_dispatcher import AlertDispatcherService, _format_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rec(
    status: str = "ready_to_push",
    channel: str = "whatsapp",
    message_text: str = "Call in 2 extra servers for dinner.",
    triggering_factor: str = "High occupancy expected: 92%",
    property_id: str | None = None,
    rec_id: str | None = None,
) -> MagicMock:
    rec = MagicMock(spec=StaffingRecommendation)
    rec.id = rec_id or uuid.uuid4()
    rec.status = status
    rec.message_text = message_text
    rec.triggering_factor = triggering_factor
    rec.property_id = property_id or str(uuid.uuid4())
    rec.dispatched_at = None
    rec.dispatch_channel = None
    return rec


def _make_profile(
    channel: str = "whatsapp",
    phone: str = "+33600000000",
    email: str = "gm@hotel.com",
    tenant_id: str | None = None,
) -> MagicMock:
    profile = MagicMock(spec=RestaurantProfile)
    profile.tenant_id = tenant_id or str(uuid.uuid4())
    profile.preferred_channel = channel
    profile.phone_number = phone
    profile.notification_email = email
    return profile


def _make_session(profile: RestaurantProfile | None = None):
    """Build a minimal AsyncSession mock that yields the given profile."""
    session = AsyncMock()

    async def _execute(stmt):
        result = MagicMock()
        result.scalars.return_value.first.return_value = profile
        result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# dispatch_one — channel routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_one_whatsapp_calls_send_whatsapp():
    rec = _make_rec(channel="whatsapp")
    profile = _make_profile(channel="whatsapp", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is True
    mock_instance.send_whatsapp.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_one_sms_calls_send_sms():
    rec = _make_rec(channel="sms")
    profile = _make_profile(channel="sms", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is True
    mock_instance.send_sms.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_one_email_calls_send_email():
    rec = _make_rec(channel="email")
    profile = _make_profile(channel="email", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.SendGridClient") as MockSG:
        mock_instance = AsyncMock()
        MockSG.return_value = mock_instance
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is True
    mock_instance.send_email.assert_awaited_once()


# ---------------------------------------------------------------------------
# dispatch_one — status updates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_one_updates_status_to_dispatched():
    rec = _make_rec(channel="whatsapp")
    profile = _make_profile(channel="whatsapp", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        await AlertDispatcherService().dispatch_one(rec, session)

    assert rec.status == "dispatched"
    assert rec.dispatch_channel == "whatsapp"


@pytest.mark.asyncio
async def test_dispatch_one_sets_dispatched_at():
    rec = _make_rec(channel="whatsapp")
    profile = _make_profile(channel="whatsapp", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    before = datetime.now(tz=timezone.utc)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        await AlertDispatcherService().dispatch_one(rec, session)

    assert rec.dispatched_at is not None
    assert rec.dispatched_at >= before


# ---------------------------------------------------------------------------
# dispatch_one — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_one_not_configured_skips_gracefully():
    """NotConfiguredError must log a warning, set status to config_error, and return False."""
    from app.core.exceptions import NotConfiguredError

    rec = _make_rec(channel="whatsapp")
    profile = _make_profile(channel="whatsapp", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch(
        "app.services.alert_dispatcher.TwilioClient",
        side_effect=NotConfiguredError("Twilio"),
    ):
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is False
    assert rec.status == "config_error"  # permanently broken config
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_dispatch_one_already_dispatched_skipped():
    """Idempotency: already-dispatched recommendations must never be re-sent."""
    rec = _make_rec(status="dispatched")
    session = _make_session()

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is False
    MockTwilio.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_failure_leaves_status_ready_to_push():
    """On unexpected dispatch error, status must remain ready_to_push."""
    rec = _make_rec(channel="whatsapp")
    profile = _make_profile(channel="whatsapp", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        mock_instance.send_whatsapp.side_effect = RuntimeError("Network error")
        MockTwilio.return_value = mock_instance

        with pytest.raises(RuntimeError):
            await AlertDispatcherService().dispatch_one(rec, session)

    assert rec.status == "ready_to_push"
    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pending_processes_all_ready_to_push():
    """run_pending dispatches every ready_to_push recommendation."""
    prop_id = str(uuid.uuid4())
    rec1 = _make_rec(property_id=prop_id)
    rec2 = _make_rec(property_id=prop_id, rec_id=uuid.uuid4())
    profile = _make_profile(tenant_id=prop_id)

    session = AsyncMock()

    call_count = 0

    async def _execute(stmt):
        nonlocal call_count
        result = MagicMock()
        call_count += 1
        if call_count == 1:
            # First call: return pending recommendations list
            result.scalars.return_value.all.return_value = [rec1, rec2]
            result.scalars.return_value.first.return_value = None
        else:
            # Subsequent calls: profile lookup
            result.scalars.return_value.first.return_value = profile
            result.scalars.return_value.all.return_value = []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    session.commit = AsyncMock()

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        await AlertDispatcherService().run_pending(session)

    assert rec1.status == "dispatched"
    assert rec2.status == "dispatched"


@pytest.mark.asyncio
async def test_run_pending_skips_dispatched():
    """run_pending with empty result set (already dispatched) must not dispatch anything."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result_mock)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        await AlertDispatcherService().run_pending(session)

    MockTwilio.assert_not_called()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_one_unknown_channel_falls_back_to_whatsapp():
    """Unknown channel must fall back to WhatsApp instead of crashing."""
    rec = _make_rec()
    profile = _make_profile(channel="telegram", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        mock_instance = AsyncMock()
        MockTwilio.return_value = mock_instance
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is True
    mock_instance.send_whatsapp.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_one_missing_profile_returns_false():
    """When no restaurant profile exists for the property, skip gracefully."""
    rec = _make_rec()
    session = _make_session(profile=None)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        result = await AlertDispatcherService().dispatch_one(rec, session)

    assert result is False
    MockTwilio.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_pending_no_recommendations_does_nothing():
    """run_pending with empty result set must not attempt any dispatch."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result_mock)

    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        await AlertDispatcherService().run_pending(session)

    MockTwilio.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_one_email_uses_correct_subject():
    """Email dispatch must use the 'Aetherix Staffing Alert' subject."""
    rec = _make_rec(channel="email")
    profile = _make_profile(channel="email", tenant_id=str(rec.property_id))
    session = _make_session(profile=profile)

    with patch("app.services.alert_dispatcher.SendGridClient") as MockSG:
        mock_instance = AsyncMock()
        MockSG.return_value = mock_instance
        await AlertDispatcherService().dispatch_one(rec, session)

    call_kwargs = mock_instance.send_email.call_args
    # subject may be positional or keyword
    args = call_kwargs.args
    kwargs = call_kwargs.kwargs
    subject = kwargs.get("subject") or (args[1] if len(args) > 1 else "")
    assert "Aetherix" in subject


# ---------------------------------------------------------------------------
# _format_message unit tests
# ---------------------------------------------------------------------------


def test_format_message_includes_triggering_factor():
    """_format_message must append triggering_factor to the body."""
    rec = _make_rec(
        message_text="Call in 2 extra servers.",
        triggering_factor="High occupancy: 92%",
    )
    msg = _format_message(rec)
    assert "Call in 2 extra servers." in msg
    assert "High occupancy: 92%" in msg


def test_format_message_without_triggering_factor():
    """_format_message must work when triggering_factor is None."""
    rec = _make_rec(message_text="No changes needed.", triggering_factor=None)
    msg = _format_message(rec)
    assert "No changes needed." in msg
    assert "Context:" not in msg


# ---------------------------------------------------------------------------
# Route integration tests — POST /api/v1/notifications/dispatch → 202
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    from fastapi import FastAPI as _FastAPI, HTTPException
    from app.api.routes.notifications import router
    from app.core.error_handlers import problem_details_handler

    test_app = _FastAPI()
    test_app.add_exception_handler(HTTPException, problem_details_handler)
    test_app.include_router(router, prefix="/api/v1")
    return test_app


@pytest.fixture
def notifications_client():
    """TestClient with get_db overridden and run_pending mocked."""
    from app.db.session import get_db

    app = _build_test_app()

    async def _mock_db():
        db = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = _mock_db

    with patch(
        "app.services.alert_dispatcher.AlertDispatcherService.run_pending",
        new_callable=AsyncMock,
    ):
        yield TestClient(app)


def test_dispatch_route_returns_202(notifications_client):
    """POST /api/v1/notifications/dispatch must return 202 Accepted."""
    response = notifications_client.post("/api/v1/notifications/dispatch")
    assert response.status_code == 202


def test_dispatch_route_returns_accepted_status(notifications_client):
    """Response body must include status=accepted."""
    response = notifications_client.post("/api/v1/notifications/dispatch")
    data = response.json()
    assert data.get("status") == "accepted"

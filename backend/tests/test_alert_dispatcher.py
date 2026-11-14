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
  - test_run_pending_processes_all_ready_to_push  (real SQLite, HOS-369)
  - HOS-369: atomic claim, two concurrent workers, lease recovery, bounded retries
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

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base, RestaurantProfile, StaffingRecommendation
from app.services import alert_dispatcher as ad
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


def test_format_message_does_not_repeat_a_factor_already_in_the_message():
    """The formatter writes "Trigger: <factor>"; the dispatcher must not add it twice."""
    rec = _make_rec(
        message_text="Add 2 staff for 19:00–23:00. Trigger: match à 2 km (21:00).",
        triggering_factor="match à 2 km (21:00)",
    )
    msg = _format_message(rec)
    assert msg.count("match à 2 km (21:00)") == 1
    assert "Context:" not in msg


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
    from fastapi import FastAPI as _FastAPI
    from fastapi import HTTPException

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
    from app.core.security import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {"id": "ops", "is_superuser": True}

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

# ---------------------------------------------------------------------------
# HOS-369 (16.48) — atomic claim, recovery, bounded retries (real SQLite)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'd.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed(factory, n: int = 1, *, with_profile: bool = True) -> list[uuid.UUID]:
    now = datetime.now(tz=timezone.utc)
    ids = []
    async with factory() as s:
        for _ in range(n):
            prop = uuid.uuid4()
            if with_profile:
                s.add(
                    RestaurantProfile(
                        id=prop, property_id=prop, tenant_id=f"t_{prop}",
                        property_name="H", outlet_name="O", total_seats=40,
                        preferred_channel="whatsapp", phone_number="+33600000000",
                    )
                )
            rec = StaffingRecommendation(
                id=uuid.uuid4(), tenant_id=f"t_{prop}", property_id=prop,
                anomaly_id=uuid.uuid4(), message_text="Add 2 servers.",
                window_start=now, window_end=now, status="ready_to_push",
            )
            s.add(rec)
            ids.append(rec.id)
        await s.commit()
    return ids


async def _row(factory, rec_id) -> StaffingRecommendation:
    async with factory() as s:
        return (
            await s.execute(select(StaffingRecommendation).where(StaffingRecommendation.id == rec_id))
        ).scalars().one()


async def _expire_lease(factory, rec_id) -> None:
    """Move the clock past the lease by rewinding it (no sleeping)."""
    async with factory() as s:
        await s.execute(
            StaffingRecommendation.__table__.update()
            .where(StaffingRecommendation.id == rec_id)
            .values(dispatch_claimed_at=datetime.now(tz=timezone.utc) - ad.CLAIM_LEASE - timedelta(seconds=1))
        )
        await s.commit()


def _twilio(send_error: Exception | None = None, delay: float = 0.0):
    inst = AsyncMock()

    async def _send(**kw):
        if delay:
            await asyncio.sleep(delay)
        if send_error:
            raise send_error

    inst.send_whatsapp.side_effect = _send
    return inst


@pytest.mark.asyncio
async def test_run_pending_processes_all_ready_to_push(factory):
    ids = await _seed(factory, 2)
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        inst = _twilio()
        MockTwilio.return_value = inst
        async with factory() as s:
            summary = await AlertDispatcherService().run_pending(s)
    assert (summary.claimed, summary.dispatched, summary.failed) == (2, 2, 0)
    assert inst.send_whatsapp.await_count == 2
    for i in ids:
        r = await _row(factory, i)
        assert r.status == "dispatched" and r.dispatched_at is not None


@pytest.mark.asyncio
async def test_two_concurrent_workers_send_exactly_once(factory):
    """AC2: two workers racing on the same rows -> each recommendation sent once."""
    ids = await _seed(factory, 3)
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        inst = _twilio(delay=0.05)
        MockTwilio.return_value = inst

        async def worker():
            async with factory() as s:
                return await AlertDispatcherService().run_pending(s)

        s1, s2 = await asyncio.gather(worker(), worker())
    assert inst.send_whatsapp.await_count == 3
    assert s1.dispatched + s2.dispatched == 3
    assert s1.claimed + s2.claimed == 3
    for i in ids:
        assert (await _row(factory, i)).status == "dispatched"


@pytest.mark.asyncio
async def test_claim_is_atomic_single_winner(factory):
    (rec_id,) = await _seed(factory)
    now = datetime.now(tz=timezone.utc)
    async with factory() as a, factory() as b:
        won_a = await AlertDispatcherService._claim(a, rec_id, now)
        won_b = await AlertDispatcherService._claim(b, rec_id, now)
    assert (won_a, won_b) == (True, False)
    assert (await _row(factory, rec_id)).dispatch_attempts == 1


@pytest.mark.asyncio
async def test_crashed_worker_row_is_reclaimed_after_lease(factory):
    """AC3: claim without send (worker died) -> not stuck, re-claimed after the lease."""
    (rec_id,) = await _seed(factory)
    async with factory() as s:
        assert await AlertDispatcherService._claim(s, rec_id, datetime.now(tz=timezone.utc))  # dies here
    await _expire_lease(factory, rec_id)
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        inst = _twilio()
        MockTwilio.return_value = inst
        async with factory() as s:
            summary = await AlertDispatcherService().run_pending(s)
    assert summary.dispatched == 1
    inst.send_whatsapp.assert_awaited_once()
    assert (await _row(factory, rec_id)).status == "dispatched"


@pytest.mark.asyncio
async def test_live_lease_blocks_second_worker(factory):
    (rec_id,) = await _seed(factory)
    async with factory() as s:
        assert await AlertDispatcherService._claim(s, rec_id, datetime.now(tz=timezone.utc))
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio:
        async with factory() as s:
            summary = await AlertDispatcherService().run_pending(s)
    assert summary.claimed == 0
    MockTwilio.assert_not_called()


@pytest.mark.asyncio
async def test_failed_send_is_logged_traced_counted_and_retried(factory, caplog):
    """AC4: no swallow -> logger.exception + guardrail_trip + counted; row retried."""
    (rec_id,) = await _seed(factory)
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio, patch(
        "app.services.alert_dispatcher.guardrail_trip"
    ) as trip, caplog.at_level("ERROR"):
        MockTwilio.return_value = _twilio(RuntimeError("boom"))
        async with factory() as s:
            summary = await AlertDispatcherService().run_pending(s)
    assert (summary.claimed, summary.failed, summary.dispatched) == (1, 1, 0)
    assert any("Dispatch failed for recommendation" in r.message for r in caplog.records)
    assert trip.call_args.args[2] == ad.REASON_SEND_FAILED
    r = await _row(factory, rec_id)
    assert r.status == "ready_to_push" and r.dispatch_attempts == 1  # retried after the lease

    # Right after: the lease holds, the provider is not hammered.
    with patch("app.services.alert_dispatcher.TwilioClient"):
        async with factory() as s:
            assert (await AlertDispatcherService().run_pending(s)).claimed == 0


@pytest.mark.asyncio
async def test_retries_are_bounded_then_dispatch_failed(factory):
    (rec_id,) = await _seed(factory)
    with patch("app.services.alert_dispatcher.TwilioClient") as MockTwilio, patch(
        "app.services.alert_dispatcher.guardrail_trip"
    ) as trip, patch("app.services.ops_dispatcher.dispatch_error", new=AsyncMock()) as alert:
        inst = _twilio(RuntimeError("boom"))
        MockTwilio.return_value = inst
        for _ in range(ad.MAX_DISPATCH_ATTEMPTS + 2):
            await _expire_lease(factory, rec_id)
            async with factory() as s:
                await AlertDispatcherService().run_pending(s)
    assert inst.send_whatsapp.await_count == ad.MAX_DISPATCH_ATTEMPTS  # bound respected
    r = await _row(factory, rec_id)
    assert r.status == "dispatch_failed" and r.dispatch_attempts == ad.MAX_DISPATCH_ATTEMPTS
    reasons = [c.args[2] for c in trip.call_args_list]
    assert reasons.count(ad.REASON_SEND_FAILED) == ad.MAX_DISPATCH_ATTEMPTS
    assert reasons.count(ad.REASON_RETRIES_EXHAUSTED) == 1
    alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_profile_is_bounded_not_retried_forever(factory):
    (rec_id,) = await _seed(factory, with_profile=False)
    with patch("app.services.ops_dispatcher.dispatch_error", new=AsyncMock()):
        for _ in range(ad.MAX_DISPATCH_ATTEMPTS):
            await _expire_lease(factory, rec_id)
            async with factory() as s:
                await AlertDispatcherService().run_pending(s)
    assert (await _row(factory, rec_id)).status == "dispatch_failed"

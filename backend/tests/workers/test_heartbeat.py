"""HOS-248 (Epic 12 G-1) — heartbeat / dead-man's switch unit tests.

Covers:
  * record_heartbeat writes an "ok" agent_action_log row (AC2 marker).
  * record_trip writes a typed "tool_error" row + raises an ops alert (AC1/AC3).
  * debounce suppresses repeat alerts for the same (job, reason).
  * heartbeat_monitor trips on stale / never-fresh heartbeats and stays silent
    on fresh ones or when no heartbeat exists yet (AC2).
  * outer failure routes through dispatch_error and re-raises (worker convention).
  * register_heartbeat_monitor_job injects the job without starting the scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers import heartbeat

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _CapturingSession:
    """Async ctx manager that records add()'d rows and no-ops commit()."""

    def __init__(self, store: list):
        self._store = store

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    def add(self, obj):
        self._store.append(obj)

    async def commit(self):
        return None


class _CapturingSessionFactory:
    def __init__(self, store: list):
        self._store = store

    def __call__(self):
        return _CapturingSession(self._store)


class _FakeAsyncSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *_):
        return False


class _FailingSession:
    async def __aenter__(self):
        raise RuntimeError("DB unavailable")

    async def __aexit__(self, *_):
        return False


@pytest.fixture(autouse=True)
def _reset_debounce():
    heartbeat._last_alerted.clear()
    yield
    heartbeat._last_alerted.clear()


# ---------------------------------------------------------------------------
# record_heartbeat (AC2 marker / T1)
# ---------------------------------------------------------------------------

async def test_record_heartbeat_writes_ok_row():
    store: list = []
    with patch.object(heartbeat, "AsyncSessionLocal", _CapturingSessionFactory(store)):
        await heartbeat.record_heartbeat("receipt_dispatcher")

    assert len(store) == 1
    row = store[0]
    assert row.tool_name == "scheduler.receipt_dispatcher"
    assert row.status == "ok"
    assert row.hotel_id == heartbeat.SYSTEM_HOTEL_ID
    assert row.payload["kind"] == "heartbeat"


async def test_record_heartbeat_never_raises_on_db_failure():
    with patch.object(heartbeat, "AsyncSessionLocal", lambda: _FailingSession()):
        # Must swallow — instrumentation never breaks the observed job.
        await heartbeat.record_heartbeat("dispatch_worker")


# ---------------------------------------------------------------------------
# record_trip (AC1 / AC3)
# ---------------------------------------------------------------------------

async def test_record_trip_writes_typed_row_and_dispatches():
    store: list = []
    dispatch = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", _CapturingSessionFactory(store)),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
    ):
        emitted = await heartbeat.record_trip(
            "weekly_digest", heartbeat.REASON_PARTIAL, "2/5 hotels failed."
        )

    assert emitted is True
    assert len(store) == 1
    row = store[0]
    assert row.status == "tool_error"
    assert row.error_code == heartbeat.REASON_PARTIAL
    assert row.tool_name == "scheduler.weekly_digest"
    dispatch.assert_awaited_once()
    assert "weekly_digest" in dispatch.await_args.kwargs["title"]


async def test_record_trip_debounce_suppresses_repeat():
    dispatch = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", _CapturingSessionFactory([])),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
    ):
        first = await heartbeat.record_trip("dispatch_worker", heartbeat.REASON_DEAD_MAN, "x")
        second = await heartbeat.record_trip("dispatch_worker", heartbeat.REASON_DEAD_MAN, "x")

    assert first is True
    assert second is False
    dispatch.assert_awaited_once()  # only the first alert went out


async def test_record_trip_debounce_can_be_disabled():
    dispatch = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", _CapturingSessionFactory([])),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
    ):
        await heartbeat.record_trip("dispatch_worker", heartbeat.REASON_DEAD_MAN, "x", debounce=False)
        await heartbeat.record_trip("dispatch_worker", heartbeat.REASON_DEAD_MAN, "x", debounce=False)

    assert dispatch.await_count == 2


# ---------------------------------------------------------------------------
# heartbeat_monitor — dead-man's switch (AC2)
# ---------------------------------------------------------------------------

async def test_monitor_trips_on_stale_heartbeat():
    stale = datetime.utcnow() - timedelta(days=2)
    trip = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", lambda: _FakeAsyncSession()),
        patch.object(heartbeat, "monitored_jobs", return_value=("dispatch_worker",)),
        patch.object(heartbeat, "_last_heartbeat_at", AsyncMock(return_value=stale)),
        patch.object(heartbeat, "record_trip", trip),
    ):
        await heartbeat._run_heartbeat_monitor_job()

    trip.assert_awaited_once()
    args = trip.await_args.args
    assert args[0] == "dispatch_worker"
    assert args[1] == heartbeat.REASON_DEAD_MAN


async def test_monitor_silent_when_fresh():
    fresh = datetime.utcnow()
    trip = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", lambda: _FakeAsyncSession()),
        patch.object(heartbeat, "monitored_jobs", return_value=("dispatch_worker",)),
        patch.object(heartbeat, "_last_heartbeat_at", AsyncMock(return_value=fresh)),
        patch.object(heartbeat, "record_trip", trip),
    ):
        await heartbeat._run_heartbeat_monitor_job()

    trip.assert_not_awaited()


async def test_monitor_skips_when_no_heartbeat_yet():
    trip = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", lambda: _FakeAsyncSession()),
        patch.object(heartbeat, "monitored_jobs", return_value=("dispatch_worker",)),
        patch.object(heartbeat, "_last_heartbeat_at", AsyncMock(return_value=None)),
        patch.object(heartbeat, "record_trip", trip),
    ):
        await heartbeat._run_heartbeat_monitor_job()

    trip.assert_not_awaited()


async def test_monitor_dispatches_on_outer_failure():
    dispatch = AsyncMock()
    with (
        patch.object(heartbeat, "AsyncSessionLocal", lambda: _FailingSession()),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="DB unavailable"),
    ):
        await heartbeat._run_heartbeat_monitor_job()

    dispatch.assert_awaited_once()
    assert "heartbeat_monitor" in dispatch.await_args.kwargs["title"]


# ---------------------------------------------------------------------------
# Scheduler registration
# ---------------------------------------------------------------------------

def test_register_heartbeat_monitor_injects_job_without_starting():
    scheduler = MagicMock()
    heartbeat.register_heartbeat_monitor_job(scheduler)

    scheduler.add_job.assert_called_once()
    scheduler.start.assert_not_called()
    assert scheduler.add_job.call_args.kwargs.get("id") == "heartbeat_monitor"


# ---------------------------------------------------------------------------
# Cron interval guard — QA-S4 follow-up (HOS-212): minute field is 0–59, so a
# */N step with N >= 60 must not reach APScheduler (it raises ValueError there).
# ---------------------------------------------------------------------------

def test_cron_kwargs_sub_hour_interval_uses_minute_step():
    assert heartbeat._monitor_cron_trigger_kwargs(15) == {"minute": "*/15"}


def test_cron_kwargs_interval_at_or_above_60_switches_to_hour_step():
    # 60 min → every 1 hour on the hour; 120 → every 2 hours. Never minute="*/60".
    assert heartbeat._monitor_cron_trigger_kwargs(60) == {"hour": "*/1", "minute": "0"}
    assert heartbeat._monitor_cron_trigger_kwargs(150) == {"hour": "*/2", "minute": "0"}


def test_cron_kwargs_non_positive_interval_floors_to_one_minute():
    assert heartbeat._monitor_cron_trigger_kwargs(0) == {"minute": "*/1"}


def test_cron_kwargs_oversized_interval_caps_at_valid_hour_step():
    # An hour step > 23 would overflow the hour field (0–23); cap at */23.
    assert heartbeat._monitor_cron_trigger_kwargs(60 * 48) == {"hour": "*/23", "minute": "0"}


@pytest.mark.parametrize("interval", [1, 15, 59, 60, 90, 120, 1440, 5000])
def test_register_builds_a_valid_cron_trigger_for_any_interval(interval, monkeypatch):
    """The registered trigger must be constructible by APScheduler — i.e. the
    guard never lets an out-of-range minute step through (regression for the
    crash the QA-S4 finding flagged)."""
    from apscheduler.triggers.cron import CronTrigger

    monkeypatch.setattr(heartbeat.config, "HEARTBEAT_MONITOR_INTERVAL_MIN", interval)
    scheduler = MagicMock()
    heartbeat.register_heartbeat_monitor_job(scheduler)

    kwargs = scheduler.add_job.call_args.kwargs
    # Reconstruct the trigger exactly as APScheduler would from the cron kwargs.
    CronTrigger(**{k: v for k, v in kwargs.items() if k in ("minute", "hour")})

"""HOS-249 (Epic 12 G-2) — error-rate / LLM-timeout alerting unit tests.

Covers:
  * evaluate() trips each metric above its threshold and stays silent below.
  * the non-ok rate check is gated on MIN_SAMPLES (no false alarm at low volume).
  * record_trip writes a typed tool_error row + raises dispatch_anomaly (AC4).
  * debounce suppresses repeat alerts for the same reason (AC3).
  * the monitor job aggregates the window and trips once per breach.
  * register injects the job without starting the scheduler.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers import error_rate_monitor as erm

S = erm.WindowStats


@pytest.fixture(autouse=True)
def _reset_debounce():
    erm._last_alerted.clear()
    yield
    erm._last_alerted.clear()


@pytest.fixture(autouse=True)
def _fixed_thresholds(monkeypatch):
    monkeypatch.setattr(erm.config, "ERROR_RATE_WINDOW_MIN", 60)
    monkeypatch.setattr(erm.config, "ERROR_RATE_MIN_SAMPLES", 20)
    monkeypatch.setattr(erm.config, "ERROR_RATE_NONOK_THRESHOLD", 0.20)
    monkeypatch.setattr(erm.config, "ERROR_RATE_TOOL_FAILURE_THRESHOLD", 10)
    monkeypatch.setattr(erm.config, "ERROR_RATE_LLM_TIMEOUT_THRESHOLD", 5)
    monkeypatch.setattr(erm.config, "ERROR_RATE_ALERT_COOLDOWN_MIN", 60)


# ---------------------------------------------------------------------------
# evaluate() — pure threshold logic (AC1/AC2)
# ---------------------------------------------------------------------------

def test_evaluate_nominal_no_breach():
    # 100 calls, 5 non-ok (5%), 3 tool errors, 1 timeout — all under threshold.
    assert erm.evaluate(S(total=100, non_ok=5, tool_errors=3, llm_timeouts=1)) == []


def test_evaluate_trips_nonok_rate():
    reasons = [r for r, _ in erm.evaluate(S(total=100, non_ok=30, tool_errors=0, llm_timeouts=0))]
    assert erm.REASON_ERROR_RATE in reasons


def test_evaluate_rate_gated_on_min_samples():
    # 2/3 non-ok = 67% but only 3 samples (< MIN_SAMPLES) → no rate trip.
    reasons = [r for r, _ in erm.evaluate(S(total=3, non_ok=2, tool_errors=0, llm_timeouts=0))]
    assert erm.REASON_ERROR_RATE not in reasons


def test_evaluate_tool_failures_fire_regardless_of_volume():
    # Absolute spike of failures is meaningful even below MIN_SAMPLES.
    reasons = [r for r, _ in erm.evaluate(S(total=11, non_ok=11, tool_errors=11, llm_timeouts=0))]
    assert erm.REASON_TOOL_FAILURES in reasons


def test_evaluate_trips_llm_timeouts():
    reasons = [r for r, _ in erm.evaluate(S(total=50, non_ok=6, tool_errors=0, llm_timeouts=6))]
    assert erm.REASON_LLM_TIMEOUTS in reasons


def test_evaluate_can_trip_multiple_metrics_at_once():
    reasons = [r for r, _ in erm.evaluate(S(total=100, non_ok=40, tool_errors=20, llm_timeouts=9))]
    assert set(reasons) == {erm.REASON_ERROR_RATE, erm.REASON_TOOL_FAILURES, erm.REASON_LLM_TIMEOUTS}


# ---------------------------------------------------------------------------
# record_trip — typed row + anomaly dispatch + debounce (AC3/AC4)
# ---------------------------------------------------------------------------

async def test_record_trip_writes_row_and_dispatches_anomaly():
    store: list = []
    dispatch = AsyncMock()

    class _Sess:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return False
        def add(self, obj): store.append(obj)
        async def commit(self): return None

    with (
        patch.object(erm, "AsyncSessionLocal", lambda: _Sess()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", dispatch),
    ):
        emitted = await erm.record_trip(erm.REASON_LLM_TIMEOUTS, "6 timeouts")

    assert emitted is True
    assert len(store) == 1
    assert store[0].status == "tool_error"
    assert store[0].error_code == erm.REASON_LLM_TIMEOUTS
    assert store[0].tool_name == erm.MONITOR_TOOL
    dispatch.assert_awaited_once()


async def test_record_trip_debounce_suppresses_repeat():
    dispatch = AsyncMock()

    class _Sess:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): return False
        def add(self, obj): pass
        async def commit(self): return None

    with (
        patch.object(erm, "AsyncSessionLocal", lambda: _Sess()),
        patch("app.services.ops_dispatcher.dispatch_anomaly", dispatch),
    ):
        first = await erm.record_trip(erm.REASON_ERROR_RATE, "x")
        second = await erm.record_trip(erm.REASON_ERROR_RATE, "x")

    assert (first, second) == (True, False)
    dispatch.assert_awaited_once()


# ---------------------------------------------------------------------------
# job orchestration
# ---------------------------------------------------------------------------

async def test_monitor_job_trips_once_per_breach():
    stats = S(total=100, non_ok=40, tool_errors=20, llm_timeouts=0)
    trip = AsyncMock()
    with (
        patch.object(erm, "_gather_window_stats", AsyncMock(return_value=stats)),
        patch.object(erm, "AsyncSessionLocal", lambda: _NoopSession()),
        patch.object(erm, "record_trip", trip),
    ):
        await erm._run_error_rate_monitor_job()

    assert trip.await_count == 2  # rate + tool failures


async def test_monitor_job_silent_when_nominal():
    stats = S(total=100, non_ok=2, tool_errors=1, llm_timeouts=0)
    trip = AsyncMock()
    with (
        patch.object(erm, "_gather_window_stats", AsyncMock(return_value=stats)),
        patch.object(erm, "AsyncSessionLocal", lambda: _NoopSession()),
        patch.object(erm, "record_trip", trip),
    ):
        await erm._run_error_rate_monitor_job()

    trip.assert_not_awaited()


class _NoopSession:
    async def __aenter__(self): return MagicMock()
    async def __aexit__(self, *_): return False


# ---------------------------------------------------------------------------
# registration + cron guard
# ---------------------------------------------------------------------------

def test_register_injects_job_without_starting():
    scheduler = MagicMock()
    erm.register_error_rate_monitor_job(scheduler)
    scheduler.add_job.assert_called_once()
    scheduler.start.assert_not_called()
    assert scheduler.add_job.call_args.kwargs.get("id") == "error_rate_monitor"


def test_monitor_cron_minute_clamps_interval_at_or_above_60():
    assert erm._monitor_cron_minute(15) == "*/15"
    assert erm._monitor_cron_minute(90) == "*/30"
    assert erm._monitor_cron_minute(0) == "*/1"

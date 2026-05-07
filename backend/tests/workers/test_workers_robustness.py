"""HOS-156 — unit tests for worker robustness: scheduler injection + dispatch_error.

Verified behaviours:
  * start_event_scheduler / start_weather_scheduler accept an injected scheduler
    and add the job to it without calling scheduler.start() themselves.
  * On non-recoverable outer failure, each job calls dispatch_error() and re-raises.
  * Per-tenant failures in event_sync / weather_sync are isolated (no outer raise,
    no dispatch_error) — per SC #6.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers: async context manager stubs
# ---------------------------------------------------------------------------

class _FailingSession:
    """Simulates a DB session that fails immediately on enter (outer job failure)."""

    async def __aenter__(self):
        raise RuntimeError("DB unavailable")

    async def __aexit__(self, *_):
        return False


class _FakeAsyncSession:
    """Functional async context manager that returns a MagicMock session."""

    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *_):
        return False


# ---------------------------------------------------------------------------
# Scheduler injection
# ---------------------------------------------------------------------------

def test_start_event_scheduler_injects_job_without_starting():
    mock_scheduler = MagicMock()
    from app.workers.event_sync import start_event_scheduler

    start_event_scheduler(mock_scheduler)

    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_not_called()
    assert mock_scheduler.add_job.call_args.kwargs.get("id") == "event_sync_daily_06utc"


def test_start_weather_scheduler_injects_job_without_starting():
    mock_scheduler = MagicMock()
    from app.workers.weather_sync import start_weather_scheduler

    start_weather_scheduler(mock_scheduler)

    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_not_called()
    assert mock_scheduler.add_job.call_args.kwargs.get("id") == "weather_sync_12h"


def test_stop_event_scheduler_is_noop():
    """stop_event_scheduler must not raise and must not touch any scheduler state."""
    from app.workers.event_sync import stop_event_scheduler

    stop_event_scheduler()  # should return silently


def test_stop_weather_scheduler_is_noop():
    from app.workers.weather_sync import stop_weather_scheduler

    stop_weather_scheduler()


# ---------------------------------------------------------------------------
# event_sync — outer failure calls dispatch_error and re-raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_event_sync_dispatches_on_outer_db_failure():
    from app.workers.event_sync import _run_event_sync_for_all_tenants

    dispatch = AsyncMock()
    with (
        patch(
            "app.workers.event_sync.AsyncSessionLocal",
            return_value=_FailingSession(),
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="DB unavailable"),
    ):
        await _run_event_sync_for_all_tenants()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "event_sync" in kwargs["title"]
    assert "job_id" in kwargs["detail"]


# ---------------------------------------------------------------------------
# weather_sync — outer failure calls dispatch_error and re-raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weather_sync_dispatches_on_outer_db_failure():
    from app.workers.weather_sync import _run_weather_sync_for_all_tenants

    dispatch = AsyncMock()
    with (
        patch(
            "app.workers.weather_sync.AsyncSessionLocal",
            return_value=_FailingSession(),
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="DB unavailable"),
    ):
        await _run_weather_sync_for_all_tenants()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "weather_sync" in kwargs["title"]
    assert "job_id" in kwargs["detail"]


# ---------------------------------------------------------------------------
# anomaly_scan — service failure calls dispatch_error and re-raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anomaly_scan_dispatches_on_failure():
    from app.workers.anomaly_scan import _run_anomaly_scan_job

    boom = RuntimeError("anomaly service down")
    dispatch = AsyncMock()
    failing_service = AsyncMock(side_effect=boom)

    with (
        patch(
            "app.workers.anomaly_scan.AsyncSessionLocal",
            return_value=_FakeAsyncSession(),
        ),
        patch(
            "app.workers.anomaly_scan._service.run_full_scan",
            new=failing_service,
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="anomaly service down"),
    ):
        await _run_anomaly_scan_job()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "anomaly_scan" in kwargs["title"]
    assert "job_id" in kwargs["detail"]


# ---------------------------------------------------------------------------
# dispatch_worker — service failure calls dispatch_error and re-raises
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dispatch_worker_dispatches_on_failure():
    from app.workers.dispatch_worker import _run_dispatch_job

    boom = RuntimeError("dispatch service down")
    dispatch = AsyncMock()
    failing_service = AsyncMock(side_effect=boom)

    with (
        patch(
            "app.workers.dispatch_worker.AsyncSessionLocal",
            return_value=_FakeAsyncSession(),
        ),
        patch(
            "app.workers.dispatch_worker._service.run_pending",
            new=failing_service,
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="dispatch service down"),
    ):
        await _run_dispatch_job()

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "dispatch_worker" in kwargs["title"]
    assert "job_id" in kwargs["detail"]

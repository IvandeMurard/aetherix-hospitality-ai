"""HOS-150 AC4 — unit tests for the agent_action_log partition rotation job.

These tests are DB-free: they patch `app.db.session.engine` so we capture the
SQL emitted by the job without needing a Postgres instance. The goal is to
verify:
  * `_partition_bounds` computes the right [start, end) interval for any month
    (including December → next year roll-over).
  * `rotate_partitions` always targets `<current month + 2>` (so on June 1st
    we ensure the August partition exists).
  * `ensure_partition_exists` emits an idempotent `CREATE TABLE IF NOT EXISTS`.
  * Failure path calls `dispatch_error` and re-raises.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.agent_action_log_partition_rotation import (
    _next_month,
    _partition_bounds,
    ensure_partition_exists,
    rotate_partitions,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_next_month_within_year():
    assert _next_month(date(2026, 5, 15)) == date(2026, 6, 1)


def test_next_month_across_year_boundary():
    assert _next_month(date(2026, 12, 31)) == date(2027, 1, 1)


@pytest.mark.parametrize(
    "target,expected",
    [
        (date(2026, 6, 1), ("agent_action_log_2026_06", "2026-06-01", "2026-07-01")),
        (date(2026, 12, 15), ("agent_action_log_2026_12", "2026-12-01", "2027-01-01")),
        (date(2027, 1, 1), ("agent_action_log_2027_01", "2027-01-01", "2027-02-01")),
    ],
)
def test_partition_bounds(target, expected):
    assert _partition_bounds(target) == expected


# ---------------------------------------------------------------------------
# ensure_partition_exists — captures emitted SQL via a mocked engine
# ---------------------------------------------------------------------------

class _FakeConn:
    def __init__(self):
        self.executed: list[str] = []

    async def execute(self, stmt):
        # SQLAlchemy text() objects expose .text
        self.executed.append(getattr(stmt, "text", str(stmt)))


class _FakeBegin:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_ensure_partition_exists_emits_idempotent_sql():
    fake_conn = _FakeConn()
    fake_engine = MagicMock()
    fake_engine.begin = lambda: _FakeBegin(fake_conn)

    with patch(
        "app.workers.agent_action_log_partition_rotation.engine", fake_engine
    ):
        name = await ensure_partition_exists(date(2026, 8, 1))

    assert name == "agent_action_log_2026_08"
    assert len(fake_conn.executed) == 1
    sql = fake_conn.executed[0]
    assert "CREATE TABLE IF NOT EXISTS" in sql
    assert "agent_action_log_2026_08" in sql
    assert "FROM ('2026-08-01') TO ('2026-09-01')" in sql


# ---------------------------------------------------------------------------
# rotate_partitions — month + 2 logic + error path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rotate_partitions_targets_month_plus_two():
    """On 2026-06-01 the cron should ensure the August 2026 partition."""
    captured: list[date] = []

    async def fake_ensure(target: date) -> str:
        captured.append(target)
        return "stub"

    with patch(
        "app.workers.agent_action_log_partition_rotation.ensure_partition_exists",
        side_effect=fake_ensure,
    ):
        await rotate_partitions(today=date(2026, 6, 1))

    assert captured == [date(2026, 8, 1)]


@pytest.mark.asyncio
async def test_rotate_partitions_handles_year_rollover():
    """On 2026-11-15 the cron should ensure the January 2027 partition."""
    captured: list[date] = []

    async def fake_ensure(target: date) -> str:
        captured.append(target)
        return "stub"

    with patch(
        "app.workers.agent_action_log_partition_rotation.ensure_partition_exists",
        side_effect=fake_ensure,
    ):
        await rotate_partitions(today=date(2026, 11, 15))

    assert captured == [date(2027, 1, 1)]


@pytest.mark.asyncio
async def test_rotate_partitions_dispatches_error_on_failure():
    """If partition creation raises, dispatch_error fires and exception propagates."""
    boom = RuntimeError("simulated DB outage")
    dispatch = AsyncMock()

    with (
        patch(
            "app.workers.agent_action_log_partition_rotation.ensure_partition_exists",
            side_effect=boom,
        ),
        patch("app.services.ops_dispatcher.dispatch_error", dispatch),
        pytest.raises(RuntimeError, match="simulated DB outage"),
    ):
        await rotate_partitions(today=date(2026, 6, 1))

    dispatch.assert_awaited_once()
    kwargs = dispatch.await_args.kwargs
    assert "partition rotation failed" in kwargs["title"]
    assert "2026-08-01" in kwargs["detail"]

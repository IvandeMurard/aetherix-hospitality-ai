"""P3-3 tests — kpi_aggregator worker (HOS-177).

Pure-mock tests: no DB, no network.

Covered:
  1. compute_rate: zero denominator → None
  2. compute_rate: all followed → 1.0
  3. compute_rate: all rejected → 0.0
  4. compute_rate: mixed 2/1/1 → 0.5
  5. run_kpi_aggregation: zero recommendations → no kpi_daily row written
     (source = staffing_recommendations, human decisions only — ADR-0007 §17.6)
  6. run_kpi_aggregation: single tenant → correct upsert called
  7. run_kpi_aggregation: two tenants → two upserts
  8. _check_and_emit_alerts: rolling < 0.30, denom >= 5 → alert row written
  9. _check_and_emit_alerts: rolling < 0.30, denom < 5 → no alert (false-alert guard)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.kpi_aggregator import (
    _KPI_NAME,
    _check_and_emit_alerts,
    compute_rate,
    run_kpi_aggregation,
)

# ---------------------------------------------------------------------------
# 1–4. compute_rate — pure function, no mocks needed
# ---------------------------------------------------------------------------

def test_compute_rate_zero_denominator():
    assert compute_rate(0, 0, 0) is None


def test_compute_rate_all_followed():
    assert compute_rate(5, 0, 0) == 1.0


def test_compute_rate_all_rejected():
    assert compute_rate(0, 3, 0) == 0.0


def test_compute_rate_mixed():
    result = compute_rate(2, 1, 1)
    assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Helpers for DB-mock tests
# ---------------------------------------------------------------------------

class _FakeRow:
    """Minimal row stand-in supporting attribute access."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _make_engine_mock(mv_rows: list[_FakeRow], rolling_rows: list[_FakeRow], dedup_rows: list[_FakeRow]):
    """Return a mock engine whose begin() context manager sequences execute() results."""
    conn = AsyncMock()

    execute_results = []

    # Call 1: SELECT human decisions from staffing_recommendations
    mv_result = MagicMock()
    mv_result.fetchall.return_value = mv_rows
    execute_results.append(mv_result)

    # Calls 3..N: INSERT into kpi_daily (one per tenant row with rate != None)
    for _ in mv_rows:
        upsert_result = MagicMock()
        execute_results.append(upsert_result)

    # After upserts: rolling alert SELECT
    rolling_result = MagicMock()
    rolling_result.fetchall.return_value = rolling_rows
    execute_results.append(rolling_result)

    # For each rolling row: dedup SELECT + optional INSERT
    for dr in dedup_rows:
        dedup_result = MagicMock()
        dedup_result.fetchone.return_value = dr
        execute_results.append(dedup_result)
        if dr is None:
            # Will INSERT alert row
            insert_result = MagicMock()
            execute_results.append(insert_result)

    conn.execute = AsyncMock(side_effect=execute_results)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)

    engine_mock = MagicMock()
    engine_mock.begin.return_value = ctx
    return engine_mock, conn


# ---------------------------------------------------------------------------
# 5. Zero recommendations → no kpi_daily upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_recommendations_no_row_written():
    engine_mock, conn = _make_engine_mock(
        mv_rows=[],
        rolling_rows=[],
        dedup_rows=[],
    )
    with patch("app.workers.kpi_aggregator.engine", engine_mock):
        await run_kpi_aggregation()

    # decisions SELECT + alert rolling SELECT
    assert conn.execute.await_count == 2


# ---------------------------------------------------------------------------
# 6. Single tenant row → upsert called with correct rate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_tenant_upsert_called():
    row = _FakeRow(hotel_id="hotel_a", followed=5, rejected=0, neutral=0)
    engine_mock, conn = _make_engine_mock(
        mv_rows=[row],
        rolling_rows=[],
        dedup_rows=[],
    )
    with patch("app.workers.kpi_aggregator.engine", engine_mock):
        await run_kpi_aggregation()

    # decisions select + upsert + alert select = 3
    assert conn.execute.await_count == 3

    # Check upsert call params (index 1: after the decisions select)
    upsert_call = conn.execute.await_args_list[1]
    params = upsert_call.args[1]
    assert params["kpi_name"] == _KPI_NAME
    assert params["value"] == pytest.approx(1.0)
    assert params["numerator"] == 5
    assert params["denominator"] == 5


# ---------------------------------------------------------------------------
# 7. Two tenants → two upsert rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_two_tenants_two_upserts():
    rows = [
        _FakeRow(hotel_id="hotel_a", followed=2, rejected=1, neutral=1),
        _FakeRow(hotel_id="hotel_b", followed=3, rejected=0, neutral=2),
    ]
    engine_mock, conn = _make_engine_mock(
        mv_rows=rows,
        rolling_rows=[],
        dedup_rows=[],
    )
    with patch("app.workers.kpi_aggregator.engine", engine_mock):
        await run_kpi_aggregation()

    # decisions select + 2 upserts + alert select = 4
    assert conn.execute.await_count == 4

    upsert_a = conn.execute.await_args_list[1].args[1]
    upsert_b = conn.execute.await_args_list[2].args[1]
    assert upsert_a["tenant_id"] == "hotel_a"
    assert upsert_a["value"] == pytest.approx(0.5)
    assert upsert_b["tenant_id"] == "hotel_b"
    assert upsert_b["value"] == pytest.approx(3 / 5)


# ---------------------------------------------------------------------------
# 8. Alert emitted when rolling < 0.30 with denominator >= 5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alert_emitted_when_rolling_below_threshold_with_sufficient_denom():
    rolling_row = _FakeRow(tenant_id="hotel_low", rolling_rate=0.20, window_denom=10)

    conn = AsyncMock()

    # _check_and_emit_alerts makes 3 calls directly on conn:
    #   1. rolling SELECT, 2. dedup SELECT, 3. INSERT alert row
    rolling_result = MagicMock()
    rolling_result.fetchall.return_value = [rolling_row]
    dedup_result = MagicMock()
    dedup_result.fetchone.return_value = None  # no existing alert today
    insert_result = MagicMock()

    conn.execute = AsyncMock(side_effect=[rolling_result, dedup_result, insert_result])

    today = date(2026, 5, 20)
    await _check_and_emit_alerts(conn, today)

    # rolling SELECT + dedup SELECT + INSERT = 3 calls
    assert conn.execute.await_count == 3

    insert_call = conn.execute.await_args_list[2]
    params = insert_call.args[1]
    import json
    payload = json.loads(params["payload"])
    assert payload["kpi_alert"] == "trust_low"
    assert payload["rolling_rate"] == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# 9. No alert when denominator < 5 (false-alert guard enforced in SQL HAVING)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_alert_when_denominator_below_minimum():
    """The HAVING clause in the SQL filters sparse tenants; rolling_rows is empty."""
    conn = AsyncMock()

    # rolling SELECT returns empty (HAVING SUM(denominator) >= 5 filtered it out)
    rolling_result = MagicMock()
    rolling_result.fetchall.return_value = []
    conn.execute = AsyncMock(return_value=rolling_result)

    today = date(2026, 5, 20)
    with patch("app.workers.kpi_aggregator.engine", MagicMock()):
        await _check_and_emit_alerts(conn, today)

    # Only the rolling SELECT — no dedup check, no INSERT
    assert conn.execute.await_count == 1


@pytest.mark.asyncio
async def test_aggregation_reads_human_decisions_on_recommendations():
    """ADR-0007 §17.6: the rate is read from staffing_recommendations, human
    deciders only — not from the old request_id-joined materialized view."""
    engine_mock, conn = _make_engine_mock(mv_rows=[], rolling_rows=[], dedup_rows=[])
    with patch("app.workers.kpi_aggregator.engine", engine_mock):
        await run_kpi_aggregation()
    sql = str(conn.execute.await_args_list[0].args[0])
    assert "FROM staffing_recommendations" in sql
    assert "decided_by IN ('human_whatsapp', 'human_via_host')" in sql
    assert "recommendation_acceptance_daily" not in sql

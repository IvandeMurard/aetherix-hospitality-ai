"""HOS-252 (Epic 12 G-5) — output sanity bounds unit tests.

Covers:
  * nominal output → within bounds, no flags.
  * over-capacity covers → clamp + route_to_human + typed flag.
  * absurd headcount delta vs baseline → flag.
  * budget overrun (absorbed check) → flag mentioning "daily".
  * record_sanity_trip writes one row per flag + raises an ops anomaly.
  * staffing_service clamps the delivered headcount on a capacity breach.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services import output_sanity as osan
from app.services.staffing_service import StaffingConfig, StaffingService


@pytest.fixture(autouse=True)
def _thresholds(monkeypatch):
    monkeypatch.setattr(osan.config, "OUTPUT_SANITY_MAX_HEADCOUNT_DELTA_MULT", 3.0)
    monkeypatch.setattr(osan.config, "FEEDBACK_COVERS_CAPACITY_MULTIPLIER", 1.5)
    monkeypatch.setattr(osan.config, "FEEDBACK_COVERS_DEFAULT_TURNS", 3)


# ---------------------------------------------------------------------------
# evaluate() — pure bounds
# ---------------------------------------------------------------------------

def test_nominal_within_bounds():
    v = osan.evaluate(80, 6, total_seats=50, turns_sum=3, baseline_headcount=13, labor_cost=400, labor_budget=1200)
    assert v.within_bounds
    assert v.flags == []
    assert v.clamped_covers is None


def test_over_capacity_clamps_and_routes_to_human():
    # 50 seats × 3 turns × 1.5 = 225 ceiling; 6000 covers is way over.
    v = osan.evaluate(6000, 40, total_seats=50, turns_sum=3, baseline_headcount=13)
    assert not v.within_bounds
    assert v.route_to_human
    assert v.clamped_covers == 225
    assert osan.REASON_OVER_CAPACITY in [r for r, _ in v.flags]


def test_absurd_headcount_delta_flagged():
    # headcount 50 vs baseline 13 → 3.8× > 3× → flag (capacity not checked here).
    v = osan.evaluate(80, 50, baseline_headcount=13)
    assert not v.within_bounds
    assert osan.REASON_ABSURD_DELTA in [r for r, _ in v.flags]


def test_budget_overrun_flag_mentions_daily():
    v = osan.evaluate(80, 6, labor_cost=2000, labor_budget=1200)
    reasons = [r for r, _ in v.flags]
    assert osan.REASON_BUDGET in reasons
    assert "daily" in v.warnings[0].lower()


def test_capacity_skipped_when_seats_unknown():
    v = osan.evaluate(6000, 6, total_seats=None, baseline_headcount=13)
    assert v.clamped_covers is None  # no capacity bound without seats


# ---------------------------------------------------------------------------
# record_sanity_trip
# ---------------------------------------------------------------------------

class _Sess:
    def __init__(self, store): self._store = store
    async def __aenter__(self): return self
    async def __aexit__(self, *_): return False
    def add(self, obj): self._store.append(obj)
    async def commit(self): return None


async def test_record_trip_writes_one_row_per_flag_and_alerts():
    store: list = []
    anomaly = AsyncMock()
    v = osan.evaluate(6000, 50, total_seats=50, turns_sum=3, baseline_headcount=13)
    assert len(v.flags) == 2  # over_capacity + absurd_delta
    with (
        patch.object(osan, "AsyncSessionLocal", lambda: _Sess(store)),
        patch("app.services.ops_dispatcher.dispatch_anomaly", anomaly),
    ):
        await osan.record_sanity_trip("hotel_x", v)
    assert len(store) == 2
    assert {row.error_code for row in store} == {osan.REASON_OVER_CAPACITY, osan.REASON_ABSURD_DELTA}
    assert all(row.tool_name == osan.SANITY_TOOL for row in store)
    anomaly.assert_awaited_once()


async def test_record_trip_noop_when_within_bounds():
    store: list = []
    with patch.object(osan, "AsyncSessionLocal", lambda: _Sess(store)):
        await osan.record_sanity_trip("hotel_x", osan.SanityVerdict())
    assert store == []


# ---------------------------------------------------------------------------
# staffing_service integration — clamp on capacity breach
# ---------------------------------------------------------------------------

async def test_staffing_clamps_headcount_on_capacity_breach():
    service = StaffingService()
    cfg = StaffingConfig()
    with patch("app.services.output_sanity.record_sanity_trip", new_callable=AsyncMock) as trip:
        # 20 seats × 3 × 1.5 = 90 ceiling; ask for 6000 covers.
        result = await service.calculate_recommendation(
            6000, cfg, hotel_id="hotel_x", total_seats=20, turns_sum=3,
        )
    # Delivered headcount is computed on the clamped capacity (90), not 6000.
    capped_servers = (90 + cfg.covers_per_server - 1) // cfg.covers_per_server
    assert result["servers"] == capped_servers
    assert result["sanity"]["route_to_human"] is True
    assert result["sanity"]["clamped_covers"] == 90
    assert osan.REASON_OVER_CAPACITY in result["sanity"]["flags"]
    trip.assert_awaited_once()


async def test_staffing_nominal_no_trip_no_flags():
    service = StaffingService()
    with patch("app.services.output_sanity.record_sanity_trip", new_callable=AsyncMock) as trip:
        result = await service.calculate_recommendation(80, hotel_id="hotel_x", total_seats=200, turns_sum=3)
    assert result["sanity"]["within_bounds"] is True
    assert result["sanity"]["flags"] == []
    trip.assert_not_awaited()

"""HOS-251 (Epic 12 G-4) — confidence-tiered forecast guardrail unit tests.

Contract under test: the guardrail NEVER blanks a recommendation.
  * nominal confidence → no flag, Prophet covers unchanged.
  * Tier 1 (confidence < WARN) → recommendation dispatched + abstention flag.
  * Tier 2 (confidence < CATASTROPHE or live MAPE > ceiling) → baseline fallback,
    still delivered, tagged baseline.
  * baseline resolution prefers context history, else degrades to Prophet point.
  * record_forecast_trip writes a typed abstention row; Tier 2 also alerts ops.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import forecast_guardrail as fg


@pytest.fixture(autouse=True)
def _thresholds(monkeypatch):
    monkeypatch.setattr(fg.config, "FORECAST_CONFIDENCE_WARN", 0.6)
    monkeypatch.setattr(fg.config, "FORECAST_CONFIDENCE_CATASTROPHE", 0.4)
    monkeypatch.setattr(fg.config, "FORECAST_MAPE_CATASTROPHE", 35.0)
    monkeypatch.setattr(fg.config, "FORECAST_BASELINE_DEFAULT_COVERS", 0)


# ---------------------------------------------------------------------------
# evaluate() — pure tiering
# ---------------------------------------------------------------------------

def test_nominal_confidence_no_flag():
    v = fg.evaluate(80, 0.85)
    assert v.tier == fg.NOMINAL
    assert v.is_nominal
    assert v.effective_covers == 80
    assert v.abstention is None
    assert v.baseline_used is False


def test_tier1_dispatches_with_flag_never_blanked():
    v = fg.evaluate(80, 0.55)
    assert v.tier == fg.TIER1_FLAG
    assert v.effective_covers == 80  # Prophet number still delivered
    assert v.baseline_used is False
    assert v.abstention is not None
    assert v.abstention.reason == "confidence_below_threshold"
    assert v.abstention.human_message  # localized, non-empty caveat
    # Crucially: a recommendation IS produced (effective_covers > 0), not blanked.
    assert bool(v.effective_covers)


def test_tier2_on_catastrophic_confidence_uses_context_baseline():
    v = fg.evaluate(80, 0.30, context={"baseline_covers": 50})
    assert v.tier == fg.TIER2_FALLBACK
    assert v.effective_covers == 50
    assert v.baseline_used is True
    assert v.abstention.reason == "cold_start_meta_learner_drift"


def test_tier2_on_live_mape_breach_even_with_ok_confidence():
    v = fg.evaluate(80, 0.85, context={"recent_avg_covers": 60}, live_mape=40.0)
    assert v.tier == fg.TIER2_FALLBACK
    assert v.effective_covers == 60
    assert v.baseline_used is True


def test_tier2_without_baseline_degrades_to_prophet_point_still_delivered():
    v = fg.evaluate(80, 0.30)
    assert v.tier == fg.TIER2_FALLBACK
    assert v.baseline_used is True
    assert v.effective_covers == 80  # degraded fallback — never silent/zero
    assert bool(v.effective_covers)


def test_tier2_uses_configured_default_prior(monkeypatch):
    monkeypatch.setattr(fg.config, "FORECAST_BASELINE_DEFAULT_COVERS", 42)
    covers, real = fg.simple_baseline(None, 80)
    assert (covers, real) == (42, False)


def test_live_mape_under_ceiling_is_nominal():
    assert fg.evaluate(80, 0.85, live_mape=10.0).tier == fg.NOMINAL


# ---------------------------------------------------------------------------
# record_forecast_trip — typed logging + ops alert
# ---------------------------------------------------------------------------

class _Sess:
    def __init__(self, store): self._store = store
    async def __aenter__(self): return self
    async def __aexit__(self, *_): return False
    def add(self, obj): self._store.append(obj)
    async def commit(self): return None


async def test_nominal_verdict_logs_nothing():
    store: list = []
    with patch.object(fg, "AsyncSessionLocal", lambda: _Sess(store)):
        await fg.record_forecast_trip("hotel_x", fg.evaluate(80, 0.85))
    assert store == []


async def test_tier1_logs_typed_abstention_row_no_ops_alert():
    store: list = []
    anomaly = AsyncMock()
    with (
        patch.object(fg, "AsyncSessionLocal", lambda: _Sess(store)),
        patch("app.services.ops_dispatcher.dispatch_anomaly", anomaly),
    ):
        await fg.record_forecast_trip("hotel_x", fg.evaluate(80, 0.55))
    assert len(store) == 1
    row = store[0]
    assert row.status == "tool_error"
    assert row.abstention_reason == "confidence_below_threshold"
    assert row.abstention_layer == "forecast"
    assert row.tool_name == fg.GUARDRAIL_TOOL
    anomaly.assert_not_awaited()  # Tier 1 is a routine caveat, no ops noise


async def test_tier2_logs_row_and_raises_ops_anomaly():
    store: list = []
    anomaly = AsyncMock()
    with (
        patch.object(fg, "AsyncSessionLocal", lambda: _Sess(store)),
        patch("app.services.ops_dispatcher.dispatch_anomaly", anomaly),
    ):
        await fg.record_forecast_trip("hotel_x", fg.evaluate(80, 0.30, context={"baseline_covers": 50}))
    assert len(store) == 1
    assert store[0].abstention_reason == "cold_start_meta_learner_drift"
    anomaly.assert_awaited_once()


# ---------------------------------------------------------------------------
# Engine integration — Tier-2 swaps in the baseline AND recomputes staffing
# ---------------------------------------------------------------------------

async def _engine_with_staffer():
    from app.services.aetherix_engine import AetherixEngine

    engine = AetherixEngine.__new__(AetherixEngine)  # skip heavy __init__
    staffer = MagicMock()
    staffer.calculate_recommendation = AsyncMock(return_value={"servers": 3})
    engine._staffer = staffer
    return engine, staffer


async def test_engine_tier1_attaches_caveat_keeps_covers():
    engine, staffer = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.55}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    assert out["prediction"]["covers"] == 80          # unchanged
    assert out["forecast_guardrail"]["tier"] == fg.TIER1_FLAG
    assert out["forecast_guardrail"]["human_message"]
    staffer.calculate_recommendation.assert_not_awaited()  # no recompute on Tier 1


async def test_engine_tier2_swaps_baseline_and_recomputes_staffing():
    engine, staffer = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.30}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {"baseline_covers": 50})
    assert out["prediction"]["covers"] == 50
    assert out["prediction"]["baseline_used"] is True
    assert out["staffing_recommendation"] == {"servers": 3}
    staffer.calculate_recommendation.assert_awaited_once_with(50)


async def test_engine_guardrail_failure_is_non_fatal():
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.30}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "apply", AsyncMock(side_effect=RuntimeError("boom"))):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    # Original recommendation survives a guardrail failure.
    assert out["staffing_recommendation"] == {"servers": 6}

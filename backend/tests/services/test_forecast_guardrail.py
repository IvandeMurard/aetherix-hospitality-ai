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

from datetime import date
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
    result = {"prediction": {"covers": 80, "confidence": 0.30}, "staffing_recommendation": {"servers": 6},
              "date": "2026-07-14", "service_type": "dinner"}
    context = {"baseline_covers": 50}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, context)
    assert out["prediction"]["covers"] == 50
    assert out["prediction"]["baseline_used"] is True
    assert out["staffing_recommendation"] == {"servers": 3}
    # HOS-345: the recompute keeps the service's context classes
    staffer.calculate_recommendation.assert_awaited_once_with(
        50, tenant_id="hotel_x", target_date=date(2026, 7, 14), service_type="dinner", context=context)


async def test_engine_guardrail_failure_is_non_fatal():
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.30}, "staffing_recommendation": {"servers": 6}}
    with (
        patch.object(fg, "apply", AsyncMock(side_effect=RuntimeError("boom"))),
        patch.object(fg, "record_forecast_trip", AsyncMock()),
    ):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    # Original recommendation survives a guardrail failure.
    assert out["staffing_recommendation"] == {"servers": 6}


# ---------------------------------------------------------------------------
# Rule B (PO 14/11/2026, HOS-366, audit of silences case 9): a guardrail that
# fails yields a typed "not verified" verdict — delivered, flagged, recorded.
# ---------------------------------------------------------------------------

def test_missing_confidence_is_not_verified_not_nominal():
    v = fg.evaluate(80, None)
    assert v.tier == fg.NOT_VERIFIED
    assert not v.is_verified and not v.is_nominal
    assert v.reason == "guardrail_not_verified"
    assert v.effective_covers == 80          # delivered unchanged, nothing invented
    assert v.confidence is None              # no default confidence made up
    assert v.baseline_used is False
    assert v.abstention is not None and v.abstention.reason == "guardrail_not_verified"


def test_crash_inside_the_tiering_is_a_not_verified_verdict(monkeypatch):
    monkeypatch.setattr(fg, "_evaluate", MagicMock(side_effect=ZeroDivisionError("boom")))
    v = fg.evaluate(80, 0.9)
    assert v.tier == fg.NOT_VERIFIED
    assert "ZeroDivisionError" in v.detail
    assert v.failed_checks == (fg.GUARDRAIL_TOOL,)


def test_not_verified_message_is_qualitative_no_number():
    import re

    v = fg.not_verified(80, check="x", detail="y", locale="fr")
    msg = v.abstention.human_message
    assert msg and not re.search(r"\d", msg)       # no confidence figure, no percentage
    assert "guardrail_not_verified" not in msg     # never the raw code
    assert not re.search(r"\d", fg.not_verified(80, check="x", detail="y", locale="en").abstention.human_message)


async def test_not_verified_logs_typed_row_and_raises_ops_error():
    store: list = []
    error = AsyncMock()
    with (
        patch.object(fg, "AsyncSessionLocal", lambda: _Sess(store)),
        patch("app.services.ops_dispatcher.dispatch_error", error),
    ):
        await fg.record_forecast_trip("hotel_x", fg.evaluate(80, None))
    assert len(store) == 1
    assert store[0].abstention_reason == "guardrail_not_verified"
    assert store[0].error_code == "guardrail_not_verified"
    assert store[0].payload["failed_checks"] == [fg.GUARDRAIL_TOOL]
    error.assert_awaited_once()


async def test_engine_guardrail_crash_delivers_forecast_flagged_not_verified():
    engine, staffer = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.9}, "staffing_recommendation": {"servers": 6}}
    trip = AsyncMock()
    with (
        patch.object(fg, "apply", AsyncMock(side_effect=RuntimeError("boom"))),
        patch.object(fg, "record_forecast_trip", trip),
    ):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    assert out["prediction"]["covers"] == 80                 # delivered, unchanged
    assert out["staffing_recommendation"] == {"servers": 6}
    guard = out["forecast_guardrail"]
    assert guard["tier"] == fg.NOT_VERIFIED
    assert guard["verified"] is False                        # never presented as verified
    assert guard["reserve"] and guard["human_message"]
    assert guard["not_verified_checks"] == [fg.GUARDRAIL_TOOL]
    # The typed event (NFR2): one trip with the not-verified verdict.
    (hotel, verdict), _ = trip.await_args
    assert hotel == "hotel_x" and verdict.reason == "guardrail_not_verified"


async def test_engine_staffing_recompute_crash_does_not_half_apply_the_baseline():
    engine, staffer = await _engine_with_staffer()
    staffer.calculate_recommendation = AsyncMock(side_effect=RuntimeError("rules unavailable"))
    result = {"prediction": {"covers": 80, "confidence": 0.30}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {"baseline_covers": 50})
    # Before HOS-366 the baseline covers were written, then the recompute failed:
    # a baseline figure next to the Prophet staffing, shipped as if checked.
    assert out["prediction"]["covers"] == 80
    assert "baseline_used" not in out["prediction"]
    assert out["forecast_guardrail"]["verified"] is False


async def test_engine_missing_confidence_is_flagged_not_skipped():
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": None}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "AsyncSessionLocal", lambda: _Sess([])), \
            patch("app.services.ops_dispatcher.dispatch_error", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    assert out["forecast_guardrail"]["verified"] is False


async def test_engine_flags_a_check_the_orchestrator_could_not_run():
    """Audit case 12: the orchestrator reports the constitution it could not
    build; the engine turns it into the typed verdict and records the event."""
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.9}, "staffing_recommendation": {"servers": 6},
              "unverified_checks": ["agent_constitution"]}
    trip = AsyncMock()
    with patch.object(fg, "record_forecast_trip", trip):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    assert "unverified_checks" not in out                  # folded into the verdict
    guard = out["forecast_guardrail"]
    assert guard["verified"] is False and guard["tier"] == fg.NOT_VERIFIED
    assert guard["not_verified_checks"] == ["agent_constitution"]
    assert out["prediction"]["covers"] == 80
    recorded = [c.args[1] for c in trip.await_args_list]
    assert any(v.reason == "guardrail_not_verified" and v.failed_checks == ("agent_constitution",)
               for v in recorded)


async def test_engine_keeps_a_tier_caveat_and_adds_the_not_verified_flag():
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.55}, "staffing_recommendation": {"servers": 6},
              "unverified_checks": ["agent_constitution"]}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    guard = out["forecast_guardrail"]
    assert guard["tier"] == fg.TIER1_FLAG                  # the G-4 verdict is kept
    assert guard["verified"] is False                      # and the forecast is still not verified
    assert guard["reserve"]


def test_deterministic_explanation_has_no_confidence_figure():
    from app.services.reasoning_service import ReasoningService

    out = ReasoningService(llm=MagicMock()).deterministic_explanation(
        80, date(2026, 11, 17), "dinner", {"weather": {"condition": "rain"}}, [])
    assert out["explanation_source"] == "deterministic"
    assert out["claude_used"] is False
    assert "80 covers" in out["summary"] and "%" not in out["summary"]


async def test_engine_nominal_stays_clean():
    engine, _ = await _engine_with_staffer()
    result = {"prediction": {"covers": 80, "confidence": 0.9}, "staffing_recommendation": {"servers": 6}}
    with patch.object(fg, "record_forecast_trip", AsyncMock()):
        out = await engine._apply_forecast_guardrail("hotel_x", result, {})
    assert "forecast_guardrail" not in out


def test_forecast_reply_shows_the_reserve_without_a_number():
    from app.services.forecast_reply import render_forecast

    result = {
        "prediction": {"covers": 80, "confidence": 0.9, "is_mock": False},
        "staffing_recommendation": {},
        "forecast_guardrail": {"tier": fg.NOT_VERIFIED, "verified": False},
    }
    text = render_forecast(result, {}, date(2026, 11, 17), "dinner", "fr", demo_notice=False)
    assert "*80 couverts*" in text
    assert "Non vérifié" in text
    assert "%" not in text                     # no confidence percentage shown
    clean = render_forecast({**result, "forecast_guardrail": None}, {}, date(2026, 11, 17),
                            "dinner", "fr", demo_notice=False)
    assert "Non vérifié" not in clean

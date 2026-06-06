"""EVAL-1 (HOS-205) — stratified forecast metrics + regression diff.

Tests the pure `compute_metrics` / `diff_forecast` logic deterministically with
hand-made predictions — no Prophet/Stan in the unit path (fast, reproducible).
"""
from __future__ import annotations

import pytest

from scripts.eval.baselines import diff_forecast
from scripts.eval.eval_forecast import compute_metrics


def _sc(sid: str, category: str, value: float, tol: float) -> dict:
    return {
        "id": sid,
        "category": category,
        "layer": "forecast",
        "expected": {"covers": {"value": value, "tolerance_pct": tol}},
    }


def test_compute_metrics_stratifies_by_category():
    scenarios = [
        _sc("a", "normal_day", 100, 0.15),
        _sc("b", "normal_day", 100, 0.15),
        _sc("c", "event_day", 100, 0.20),
    ]
    predictions = {
        "a": {"yhat": 110, "yhat_lower": 90, "yhat_upper": 120},   # err .10, tol pass, hit
        "b": {"yhat": 80, "yhat_lower": 70, "yhat_upper": 95},     # err .20, tol fail, miss
        "c": {"yhat": 130, "yhat_lower": 100, "yhat_upper": 160},  # err .30, tol fail, hit
    }

    r = compute_metrics(scenarios, predictions)

    assert r["per_category_count"] == {"event_day": 1, "normal_day": 2}
    assert r["per_category_mape"]["normal_day"] == pytest.approx(0.15)   # mean(.10, .20)
    assert r["per_category_mape"]["event_day"] == pytest.approx(0.30)
    assert r["overall_mape_j1_holdout"] == pytest.approx(0.20)           # mean(.10, .20, .30)
    assert r["interval_coverage_pct"] == pytest.approx(2 / 3, abs=0.01)  # a, c hit
    assert r["tolerance_pass_rate"] == pytest.approx(1 / 3, abs=0.01)    # only a
    assert r["scenario_count"] == 3
    assert r["seed"] == 42


def test_compute_metrics_skips_missing_predictions_and_zero_expected():
    scenarios = [
        _sc("a", "normal_day", 100, 0.15),
        _sc("missing", "normal_day", 100, 0.15),
        _sc("zero", "normal_day", 0, 0.15),
    ]
    predictions = {
        "a": {"yhat": 100, "yhat_lower": 90, "yhat_upper": 110},
        "zero": {"yhat": 10, "yhat_lower": 0, "yhat_upper": 20},
    }
    r = compute_metrics(scenarios, predictions)
    assert r["scenario_count"] == 1  # missing prediction + zero-expected dropped


def test_diff_flags_regression_over_3pp():
    base = {"per_category_mape": {"normal_day": 0.10, "event_day": 0.20}}
    current = {"per_category_mape": {"normal_day": 0.14, "event_day": 0.205}}  # +4pp / +0.5pp

    d = diff_forecast(current, base)

    assert d["has_baseline"] is True
    assert len(d["regressions"]) == 1
    assert d["regressions"][0]["category"] == "normal_day"
    assert d["regressions"][0]["delta_pp"] == pytest.approx(4.0, abs=0.01)


def test_diff_no_baseline():
    d = diff_forecast({"per_category_mape": {"normal_day": 0.1}}, None)
    assert d["has_baseline"] is False
    assert d["regressions"] == []

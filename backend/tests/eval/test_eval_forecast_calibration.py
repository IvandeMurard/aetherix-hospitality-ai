"""Freeze rule of the calibration eval (ADR-0007 §18.2) — pure, no Prophet."""
from scripts.eval.eval_forecast_calibration import category, freeze_verdict


def _r(before, after):
    return {"coverage_before_test": {"gap_pp": before}, "coverage_after_test": {"gap_pp": after}}


def test_freeze_requires_improvement_and_no_undercoverage():
    assert freeze_verdict(_r(-13.3, 8.1))[0] is True
    assert freeze_verdict(_r(-13.3, -6.0))[0] is False  # under-covers > 5 pp
    assert freeze_verdict(_r(-3.0, 4.0))[0] is False    # not closer to nominal
    assert freeze_verdict(_r(None, 1.0))[0] is False


def test_category_matches_golden_taxonomy():
    assert category({"event_impact": 0.2, "weather_score": 0.5}) == "event_day"
    assert category({"event_impact": 0.0, "weather_score": 0.1}) == "weather_anomaly"
    assert category({"event_impact": 0.0, "weather_score": 0.9}) == "weather_anomaly"
    assert category({"event_impact": 0.0, "weather_score": 0.5}) == "normal_day"

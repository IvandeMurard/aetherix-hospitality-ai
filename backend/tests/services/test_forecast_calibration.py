"""Forecast uncertainty calibration (ADR-0007 §18.2)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services import forecast_calibration as fc
from app.services.prediction_engine import FORECASTER_ID, INTERVAL_NOMINAL_LEVEL, PredictionEngine

ARTIFACT = fc.CALIBRATION_DIR / "prophet-predictionengine-synthetic-v1.json"


def _cal(residuals, **kw):
    base = dict(version="t-v1", forecaster="f", provenance="synthetic", created_at="2026-09-25")
    base.update(kw)
    return fc.fit(residuals, **base)


def test_relative_residual():
    assert fc.relative_residual(110, 100) == pytest.approx(0.10)
    assert fc.relative_residual(90, 0) is None


def test_conformal_rank_is_conservative_and_flags_thin_tails():
    rs = sorted(range(1, 11))  # n = 10
    assert fc.conformal_quantile(rs, 0.5) == (6, False)     # ceil(11*0.5)=6
    assert fc.conformal_quantile(rs, 0.9) == (10, False)    # ceil(9.9)=10
    assert fc.conformal_quantile(rs, 0.95) == (10, True)    # rank 11 > n → clamped
    assert fc.conformal_quantile(rs, 0.1) == (1, False)     # floor(1.1)=1
    assert fc.conformal_quantile(rs, 0.05) == (1, True)     # floor(0.55)=0 → clamped


def test_fit_quantiles_and_interval_on_uniform_residuals():
    rs = [(-0.5 + k / 1000) for k in range(1001)]  # uniform on [-0.5, 0.5]
    cal = _cal(rs)
    assert cal.clamped_grid_points == 0
    lo, hi = cal.interval(100.0, 0.8)
    assert lo == pytest.approx(60, abs=0.5) and hi == pytest.approx(140, abs=0.5)
    p, res = cal.prob_at_or_below(100.0, 100.0)
    assert res == "exact" and p == pytest.approx(0.5, abs=0.01)
    assert cal.prob_at_or_below(100.0, 10.0)[1] == "below_grid"
    assert cal.prob_at_or_below(100.0, 1000.0)[1] == "above_grid"
    # E[(D-100)+] for D uniform on [50,150] = 12.5
    assert cal.expected_shortfall(100.0, 100.0) == pytest.approx(12.5, abs=0.6)
    assert cal.expected_excess(100.0, 100.0) == pytest.approx(12.5, abs=0.6)
    assert cal.quantile(10.0, 0.01) >= 0


def test_fit_rejects_empty_and_bad_provenance():
    with pytest.raises(ValueError):
        _cal([None, float("nan")])
    with pytest.raises(ValueError):
        _cal([0.1], provenance="guessed")


def test_coverage_per_category_and_lead():
    recs = [
        fc.IntervalRecord(10, 5, 15, "a", 1),
        fc.IntervalRecord(20, 5, 15, "a", 2),
        fc.IntervalRecord(10, 5, 15, "b", 1),
        fc.IntervalRecord(10, 11, 15, "b", 1),
    ]
    c = fc.coverage(recs, 0.8)
    assert c["n"] == 4 and c["coverage"] == 0.5 and c["gap_pp"] == -30.0
    assert c["per_category"]["a"] == {"n": 2, "coverage": 0.5}
    assert c["per_lead_days"]["1"] == {"n": 3, "coverage": 0.6667}
    assert c["per_category_lead"]["b|1"]["n"] == 2


def test_realised_coverage_flags_manager_declared_actuals_as_not_independent():
    rows = [
        {"actual_covers": 100, "interval_lower": 90, "interval_upper": 110,
         "actual_covers_source": "manager_feedback", "task_class": "staffing.add"},
        {"actual_covers": 150, "interval_lower": 90, "interval_upper": 110,
         "actual_covers_source": "manager_feedback", "task_class": "staffing.add"},
        {"actual_covers": None, "interval_lower": 90, "interval_upper": 110},
        {"actual_covers": 100},  # no stored interval → skipped
    ]
    out = fc.realised_coverage(rows)
    assert out["n"] == 2 and out["coverage"] == 0.5
    assert out["independent_actuals"] is False
    pos = fc.realised_coverage([{**rows[0], "actual_covers_source": "pos_data"}])
    assert pos["independent_actuals"] is True


def test_load_active_never_borrows_another_forecaster(tmp_path: Path):
    active = _cal([0.1, -0.1], forecaster="anomaly-heuristic-v1")
    active.status = "active"
    active.dump(tmp_path / "a.json")
    _cal([0.1, -0.1], forecaster=FORECASTER_ID).dump(tmp_path / "b.json")  # proposed
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert fc.load_active(FORECASTER_ID, tmp_path) is None
    assert fc.load_active("anomaly-heuristic-v1", tmp_path).forecaster == "anomaly-heuristic-v1"


def test_committed_artifact_is_labelled_and_passed_the_freeze_rule():
    d = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cal = fc.Calibration.from_dict(d)
    assert cal.forecaster == FORECASTER_ID and cal.status == "active"
    assert cal.provenance == "synthetic" and cal.training_data_source == "synthetic"
    assert cal.nominal_level == INTERVAL_NOMINAL_LEVEL
    assert cal.canary_runs >= 3 and cal.canary_identical is True
    before, after = cal.coverage_before["coverage"], cal.coverage_after["coverage"]
    assert abs(after - 0.8) < abs(before - 0.8)
    assert after >= 0.8 - 0.05  # never frozen while under-covering (understates risk)
    assert cal.coverage_after["n"] >= 100
    assert all(math.isfinite(v) for v in cal.residual_quantiles.values())


def test_prediction_engine_applies_calibration_only_to_matching_training_data():
    eng = PredictionEngine()
    eng.data_source = "mcp_sandbox"
    assert eng.calibration() is None and eng._calibrated_block(100.0) is None
    eng.data_source = "synthetic"
    block = eng._calibrated_block(100.0)
    assert block["label"] == "synthetic-calibrated"
    assert block["lower"] < 100 < block["upper"]
    assert block["measured_n"] >= 100


@pytest.mark.asyncio
async def test_untrained_mock_prediction_carries_no_calibration():
    from datetime import date

    res = await PredictionEngine().predict(date(2026, 10, 1))
    assert res.is_mock and res.calibrated is None
    assert res.to_dict()["interval_nominal_level"] == INTERVAL_NOMINAL_LEVEL


def test_model_sidecar_round_trips_data_source(tmp_path: Path, monkeypatch):
    import prophet.serialize as ps

    monkeypatch.setattr(ps, "model_to_json", lambda m: "{}")
    eng = PredictionEngine()
    eng.data_source = "synthetic"
    eng.is_trained, eng.model = True, object()
    eng.save_model(str(tmp_path / "m.json"))
    meta = json.loads((tmp_path / "m.json.meta.json").read_text())
    assert meta == {"data_source": "synthetic", "forecaster": FORECASTER_ID}

    monkeypatch.setattr(ps, "model_from_json", lambda s: object())
    loaded = PredictionEngine()
    loaded.load_model(str(tmp_path / "m.json"))
    assert loaded.data_source == "synthetic"

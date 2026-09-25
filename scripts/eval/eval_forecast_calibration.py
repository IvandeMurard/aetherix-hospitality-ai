"""Forecast interval calibration eval — arm A (ADR-0007 §18.2).

Measures whether Prophet's nominal 80 % interval contains the realised value
80 % of the time, per category and lead time, and whether a split-conformal
recalibration (``app.services.forecast_calibration``) fixes it — on a test set
disjoint in time from the calibration set.

Data: ``backend/data/demo/prophet_training.json`` — **synthetic** (generated
by ``scripts/ops/generate_demo_data.py`` from the same regressors Prophet is
given). Every number this script produces is labelled synthetic; it is a check
of the method and of the pipeline, not of forecast uncertainty on a real hotel.

Method (deterministic, seed 42):
  * rolling origin: from day ``FIRST_ORIGIN`` every ``STEP`` days, fit Prophet
    (the ``PredictionEngine`` configuration: weekly + yearly seasonality, FR
    holidays, regressors weather_score / event_impact / occupancy, interval
    width 0.80) on all days before the origin, predict the next ``HORIZON``
    days with their realised regressors (lead time 1…HORIZON);
  * origins in the first half → calibration residuals; second half → test;
  * before = Prophet's own 80 % interval on the test set;
    after = conformal 80 % interval fitted on the calibration set only.

Usage (from repo root, with the backend venv):
  backend/.venv/bin/python -m scripts.eval.eval_forecast_calibration \
      --runs 3 --json-out eval/baselines/forecast_calibration_baseline.json \
      --freeze backend/data/calibration/prophet-predictionengine-synthetic-v1.json

``--check`` (CI, eval-gate.yml) exits 1 when a fresh recalibration fails the
freeze rule below. ``--freeze`` writes the runtime calibration only if (canary rule, Décision
#29) the ``--runs`` repeats are identical and ``--runs >= 3``, and (freeze
rule) the recalibrated test coverage is closer to nominal than before and not
more than ``MAX_UNDERCOVER_PP`` below nominal — under-coverage is the direction
that understates risk. Exit 2 otherwise.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

from app.services import forecast_calibration as fc  # noqa: E402

DEMO_DATA = _ROOT / "backend" / "data" / "demo" / "prophet_training.json"
REGRESSORS = ("weather_score", "event_impact", "occupancy")
NOMINAL = 0.80
SEED = 42
FIRST_ORIGIN = 120
STEP = 7
HORIZON = 7
FORECASTER = "prophet-predictionengine-v1"
MAX_UNDERCOVER_PP = 5.0
DATA_PROVENANCE = (
    "synthetic — backend/data/demo/prophet_training.json, generated from the "
    "same regressors Prophet is given. Checks the method, not uncertainty on a "
    "real hotel."
)


def category(row: dict) -> str:
    """Same taxonomy as the golden forecast scenarios."""
    if float(row.get("event_impact") or 0) > 0:
        return "event_day"
    ws = float(row.get("weather_score") or 0)
    if ws <= 0.1 or ws >= 0.9:
        return "weather_anomaly"
    return "normal_day"


def backtest(demo_data: Path = DEMO_DATA, seed: int = SEED) -> list[dict]:
    """One record per (origin, lead): actual, yhat, Prophet lower/upper."""
    import numpy as np
    import pandas as pd
    from prophet import Prophet

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)

    rows = json.loads(Path(demo_data).read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["ds"] = pd.to_datetime(df["ds"])
    out: list[dict] = []
    origins = list(range(FIRST_ORIGIN, len(df) - HORIZON + 1, STEP))
    for oi, origin in enumerate(origins):
        np.random.seed(seed)
        train = df.iloc[:origin]
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=NOMINAL,
            changepoint_prior_scale=0.05,
        )
        model.add_country_holidays(country_name="FR")
        for reg in REGRESSORS:
            model.add_regressor(reg)
        model.fit(train)
        future = df.iloc[origin:origin + HORIZON][["ds", *REGRESSORS]]
        fcst = model.predict(future)
        for lead, ((_, truth), (_, pred)) in enumerate(
            zip(df.iloc[origin:origin + HORIZON].iterrows(), fcst.iterrows()), start=1
        ):
            out.append({
                "origin_index": oi,
                "date": truth["ds"].strftime("%Y-%m-%d"),
                "lead_days": lead,
                "category": category(truth.to_dict()),
                "actual": float(truth["y"]),
                "yhat": round(float(pred["yhat"]), 4),
                "lower": round(float(pred["yhat_lower"]), 4),
                "upper": round(float(pred["yhat_upper"]), 4),
            })
    return out


def evaluate(records: list[dict], created_at: str) -> tuple[dict, fc.Calibration]:
    n_origins = max(r["origin_index"] for r in records) + 1
    split = n_origins // 2
    calib = [r for r in records if r["origin_index"] < split]
    test = [r for r in records if r["origin_index"] >= split]

    cal = fc.fit(
        (fc.relative_residual(r["actual"], r["yhat"]) for r in calib),
        version="prophet-predictionengine-synthetic-v1",
        forecaster=FORECASTER,
        provenance="synthetic",
        created_at=created_at,
        nominal_level=NOMINAL,
    )

    def _records(rs, use_cal: bool, level: float = NOMINAL):
        out = []
        for r in rs:
            if use_cal:
                lo, hi = cal.interval(r["yhat"], level)
            else:
                lo, hi = r["lower"], r["upper"]
            out.append(fc.IntervalRecord(r["actual"], lo, hi, r["category"], r["lead_days"]))
        return out

    before = fc.coverage(_records(test, False), NOMINAL)
    after = fc.coverage(_records(test, True), NOMINAL)
    after_other = {
        f"{lvl:.2f}": fc.coverage(_records(test, True, lvl), lvl)["coverage"]
        for lvl in (0.5, 0.9)
    }
    before_calib_set = fc.coverage(_records(calib, False), NOMINAL)["coverage"]

    report = {
        "layer": "forecast_calibration",
        "data_provenance": DATA_PROVENANCE,
        "forecaster": FORECASTER,
        "nominal_level": NOMINAL,
        "method": {
            "backtest": f"rolling origin from day {FIRST_ORIGIN}, every {STEP} days, horizon {HORIZON}",
            "split": f"origins 0..{split - 1} calibration ({len(calib)} forecasts), "
                     f"{split}..{n_origins - 1} test ({len(test)} forecasts), disjoint in time",
            "recalibration": cal.method,
            "seed": SEED,
        },
        "n_origins": n_origins,
        "n_forecasts": len(records),
        "coverage_before_test": before,
        "coverage_after_test": after,
        "coverage_after_test_other_levels": after_other,
        "coverage_before_calibration_set": before_calib_set,
        "calibration_version": cal.version,
        "calibration_clamped_grid_points": cal.clamped_grid_points,
    }
    cal.coverage_before = {"n": before["n"], "coverage": before["coverage"],
                           "per_category": before["per_category"],
                           "per_lead_days": before["per_lead_days"]}
    cal.coverage_after = {"n": after["n"], "coverage": after["coverage"],
                          "per_category": after["per_category"],
                          "per_lead_days": after["per_lead_days"],
                          "other_levels": after_other}
    cal.independent_actuals = None  # synthetic: not applicable
    cal.training_data_source = "synthetic"
    cal.notes = [
        "Synthetic series: risk statements built on this calibration must say "
        "'synthetic-calibrated' (ADR-0007 §18.2).",
        "Valid for the Prophet PredictionEngine forecaster only; never applied to "
        "the anomaly-detection heuristic that drives dispatched staffing "
        "recommendations.",
    ]
    return report, cal


def freeze_verdict(report: dict) -> tuple[bool, str]:
    """Freeze rule: closer to nominal than before, and not under-covering by
    more than MAX_UNDERCOVER_PP. Returns (ok, reason)."""
    b = report["coverage_before_test"]["gap_pp"]
    a = report["coverage_after_test"]["gap_pp"]
    if a is None or b is None:
        return False, "no test coverage"
    if a < -MAX_UNDERCOVER_PP:
        return False, f"after under-covers by {-a:g} pp (> {MAX_UNDERCOVER_PP:g})"
    if abs(a) >= abs(b):
        return False, f"after gap {a:g} pp not closer to nominal than before {b:g} pp"
    return True, f"gap {b:g} pp → {a:g} pp"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a fresh recalibration fails the freeze rule (CI gate)")
    ap.add_argument("--freeze", type=Path, default=None,
                    help="write the runtime calibration (requires --runs >= 3, identical runs)")
    args = ap.parse_args()

    created_at = datetime.now(timezone.utc).date().isoformat()
    runs = [backtest() for _ in range(max(1, args.runs))]
    identical = all(r == runs[0] for r in runs[1:])
    report, cal = evaluate(runs[0], created_at)
    report["canary"] = {"runs": len(runs), "identical": identical}
    ok, why = freeze_verdict(report)
    report["freeze_rule"] = {"passes": ok, "reason": why, "max_undercover_pp": MAX_UNDERCOVER_PP}
    cal.canary_runs = len(runs)
    cal.canary_identical = identical

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    b, a = report["coverage_before_test"], report["coverage_after_test"]
    print(
        f"[forecast_calibration] SYNTHETIC · nominal {NOMINAL:.0%} · test n={a['n']} · "
        f"before {b['coverage']} → after {a['coverage']} · runs={len(runs)} identical={identical}"
    )

    if args.check and not ok:
        print(f"[forecast_calibration] CHECK FAILED: {why}")
        return 1

    if args.freeze:
        if len(runs) < 3 or not identical:
            print("[forecast_calibration] freeze refused: needs >= 3 identical runs (canary rule)")
            return 2
        if not ok:
            print(f"[forecast_calibration] freeze refused: {why}")
            return 2
        cal.status = "active"
        cal.dump(args.freeze)
        print(f"[forecast_calibration] frozen → {args.freeze}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

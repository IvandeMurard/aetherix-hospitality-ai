"""Forecast eval — stratified per-category MAPE + tolerance + interval coverage.

EVAL-1 (HOS-205), ADR-0007 §5.b. Refactor of `scripts/ops/measure_mape_j1.py`:
keeps the Prophet train/predict core, adds per-`category` stratification driven
by `eval/golden_dataset.jsonl`.

Method (reproducible, seed=42): the golden forecast scenarios are held out of the
training set, Prophet is fit once on the remainder, then each scenario date is
predicted out-of-sample using its real regressor values. MAPE is grouped by the
scenario's taxonomy `category`.

The pure metric computation (`compute_metrics`) is separated from the Prophet
fit (`fit_and_predict`) so it can be unit-tested deterministically without Stan.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

from .loader import DEFAULT_DATASET, load_scenarios

logger = logging.getLogger("eval_forecast")

_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_DATA = _ROOT / "backend" / "data" / "demo" / "prophet_training.json"
REGRESSORS = ("weather_score", "event_impact", "occupancy")
INTERVAL_WIDTH = 0.80
SEED = 42


def _expected_covers(scenario: dict) -> tuple[float, float]:
    """Return (value, tolerance_pct) from a forecast scenario's expected block."""
    covers = scenario["expected"]["covers"]
    return float(covers["value"]), float(covers["tolerance_pct"])


def compute_metrics(scenarios: list[dict], predictions: dict[str, dict]) -> dict:
    """Pure stratification — no Prophet. `predictions[id]` = {yhat, yhat_lower, yhat_upper}.

    Produces the ADR §5.b result shape + per-scenario detail.
    """
    per_cat_err: dict[str, list[float]] = defaultdict(list)
    all_err: list[float] = []
    interval_hits: list[bool] = []
    tol_passes: list[bool] = []
    details: list[dict] = []

    for sc in scenarios:
        sid = sc["id"]
        if sid not in predictions:
            continue
        expected, tol = _expected_covers(sc)
        if expected <= 0:
            continue
        pred = predictions[sid]
        yhat = float(pred["yhat"])
        lower = float(pred.get("yhat_lower", yhat))
        upper = float(pred.get("yhat_upper", yhat))

        abs_pct_err = abs(expected - yhat) / expected
        tol_pass = abs_pct_err <= tol
        interval_hit = lower <= expected <= upper

        cat = sc["category"]
        per_cat_err[cat].append(abs_pct_err)
        all_err.append(abs_pct_err)
        interval_hits.append(interval_hit)
        tol_passes.append(tol_pass)
        details.append(
            {
                "id": sid,
                "category": cat,
                "expected": expected,
                "yhat": round(yhat, 1),
                "abs_pct_err": round(abs_pct_err, 4),
                "tolerance_pct": tol,
                "tolerance_pass": tol_pass,
                "interval_hit": interval_hit,
            }
        )

    def _mean(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    return {
        "layer": "forecast",
        "method": (
            "stratified scattered-holdout, edge-case-weighted — surfaces "
            "per-category weakness; NOT the Décision #14 contiguous-30d gate (15.09%)"
        ),
        "overall_mape_j1_holdout": _mean(all_err),
        "per_category_mape": {c: _mean(v) for c, v in sorted(per_cat_err.items())},
        "per_category_count": {c: len(v) for c, v in sorted(per_cat_err.items())},
        "interval_coverage_pct": (
            round(sum(interval_hits) / len(interval_hits), 4) if interval_hits else None
        ),
        "tolerance_pass_rate": (
            round(sum(tol_passes) / len(tol_passes), 4) if tol_passes else None
        ),
        "scenario_count": len(details),
        "seed": SEED,
        "regressors": list(REGRESSORS),
        "scenarios": details,
    }


def fit_and_predict(scenarios: list[dict], demo_data: Path = DEMO_DATA, seed: int = SEED) -> dict[str, dict]:
    """Train Prophet on the demo series minus the scenario dates, predict each
    scenario date out-of-sample. Returns {id: {yhat, yhat_lower, yhat_upper}}."""
    import numpy as np
    import pandas as pd
    from prophet import Prophet

    np.random.seed(seed)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)

    rows = json.loads(Path(demo_data).read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["ds"] = pd.to_datetime(df["ds"])

    holdout_dates = {sc["input"]["date"] for sc in scenarios}
    train = df[~df["ds"].dt.strftime("%Y-%m-%d").isin(holdout_dates)].copy()

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=INTERVAL_WIDTH,
        changepoint_prior_scale=0.05,
    )
    for reg in REGRESSORS:
        if reg in df.columns:
            model.add_regressor(reg)
    model.fit(train)

    future_rows = []
    for sc in scenarios:
        inp = sc["input"]
        row = {"ds": pd.to_datetime(inp["date"])}
        for reg in REGRESSORS:
            row[reg] = inp.get(reg, 0.0)
        future_rows.append((sc["id"], row))

    future = pd.DataFrame([r for _, r in future_rows])
    forecast = model.predict(future)

    predictions: dict[str, dict] = {}
    for (sid, _), (_, fc) in zip(future_rows, forecast.iterrows()):
        predictions[sid] = {
            "yhat": float(fc["yhat"]),
            "yhat_lower": float(fc["yhat_lower"]),
            "yhat_upper": float(fc["yhat_upper"]),
        }
    return predictions


def run(dataset: Path = DEFAULT_DATASET, demo_data: Path = DEMO_DATA, seed: int = SEED) -> dict:
    """Full forecast eval: load forecast scenarios, fit+predict, compute metrics."""
    scenarios = load_scenarios(dataset, layer="forecast")
    if not scenarios:
        raise SystemExit("[eval_forecast] no forecast scenarios in dataset")
    predictions = fit_and_predict(scenarios, demo_data=demo_data, seed=seed)
    return compute_metrics(scenarios, predictions)

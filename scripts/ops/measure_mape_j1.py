"""measure_mape_j1.py — HOS-190 AC3 gate measurement (Décision #14).

.. deprecated:: HOS-205 (EVAL-1)
   This remains the canonical **Décision #14 gate** metric (contiguous-30d
   out-of-sample MAPE, 15.09%). For the *stratified per-category* eval driven by
   ``eval/golden_dataset.jsonl`` (edge-case-weighted, regression-gated), use
   ``scripts/eval/eval_forecast.py`` / ``python -m scripts.eval.run_all``.
   The two are complementary, not interchangeable.

Computes **out-of-sample** MAPE J+1 on the synthetic 365-day dataset by training
Prophet on days 1–335 and predicting days 336–365, then comparing predicted vs
actual covers.

The training endpoint (POST /api/v1/predictions/train) returns *in-sample* MAPE,
which is optimistic — it measures fit, not forecast skill. The honest gate metric
for Décision #14 (MAPE ≤ 22%) must be measured out-of-sample, as documented in
the story pack T7.

Usage:
    python scripts/ops/measure_mape_j1.py
    # → prints JSON with both metrics, exit 0 if MAPE_J+1 ≤ 22%, exit 3 otherwise

Optional flags:
    --holdout N        Number of last days used as held-out window (default: 30)
    --no-regressors    Train without weather/event/occupancy regressors (baseline)
    --json-out PATH    Also write the result JSON to a file

Exit codes:
    0 — gate PASS (mape_j1_holdout ≤ 0.22)
    3 — gate FAIL (pivot ticket required, see HOS-190 Phase C)
    4 — data missing / corrupt
    5 — training or prediction failed
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("measure_mape_j1")

# Silence Prophet/cmdstanpy chatter
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_DATA = REPO_ROOT / "backend" / "data" / "demo" / "prophet_training.json"
GATE_THRESHOLD = 0.22  # Décision #14 — non-negotiable


def _load_dataset() -> pd.DataFrame:
    if not DEMO_DATA.exists():
        log.error("Demo dataset missing: %s", DEMO_DATA)
        log.error("Run: python scripts/ops/generate_demo_data.py first")
        sys.exit(4)
    rows = json.loads(DEMO_DATA.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df["ds"] = pd.to_datetime(df["ds"])
    df.sort_values("ds", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _make_prophet(use_regressors: bool, df_columns: set[str]):
    from prophet import Prophet

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.80,
        changepoint_prior_scale=0.05,
    )
    try:
        model.add_country_holidays(country_name="FR")
    except Exception as exc:  # pragma: no cover — defensive
        log.warning("add_country_holidays failed: %s", exc)

    regressors: list[str] = []
    if use_regressors:
        for reg in ("weather_score", "event_impact", "occupancy"):
            if reg in df_columns:
                model.add_regressor(reg)
                regressors.append(reg)
    return model, regressors


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    mask = y_true > 0
    if mask.sum() == 0:
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])))


def measure(holdout_days: int, use_regressors: bool) -> dict:
    df = _load_dataset()
    n = len(df)
    if holdout_days >= n - 30:
        log.error("Holdout %d too large for %d-row dataset", holdout_days, n)
        sys.exit(4)

    train = df.iloc[: n - holdout_days].copy()
    test = df.iloc[n - holdout_days :].copy()
    log.info(
        "Split: train=%d rows (%s → %s), test=%d rows (%s → %s)",
        len(train),
        train["ds"].iloc[0].date(),
        train["ds"].iloc[-1].date(),
        len(test),
        test["ds"].iloc[0].date(),
        test["ds"].iloc[-1].date(),
    )

    model, regressors = _make_prophet(use_regressors, set(df.columns))

    t0 = time.monotonic()
    try:
        model.fit(train)
    except Exception as exc:
        log.exception("Prophet training failed: %s", exc)
        sys.exit(5)
    train_ms = int((time.monotonic() - t0) * 1000)
    log.info("Prophet trained in %d ms (regressors=%s)", train_ms, regressors or "none")

    # In-sample MAPE
    pred_in = model.predict(train[["ds"] + regressors].copy())
    mape_in = _mape(train["y"].values, pred_in["yhat"].values)

    # Out-of-sample MAPE — feed actual regressor values for the holdout window
    pred_out = model.predict(test[["ds"] + regressors].copy())
    mape_out = _mape(test["y"].values, pred_out["yhat"].values)

    # Per-day breakdown for the holdout window — helps diagnose failures
    breakdown = pd.DataFrame({
        "ds": test["ds"].dt.strftime("%Y-%m-%d").values,
        "y_true": test["y"].astype(int).values,
        "y_pred": pred_out["yhat"].round().astype(int).values,
        "abs_pct_err": np.abs(test["y"].values - pred_out["yhat"].values) / np.maximum(test["y"].values, 1),
    })

    return {
        "dataset": str(DEMO_DATA.relative_to(REPO_ROOT)),
        "rows_total": n,
        "rows_train": len(train),
        "rows_holdout": len(test),
        "regressors_used": regressors,
        "training_duration_ms": train_ms,
        "mape_in_sample": round(mape_in, 4) if mape_in is not None else None,
        "mape_j1_holdout": round(mape_out, 4) if mape_out is not None else None,
        "gate_threshold": GATE_THRESHOLD,
        "gate_pass": (mape_out is not None and mape_out <= GATE_THRESHOLD),
        "holdout_breakdown": breakdown.to_dict(orient="records"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", type=int, default=30, help="Held-out tail days (default: 30)")
    parser.add_argument("--no-regressors", action="store_true", help="Train without regressors (baseline)")
    parser.add_argument("--json-out", type=Path, default=None, help="Write full result JSON to this path")
    args = parser.parse_args()

    result = measure(holdout_days=args.holdout, use_regressors=not args.no_regressors)

    # Human-readable summary
    print()
    print("=" * 64)
    print(f"  Dataset       : {result['dataset']}")
    print(f"  Train / Hold  : {result['rows_train']} / {result['rows_holdout']} days")
    print(f"  Regressors    : {result['regressors_used'] or '(none — baseline)'}")
    print(f"  In-sample MAPE: {result['mape_in_sample']*100:.2f}%" if result["mape_in_sample"] is not None else "  In-sample MAPE: N/A")
    if result["mape_j1_holdout"] is not None:
        print(f"  J+1 MAPE      : {result['mape_j1_holdout']*100:.2f}%  (gate ≤ {GATE_THRESHOLD*100:.0f}%)")
    print(f"  Gate decision : {'PASS ✅' if result['gate_pass'] else 'FAIL ❌ — pivot ticket required (Décision #14)'}")
    print("=" * 64)
    print()

    # Compact JSON (drop breakdown unless --json-out)
    compact = {k: v for k, v in result.items() if k != "holdout_breakdown"}
    print(json.dumps(compact, indent=2))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        print(f"\nFull result (with per-day breakdown) → {args.json_out}")

    return 0 if result["gate_pass"] else 3


if __name__ == "__main__":
    sys.exit(main())

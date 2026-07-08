"""Real-data forecast benchmark — Recruit Restaurant Visitor Forecasting (HOS-307).

Replaces the retired synthetic MAPE (circular: demo data was generated from the
same regressors Prophet consumes — see docs/context/analyse-critique-2026-07.md).

Dataset: Kaggle "Recruit Restaurant Visitor Forecasting" — real daily visitor
counts for 829 Japanese restaurants (2016-01-01 → 2017-04-22) + holiday flags.
Files expected in --data-dir: air_visit_data.csv, date_info.csv.

Protocol (deterministic, no sampling):
- Restaurants: the N stores with the longest observed history (ties broken by
  store id), default N=30.
- Rolling origin: 6 origins per store at T-30/-25/-20/-15/-10/-5 relative to
  each store's last observed date (5-day spacing so each lead time covers
  rotating weekdays — weekly spacing would pin J+2 to Mondays and skew MAPE).
  At each origin, train on all data <= origin and forecast the next 7 calendar
  days. Missing actuals (restaurant closed) are skipped in scoring.
- Metric: MAPE per lead time (J+1 / J+3 / J+7) pooled across stores x origins,
  plus all-leads MAPE.

Models:
1. naive        — mean of the last 4 same-weekday actuals at or before origin
                  (the baseline any maitre d'hotel computes in their head).
2. prophet      — the Aetherix PredictionEngine configuration as-is
                  (weekly+yearly seasonality, interval 0.80,
                  changepoint_prior_scale 0.05) + holiday_flg regressor
                  (known-in-future, like Aetherix's event_impact).
3. lightgbm     — one global model across stores per origin: dow, month,
                  holiday_flg, lags 7/14/21/28, 28-day rolling mean (leak-free
                  for leads <= 7 since all lags >= 7).

Usage:
    python scripts/ops/benchmark_recruit.py \
        --data-dir backend/data/benchmarks \
        --out eval/benchmarks/recruit_results.json

Decision rule (HOS-307 AC4): Prophet must beat the naive baseline by >= 5 MAPE
points overall, otherwise a model-pivot decision is documented.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

logging.getLogger("prophet").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("cmdstanpy").propagate = False

SEED = 42
N_STORES_DEFAULT = 30
# Origins spaced 5 days apart (not 7): with weekly spacing every lead falls on
# a single weekday (J+2 = always Monday -> tiny actuals dominate the APE).
# 5-day spacing rotates the weekday phase across origins.
ORIGIN_OFFSETS = (30, 25, 20, 15, 10, 5)
ORIGINS_PER_STORE = len(ORIGIN_OFFSETS)
HORIZON = 7
REPORT_LEADS = (1, 3, 7)
NAIVE_WEEKS = 4


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    visits = pd.read_csv(data_dir / "air_visit_data.csv", parse_dates=["visit_date"])
    dates = pd.read_csv(data_dir / "date_info.csv", parse_dates=["calendar_date"])
    dates = dates.rename(columns={"calendar_date": "visit_date"})[["visit_date", "holiday_flg"]]
    return visits, dates


def select_stores(visits: pd.DataFrame, n: int) -> list[str]:
    counts = visits.groupby("air_store_id").size().reset_index(name="n_days")
    counts = counts.sort_values(["n_days", "air_store_id"], ascending=[False, True])
    return counts.head(n)["air_store_id"].tolist()


def store_frame(visits: pd.DataFrame, dates: pd.DataFrame, store: str) -> pd.DataFrame:
    df = visits[visits["air_store_id"] == store][["visit_date", "visitors"]].copy()
    df = df.sort_values("visit_date").merge(dates, on="visit_date", how="left")
    df["holiday_flg"] = df["holiday_flg"].fillna(0).astype(int)
    return df.reset_index(drop=True)


def origins_for(df: pd.DataFrame) -> list[pd.Timestamp]:
    last = df["visit_date"].max()
    return [last - pd.Timedelta(days=d) for d in ORIGIN_OFFSETS]


# ---------------------------------------------------------------------------
# Models — each returns {target_date: prediction} for the 7 days after origin
# ---------------------------------------------------------------------------

def predict_naive(train: pd.DataFrame, origin: pd.Timestamp) -> dict[pd.Timestamp, float]:
    preds: dict[pd.Timestamp, float] = {}
    by_date = train.set_index("visit_date")["visitors"]
    for lead in range(1, HORIZON + 1):
        target = origin + pd.Timedelta(days=lead)
        same_dow = [target - pd.Timedelta(weeks=w) for w in range(1, 12)]
        vals = [by_date[d] for d in same_dow if d in by_date.index][:NAIVE_WEEKS]
        if vals:
            preds[target] = float(np.mean(vals))
    return preds


def predict_prophet(train: pd.DataFrame, origin: pd.Timestamp,
                    dates: pd.DataFrame) -> dict[pd.Timestamp, float]:
    from prophet import Prophet

    # Mirror of backend/app/services/prediction_engine.py::train()
    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.80,
        changepoint_prior_scale=0.05,
    )
    m.add_regressor("holiday_flg")
    fit_df = train.rename(columns={"visit_date": "ds", "visitors": "y"})[
        ["ds", "y", "holiday_flg"]
    ]
    import io
    from contextlib import redirect_stderr, redirect_stdout
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        m.fit(fit_df)

    future_dates = [origin + pd.Timedelta(days=k) for k in range(1, HORIZON + 1)]
    future = pd.DataFrame({"ds": future_dates}).merge(
        dates.rename(columns={"visit_date": "ds"}), on="ds", how="left"
    )
    future["holiday_flg"] = future["holiday_flg"].fillna(0).astype(int)
    fc = m.predict(future)
    return {row["ds"]: max(0.0, float(row["yhat"])) for _, row in fc.iterrows()}


def _lgbm_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["dow"] = out["visit_date"].dt.dayofweek
    out["month"] = out["visit_date"].dt.month
    by_store = out.groupby("air_store_id", group_keys=False)
    for lag in (7, 14, 21, 28):
        out[f"lag{lag}"] = by_store["visitors"].shift(lag)
    out["roll28"] = by_store["visitors"].apply(
        lambda s: s.shift(7).rolling(28, min_periods=7).mean()
    )
    return out


FEATS = ["dow", "month", "holiday_flg", "lag7", "lag14", "lag21", "lag28", "roll28", "store_code"]


def fit_lgbm_global(all_train: pd.DataFrame):
    import lightgbm as lgb

    feats = _lgbm_features(all_train).dropna(subset=["lag28"])
    model = lgb.LGBMRegressor(
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        random_state=SEED,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
    )
    model.fit(feats[FEATS], feats["visitors"], categorical_feature=["dow", "month", "store_code"])
    return model


def predict_lgbm(model, store_hist: pd.DataFrame, store_code: int, origin: pd.Timestamp,
                 dates: pd.DataFrame) -> dict[pd.Timestamp, float]:
    by_date = store_hist.set_index("visit_date")["visitors"]
    hol = dates.set_index("visit_date")["holiday_flg"]
    rows = []
    targets = []
    roll_src = by_date[by_date.index <= origin - pd.Timedelta(days=7)]
    roll28 = float(roll_src.tail(28).mean()) if len(roll_src) >= 7 else np.nan
    for lead in range(1, HORIZON + 1):
        target = origin + pd.Timedelta(days=lead)
        lags = {f"lag{l}": by_date.get(target - pd.Timedelta(days=l), np.nan) for l in (7, 14, 21, 28)}
        if np.isnan(lags["lag28"]) or np.isnan(roll28):
            continue
        rows.append({
            "dow": target.dayofweek, "month": target.month,
            "holiday_flg": int(hol.get(target, 0)), **lags,
            "roll28": roll28, "store_code": store_code,
        })
        targets.append(target)
    if not rows:
        return {}
    preds = model.predict(pd.DataFrame(rows)[FEATS])
    return {t: max(0.0, float(p)) for t, p in zip(targets, preds)}


# ---------------------------------------------------------------------------
# Benchmark loop
# ---------------------------------------------------------------------------

def run(data_dir: Path, out_path: Path, n_stores: int) -> dict:
    np.random.seed(SEED)
    visits, dates = load_data(data_dir)
    stores = select_stores(visits, n_stores)
    store_code = {s: i for i, s in enumerate(stores)}

    frames = {s: store_frame(visits, dates, s) for s in stores}
    all_origins = sorted({o for s in stores for o in origins_for(frames[s])})

    # One global LightGBM fit per origin (trained on all selected stores).
    lgbm_models = {}
    pool = pd.concat(
        [frames[s].assign(air_store_id=s, store_code=store_code[s]) for s in stores],
        ignore_index=True,
    )
    for origin in all_origins:
        lgbm_models[origin] = fit_lgbm_global(pool[pool["visit_date"] <= origin])

    records = []
    t0 = time.time()
    for si, store in enumerate(stores):
        df = frames[store]
        actual = df.set_index("visit_date")["visitors"]
        for origin in origins_for(df):
            train = df[df["visit_date"] <= origin]
            if len(train) < 90:
                continue
            preds = {
                "naive": predict_naive(train, origin),
                "prophet": predict_prophet(train, origin, dates),
                "lightgbm": predict_lgbm(
                    lgbm_models[origin], df[df["visit_date"] <= origin],
                    store_code[store], origin, dates,
                ),
            }
            for model_name, p in preds.items():
                for target, yhat in p.items():
                    if target not in actual.index or actual[target] <= 0:
                        continue
                    lead = (target - origin).days
                    ape = abs(actual[target] - yhat) / actual[target]
                    records.append({
                        "store": store, "origin": str(origin.date()),
                        "lead": lead, "model": model_name, "ape": ape,
                    })
        print(f"[{si+1}/{len(stores)}] {store} done ({time.time()-t0:.0f}s)", flush=True)

    rec = pd.DataFrame(records)
    summary: dict = {"protocol": {
        "dataset": "Kaggle Recruit Restaurant Visitor Forecasting (real visitors, 829 JP restaurants)",
        "n_stores": len(stores), "origins_per_store": ORIGINS_PER_STORE,
        "horizon_days": HORIZON, "naive": f"mean of last {NAIVE_WEEKS} same weekdays",
        "prophet": "Aetherix PredictionEngine config + holiday_flg regressor",
        "lightgbm": "global model, lags 7/14/21/28 + roll28 + dow/month/holiday, seed 42",
        "seed": SEED, "scored_points": int(len(rec) / 3),
    }, "mape_pct": {}}

    summary["mdape_pct"] = {}
    for model_name in ("naive", "prophet", "lightgbm"):
        sub = rec[rec["model"] == model_name]
        entry = {"all_leads": round(100 * sub["ape"].mean(), 2)}
        med = {"all_leads": round(100 * sub["ape"].median(), 2)}
        for lead in range(1, HORIZON + 1):
            lead_sub = sub[sub["lead"] == lead]["ape"]
            entry[f"J+{lead}"] = round(100 * lead_sub.mean(), 2)
            med[f"J+{lead}"] = round(100 * lead_sub.median(), 2)
        summary["mape_pct"][model_name] = entry
        # MAPE is fragile on tiny-actual days (2 visitors -> 400% APE);
        # MdAPE is reported alongside for robustness, AC4 stays on MAPE.
        summary["mdape_pct"][model_name] = med

    naive_all = summary["mape_pct"]["naive"]["all_leads"]
    prophet_all = summary["mape_pct"]["prophet"]["all_leads"]
    summary["ac4_verdict"] = {
        "rule": "Prophet must beat naive by >= 5 MAPE points (all leads)",
        "prophet_minus_naive_pp": round(prophet_all - naive_all, 2),
        "pass": bool(naive_all - prophet_all >= 5.0),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["mape_pct"], indent=2))
    print("AC4:", summary["ac4_verdict"])
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("backend/data/benchmarks"))
    ap.add_argument("--out", type=Path, default=Path("eval/benchmarks/recruit_results.json"))
    ap.add_argument("--n-stores", type=int, default=N_STORES_DEFAULT)
    args = ap.parse_args()
    run(args.data_dir, args.out, args.n_stores)
    return 0


if __name__ == "__main__":
    sys.exit(main())

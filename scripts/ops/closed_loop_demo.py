"""Closed-loop outcome-capture demo — HOS-310 (Story 16.10).

Proves the *plumbing* of the Aetherix learning loop end-to-end, on synthetic
sandbox data (announced as such — this demonstrates the loop mechanics, not
forecast accuracy, which is benchmarked separately on real data in HOS-307):

    forecast J-1  ->  staffing recommendation  ->  WhatsApp-style receipt
        ->  simulated manager feedback (accept / modify)
        ->  actual covers revealed  ->  G-3 bounds check (feedback_guard)
        ->  outcome captured  ->  weekly recalibration (Prophet retrain)

It exercises the REAL services (PredictionEngine, StaffingService,
feedback_guard.evaluate) — not mocks — plus the HOS-311 observability spans.

Narrative device: a +25% demand regime shift on day 15 (a new corporate
banquet contract). The report shows the forecast drifting right after the
shift and the weekly recalibration closing the gap — the reason the loop
exists.

Deterministic: fixed seeds, no network, no DB writes. Reruns produce the
same JSON report (Décision #29 discipline). Console output narrates the
day-by-day loop (G-3 rejection, regime shift, recalibrations).

Usage:
    backend/.venv/Scripts/python scripts/ops/closed_loop_demo.py \
        [--days 30] [--out eval/reports/closed_loop_demo.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Windows consoles default to cp1252 — force UTF-8 so the receipt/report
# rendering (emoji, arrows) never crashes the loop.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ops"))

# Imports below pull app.db.session which builds an engine object from
# DATABASE_URL at import time (no connection is opened; this demo never
# touches the DB). Provide a dummy so the script runs anywhere.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://demo:demo@localhost:5432/demo")

import pandas as pd  # noqa: E402

from generate_demo_data import generate  # noqa: E402 — scripts/ops sibling

from app.core.observability import span as obs_span  # noqa: E402
from app.services.feedback_guard import evaluate as bounds_evaluate  # noqa: E402
from app.services.prediction_engine import PredictionEngine  # noqa: E402
from app.services.staffing_service import StaffingService  # noqa: E402

SEED = 42
TOTAL_SEATS = 120.0
SHIFT_DAY = 15          # regime shift: new banquet contract from this day
SHIFT_FACTOR = 1.25     # +25% demand
RETRAIN_EVERY = 7       # weekly recalibration
MANAGER_TOLERANCE = 0.20  # manager accepts within ±20% of their own guess
CORRUPT_DAY = 10        # a buggy POS export reports an absurd actual that day
CORRUPT_VALUE = 900.0   # >> capacity ceiling — must be rejected by G-3


def _naive_guess(history: list[dict], target: date) -> float | None:
    """The manager's mental model: mean of the last 4 same weekdays."""
    same_dow = [r["y"] for r in history if date.fromisoformat(r["ds"]).weekday() == target.weekday()]
    return sum(same_dow[-4:]) / len(same_dow[-4:]) if same_dow else None


async def run(days: int, out_path: Path) -> dict:
    rng = random.Random(SEED)
    # Prophet's uncertainty intervals (yhat_lower/upper) are Monte-Carlo
    # sampled via numpy's global RNG — seed it so reruns are bit-identical.
    import numpy as np
    np.random.seed(SEED)

    # History = full 2025 synthetic year; future truth = start of 2026
    # (different seed → genuinely unseen values), with the regime shift.
    history = generate(2025, seed=SEED)
    future = generate(2026, seed=SEED + 1)[:days]
    for i, row in enumerate(future):
        if i + 1 >= SHIFT_DAY:
            row["y"] = round(row["y"] * SHIFT_FACTOR)

    engine = PredictionEngine()
    staffer = StaffingService()

    async def retrain() -> None:
        df = pd.DataFrame(history)
        df["ds"] = pd.to_datetime(df["ds"])
        await engine.train(df)

    await retrain()
    retrains = 1

    ledger: list[dict] = []
    print(f"— Closed loop: {days} jours simulés, choc de régime au jour {SHIFT_DAY} "
          f"(+{int((SHIFT_FACTOR-1)*100)}%), recalibration hebdomadaire —\n")

    for i, row in enumerate(future, start=1):
        day = date.fromisoformat(row["ds"])
        with obs_span("closed_loop.day", day=row["ds"], index=i):
            # 1. J-1 forecast (regressors are known-in-advance signals).
            features = {k: row[k] for k in ("weather_score", "event_impact", "occupancy")}
            pred = await engine.predict(day, features=features)

            # 2. Staffing recommendation (real service).
            staffing = await staffer.calculate_recommendation(
                pred.predicted, confidence=pred.confidence
            )

            # 3. Simulated manager: compares to their own naive guess.
            guess = _naive_guess(history, day) or pred.predicted
            deviation = abs(pred.predicted - guess) / max(guess, 1.0)
            if deviation <= MANAGER_TOLERANCE or rng.random() < 0.15:
                feedback, trusted_covers = "accepted", pred.predicted
            else:
                feedback, trusted_covers = "modified", round(guess)

            # 4. Day passes — actual covers revealed; G-3 bounds gate before
            #    the outcome is allowed to feed training (feedback_guard).
            #    On CORRUPT_DAY the POS export is buggy: the gate must reject
            #    it so the poisoned value never reaches the training set.
            reported = CORRUPT_VALUE if i == CORRUPT_DAY else float(row["y"])
            verdict = bounds_evaluate(reported, total_seats=TOTAL_SEATS)
            if verdict.plausible:
                history.append(row)
                ape_pct = round(100 * abs(reported - pred.predicted) / reported, 1)
            else:
                ape_pct = None  # quarantined outcome — excluded from metrics

            ledger.append({
                "day": row["ds"], "index": i,
                "predicted": pred.predicted, "range": [pred.lower, pred.upper],
                "confidence": pred.confidence, "staffing": staffing,
                "manager_feedback": feedback, "manager_counter": trusted_covers,
                "actual_reported": reported, "ape_pct": ape_pct,
                "bounds": verdict.severity, "bounds_reason": verdict.reason,
                "post_shift": i >= SHIFT_DAY,
            })
            fb_icon = "OK " if feedback == "accepted" else f"->{trusted_covers}"
            ape_txt = f"APE {ape_pct:>5.1f}%" if ape_pct is not None else "⛔ rejeté G-3"
            print(f"J{i:>2} {day} · prévu {pred.predicted:>3} [{pred.lower}-{pred.upper}] "
                  f"· manager {fb_icon} · réel {reported:>5.0f} · {ape_txt}"
                  + ("  ⚡ choc de régime" if i == SHIFT_DAY else "")
                  + (f"  ({verdict.reason})" if not verdict.plausible else ""))

            # 5. Weekly recalibration on captured outcomes.
            if i % RETRAIN_EVERY == 0 and i < days:
                await retrain()
                retrains += 1
                print(f"      ↻ recalibration #{retrains} (historique {len(history)} jours)")

    # ------------------------------- report -------------------------------
    df = pd.DataFrame(ledger)
    def mape(sub: pd.DataFrame) -> float:
        return float(round(sub["ape_pct"].dropna().mean(), 1))

    weeks = {f"semaine {w+1}": mape(df[(df["index"] > 7*w) & (df["index"] <= 7*(w+1))])
             for w in range((days + 6) // 7)}
    post_shift_before_recal = df[(df["index"] >= SHIFT_DAY) & (df["index"] <= SHIFT_DAY + 6)]
    post_shift_after_recal = df[df["index"] > SHIFT_DAY + 6]

    report = {
        "protocol": {
            "days": days, "seed": SEED, "regime_shift_day": SHIFT_DAY,
            "shift_factor": SHIFT_FACTOR, "retrain_every_days": RETRAIN_EVERY,
            "services": "real PredictionEngine / StaffingService / feedback_guard.evaluate",
            "data": "synthetic sandbox (loop mechanics demo — accuracy is HOS-307's job)",
        },
        "metrics": {
            "mape_by_week_pct": weeks,
            "mape_post_shift_before_recalibration_pct": mape(post_shift_before_recal),
            "mape_post_shift_after_recalibration_pct": mape(post_shift_after_recal),
            "acceptance_rate_pct": float(round(100 * (df["manager_feedback"] == "accepted").mean(), 1)),
            "bounds_rejections": int((df["bounds"] != "ok").sum()),
            "recalibrations": retrains,
            "outcomes_captured": int(df["ape_pct"].notna().sum()),
        },
        "ledger": ledger,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))

    m = report["metrics"]
    print("\n================ RAPPORT BOUCLE FERMÉE ================")
    print(f"MAPE par semaine        : {m['mape_by_week_pct']}")
    print(f"MAPE post-choc AVANT recalibration (J{SHIFT_DAY}-J{SHIFT_DAY+6}) : "
          f"{m['mape_post_shift_before_recalibration_pct']}%")
    print(f"MAPE post-choc APRÈS recalibration (J{SHIFT_DAY+7}+)  : "
          f"{m['mape_post_shift_after_recalibration_pct']}%")
    print(f"Taux d'acceptation manager : {m['acceptance_rate_pct']}%")
    print(f"Rejets bornes G-3 : {m['bounds_rejections']} · Recalibrations : {m['recalibrations']}")
    print(f"→ {out_path}")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    # eval/reports/ is gitignored — this is a regenerable runtime artifact.
    ap.add_argument("--out", type=Path, default=Path("eval/reports/closed_loop_demo.json"))
    args = ap.parse_args()
    asyncio.run(run(args.days, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

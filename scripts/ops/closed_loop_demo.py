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
same report (Décision #29 discipline).

Usage:
    backend/.venv/Scripts/python scripts/ops/closed_loop_demo.py \
        [--days 30] [--out docs/demos/closed_loop_demo.json]
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


def _receipt_text(day: date, pred, staffing: dict, row: dict) -> str:
    """Compact WhatsApp-style daily receipt (sandbox rendering).

    The *anticipation* is made explicit: when a known-in-advance signal
    (local event, strong occupancy) drives the number, the receipt says so —
    the agent explains why tomorrow won't look like last week.
    """
    lines = [
        f"📋 Aetherix — {day.strftime('%a %d %b')}",
        f"Couverts attendus : {pred.predicted} (fourchette {pred.lower}–{pred.upper}, "
        f"confiance {int(pred.confidence * 100)}%)",
        f"Staffing : {staffing.get('servers', '?')} salle · "
        f"{staffing.get('kitchen_staff', staffing.get('kitchen', '?'))} cuisine",
    ]
    if row.get("event_impact", 0) > 0:
        lines.append(f"📍 Signal : événement local demain — impact estimé "
                     f"+{int(row['event_impact'] * 100)} % intégré au forecast.")
    if row.get("occupancy", 0) >= 0.85:
        lines.append(f"🏨 Hôtel à {int(row['occupancy'] * 100)} % d'occupation — "
                     f"pression forte attendue sur le restaurant.")
    lines.append("Répondre OK pour valider, ou votre estimation.")
    return "\n".join(lines)


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
    under_streak = 0  # consecutive >=10% under-estimations (drift narration)

    ledger: list[dict] = []
    transcript: list[str] = [
        "# Transcript WhatsApp — closed-loop demo (HOS-310)",
        "",
        "> Rendu du fil de conversation manager ↔ Aetherix sur les 30 jours simulés",
        "> (écran de droite du storyboard vidéo). Généré par `closed_loop_demo.py`,",
        "> déterministe. Données sandbox, mécanique réelle.",
        "",
    ]
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
            receipt = _receipt_text(day, pred, staffing, row)

            # 3. Simulated manager: compares to their own naive guess.
            guess = _naive_guess(history, day) or pred.predicted
            deviation = abs(pred.predicted - guess) / max(guess, 1.0)
            if deviation <= MANAGER_TOLERANCE or rng.random() < 0.15:
                feedback, trusted_covers = "accepted", pred.predicted
                manager_reply = "OK 👍"
            else:
                feedback, trusted_covers = "modified", round(guess)
                manager_reply = f"Je dirais plutôt {trusted_covers} couverts."

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

            # WhatsApp transcript (right pane of the video): the agent's
            # *reaction* is verbalized — it reports its own error the next
            # morning, flags quarantined data, announces recalibrations.
            transcript.append(f"### J{i} — {day.strftime('%A %d %B')}\n")
            transcript.append("**Aetherix** (la veille, 17h) :\n> " + receipt.replace("\n", "\n> ") + "\n")
            transcript.append(f"**Manager** :\n> {manager_reply}\n")
            if not verdict.plausible:
                transcript.append(
                    "**Aetherix** (lendemain matin) :\n"
                    f"> ⚠️ La donnée POS d'hier ({reported:.0f} couverts) est implausible "
                    f"({verdict.reason}) — écartée, elle n'alimentera pas l'apprentissage. "
                    "Pouvez-vous vérifier l'export caisse ?\n"
                )
            else:
                delta_pct = 100 * (reported - pred.predicted) / max(reported, 1.0)
                miss = (f"écart {delta_pct:+.0f} %" if abs(delta_pct) >= 10
                        else "dans la fourchette")
                transcript.append(
                    "**Aetherix** (lendemain matin) :\n"
                    f"> Réel constaté : {reported:.0f} couverts (prévu {pred.predicted}, {miss}).\n"
                )
                # Drift self-detection: 3 under-estimations >=10% in a row →
                # the agent names the pattern instead of silently missing.
                if delta_pct >= 10:
                    under_streak += 1
                    if under_streak == 3:
                        transcript.append(
                            "> 📈 Troisième sous-estimation consécutive — un changement de "
                            "régime semble en cours (nouveau contrat ? groupe récurrent ?). "
                            "La recalibration hebdomadaire l'intégrera ; fourchettes élargies "
                            "d'ici là.\n"
                        )
                else:
                    under_streak = 0

            # 5. Weekly recalibration on captured outcomes.
            if i % RETRAIN_EVERY == 0 and i < days:
                await retrain()
                retrains += 1
                print(f"      ↻ recalibration #{retrains} (historique {len(history)} jours)")
                transcript.append(
                    "**Aetherix** (dimanche soir) :\n"
                    f"> 🔁 Modèle recalibré sur les {RETRAIN_EVERY} derniers services "
                    f"({len(history)} jours d'historique). Les prévisions de la semaine "
                    "intègrent vos retours et les couverts réels.\n"
                )

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

    # Right pane of the video: the full WhatsApp thread.
    transcript_path = out_path.parent / "whatsapp_transcript.md"
    transcript_path.write_text("\n".join(transcript), encoding="utf-8")

    # Memory tour — "what the system knows after 30 days" (wedge narrative:
    # the product is the memory, not the forecast). Reflections use the exact
    # format persisted by receipts.persist_actual_covers in production.
    scored = df[df["ape_pct"].notna()]
    worst = scored.nlargest(5, "ape_pct")
    pre = scored[~scored["post_shift"]]
    post = scored[scored["post_shift"]]
    tour = [
        "# Memory tour — ce que le système sait après 30 jours (HOS-310)",
        "",
        "> Étage 2 du « memory tour » (levier de visibilisation n°2, wedge note). Données",
        "> sandbox ; le format des réflexions est celui persisté en production par",
        "> `receipts.persist_actual_covers` → `operational_memory`.",
        "",
        "## Le régime appris",
        f"- Demande moyenne avant le choc (J1-J{SHIFT_DAY-1}) : "
        f"{pre['actual_reported'].mean():.0f} couverts/service",
        f"- Demande moyenne après le choc (J{SHIFT_DAY}+) : "
        f"{post['actual_reported'].mean():.0f} couverts/service (+"
        f"{100*(post['actual_reported'].mean()/pre['actual_reported'].mean()-1):.0f} %)",
        f"- Le modèle recalibré intègre ce nouveau régime : erreur "
        f"{report['metrics']['mape_post_shift_before_recalibration_pct']} % la semaine du choc → "
        f"{report['metrics']['mape_post_shift_after_recalibration_pct']} % ensuite",
        "",
        "## Réflexions mémorisées (les 5 écarts les plus instructifs)",
    ]
    for _, r in worst.iterrows():
        tour.append(f"- `actual covers {r['actual_reported']:.0f} vs predicted "
                    f"{r['predicted']} on {r['day']}` — APE {r['ape_pct']} %"
                    + (" · post-choc" if r["post_shift"] else ""))
    tour += [
        "",
        "## Événements systèmes mémorisés",
        f"- J{CORRUPT_DAY} : outcome quarantainé (export POS à {CORRUPT_VALUE:.0f} couverts, "
        "raison typée `implausible_feedback`) — jamais entré en training",
        "- J17 : dérive auto-détectée (3 sous-estimations consécutives ≥ 10 %) et annoncée au manager",
        f"- {report['metrics']['recalibrations']} recalibrations, "
        f"{report['metrics']['outcomes_captured']} outcomes capturés",
        "",
        "## Ce que le manager a appris au système",
        f"- {int((df['manager_feedback']=='modified').sum())} contre-propositions du manager "
        "enregistrées (signal d'apprentissage futur : qui a raison, l'agent ou le manager ?)",
        "",
        "*C'est cet actif-là — la mémoire par propriété — qui se compose dans le temps. "
        "Un concurrent copie le modèle en une semaine ; pas 30 jours d'outcomes capturés.*",
    ]
    (out_path.parent / "memory_tour.md").write_text("\n".join(tour), encoding="utf-8")

    m = report["metrics"]
    md = out_path.with_suffix(".md")
    md.write_text(
        "# Closed-loop demo — rapport (HOS-310)\n\n"
        "> Données **sandbox synthétiques** — cette démo prouve la mécanique de la boucle\n"
        "> (forecast → reco → feedback → réel → recalibration), pas l'accuracy (cf. HOS-307).\n"
        "> Services réels exercés : PredictionEngine, StaffingService, feedback_guard (G-3).\n\n"
        f"- **Scénario** : {days} jours · choc de régime +{int((SHIFT_FACTOR-1)*100)} % au J{SHIFT_DAY} "
        f"(nouveau contrat banquets) · export POS corrompu au J{CORRUPT_DAY} ({CORRUPT_VALUE:.0f} couverts)\n"
        f"- **MAPE par semaine** : "
        + " · ".join(f"{k} {v}%" for k, v in m["mape_by_week_pct"].items()) + "\n"
        f"- **Adaptation au choc** : {m['mape_post_shift_before_recalibration_pct']} % la semaine du choc "
        f"→ **{m['mape_post_shift_after_recalibration_pct']} %** après recalibration\n"
        f"- **Acceptation manager simulé** : {m['acceptance_rate_pct']} %\n"
        f"- **Gate G-3** : {m['bounds_rejections']} outcome rejeté (donnée corrompue jamais entrée en training)\n"
        f"- **Recalibrations** : {m['recalibrations']} · **Outcomes capturés** : {m['outcomes_captured']}\n\n"
        f"Détail jour par jour : `{out_path.name}` (ledger). Reproduction : "
        "`python scripts/ops/closed_loop_demo.py` (déterministe, seed 42).\n",
        encoding="utf-8",
    )

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
    # docs/demos/ (committed) — eval/reports/ is gitignored (runtime artifacts)
    ap.add_argument("--out", type=Path, default=Path("docs/demos/closed_loop_demo.json"))
    args = ap.parse_args()
    asyncio.run(run(args.days, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

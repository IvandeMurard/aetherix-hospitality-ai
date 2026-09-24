"""Baseline load/save + regression diff — ADR-0007 §5.b / §D2.

Git-tracked `eval/baselines/<layer>_baseline.json` is the runtime source of
truth (ADR §6.c). A regression is a per-category MAPE increase beyond
`REGRESSION_PP` percentage points versus the frozen baseline (AC10).
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINES_DIR = _ROOT / "eval" / "baselines"

# AC10 — fail threshold: > 3pp per-category MAPE regression vs baseline.
REGRESSION_PP = 0.03

# EVAL-4 (HOS-208) — fail threshold: parser accuracy drop > 2pp vs baseline.
PARSER_ACCURACY_DROP_PP = 0.02


def baseline_path(layer: str) -> Path:
    return BASELINES_DIR / f"{layer}_baseline.json"


def load_baseline(layer: str) -> dict | None:
    path = baseline_path(layer)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(layer: str, result: dict) -> Path:
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = baseline_path(layer)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return path


def diff_parser(result: dict, baseline: dict | None) -> dict:
    """Parser regression vs the real-model baseline (EVAL-4, ADR-0007 §15).

    Only a real-backend result is compared, and only against a real-backend
    baseline. The fake backend is a plumbing check: it has no baseline and can
    never regress or pass on quality. A baseline that is not a real-model run is
    ignored rather than trusted.
    """
    if result.get("backend") != "real":
        return {
            "has_baseline": False,
            "regressed": False,
            "accuracy_delta_pp": None,
            "plumbing_only": True,
        }
    breaches = (result.get("thresholds") or {}).get("breaches") or []
    if not baseline or baseline.get("backend") != "real":
        return {
            "has_baseline": False,
            "regressed": False,
            "accuracy_delta_pp": None,
            "below_threshold": bool(breaches),
        }
    cur = result.get("accuracy")
    base = baseline.get("accuracy")
    if cur is None or base is None:
        return {"has_baseline": True, "regressed": False, "accuracy_delta_pp": None,
                "below_threshold": bool(breaches)}
    delta = cur - base
    return {
        "has_baseline": True,
        "regressed": delta < -PARSER_ACCURACY_DROP_PP,
        "accuracy_delta_pp": round(delta * 100, 2),
        "below_threshold": bool(breaches),
    }


def parser_baseline_freeze_refusal(result: dict) -> str | None:
    """Why a parser result may NOT be frozen as baseline, or None if it may.

    Canary rule (Décision #29, applied to the LLM): three runs at the production
    temperature with identical per-case predictions (variance 0.00pp). A fake
    result is never a baseline.
    """
    if result.get("backend") != "real":
        return "fake backend is a plumbing check — it is never frozen as a parser baseline"
    canary = result.get("canary") or {}
    if canary.get("runs", 0) < 3:
        return f"canary needs >= 3 runs, got {canary.get('runs', 0)} (use --runs 3)"
    if not canary.get("identical_predictions") or canary.get("variance_pp") != 0:
        return (
            f"runs disagree (variance {canary.get('variance_pp')}pp, identical "
            f"predictions={canary.get('identical_predictions')}) — not frozen"
        )
    return None


def diff_guardrail(result: dict, baseline: dict | None) -> dict:
    """Guardrail regression (HOS-321) — any drop is a regression, no tolerance.

    Deliberately stricter than forecast/parser: those measure a stochastic
    quantity where a small delta is noise. This layer measures whether a typed
    reason still fires, which is binary. Losing one covered reason means a
    failure path went untested — there is no acceptable margin.
    """
    if not baseline:
        return {"has_baseline": False, "regressed": False, "lost_reasons": []}

    base_reasons = set(baseline.get("reasons_covered") or [])
    cur_reasons = set(result.get("reasons_covered") or [])
    lost = sorted(base_reasons - cur_reasons)

    base_acc = baseline.get("accuracy")
    cur_acc = result.get("accuracy")
    acc_dropped = (
        base_acc is not None and cur_acc is not None and cur_acc < base_acc
    )

    return {
        "has_baseline": True,
        "regressed": bool(lost) or acc_dropped,
        "lost_reasons": lost,
        "accuracy_delta_pp": (
            round((cur_acc - base_acc) * 100, 2)
            if base_acc is not None and cur_acc is not None
            else None
        ),
    }


def diff_forecast(result: dict, baseline: dict | None) -> dict:
    """Per-category MAPE delta vs baseline + regression verdict.

    Returns {has_baseline, regressions:[{category, baseline, current, delta_pp}],
    deltas:{category: delta_pp}}.
    """
    if not baseline:
        return {"has_baseline": False, "regressions": [], "deltas": {}}

    base = baseline.get("per_category_mape", {})
    cur = result.get("per_category_mape", {})
    deltas: dict[str, float] = {}
    regressions: list[dict] = []
    for cat, cur_mape in cur.items():
        if cat not in base or base[cat] is None or cur_mape is None:
            continue
        delta = cur_mape - base[cat]
        deltas[cat] = round(delta, 4)
        if delta > REGRESSION_PP:
            regressions.append(
                {
                    "category": cat,
                    "baseline": round(base[cat], 4),
                    "current": round(cur_mape, 4),
                    "delta_pp": round(delta * 100, 2),
                }
            )
    return {"has_baseline": True, "regressions": regressions, "deltas": deltas}

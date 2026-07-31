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
    """Parser accuracy regression vs baseline (EVAL-4 — drop > 2pp = regression)."""
    if not baseline:
        return {"has_baseline": False, "regressed": False, "accuracy_delta_pp": None}
    cur = result.get("accuracy")
    base = baseline.get("accuracy")
    if cur is None or base is None:
        return {"has_baseline": True, "regressed": False, "accuracy_delta_pp": None}
    delta = cur - base
    return {
        "has_baseline": True,
        "regressed": delta < -PARSER_ACCURACY_DROP_PP,
        "accuracy_delta_pp": round(delta * 100, 2),
    }


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

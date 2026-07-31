"""Runtime-guardrail trip eval — HOS-321, ADR-0009 / NFR2.

Every guardrail trip must be logged with a *typed reason* (Décision #27, NFR2).
Before this layer, 11 of the 13 declared reasons were exercised by no scenario:
the failure paths of Epic 12 were untested. Detected by the architectural
hygiene agent (HOS-320, detector D4).

What a scenario asserts here is deliberately NOT a business value. It asserts:

    given this input, did the expected typed reason fire — and only that one?

Two consequences that matter:

* **Negative scenarios are mandatory.** A guardrail that trips on everything
  would pass a suite made only of positive cases. Each reason is paired with a
  nominal input expecting `null`.
* **This does not reopen ADR-0007 §D2.g.** That boundary exempts runtime
  guardrails (Bras B) from EVAL-1 *metric* coverage. Locking a reason string is
  a different object: it is regression cover on the NFR2 contract itself.

Every predicate called here is pure — no DB, no network, no Prophet. That is
what makes this layer deterministic enough to gate a merge (Décision #29).
"""
from __future__ import annotations

import sys
from pathlib import Path

from .loader import DEFAULT_DATASET, load_scenarios

# `backend/` on the path so `app.*` imports resolve. eval_parser only touches
# `app` in its nightly `real` branch, which CI never runs — this layer needs the
# guardrail modules on every run, so the path is set up here rather than left to
# the caller's environment.
_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# ─── Predicate registry ───────────────────────────────────────────────────────
# scenario `input.guard` → callable(**input.args) -> reason | None
# Each entry normalises its guardrail's native return shape to a single reason
# string (or None for "no trip"), so scenarios stay uniform across guardrails.


def _forecast(**kw) -> str | None:
    from app.services import forecast_guardrail

    verdict = forecast_guardrail.evaluate(**kw)
    return verdict.reason


def _feedback(**kw) -> str | None:
    from app.services import feedback_guard

    return feedback_guard.evaluate(**kw).reason


def _output_sanity(**kw) -> str | None:
    from app.services import output_sanity

    flags = output_sanity.evaluate(**kw).flags
    return flags[0][0] if flags else None


def _error_rate(**kw) -> str | None:
    from app.workers import error_rate_monitor

    stats = error_rate_monitor.WindowStats(**kw)
    breaches = error_rate_monitor.evaluate(stats)
    return breaches[0][0] if breaches else None


def _dead_man(**kw) -> str | None:
    from app.workers import heartbeat

    breach = heartbeat.evaluate_dead_man(**kw)
    return breach[0] if breach else None


def _partial(**kw) -> str | None:
    from app.workers import heartbeat

    breach = heartbeat.evaluate_partial(**kw)
    return breach[0] if breach else None


def _job_error(**kw) -> str | None:
    from app.workers import heartbeat

    breach = heartbeat.evaluate_job_error(**kw)
    return breach[0] if breach else None


def _mock_suppression(**kw) -> str | None:
    from app.services import whatsapp_service

    breach = whatsapp_service.evaluate_mock_suppression(**kw)
    return breach[0] if breach else None


GUARDS = {
    "forecast_guardrail": _forecast,
    "feedback_guard": _feedback,
    "output_sanity": _output_sanity,
    "error_rate_monitor": _error_rate,
    "heartbeat_dead_man": _dead_man,
    "heartbeat_partial": _partial,
    "heartbeat_job_error": _job_error,
    "mock_forecast": _mock_suppression,
}


def compute_guardrail_metrics(scenarios: list[dict]) -> dict:
    """Pure metrics: per-scenario verdict, per-reason coverage, accuracy.

    `expected.reason` is the ground truth — `null` means "must not trip".
    """
    results: list[dict] = []
    correct = 0

    for sc in scenarios:
        spec = sc.get("input", {})
        guard_name = spec.get("guard")
        expected = sc.get("expected", {}).get("reason")

        guard = GUARDS.get(guard_name)
        if guard is None:
            results.append({
                "id": sc.get("id"),
                "guard": guard_name,
                "expected": expected,
                "actual": None,
                "ok": False,
                "error": f"unknown guard {guard_name!r}",
            })
            continue

        try:
            actual = guard(**spec.get("args", {}))
            error = None
        except Exception as exc:  # noqa: BLE001 — a crashing guard is a failed scenario
            actual, error = None, f"{type(exc).__name__}: {exc}"

        ok = error is None and actual == expected
        correct += int(ok)
        results.append({
            "id": sc.get("id"),
            "guard": guard_name,
            "expected": expected,
            "actual": actual,
            "ok": ok,
            "error": error,
        })

    total = len(results)

    # Reason coverage: which typed reasons does at least one *positive* scenario
    # exercise? This is the number HOS-320 D4 watches.
    covered = sorted({
        r["expected"] for r in results if r["expected"] is not None and r["ok"]
    })
    negatives = sum(1 for r in results if r["expected"] is None)

    return {
        "layer": "guardrail",
        "accuracy": round(correct / total, 4) if total else None,
        "n": total,
        "n_negative": negatives,
        "reasons_covered": covered,
        "n_reasons_covered": len(covered),
        "failures": [r for r in results if not r["ok"]],
        "results": results,
    }


def run(dataset: Path = DEFAULT_DATASET, seed: int = 42) -> dict:
    """Load guardrail_trip scenarios and evaluate every predicate."""
    scenarios = [
        s for s in load_scenarios(dataset, layer="guardrail")
        if s.get("category") == "guardrail_trip"
    ]
    if not scenarios:
        raise SystemExit("[eval_guardrail] no guardrail_trip scenarios in dataset")
    return compute_guardrail_metrics(scenarios)

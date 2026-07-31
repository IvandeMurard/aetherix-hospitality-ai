"""HOS-321 — guardrail eval layer: metrics, diff, and the extracted predicates.

Two halves:
  * `compute_guardrail_metrics` / `diff_guardrail` — pure eval logic, exercised
    with synthetic scenarios so the tests do not move when the real dataset does.
  * the predicates extracted from the async job bodies (heartbeat ×3, whatsapp)
    — previously untestable without a database, and untested. These are the
    first tests they have.
"""
from __future__ import annotations

import pytest

from scripts.eval.baselines import diff_guardrail
from scripts.eval.eval_guardrail import compute_guardrail_metrics


def _sc(sid: str, guard: str, args: dict, reason: str | None) -> dict:
    return {
        "id": sid,
        "category": "guardrail_trip",
        "layer": "guardrail",
        "input": {"guard": guard, "args": args},
        "expected": {"reason": reason},
    }


# ─── Metrics ──────────────────────────────────────────────────────────────────


def test_positive_and_negative_scenarios_both_count():
    scenarios = [
        _sc("pos", "heartbeat_partial", {"failed": 3, "dispatched": 7}, "partial_hotel_failures"),
        _sc("neg", "heartbeat_partial", {"failed": 0, "dispatched": 10}, None),
    ]

    r = compute_guardrail_metrics(scenarios)

    assert r["accuracy"] == 1.0
    assert r["n"] == 2
    assert r["n_negative"] == 1
    assert r["reasons_covered"] == ["partial_hotel_failures"]


def test_wrong_reason_is_a_failure():
    """A guard firing the *wrong* typed reason must not pass — NFR2 is about the
    reason, not merely about tripping."""
    scenarios = [
        _sc("x", "heartbeat_partial", {"failed": 1, "dispatched": 1}, "dead_man_timeout"),
    ]

    r = compute_guardrail_metrics(scenarios)

    assert r["accuracy"] == 0.0
    assert r["failures"][0]["actual"] == "partial_hotel_failures"
    assert r["reasons_covered"] == []


def test_a_guard_that_trips_on_everything_fails_its_negative():
    scenarios = [
        _sc("pos", "heartbeat_job_error", {"exc": "boom"}, "job_error"),
        _sc("neg", "heartbeat_job_error", {"exc": None}, "job_error"),  # wrong expectation
    ]

    r = compute_guardrail_metrics(scenarios)

    assert r["accuracy"] == 0.5


def test_unknown_guard_is_reported_not_silently_skipped():
    r = compute_guardrail_metrics([_sc("x", "nope", {}, "whatever")])

    assert r["accuracy"] == 0.0
    assert "unknown guard" in r["failures"][0]["error"]


def test_crashing_guard_is_a_failure_even_when_expecting_no_trip():
    """Expected None + a crash is still a failure — otherwise an import error
    would masquerade as a clean negative (the exact shape of a silent pass)."""
    r = compute_guardrail_metrics([_sc("x", "heartbeat_partial", {"bad_kwarg": 1}, None)])

    assert r["accuracy"] == 0.0
    assert r["failures"][0]["error"]


# ─── Baseline diff ────────────────────────────────────────────────────────────


def test_losing_a_covered_reason_is_a_regression():
    baseline = {"reasons_covered": ["job_error", "dead_man_timeout"], "accuracy": 1.0}
    result = {"reasons_covered": ["job_error"], "accuracy": 1.0}

    diff = diff_guardrail(result, baseline)

    assert diff["regressed"] is True
    assert diff["lost_reasons"] == ["dead_man_timeout"]


def test_any_accuracy_drop_is_a_regression_no_tolerance():
    """Stricter than forecast/parser on purpose: this layer measures a binary
    property, so there is no noise margin to absorb."""
    baseline = {"reasons_covered": ["job_error"], "accuracy": 1.0}
    result = {"reasons_covered": ["job_error"], "accuracy": 0.99}

    assert diff_guardrail(result, baseline)["regressed"] is True


def test_gaining_a_reason_is_not_a_regression():
    baseline = {"reasons_covered": ["job_error"], "accuracy": 1.0}
    result = {"reasons_covered": ["job_error", "dead_man_timeout"], "accuracy": 1.0}

    diff = diff_guardrail(result, baseline)

    assert diff["regressed"] is False
    assert diff["lost_reasons"] == []


def test_no_baseline_is_not_a_regression():
    assert diff_guardrail({"reasons_covered": [], "accuracy": None}, None)["regressed"] is False


# ─── Extracted predicates (production code, first tests) ──────────────────────


@pytest.mark.parametrize(
    "gap_min,window_min,expected",
    [
        (120, 60, "dead_man_timeout"),
        (60, 60, None),      # boundary: equal is inside the window
        (30, 60, None),
        (999, None, None),   # unregistered job → never trips
    ],
)
def test_evaluate_dead_man(gap_min, window_min, expected):
    from app.workers.heartbeat import evaluate_dead_man

    breach = evaluate_dead_man(gap_min, window_min)
    assert (breach[0] if breach else None) == expected


@pytest.mark.parametrize(
    "failed,dispatched,expected",
    [(3, 7, "partial_hotel_failures"), (1, 0, "partial_hotel_failures"), (0, 10, None)],
)
def test_evaluate_partial(failed, dispatched, expected):
    from app.workers.heartbeat import evaluate_partial

    breach = evaluate_partial(failed, dispatched)
    assert (breach[0] if breach else None) == expected


def test_evaluate_partial_details_report_the_ratio():
    from app.workers.heartbeat import evaluate_partial

    _, detail = evaluate_partial(3, 7)
    assert "3/10" in detail


@pytest.mark.parametrize(
    "exc,expected",
    [(RuntimeError("boom"), "job_error"), ("already formatted", "job_error"), (None, None)],
)
def test_evaluate_job_error(exc, expected):
    from app.workers.heartbeat import evaluate_job_error

    breach = evaluate_job_error(exc)
    assert (breach[0] if breach else None) == expected


@pytest.mark.parametrize(
    "is_mock,demo_mode,expected",
    [
        (True, False, "mock_forecast_suppressed"),
        (True, True, None),    # demo: numbers allowed but visibly marked
        (False, False, None),
        (False, True, None),
    ],
)
def test_evaluate_mock_suppression(is_mock, demo_mode, expected):
    from app.services.whatsapp_service import evaluate_mock_suppression

    breach = evaluate_mock_suppression(is_mock, demo_mode)
    assert (breach[0] if breach else None) == expected

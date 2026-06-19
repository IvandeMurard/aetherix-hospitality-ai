"""HOS-216 (EVAL-1 gate / ADR-0007 §4) — check_eval_coverage unit tests.

Exercises the gate's verdict logic with the engine + git diff + cache fully
mocked: exit codes 0/1/2/3, eval-exempt skip, cache hit, touched-but-not-
evaluated, and not-yet-evaluable layers. No Prophet, no git, no network (AC6).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_GATE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "check_eval_coverage.py"
_spec = importlib.util.spec_from_file_location("check_eval_coverage", _GATE_PATH)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _forecast_payload(*, pass_cats: int, fail_cats: int = 0, regression: bool = False):
    scenarios = [{"category": f"p{i}", "tolerance_pass": True} for i in range(pass_cats)]
    scenarios += [{"category": f"f{i}", "tolerance_pass": False} for i in range(fail_cats)]
    result = {"layer": "forecast", "overall_mape_j1_holdout": 0.10, "scenarios": scenarios}
    diff = {"has_baseline": True, "regressions": [{"category": "x"}] if regression else [], "deltas": {}}
    return (1 if regression else 0, {"result": result, "diff": diff})


def _parser_payload():
    return (0, {"result": {"layer": "parser", "accuracy": 0.9}, "diff": {"has_baseline": True, "regressed": False}})


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Default seams: no labels, empty cache, no-op cache write, defaults argv."""
    monkeypatch.setattr(gate, "get_pr_labels", lambda: set())
    monkeypatch.setattr(gate, "_load_cache", lambda: {})
    monkeypatch.setattr(gate, "_save_cache", lambda key: None)
    monkeypatch.setattr(sys, "argv", ["check_eval_coverage"])


def _set_changed(monkeypatch, files: list[str]):
    monkeypatch.setattr(gate, "get_changed_files", lambda base_ref: files)


def _set_engine(monkeypatch, by_layer: dict):
    def fake(layer, json_out, md_out):
        return by_layer[layer]
    monkeypatch.setattr(gate, "invoke_run_all", fake)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_eval_exempt_label_skips(monkeypatch):
    monkeypatch.setattr(gate, "get_pr_labels", lambda: {"eval-exempt"})
    _set_changed(monkeypatch, ["backend/app/services/prediction_engine.py"])
    assert gate.main() == gate.PASS


def test_no_trigger_touched_passes(monkeypatch):
    _set_changed(monkeypatch, ["README.md", "docs/x.md"])
    assert gate.main() == gate.PASS


def test_regression_fails(monkeypatch):
    _set_changed(monkeypatch, ["backend/app/services/prediction_engine.py",
                               "eval/golden_dataset.jsonl"])
    _set_engine(monkeypatch, {"forecast": _forecast_payload(pass_cats=5, regression=True),
                              "parser": _parser_payload()})
    assert gate.main() == gate.FAIL


def test_low_coverage_fails(monkeypatch):
    # 1 pass / (1 pass + 2 fail) = 33% < 60% -> FAIL
    _set_changed(monkeypatch, ["eval/golden_dataset.jsonl"])
    _set_engine(monkeypatch, {"forecast": _forecast_payload(pass_cats=1, fail_cats=2),
                              "parser": _parser_payload()})
    assert gate.main() == gate.FAIL


def test_mid_coverage_warns(monkeypatch):
    # 3 pass / 4 = 75% -> WARN (60-80%)
    _set_changed(monkeypatch, ["eval/golden_dataset.jsonl"])
    _set_engine(monkeypatch, {"forecast": _forecast_payload(pass_cats=3, fail_cats=1),
                              "parser": _parser_payload()})
    assert gate.main() == gate.WARN


def test_full_coverage_passes(monkeypatch):
    # 5 pass / 5 = 100%, dataset touched (no touched-but-not-evaluated) -> PASS
    _set_changed(monkeypatch, ["eval/golden_dataset.jsonl"])
    _set_engine(monkeypatch, {"forecast": _forecast_payload(pass_cats=5),
                              "parser": _parser_payload()})
    assert gate.main() == gate.PASS


def test_engine_crash_errors(monkeypatch):
    _set_changed(monkeypatch, ["eval/golden_dataset.jsonl"])
    _set_engine(monkeypatch, {"forecast": (2, None), "parser": _parser_payload()})
    assert gate.main() == gate.ERROR


def test_touched_but_not_evaluated_warns(monkeypatch):
    # Code trigger changed, golden dataset NOT -> WARN even with good coverage.
    _set_changed(monkeypatch, ["backend/app/services/prediction_engine.py"])
    _set_engine(monkeypatch, {"forecast": _forecast_payload(pass_cats=5)})
    assert gate.main() == gate.WARN


def test_layer_without_runner_warns(monkeypatch):
    # receipts.py -> 'receipt' layer, which has no runner yet -> WARN, no engine call.
    _set_changed(monkeypatch, ["backend/app/services/receipts.py"])
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("engine must not run for an unevaluable layer")

    monkeypatch.setattr(gate, "invoke_run_all", _boom)
    assert gate.main() == gate.WARN
    assert called["n"] == 0


def test_cache_hit_skips_engine(monkeypatch):
    touched = ["eval/golden_dataset.jsonl"]
    _set_changed(monkeypatch, touched)
    key = gate.cache_key(touched)
    monkeypatch.setattr(gate, "_load_cache", lambda: {"last_pass_key": key})

    def _boom(*a, **k):
        raise AssertionError("engine must not run on a cache hit")

    monkeypatch.setattr(gate, "invoke_run_all", _boom)
    assert gate.main() == gate.PASS

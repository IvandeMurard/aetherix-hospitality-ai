"""HOS-209 (EVAL-5) — eval_latency unit tests.

Percentile + verdict are pure → asserted exactly. The measurement loop runs with
an injected fake call (no server, no network, no real timing assertions).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "eval" / "eval_latency.py"
_spec = importlib.util.spec_from_file_location("eval_latency", _PATH)
el = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(el)


def test_percentile_nearest_rank_exact():
    xs = [10, 20, 30, 40, 50]
    assert el.percentile(xs, 50) == 30
    assert el.percentile(xs, 95) == 50
    assert el.percentile(xs, 99) == 50
    assert el.percentile([42], 50) == 42
    assert el.percentile([], 50) is None
    # Order-independence
    assert el.percentile([50, 10, 30, 20, 40], 50) == 30


def test_summarize_shape_and_values():
    s = el.summarize([10, 20, 30, 40, 50])
    assert s == {"p50_ms": 30, "p95_ms": 50, "p99_ms": 50, "count": 5}


def test_verdict_breached_and_margin():
    breached = el.verdict({"p95_ms": 9000}, {"p95_ms": 8000})
    assert breached["breached"] is True
    assert breached["margin_ms"] == -1000

    ok = el.verdict({"p95_ms": 5000}, {"p95_ms": 8000})
    assert ok["breached"] is False
    assert ok["margin_ms"] == 3000

    # Missing SLO → cannot breach.
    assert el.verdict({"p95_ms": 9000}, {})["breached"] is False


def test_evaluate_flags_any_breach():
    measured = {"a": {"p95_ms": 9000}, "b": {"p95_ms": 1000}}
    baseline = {"endpoints": {"a": {"p95_ms": 8000}, "b": {"p95_ms": 5000}}}
    report, breached = el.evaluate(measured, baseline)
    assert breached is True
    assert report["a"]["breached"] is True
    assert report["b"]["breached"] is False


async def test_measure_runs_warmup_then_timed():
    calls = {"n": 0}

    async def _fake():
        calls["n"] += 1

    samples = await el.measure(_fake, calls=3, warmup=2)
    assert len(samples) == 3            # only timed calls returned
    assert calls["n"] == 5             # warmup (2) + timed (3)
    assert all(isinstance(x, float) and x >= 0 for x in samples)


def test_baseline_loads_and_has_p95():
    bl = el.load_baseline()
    assert bl["layer"] == "latency"
    assert bl["endpoints"]["mcp_tool_call"]["p95_ms"] == 5000

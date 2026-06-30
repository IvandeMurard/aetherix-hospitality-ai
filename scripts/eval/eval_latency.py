"""Latency SLO eval — EVAL-5 (HOS-209), ADR-0007 §5.e.

Measures p50/p95/p99 per endpoint and checks each endpoint's p95 against the SLO
baseline (`eval/baselines/latency_baseline.json`). The percentile computation, the
summary, and the verdict are pure functions (unit-tested exactly); the timing loop
takes an injectable async `call`, so CI tests run with a simulated client — no
server, no network. A real run drives the FastAPI app in-process via httpx
ASGITransport, or hits staging when `LATENCY_TARGET_BASE_URL` is set.

Usage:
  LATENCY_TARGET_BASE_URL=https://staging.example python scripts/eval/eval_latency.py --calls 20 --strict
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE = _ROOT / "eval" / "baselines" / "latency_baseline.json"

SEED = 42
WARMUP = 3

# Endpoints probed by a real run → (method, path). Keyed by baseline endpoint name.
LIVE_ENDPOINTS = {
    "GET /api/v1/predictions/today": ("GET", "/api/v1/predictions/current"),
    "GET /api/v1/recommendations/today": ("GET", "/api/v1/dashboard/recommendations"),
}


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (deterministic, no interpolation). p in [0, 100]."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarize(samples_ms: list[float]) -> dict:
    """p50/p95/p99 + count from a list of per-call latencies (ms)."""
    return {
        "p50_ms": percentile(samples_ms, 50),
        "p95_ms": percentile(samples_ms, 95),
        "p99_ms": percentile(samples_ms, 99),
        "count": len(samples_ms),
    }


def verdict(summary: dict, slo: dict) -> dict:
    """Compare a summary against an endpoint's SLO row. p95 is the gate."""
    p95 = summary.get("p95_ms")
    threshold = slo.get("p95_ms")
    breached = p95 is not None and threshold is not None and p95 > threshold
    return {
        "p95_ms": p95,
        "slo_p95_ms": threshold,
        "breached": breached,
        "margin_ms": None if (p95 is None or threshold is None) else round(threshold - p95, 1),
    }


async def measure(call: Callable[[], Awaitable[None]], calls: int, warmup: int = WARMUP) -> list[float]:
    """Run `warmup` untimed calls then `calls` timed calls; return latencies (ms).

    `call` is injected so tests can simulate latency without a server.
    """
    for _ in range(warmup):
        await call()
    samples: list[float] = []
    for _ in range(calls):
        start = time.perf_counter()
        await call()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def load_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


async def _run_live(base_url: str, calls: int, warmup: int) -> dict:
    """Probe LIVE_ENDPOINTS over httpx; return {endpoint: summary}."""
    import httpx

    results: dict[str, dict] = {}
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        for name, (method, path) in LIVE_ENDPOINTS.items():
            async def _call(method=method, path=path):
                await client.request(method, path)

            results[name] = summarize(await measure(_call, calls=calls, warmup=warmup))
    return results


def evaluate(measured: dict, baseline: dict) -> tuple[dict, bool]:
    """Build per-endpoint verdicts; return (report, any_breached)."""
    slos = baseline.get("endpoints", {})
    report: dict[str, dict] = {}
    any_breached = False
    for name, summary in measured.items():
        v = verdict(summary, slos.get(name, {}))
        report[name] = {**summary, **v}
        any_breached = any_breached or v["breached"]
    return report, any_breached


def main() -> int:
    parser = argparse.ArgumentParser(description="Latency SLO eval (ADR-0007 §5.e)")
    parser.add_argument("--calls", type=int, default=20, help="Timed calls per endpoint")
    parser.add_argument("--warmup", type=int, default=WARMUP, help="Untimed warmup calls")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any p95 > SLO")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    base_url = os.environ.get("LATENCY_TARGET_BASE_URL")
    if not base_url:
        print(
            "[eval_latency] LATENCY_TARGET_BASE_URL not set — nothing to probe. "
            "Set it to a staging URL (the SLO bench runs against staging, not per-PR CI)."
        )
        return 0

    baseline = load_baseline()
    measured = asyncio.run(_run_live(base_url, args.calls, args.warmup))
    report, breached = evaluate(measured, baseline)

    for name, row in report.items():
        flag = "BREACH" if row["breached"] else "ok"
        print(f"[eval_latency] {name}: p95={row['p95_ms']}ms slo={row['slo_p95_ms']}ms [{flag}]")

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return 1 if (breached and args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())

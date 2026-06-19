"""HOS-209 (EVAL-5) — latency_slo_worker unit tests.

Pure breach detection asserted directly; the job is asserted non-blocking on a DB
failure and to inject its cron job without starting the scheduler.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.workers import latency_slo_worker as w


def test_load_slo_p95_has_default_and_endpoints():
    slo = w.load_slo_p95()
    assert slo["mcp_tool_call"] == 5000
    assert slo["_default"] == 5000  # default = tool-call SLO
    assert slo["inbound_parser_haiku"] == 2000


def test_breaching_endpoints_uses_exact_then_default():
    slo = {"known": 1000, "_default": 5000}
    rows = [
        {"endpoint": "known", "p95_ms": 1500},   # > exact 1000 -> breach
        {"endpoint": "known", "p95_ms": 900},    # under -> ok
        {"endpoint": "other", "p95_ms": 6000},   # > default 5000 -> breach
        {"endpoint": "other", "p95_ms": 4000},   # under default -> ok
    ]
    breaches = w.breaching_endpoints(rows, slo)
    eps = [(b["endpoint"], b["p95_ms"]) for b in breaches]
    assert eps == [("known", 1500), ("other", 6000)]


def test_breaching_endpoints_skips_when_no_slo_and_no_default():
    rows = [{"endpoint": "x", "p95_ms": 9999}]
    assert w.breaching_endpoints(rows, {}) == []


def test_breaching_endpoints_ignores_null_p95():
    rows = [{"endpoint": "x", "p95_ms": None}]
    assert w.breaching_endpoints(rows, {"_default": 1000}) == []


async def test_job_is_non_blocking_on_db_failure(monkeypatch):
    class _BoomEngine:
        def begin(self):
            raise RuntimeError("DB down")

    monkeypatch.setattr(w, "engine", _BoomEngine())
    # Must swallow — instrumentation never breaks the app.
    await w.run_latency_slo_job()


def test_register_injects_job_without_starting():
    scheduler = MagicMock()
    w.register_latency_slo_job(scheduler)
    scheduler.add_job.assert_called_once()
    scheduler.start.assert_not_called()
    assert scheduler.add_job.call_args.kwargs.get("id") == "latency_slo_worker"

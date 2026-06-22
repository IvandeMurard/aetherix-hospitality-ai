"""Latency SLO MV refresh + breach alerting — EVAL-5 (HOS-209), ADR-0007 §5.e.

Nightly APScheduler job that (1) refreshes the `latency_slo_daily` MV and (2)
raises a WhatsApp ops anomaly for any endpoint whose daily p95 breaches its SLO
(`eval/baselines/latency_baseline.json`). Fire-and-forget: a failure here never
breaks the app (mirrors kpi_aggregator).

Granularity note (AC5): the brief's "p95 breached > 5 consecutive minutes" needs
minute-bucketed latency; the daily MV gives a daily p95, so we alert on a daily
breach. Sub-window consecutive-breach detection is a follow-up once REST endpoint
latency is persisted at finer granularity (see docs/ops/latency-slo.md).
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BASELINE = _ROOT / "eval" / "baselines" / "latency_baseline.json"
# Persisted latency_ms today is MCP/LLM tool calls — judge them against the
# tool-call SLO unless an endpoint name matches a baseline row exactly.
_DEFAULT_SLO_KEY = "mcp_tool_call"


def load_slo_p95() -> dict[str, float]:
    """endpoint-name -> p95 SLO (ms) from the baseline, plus a `_default`."""
    data = json.loads(_BASELINE.read_text(encoding="utf-8"))
    slo: dict[str, float] = {}
    for name, row in data.get("endpoints", {}).items():
        if row.get("p95_ms") is not None:
            slo[name] = float(row["p95_ms"])
    if _DEFAULT_SLO_KEY in slo:
        slo["_default"] = slo[_DEFAULT_SLO_KEY]
    return slo


def breaching_endpoints(rows: list[dict], slo_p95: dict[str, float]) -> list[dict]:
    """Pure: return the rows whose p95 exceeds their SLO (default for unknown).

    `rows` items: {"endpoint", "p95_ms", ...}. An endpoint with no matching SLO
    and no `_default` is skipped (can't judge it).
    """
    breaches: list[dict] = []
    for r in rows:
        threshold = slo_p95.get(r["endpoint"], slo_p95.get("_default"))
        p95 = r.get("p95_ms")
        if threshold is not None and p95 is not None and p95 > threshold:
            breaches.append(
                {"endpoint": r["endpoint"], "p95_ms": p95, "slo_p95_ms": threshold}
            )
    return breaches


async def _refresh_mv(conn) -> None:
    """REFRESH the MV (non-concurrent on first, never-populated refresh)."""
    populated = (
        await conn.execute(
            text(
                "SELECT relispopulated FROM pg_class "
                "WHERE oid = 'latency_slo_daily'::regclass"
            )
        )
    ).scalar()
    if populated:
        await conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latency_slo_daily"))
    else:
        await conn.execute(text("REFRESH MATERIALIZED VIEW latency_slo_daily"))


async def _today_rows(conn) -> list[dict]:
    result = await conn.execute(
        text(
            """
            SELECT endpoint, p95_ms, p50_ms, p99_ms, sample_count
            FROM latency_slo_daily
            WHERE day = (NOW() AT TIME ZONE 'UTC')::date
            """
        )
    )
    return [
        {
            "endpoint": row.endpoint,
            "p95_ms": float(row.p95_ms) if row.p95_ms is not None else None,
            "sample_count": int(row.sample_count),
        }
        for row in result.fetchall()
    ]


async def run_latency_slo_job() -> None:
    """Refresh the MV + alert on p95 SLO breaches. Non-blocking."""
    job_id = str(uuid.uuid4())[:8]
    try:
        async with engine.begin() as conn:
            await _refresh_mv(conn)
            rows = await _today_rows(conn)

        breaches = breaching_endpoints(rows, load_slo_p95())
        logger.info(
            "latency_slo_worker: refreshed MV, %d endpoints, %d breach(es) job_id=%s",
            len(rows),
            len(breaches),
            job_id,
        )
        if breaches:
            await _alert(breaches)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "latency_slo_worker: job failed (non-blocking) job_id=%s error=%s", job_id, exc
        )


async def _alert(breaches: list[dict]) -> None:
    detail = "Latency SLO p95 breach(es) today:\n" + "\n".join(
        f"- {b['endpoint']}: p95 {b['p95_ms']:.0f}ms > SLO {b['slo_p95_ms']:.0f}ms"
        for b in breaches
    )
    try:
        from app.services.ops_dispatcher import dispatch_anomaly

        await dispatch_anomaly(
            title=f"Latency SLO breach — {len(breaches)} endpoint(s)",
            detail=detail,
            tags=["latency", "slo"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("latency_slo_worker: alert dispatch failed: %s", exc)


def register_latency_slo_job(scheduler) -> None:
    """Register the nightly latency SLO refresh+alert job (03:10 UTC)."""
    scheduler.add_job(
        run_latency_slo_job,
        trigger="cron",
        hour=3,
        minute=10,
        id="latency_slo_worker",
        replace_existing=True,
    )
    logger.info("latency_slo_worker: cron job registered (nightly 03:10 UTC)")

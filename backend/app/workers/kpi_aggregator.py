"""APScheduler job — daily Trust-KPI aggregation at 02:30 UTC (HOS-177 / P3-3).

Computes recommendation_acceptance_rate per tenant from the
recommendation_acceptance_daily materialized view and persists results to
kpi_daily. Emits a trust_low alert row to agent_action_log when the 7-day
rolling rate drops below 0.30 for a tenant with enough signal (denominator >= 5).

Rate formula (spec decision — outcome vocab mismatch resolved):
    rate = followed / (followed + rejected + neutral)
where denominator excludes NULL manager_feedback rows (handled by the MV WHERE clause).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

_KPI_NAME = "recommendation_acceptance_rate"
_ALERT_THRESHOLD = 0.30
_ALERT_MIN_DENOMINATOR = 5  # avoid false alerts on sparse data


# ---------------------------------------------------------------------------
# Pure computation helpers (testable without DB)
# ---------------------------------------------------------------------------

def compute_rate(followed: int, rejected: int, neutral: int) -> Optional[float]:
    """Return acceptance rate or None when denominator is zero."""
    denominator = followed + rejected + neutral
    if denominator == 0:
        return None
    return followed / denominator


# ---------------------------------------------------------------------------
# DB-level helpers
# ---------------------------------------------------------------------------

async def _aggregate_yesterday(conn, yesterday: date) -> list[dict]:
    """Return per-tenant aggregates for yesterday from the MV."""
    result = await conn.execute(
        text("""
            SELECT
                hotel_id,
                COALESCE(SUM(cnt) FILTER (WHERE manager_feedback = 'followed'), 0) AS followed,
                COALESCE(SUM(cnt) FILTER (WHERE manager_feedback = 'rejected'), 0) AS rejected,
                COALESCE(SUM(cnt) FILTER (WHERE manager_feedback = 'neutral'),  0) AS neutral
            FROM recommendation_acceptance_daily
            WHERE kpi_date = :kpi_date
            GROUP BY hotel_id
        """),
        {"kpi_date": yesterday},
    )
    return [
        {
            "hotel_id": row.hotel_id,
            "followed": int(row.followed),
            "rejected": int(row.rejected),
            "neutral": int(row.neutral),
        }
        for row in result.fetchall()
    ]


async def _upsert_kpi_row(
    conn,
    tenant_id: str,
    kpi_date: date,
    rate: float,
    numerator: int,
    denominator: int,
) -> None:
    await conn.execute(
        text("""
            INSERT INTO kpi_daily
                (tenant_id, kpi_date, kpi_name, value, numerator, denominator, computed_at)
            VALUES
                (:tenant_id, :kpi_date, :kpi_name, :value, :numerator, :denominator, NOW())
            ON CONFLICT (tenant_id, kpi_date, kpi_name) DO UPDATE SET
                value        = EXCLUDED.value,
                numerator    = EXCLUDED.numerator,
                denominator  = EXCLUDED.denominator,
                computed_at  = NOW()
        """),
        {
            "tenant_id": tenant_id,
            "kpi_date": kpi_date,
            "kpi_name": _KPI_NAME,
            "value": rate,
            "numerator": numerator,
            "denominator": denominator,
        },
    )


async def _check_and_emit_alerts(conn, today: date) -> None:
    """Emit trust_low alert rows for tenants with 7-day rolling rate < 0.30."""
    window_start = today - timedelta(days=6)  # 7 days inclusive

    rolling = await conn.execute(
        text("""
            SELECT
                tenant_id,
                AVG(value)        AS rolling_rate,
                SUM(denominator)  AS window_denom
            FROM kpi_daily
            WHERE kpi_name    = :kpi_name
              AND kpi_date BETWEEN :window_start AND :today
            GROUP BY tenant_id
            HAVING SUM(denominator) >= :min_denom
               AND AVG(value) < :threshold
        """),
        {
            "kpi_name": _KPI_NAME,
            "window_start": window_start,
            "today": today,
            "min_denom": _ALERT_MIN_DENOMINATOR,
            "threshold": _ALERT_THRESHOLD,
        },
    )

    for row in rolling.fetchall():
        tenant_id = row.tenant_id
        rolling_rate = float(row.rolling_rate)

        # Deduplication: one alert per tenant per day
        existing = await conn.execute(
            text("""
                SELECT 1 FROM agent_action_log
                WHERE tool_name = 'kpi_aggregator'
                  AND hotel_id  = :hotel_id
                  AND DATE(created_at AT TIME ZONE 'UTC') = :today
                LIMIT 1
            """),
            {"hotel_id": tenant_id, "today": today},
        )
        if existing.fetchone() is not None:
            continue

        logger.warning(
            "kpi_aggregator: trust_low  tenant_id=%s  rolling_rate=%.3f",
            tenant_id,
            rolling_rate,
        )
        await conn.execute(
            text("""
                INSERT INTO agent_action_log
                    (hotel_id, tool_name, scopes, status, request_id, payload)
                VALUES
                    (:hotel_id, 'kpi_aggregator', ARRAY[]::TEXT[], 'ok', '', :payload)
            """),
            {
                "hotel_id": tenant_id,
                "payload": json.dumps({"kpi_alert": "trust_low", "rolling_rate": rolling_rate}),
            },
        )


# ---------------------------------------------------------------------------
# Main job entry point
# ---------------------------------------------------------------------------

async def run_kpi_aggregation() -> None:
    job_id = str(uuid.uuid4())[:8]
    yesterday = date.today() - timedelta(days=1)

    try:
        async with engine.begin() as conn:
            # Step 1: refresh the MV so today's slice is current.
            # REFRESH ... CONCURRENTLY requires the MV to be already populated;
            # on a fresh database it exists but has never been populated, so the
            # first refresh must be non-concurrent (observed on Fly staging while
            # closing HOS-190 AC6 — otherwise the cron silently never populates).
            populated = (
                await conn.execute(
                    text(
                        "SELECT relispopulated FROM pg_class "
                        "WHERE oid = 'recommendation_acceptance_daily'::regclass"
                    )
                )
            ).scalar()
            if populated:
                await conn.execute(
                    text("REFRESH MATERIALIZED VIEW CONCURRENTLY recommendation_acceptance_daily")
                )
            else:
                await conn.execute(
                    text("REFRESH MATERIALIZED VIEW recommendation_acceptance_daily")
                )

            # Step 2: aggregate yesterday's slice per tenant → upsert kpi_daily
            tenant_rows = await _aggregate_yesterday(conn, yesterday)
            tenant_count = 0
            for row in tenant_rows:
                rate = compute_rate(row["followed"], row["rejected"], row["neutral"])
                if rate is None:
                    continue  # zero recommendations — no row written
                await _upsert_kpi_row(
                    conn,
                    tenant_id=row["hotel_id"],
                    kpi_date=yesterday,
                    rate=rate,
                    numerator=row["followed"],
                    denominator=row["followed"] + row["rejected"] + row["neutral"],
                )
                tenant_count += 1

            logger.info("kpi_aggregator: computed %d tenants  job_id=%s", tenant_count, job_id)

            # Step 3: 7-day rolling alert check
            await _check_and_emit_alerts(conn, yesterday)

    except Exception as exc:
        logger.warning(
            "kpi_aggregator: aggregation failed (non-blocking)  job_id=%s  error=%s",
            job_id,
            exc,
        )


def register_kpi_aggregator_job(scheduler) -> None:
    scheduler.add_job(
        run_kpi_aggregation,
        trigger="cron",
        hour=2,
        minute=30,
        id="kpi_aggregator",
        replace_existing=True,
    )

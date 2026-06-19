-- HOS-209 (EVAL-5 / ADR-0007 §5.e, §6.d pattern) — per-endpoint latency SLO MV.
--
-- Aggregates agent_action_log.latency_ms (persisted for MCP tool + LLM calls,
-- ADR-0003) into per tool_name × day p50/p95/p99 + sample count. Read nightly by
-- latency_slo_worker for the SLO breach alert + the ops dashboard.
-- It's a MATERIALIZED VIEW (not a table) so the schema-drift gate ignores it and
-- no ORM mirror is needed — same pattern as abstention_daily.
-- Refresh: APScheduler nightly (ADR-0003 D8 pattern).
-- Migration: 20260619020000

CREATE MATERIALIZED VIEW IF NOT EXISTS latency_slo_daily AS
SELECT
    tool_name                                                          AS endpoint,
    DATE(created_at)                                                   AS day,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms)           AS p50_ms,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)           AS p95_ms,
    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)           AS p99_ms,
    COUNT(*)                                                           AS sample_count
FROM agent_action_log
WHERE latency_ms IS NOT NULL
GROUP BY tool_name, DATE(created_at);

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX IF NOT EXISTS latency_slo_daily_unique_idx
    ON latency_slo_daily (endpoint, day);

-- Trust-KPI instrumentation — HOS-177 (P3-3)
--
-- Creates:
--   1. kpi_daily — per-tenant daily KPI timeseries table (AC2)
--   2. recommendation_acceptance_daily — MV joining agent_action_log ✕
--      operational_memory.manager_feedback (AC1)
--   3. payload column on agent_action_log (AC4 alert rows)
--
-- Vocab note: recommendation_acceptance_daily counts manager_feedback
-- ('followed'|'rejected'|'neutral') which is the persisted source of truth.
-- The MV name uses 'acceptance' for product clarity; the column it counts is
-- manager_feedback (see mcp_server.py:259 feedback_map for the public→internal
-- mapping: accepted→followed, modified→neutral, rejected→rejected).
--
-- ID mapping: agent_action_log.hotel_id = operational_memory.hotel_id = tenant_id.
-- kpi_daily uses tenant_id (forward-looking naming — see docs/context/data-conventions.md).

-- -------------------------------------------------------------------------
-- 1. kpi_daily
-- -------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS kpi_daily (
    tenant_id       TEXT              NOT NULL,
    kpi_date        DATE              NOT NULL,
    kpi_name        TEXT              NOT NULL,
    value           DOUBLE PRECISION,
    numerator       INTEGER,
    denominator     INTEGER,
    computed_at     TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, kpi_date, kpi_name)
);

CREATE INDEX IF NOT EXISTS kpi_daily_tenant_date_idx
    ON kpi_daily (tenant_id, kpi_date DESC);

ALTER TABLE public.kpi_daily ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kpi_daily_service_role_all ON public.kpi_daily;
CREATE POLICY kpi_daily_service_role_all ON public.kpi_daily
    FOR ALL TO service_role
    USING (true) WITH CHECK (true);

-- -------------------------------------------------------------------------
-- 2. recommendation_acceptance_daily (materialized view)
--
-- Joins agent_action_log (recommendation tool calls, status='ok') with
-- operational_memory on request_id. Groups by (hotel_id, day, manager_feedback)
-- to give one count row per feedback bucket per property per day.
-- WITH NO DATA — refreshed daily by kpi_aggregator worker at 02:30 UTC.
-- CONCURRENTLY refresh requires the unique index below.
-- -------------------------------------------------------------------------

CREATE MATERIALIZED VIEW IF NOT EXISTS recommendation_acceptance_daily AS
SELECT
    om.hotel_id,
    DATE(om.created_at)     AS kpi_date,
    om.manager_feedback,
    COUNT(*)                AS cnt
FROM operational_memory om
INNER JOIN agent_action_log aal
       ON aal.request_id = om.request_id
      AND aal.request_id != ''
      AND aal.tool_name IN (
              'get_recommendations_with_memory_context',
              'get_operational_predictions'
          )
      AND aal.status = 'ok'
WHERE om.manager_feedback IS NOT NULL
GROUP BY om.hotel_id, DATE(om.created_at), om.manager_feedback
ORDER BY om.hotel_id, kpi_date DESC, om.manager_feedback
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS recommendation_acceptance_daily_pk
    ON recommendation_acceptance_daily (hotel_id, kpi_date, manager_feedback);

-- -------------------------------------------------------------------------
-- 3. payload column on agent_action_log (AC4 — kpi alert rows)
--
-- Additive — existing rows get NULL. The kpi_aggregator worker writes
-- {"kpi_alert": "trust_low", "rolling_rate": <float>} when the 7-day
-- rolling rate drops below 0.30 for a tenant.
-- agent_action_log is partitioned by range(created_at); ADD COLUMN IF NOT EXISTS
-- applies automatically to all existing and future partitions.
-- -------------------------------------------------------------------------

ALTER TABLE agent_action_log
    ADD COLUMN IF NOT EXISTS payload JSONB;

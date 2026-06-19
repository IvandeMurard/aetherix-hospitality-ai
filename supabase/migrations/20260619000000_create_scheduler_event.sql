-- HOS-271 — dedicated scheduler-health channel.
--
-- Heartbeats + dead-man / partial-failure trips for scheduled jobs used to be
-- written into agent_action_log (the per-MCP-tool-call billing meter, ADR-0003
-- D1). At ~720 dispatch_worker heartbeats/day/env that polluted billing rollups
-- (status='ok' colliding with the tool-call enum; hotel_id='_system' as a
-- phantom tenant in GROUP BY hotel_id) and forced an unindexed MAX() over a
-- high-write table on every monitor poll. This table is the dedicated,
-- non-tenant home for that telemetry. Append-only; rotate/truncate freely.
-- Migration: 20260619000000

CREATE TABLE IF NOT EXISTS scheduler_event (
    id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    job_name    TEXT        NOT NULL,
    event_type  TEXT        NOT NULL CHECK (event_type IN ('heartbeat','trip')),
    reason      TEXT,
    detail      TEXT,
    PRIMARY KEY (id)
);

-- Backs the dead-man's-switch lookup: MAX(created_at) per (job_name, event_type).
CREATE INDEX IF NOT EXISTS idx_scheduler_event_job_type_created
    ON scheduler_event (job_name, event_type, created_at);

-- Non-tenant system telemetry, but every public table is reachable via the
-- Supabase anon key by default — lock it to the backend service role.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'scheduler_event'
          AND relnamespace = 'public'::regnamespace
    ) THEN
        EXECUTE 'ALTER TABLE public.scheduler_event ENABLE ROW LEVEL SECURITY';

        EXECUTE 'DROP POLICY IF EXISTS scheduler_event_service_role_all ON public.scheduler_event';
        EXECUTE 'CREATE POLICY scheduler_event_service_role_all ON public.scheduler_event '
             || 'FOR ALL TO service_role USING (true) WITH CHECK (true)';
    END IF;
END $$;

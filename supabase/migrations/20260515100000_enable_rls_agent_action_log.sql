-- Enable RLS + service_role policy on agent_action_log
--
-- Background: 20260515000000_enable_rls_pre_pilot.sql skipped this table
-- because the existence check used pg_tables which doesn't include
-- partitioned parent tables. agent_action_log is partitioned by month
-- (created in 20260418000100 + 20260503000000 rotation worker).
-- This migration fixes the gap.
--
-- RLS on a partitioned parent automatically applies to all partitions.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'agent_action_log'
          AND relnamespace = 'public'::regnamespace
    ) THEN
        EXECUTE 'ALTER TABLE public.agent_action_log ENABLE ROW LEVEL SECURITY';

        EXECUTE 'DROP POLICY IF EXISTS agent_action_log_service_role_all ON public.agent_action_log';
        EXECUTE 'CREATE POLICY agent_action_log_service_role_all ON public.agent_action_log '
             || 'FOR ALL TO service_role USING (true) WITH CHECK (true)';
    END IF;
END $$;

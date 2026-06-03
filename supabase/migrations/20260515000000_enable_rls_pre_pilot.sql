-- HOS-111 — SEC-1: Pre-pilot RLS hardening for every tenant-scoped table.
--
-- Strategy (Option B from the story spec)
-- ----------------------------------------
-- The Aetherix backend connects via the Supabase ``service_role`` credential.
-- Supabase grants ``service_role`` BYPASSRLS by default, so enabling RLS does
-- not impact application traffic. The defense-in-depth wins are:
--
--   * If the backend ever switches to a non-service_role connection (or a
--     JWT-based dashboard appears), all rows stay locked down by default.
--   * Direct ``anon`` / ``authenticated`` access from the PostgREST surface
--     is denied for every operational table — no row leaks via the public API.
--   * The migration is idempotent: ``ALTER TABLE … ENABLE ROW LEVEL SECURITY``
--     is a no-op when RLS is already on, and ``DROP POLICY IF EXISTS`` makes
--     re-running safe.
--
-- For ``mcp_api_tokens`` and ``agent_action_log`` we intentionally do NOT add
-- any ``anon`` / ``authenticated`` policy — they remain strictly service_role.
--
-- Forward-looking note (out of scope for HOS-111, tracked in HOS-114/HOS-116)
-- ---------------------------------------------------------------------------
-- When the future fastapi-users dashboard exposes per-tenant reads, add an
-- ``authenticated`` policy of the form:
--
--     CREATE POLICY <table>_authenticated_read ON <table>
--       FOR SELECT TO authenticated
--       USING (tenant_id = current_setting('request.jwt.claim.tenant_id'));
--
-- and the matching INSERT/UPDATE WITH CHECK clause. We leave it to that story
-- because the JWT claim shape is not yet finalized.

-- ---------------------------------------------------------------------------
-- Helper: apply the RLS + service_role pattern to one table.
-- Wrapping each in a DO block keeps the migration idempotent and skips
-- missing tables (some staging schemas lag behind main).
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    t text;
    tables text[] := ARRAY[
        'restaurant_profiles',
        'demand_anomalies',
        'staffing_recommendations',
        'conversational_queries',
        'operational_memory',
        'fb_patterns',
        'mcp_api_tokens',
        'agent_action_log',
        'pms_sync_logs',
        'captation_baselines',
        'training_runs',
        'recommendation_cache',
        'weather_forecasts',
        'local_events'
    ];
    policy_name text;
BEGIN
    FOREACH t IN ARRAY tables LOOP
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_class c
              JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relname = t
               AND n.nspname = 'public'
               AND c.relkind = 'r'
        ) THEN
            -- 1. Enable RLS (idempotent).
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);

            -- 2. (Re)create the permissive service_role policy.
            policy_name := t || '_service_role_all';
            EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', policy_name, t);
            EXECUTE format(
                'CREATE POLICY %I ON public.%I '
                'FOR ALL TO service_role '
                'USING (true) WITH CHECK (true)',
                policy_name, t
            );
        ELSE
            RAISE NOTICE 'rls-pre-pilot: table public.% not present, skipping', t;
        END IF;
    END LOOP;
END$$;

-- ---------------------------------------------------------------------------
-- Sanity: drop the legacy "Tenant Isolation" policies created by
-- 20250313000000_enable_rls.sql. They reference a ``created_by`` column that
-- no longer exists on these tables, so they evaluate to NULL/false and
-- contribute nothing. Replacing them with the explicit service_role policy
-- above keeps the policy surface readable.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Restaurant Profiles" ON public.restaurant_profiles';
    EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Sync Logs" ON public.pms_sync_logs';
    EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Recommendation Cache" ON public.recommendation_cache';
EXCEPTION WHEN undefined_table THEN
    -- One of the legacy tables doesn't exist yet on this database. Safe to ignore.
    NULL;
END$$;

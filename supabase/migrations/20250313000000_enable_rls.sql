-- IVA-52 Enhancement: Enable RLS and Tenant Isolation
-- Run this in Supabase SQL Editor
--
-- Hardened 2026-05-15 (HOS-111): every statement is now wrapped in a
-- ``DO $$ ... IF EXISTS ... END $$`` block so the migration is idempotent and
-- tolerant of missing tables. The original unguarded ALTER TABLE statements
-- failed on a fresh Supabase preview where ``pms_sync_logs`` /
-- ``recommendation_cache`` are created by SQLAlchemy at runtime, not by an
-- earlier migration. The policies themselves reference a ``created_by``
-- column that does not exist on the current schema — they were already
-- non-functional and are replaced by ``20260515000000_enable_rls_pre_pilot.sql``.
-- We keep this file in place rather than deleting it so production
-- environments that have already recorded it in ``schema_migrations`` are
-- unaffected.

-- ---------------------------------------------------------------------------
-- 1. Enable RLS on the operational tables, if they exist.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'restaurant_profiles' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'ALTER TABLE public.restaurant_profiles ENABLE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'pms_sync_logs' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'ALTER TABLE public.pms_sync_logs ENABLE ROW LEVEL SECURITY';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'recommendation_cache' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'ALTER TABLE public.recommendation_cache ENABLE ROW LEVEL SECURITY';
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- 2. Recreate the legacy "created_by" policies only if both the table and the
--    column exist. On the current schema the column does not exist, so these
--    branches never fire — but we keep them here to preserve the original
--    migration's intent for any historical environment that still has the
--    column. ``20260515000000_enable_rls_pre_pilot.sql`` later drops these
--    policies and installs the service_role-based replacement.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'restaurant_profiles'
           AND column_name = 'created_by'
    ) THEN
        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Restaurant Profiles" ON public.restaurant_profiles';
        EXECUTE 'CREATE POLICY "Tenant Isolation: Restaurant Profiles" '
                'ON public.restaurant_profiles FOR ALL USING (auth.uid() = created_by)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'pms_sync_logs'
           AND column_name = 'created_by'
    ) THEN
        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Sync Logs" ON public.pms_sync_logs';
        EXECUTE 'CREATE POLICY "Tenant Isolation: Sync Logs" '
                'ON public.pms_sync_logs FOR ALL USING (auth.uid() = created_by)';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'recommendation_cache'
           AND column_name = 'created_by'
    ) THEN
        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Recommendation Cache" ON public.recommendation_cache';
        EXECUTE 'CREATE POLICY "Tenant Isolation: Recommendation Cache" '
                'ON public.recommendation_cache FOR ALL USING (auth.uid() = created_by)';
    END IF;
END$$;

-- ---------------------------------------------------------------------------
-- 3. Grant access to the ``authenticated`` role, if the table exists.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'restaurant_profiles' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'GRANT ALL ON public.restaurant_profiles TO authenticated';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'pms_sync_logs' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'GRANT ALL ON public.pms_sync_logs TO authenticated';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'recommendation_cache' AND n.nspname = 'public' AND c.relkind = 'r'
    ) THEN
        EXECUTE 'GRANT ALL ON public.recommendation_cache TO authenticated';
    END IF;
END$$;

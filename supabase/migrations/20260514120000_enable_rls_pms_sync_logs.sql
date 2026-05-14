-- Migration: enable row level security for pms_sync_logs if table exists
-- Created to avoid failing ALTER TABLE when the table is absent during review checks

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relname = 'pms_sync_logs' AND n.nspname = 'public' AND c.relkind = 'r'
  ) THEN
    EXECUTE 'ALTER TABLE public.pms_sync_logs ENABLE ROW LEVEL SECURITY';
  END IF;
END$$;

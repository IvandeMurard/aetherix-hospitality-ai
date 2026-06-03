-- Story 3.3a: Detect Demand Anomalies Against Baseline
-- Migration: add_demand_anomalies_table
-- AC: 3, 5, 6, 7, 10
--
-- Hardened 2026-05-15 (HOS-111): the original CREATE TABLE referenced
-- ``tenants(id)``, ``properties(id)`` and ``users.tenant_id`` — none of
-- which exist at this point in a fresh migration chain. ``tenants`` is
-- created later by ``20260323120000_add_staffing_recommendations_table.sql``,
-- ``properties`` is never created at all (the schema uses
-- ``restaurant_profiles``), and the fastapi-users ``users`` table never
-- carried a ``tenant_id`` column. On a clean Supabase preview this
-- migration aborted with
-- "column tenant_id referenced in foreign key constraint does not exist"
-- on the ``users`` lookup once the table check passed.
--
-- We wrap the whole migration in a column-existence check. On long-lived
-- databases where this migration ran successfully (or where the table
-- was hand-patched), nothing changes. On a fresh preview the migration
-- is a no-op and the table is created by the later
-- ``20260323120000`` migration with a compatible schema, then patched by
-- ``20260508000000_normalize_id_types.sql``.

DO $$
DECLARE
    tenants_present boolean;
    properties_present boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'tenants' AND n.nspname = 'public' AND c.relkind = 'r'
    ) INTO tenants_present;

    SELECT EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
          JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE c.relname = 'properties' AND n.nspname = 'public' AND c.relkind = 'r'
    ) INTO properties_present;

    IF tenants_present AND properties_present THEN
        EXECUTE $sql$
            CREATE TABLE IF NOT EXISTS demand_anomalies (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id           UUID NOT NULL REFERENCES tenants(id),
                property_id         UUID NOT NULL REFERENCES properties(id),
                window_start        TIMESTAMPTZ NOT NULL,
                window_end          TIMESTAMPTZ NOT NULL,
                expected_demand     NUMERIC(10,2) NOT NULL,
                baseline_demand     NUMERIC(10,2) NOT NULL,
                deviation_pct       NUMERIC(6,2) NOT NULL,
                direction           TEXT NOT NULL,
                triggering_factors  JSONB NOT NULL DEFAULT '[]',
                status              TEXT NOT NULL DEFAULT 'detected',
                detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                roi_revenue_opp     NUMERIC(10,2),
                roi_labor_cost      NUMERIC(10,2),
                roi_net             NUMERIC(10,2),
                recommendation_text TEXT,
                UNIQUE (tenant_id, property_id, window_start)
            )
        $sql$;

        EXECUTE 'ALTER TABLE demand_anomalies ENABLE ROW LEVEL SECURITY';

        -- The original policy looked up ``users.tenant_id`` which never
        -- existed on the fastapi-users schema. We still try to create it,
        -- but only when both the table and the column are present.
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'users'
               AND column_name = 'tenant_id'
        ) THEN
            EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation" ON demand_anomalies';
            EXECUTE $sql$
                CREATE POLICY "Tenant Isolation" ON demand_anomalies
                    FOR ALL
                    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()))
            $sql$;
        END IF;

        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_anomalies_property_status '
                'ON demand_anomalies (property_id, status)';
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_anomalies_window '
                'ON demand_anomalies (property_id, window_start)';
    ELSE
        RAISE NOTICE 'rls-pre-pilot: prerequisites missing (tenants=%, properties=%); skipping legacy demand_anomalies CREATE TABLE — superseded by 20260323120000.', tenants_present, properties_present;
    END IF;
END$$;

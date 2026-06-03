-- HOS-83 Story 3.1: Ingest Localized Weather Data
-- Creates weather_forecasts table with tenant isolation via RLS
--
-- Hardened 2026-05-15 (HOS-111): the original CREATE TABLE referenced
-- ``restaurant_profiles(tenant_id)`` as a foreign key. The ``tenant_id``
-- column on ``restaurant_profiles`` is only added later by
-- ``20260327000000_add_weather_forecasts_table.sql``, so on a clean
-- Supabase preview this migration aborted with
-- "column tenant_id referenced in foreign key constraint does not exist".
-- ``20260327000000`` is also authoritative — it ``DROP TABLE IF EXISTS
-- weather_forecasts CASCADE`` and recreates the table with the correct
-- schema — so this file is effectively superseded.
--
-- We keep the migration in place (rather than deleting it) so historical
-- ``schema_migrations`` rows remain consistent, but the entire body is
-- guarded: it only runs when ``restaurant_profiles.tenant_id`` exists,
-- which is never true at this point in a fresh chain. On a long-lived
-- database where this migration already executed successfully, the
-- ``CREATE TABLE IF NOT EXISTS`` guard makes the rerun a no-op.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'restaurant_profiles'
           AND column_name = 'tenant_id'
    ) THEN
        EXECUTE $sql$
            CREATE TABLE IF NOT EXISTS weather_forecasts (
                id          BIGSERIAL PRIMARY KEY,
                tenant_id   TEXT        NOT NULL REFERENCES restaurant_profiles(tenant_id) ON DELETE CASCADE,
                property_id TEXT        NOT NULL,

                condition_code       INTEGER,
                temperature_c        FLOAT,
                precipitation_prob   INTEGER,
                wind_speed_kmh       FLOAT,
                forecast_timestamp   TIMESTAMPTZ NOT NULL,

                fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                CONSTRAINT uq_weather_forecast UNIQUE (tenant_id, property_id, forecast_timestamp)
            )
        $sql$;

        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_weather_forecasts_tenant_ts '
                'ON weather_forecasts (tenant_id, forecast_timestamp)';

        EXECUTE 'ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY';

        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Weather Forecasts" ON weather_forecasts';
        EXECUTE $sql$
            CREATE POLICY "Tenant Isolation: Weather Forecasts" ON weather_forecasts
                FOR ALL USING (
                    tenant_id IN (
                        SELECT tenant_id FROM restaurant_profiles
                         WHERE owner_id = auth.uid()
                    )
                )
        $sql$;

        EXECUTE 'GRANT ALL ON weather_forecasts TO authenticated';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE weather_forecasts_id_seq TO authenticated';
    ELSE
        RAISE NOTICE 'rls-pre-pilot: restaurant_profiles.tenant_id absent, skipping legacy weather_forecasts creation (superseded by 20260327000000).';
    END IF;
END$$;

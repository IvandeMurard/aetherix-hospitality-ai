-- Story 3.1: Ingest Localized Weather Data (HOS-83)
-- Creates weather_forecasts table with RLS tenant isolation.
-- Upsert key: (tenant_id, property_id, forecast_timestamp)
--
-- Hardened 2026-05-15 (HOS-111): same as the sibling
-- 20260322000000_add_weather_forecasts_table.sql, this migration was
-- shipped before ``restaurant_profiles.tenant_id`` existed and aborted on
-- a fresh Supabase preview with
-- "column tenant_id referenced in foreign key constraint does not exist".
-- ``20260327000000_add_weather_forecasts_table.sql`` is authoritative
-- (it drops and recreates the table with the right schema) so the body
-- below is guarded behind a column-existence check.

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
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id           TEXT NOT NULL REFERENCES restaurant_profiles(tenant_id) ON DELETE CASCADE,
                property_id         TEXT NOT NULL,
                forecast_timestamp  TIMESTAMPTZ NOT NULL,

                condition_code      INTEGER,
                temperature_c       NUMERIC(5, 2),
                precipitation_prob  INTEGER,
                wind_speed_kmh      NUMERIC(6, 2),

                source              TEXT NOT NULL DEFAULT 'open-meteo',
                fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        $sql$;

        EXECUTE 'CREATE UNIQUE INDEX IF NOT EXISTS uq_weather_tenant_property_ts '
                'ON weather_forecasts (tenant_id, property_id, forecast_timestamp)';

        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_weather_tenant_ts '
                'ON weather_forecasts (tenant_id, forecast_timestamp)';

        EXECUTE 'ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY';

        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation: Weather Forecasts" ON weather_forecasts';
        EXECUTE $sql$
            CREATE POLICY "Tenant Isolation: Weather Forecasts"
                ON weather_forecasts
                FOR ALL
                USING (
                    tenant_id IN (
                        SELECT tenant_id FROM restaurant_profiles
                         WHERE owner_id = auth.uid()
                    )
                )
        $sql$;

        EXECUTE 'GRANT ALL ON weather_forecasts TO authenticated';
    ELSE
        RAISE NOTICE 'rls-pre-pilot: restaurant_profiles.tenant_id absent, skipping legacy weather_forecasts creation (superseded by 20260327000000).';
    END IF;
END$$;

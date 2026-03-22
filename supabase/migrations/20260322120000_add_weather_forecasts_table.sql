-- Story 3.1: Ingest Localized Weather Data (HOS-83)
-- Creates weather_forecasts table with RLS tenant isolation.
-- Upsert key: (tenant_id, property_id, forecast_timestamp)

CREATE TABLE IF NOT EXISTS weather_forecasts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           TEXT NOT NULL REFERENCES restaurant_profiles(tenant_id) ON DELETE CASCADE,
    property_id         TEXT NOT NULL,  -- mirrors restaurant_profiles.tenant_id for FK simplicity
    forecast_timestamp  TIMESTAMPTZ NOT NULL,

    -- Normalized schema (Story 3.3a cross-reference ready)
    condition_code      INTEGER,          -- WMO weather code (Open-Meteo weathercode)
    temperature_c       NUMERIC(5, 2),    -- degrees Celsius
    precipitation_prob  INTEGER,          -- 0-100 %
    wind_speed_kmh      NUMERIC(6, 2),    -- km/h

    -- Provenance
    source              TEXT NOT NULL DEFAULT 'open-meteo',
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Upsert uniqueness constraint
CREATE UNIQUE INDEX IF NOT EXISTS uq_weather_tenant_property_ts
    ON weather_forecasts (tenant_id, property_id, forecast_timestamp);

-- Indexes for Story 3.3a queries (join on tenant + time range)
CREATE INDEX IF NOT EXISTS idx_weather_tenant_ts
    ON weather_forecasts (tenant_id, forecast_timestamp);

-- ── Row-Level Security ─────────────────────────────────────────────────────
ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant Isolation: Weather Forecasts"
    ON weather_forecasts
    FOR ALL
    USING (
        tenant_id IN (
            SELECT tenant_id FROM restaurant_profiles
            WHERE owner_id = auth.uid()
        )
    );

GRANT ALL ON weather_forecasts TO authenticated;

-- HOS-83 Story 3.1: Ingest Localized Weather Data
-- Creates weather_forecasts table with tenant isolation via RLS

CREATE TABLE IF NOT EXISTS weather_forecasts (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT        NOT NULL REFERENCES restaurant_profiles(tenant_id) ON DELETE CASCADE,
    property_id TEXT        NOT NULL,

    -- Normalized weather fields (SC #4)
    condition_code       INTEGER,
    temperature_c        FLOAT,
    precipitation_prob   INTEGER,   -- 0-100 %
    wind_speed_kmh       FLOAT,
    forecast_timestamp   TIMESTAMPTZ NOT NULL,

    -- Audit
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency constraint (SC #7)
    CONSTRAINT uq_weather_forecast UNIQUE (tenant_id, property_id, forecast_timestamp)
);

-- Indexes for Story 3.3a cross-reference queries
CREATE INDEX IF NOT EXISTS idx_weather_forecasts_tenant_ts
    ON weather_forecasts (tenant_id, forecast_timestamp);

-- Row Level Security (SC #5)
ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant Isolation: Weather Forecasts" ON weather_forecasts
    FOR ALL USING (
        tenant_id IN (
            SELECT tenant_id FROM restaurant_profiles
            WHERE owner_id = auth.uid()
        )
    );

GRANT ALL ON weather_forecasts TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE weather_forecasts_id_seq TO authenticated;

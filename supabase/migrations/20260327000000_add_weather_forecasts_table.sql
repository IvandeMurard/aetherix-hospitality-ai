-- ============================================================
-- Migration: add_weather_forecasts_table
-- Story:     HOS-83 — Story 3.1: Ingest Localized Weather Data
-- Date:      2026-03-27
-- ============================================================
-- HOW TO RUN IN SUPABASE:
--   Dashboard → SQL Editor → paste this file → Run
--   OR: supabase db push (if using Supabase CLI)
-- ============================================================


-- ------------------------------------------------------------
-- 1. Enable pgvector extension (needed by HOS-99 for fb_patterns
--    and operational_memory tables — safe to run multiple times)
-- ------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;


-- ------------------------------------------------------------
-- 2. Create weather_forecasts table
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_forecasts (
    id                  BIGSERIAL PRIMARY KEY,

    -- Tenant scoping
    tenant_id           TEXT        NOT NULL
                            REFERENCES restaurant_profiles(tenant_id)
                            ON DELETE CASCADE,
    property_id         TEXT        NOT NULL,

    -- Normalized Open-Meteo fields (SC #4)
    condition_code      INTEGER,                        -- WMO weather interpretation code
    temperature_c       DOUBLE PRECISION,               -- Air temp at 2 m (°C)
    precipitation_prob  INTEGER CHECK (precipitation_prob BETWEEN 0 AND 100),
    wind_speed_kmh      DOUBLE PRECISION,               -- Wind speed at 10 m (km/h)

    forecast_timestamp  TIMESTAMPTZ NOT NULL,
    source              TEXT        NOT NULL DEFAULT 'open-meteo',
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotency: upsert key (SC #7)
    CONSTRAINT uq_weather_forecast
        UNIQUE (tenant_id, property_id, forecast_timestamp)
);


-- ------------------------------------------------------------
-- 3. Indexes for query performance
-- ------------------------------------------------------------

-- Fast lookup by tenant + time window (anomaly detection, Story 3.3a)
CREATE INDEX IF NOT EXISTS idx_weather_tenant_ts
    ON weather_forecasts (tenant_id, forecast_timestamp DESC);

-- Fast lookup by property
CREATE INDEX IF NOT EXISTS idx_weather_property
    ON weather_forecasts (property_id);


-- ------------------------------------------------------------
-- 4. Row Level Security — zero cross-tenant data leakage (SC #5)
-- ------------------------------------------------------------
ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY;

-- Authenticated users can only see rows belonging to their tenant.
-- Adjust the claim path if your JWT structure differs.
CREATE POLICY "tenant_isolation"
    ON weather_forecasts
    FOR ALL
    USING (
        tenant_id = (auth.jwt() ->> 'tenant_id')
    );

-- Service role bypasses RLS (used by FastAPI backend via SUPABASE_KEY).
-- No policy needed — service role already bypasses RLS by default in Supabase.


-- ------------------------------------------------------------
-- 5. Also create fb_patterns + operational_memory tables here
--    (HOS-99 — pgvector layer, requires extension above)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS fb_patterns (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           TEXT,                           -- NULL = global pattern
    service_type        TEXT        NOT NULL,           -- breakfast|lunch|dinner|room_service
    occupancy_band      TEXT,                           -- low|medium|high|full
    day_of_week         TEXT,
    weather_condition   TEXT,
    feedback_status     TEXT        NOT NULL DEFAULT 'neutral', -- followed|rejected|neutral
    pattern_text        TEXT        NOT NULL,
    outcome_description TEXT,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fb_patterns_service_type
    ON fb_patterns (service_type);

CREATE INDEX IF NOT EXISTS idx_fb_patterns_tenant
    ON fb_patterns (tenant_id);

-- HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_fb_patterns_embedding
    ON fb_patterns USING hnsw (embedding vector_cosine_ops);


CREATE TABLE IF NOT EXISTS operational_memory (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id            TEXT        NOT NULL,
    session_id          TEXT,
    content             TEXT        NOT NULL,
    reco_json           JSONB,
    manager_feedback    TEXT,                           -- followed|rejected|neutral
    outcome             TEXT,
    tags                JSONB,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_op_memory_hotel
    ON operational_memory (hotel_id);

CREATE INDEX IF NOT EXISTS idx_op_memory_embedding
    ON operational_memory USING hnsw (embedding vector_cosine_ops);

ALTER TABLE operational_memory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation"
    ON operational_memory
    FOR ALL
    USING (
        hotel_id = (auth.jwt() ->> 'tenant_id')
    );

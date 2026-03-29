-- ============================================================
-- Migration: add_weather_forecasts_table
-- Story:     HOS-83 — Story 3.1 + HOS-99 vector layer
-- Date:      2026-03-27
-- ============================================================
-- HOW TO RUN IN SUPABASE:
--   Dashboard → SQL Editor → paste this file → Run
--   Paste the entire file at once — order matters.
-- ============================================================


-- ── STEP 1: Patch restaurant_profiles ──────────────────────────────────────
-- Adds columns expected by the Aetherix ORM that were absent from the
-- initial manual table creation.

ALTER TABLE restaurant_profiles
    ADD COLUMN IF NOT EXISTS tenant_id           TEXT,
    ADD COLUMN IF NOT EXISTS latitude            DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude           DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS owner_id            UUID,
    ADD COLUMN IF NOT EXISTS pms_type            TEXT DEFAULT 'apaleo',
    ADD COLUMN IF NOT EXISTS pms_property_id     TEXT,
    ADD COLUMN IF NOT EXISTS preferred_channel   TEXT DEFAULT 'whatsapp',
    ADD COLUMN IF NOT EXISTS phone_number        TEXT,
    ADD COLUMN IF NOT EXISTS notification_email  TEXT,
    ADD COLUMN IF NOT EXISTS gps_lat             DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS gps_lng             DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_spend_per_cover NUMERIC(8,2),
    ADD COLUMN IF NOT EXISTS staff_hourly_rate   NUMERIC(8,2);

-- Backfill existing rows before enforcing NOT NULL
UPDATE restaurant_profiles
SET tenant_id = 'grand-hotel-main'
WHERE tenant_id IS NULL;

ALTER TABLE restaurant_profiles
    DROP CONSTRAINT IF EXISTS restaurant_profiles_tenant_id_key;

ALTER TABLE restaurant_profiles
    ADD CONSTRAINT restaurant_profiles_tenant_id_key UNIQUE (tenant_id);

ALTER TABLE restaurant_profiles
    ALTER COLUMN tenant_id SET NOT NULL;


-- ── STEP 2: Drop any incomplete tables from previous attempts ───────────────

DROP TABLE IF EXISTS operational_memory CASCADE;
DROP TABLE IF EXISTS fb_patterns        CASCADE;
DROP TABLE IF EXISTS weather_forecasts  CASCADE;


-- ── STEP 3: Enable pgvector ─────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;


-- ── STEP 4: weather_forecasts ───────────────────────────────────────────────

CREATE TABLE weather_forecasts (
    id                 BIGSERIAL   PRIMARY KEY,
    tenant_id          TEXT        NOT NULL
                           REFERENCES restaurant_profiles(tenant_id)
                           ON DELETE CASCADE,
    property_id        TEXT        NOT NULL,
    condition_code     INTEGER,
    temperature_c      DOUBLE PRECISION,
    precipitation_prob INTEGER     CHECK (precipitation_prob BETWEEN 0 AND 100),
    wind_speed_kmh     DOUBLE PRECISION,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    source             TEXT        NOT NULL DEFAULT 'open-meteo',
    fetched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_weather_forecast
        UNIQUE (tenant_id, property_id, forecast_timestamp)
);

CREATE INDEX idx_weather_tenant_ts ON weather_forecasts (tenant_id, forecast_timestamp DESC);
CREATE INDEX idx_weather_property   ON weather_forecasts (property_id);

ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON weather_forecasts FOR ALL
    USING (tenant_id = (auth.jwt() ->> 'tenant_id'));


-- ── STEP 5: fb_patterns (HOS-99 private pattern store) ─────────────────────

CREATE TABLE fb_patterns (
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

CREATE INDEX idx_fb_patterns_service ON fb_patterns (service_type);
CREATE INDEX idx_fb_patterns_embed   ON fb_patterns USING hnsw (embedding vector_cosine_ops);


-- ── STEP 6: operational_memory (HOS-99 private memory layer) ───────────────

CREATE TABLE operational_memory (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id         TEXT        NOT NULL,
    session_id       TEXT,
    content          TEXT        NOT NULL,
    reco_json        JSONB,
    manager_feedback TEXT,                           -- followed|rejected|neutral
    outcome          TEXT,
    tags             JSONB,
    embedding        vector(1536),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_op_memory_hotel ON operational_memory (hotel_id);
CREATE INDEX idx_op_memory_embed ON operational_memory USING hnsw (embedding vector_cosine_ops);

ALTER TABLE operational_memory ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON operational_memory FOR ALL
    USING (hotel_id = (auth.jwt() ->> 'tenant_id'));

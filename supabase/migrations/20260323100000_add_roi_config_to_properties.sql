-- Story 3.3b: Calculate Financial ROI for Detected Anomalies
-- Migration: add_roi_config_to_properties
-- AC: 7 — Configurable Rates per property with system-level defaults

-- Add ROI rate columns to properties table if it exists.
-- These columns are nullable so existing rows remain valid;
-- the application falls back to DEFAULT_AVG_SPEND_PER_COVER (£40)
-- and DEFAULT_STAFF_HOURLY_RATE (£14) when NULL.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'properties'
    ) THEN
        -- avg_spend_per_cover: average revenue per cover for this property (£)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'properties' AND column_name = 'avg_spend_per_cover'
        ) THEN
            ALTER TABLE properties
                ADD COLUMN avg_spend_per_cover NUMERIC(8, 2) DEFAULT 40.00;
        END IF;

        -- staff_hourly_rate: hourly cost per additional staff member (£)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'properties' AND column_name = 'staff_hourly_rate'
        ) THEN
            ALTER TABLE properties
                ADD COLUMN staff_hourly_rate NUMERIC(8, 2) DEFAULT 14.00;
        END IF;
    END IF;
END $$;

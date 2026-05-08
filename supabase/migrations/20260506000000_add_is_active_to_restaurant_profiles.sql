-- HOS-150 AC5 — anomaly_detection.run_full_scan must filter active properties.
-- Adds an `is_active` flag to restaurant_profiles so the scanner can skip
-- decommissioned outlets without relying on a `properties` table that does
-- not exist in this schema.

ALTER TABLE restaurant_profiles
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS restaurant_profiles_is_active_idx
    ON restaurant_profiles (is_active)
    WHERE is_active = TRUE;

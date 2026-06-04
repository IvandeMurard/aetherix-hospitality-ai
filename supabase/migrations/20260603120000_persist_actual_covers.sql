-- HOS-200 (Story 10.10 / P3-10) — Persist actual_covers from manager feedback.
--
-- Closes the prediction → recommendation → manager feedback → actual outcome
-- loop so real-pilot MAPE can be computed against ground truth instead of the
-- reporting_service mock fallback.
--
--   predicted_covers      — covers the model forecast for the recommendation
--                           window (copied from demand_anomalies.expected_demand
--                           at formatting time). Needed alongside actual_covers
--                           to compute real MAPE (Story 10.12 / HOS-202).
--   actual_covers         — covers reported by the manager via WhatsApp feedback
--                           (ReceiptsService.parse_inbound structured_correction).
--   actual_covers_source  — provenance of actual_covers. 'manager_feedback' now;
--                           'pos_data' reserved for Phase 4 POS ingestion.
--   actual_covers_at      — when actual_covers was recorded.
--
-- Additive, non-breaking. ORM mirror: app/db/models.py StaffingRecommendation
-- (schema drift gate — Décision #16).

-- One ALTER TABLE per column: the schema-drift parser
-- (scripts/ci/check_schema_drift.py) registers a single ADD COLUMN per
-- ALTER TABLE statement, so combined statements would hide columns from the gate.
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS predicted_covers     NUMERIC(10, 2);
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS actual_covers        NUMERIC(10, 2);
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS actual_covers_source TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS actual_covers_at     TIMESTAMPTZ;

-- Partial index: the reporting service only ever scans rows that already carry
-- a ground-truth actual (real MAPE computation), so keep the index lean.
CREATE INDEX IF NOT EXISTS staffing_recommendations_actual_covers_idx
    ON staffing_recommendations (tenant_id, window_start)
    WHERE actual_covers IS NOT NULL;

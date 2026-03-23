-- Story 4.2 (HOS-25): Format & Dispatch Alerts
-- Adds dispatch tracking columns to the staffing_recommendations table.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS dispatched_at TIMESTAMPTZ;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS dispatch_channel VARCHAR(10);

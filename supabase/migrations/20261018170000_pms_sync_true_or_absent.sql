-- HOS-352 (Décisions #28, #33, #43) — a PMS figure is true or absent.
--
-- pms_sync_logs.occupancy held two different units (the REST endpoint's raw
-- figure, or a percentage from MCP) and could hold an invented 80; fb_revenue
-- could hold total revenue or an invented 0.0. From this migration on:
--   * occupancy is two room counts, rooms_sold and rooms_available (the rate
--     is computed, never stored);
--   * fb_revenue is F&B revenue only, net of tax, in fb_revenue_currency;
--   * a figure the PMS did not give is NULL, and *_status says why.
-- The legacy occupancy column is kept for the existing rows (all sandbox /
-- demo at this date) but no longer written or read; see
-- docs/adr/0006-pos-integration.md §9.8 for what happens to those rows.
-- ORM mirror: app/db/models.py PMSSyncLog.

ALTER TABLE pms_sync_logs ADD COLUMN IF NOT EXISTS rooms_sold INTEGER;
ALTER TABLE pms_sync_logs ADD COLUMN IF NOT EXISTS rooms_available INTEGER;
ALTER TABLE pms_sync_logs ADD COLUMN IF NOT EXISTS occupancy_status VARCHAR;
ALTER TABLE pms_sync_logs ADD COLUMN IF NOT EXISTS fb_revenue_currency VARCHAR;
ALTER TABLE pms_sync_logs ADD COLUMN IF NOT EXISTS fb_revenue_status VARCHAR;

COMMENT ON COLUMN public.pms_sync_logs.occupancy IS
  'Legacy (before HOS-352): mixed units (raw REST figure or percent), may be an invented 80. Not written or read anymore.';
COMMENT ON COLUMN public.pms_sync_logs.rooms_sold IS
  'Rooms sold that day, as reported by the PMS. NULL = absent, see occupancy_status.';
COMMENT ON COLUMN public.pms_sync_logs.rooms_available IS
  'Sellable rooms that day (out of order excluded), as reported by the PMS. NULL = absent.';
COMMENT ON COLUMN public.pms_sync_logs.occupancy_status IS
  'ok | fixture | not_configured | pms_error | no_data (HOS-352).';
COMMENT ON COLUMN public.pms_sync_logs.fb_revenue IS
  'F&B revenue only, net of tax, in fb_revenue_currency. Never total revenue. NULL = absent, see fb_revenue_status. Before HOS-352: may be total revenue or an invented 0.0.';
COMMENT ON COLUMN public.pms_sync_logs.fb_revenue_status IS
  'ok | fixture | not_configured | pms_error | no_data (HOS-352).';

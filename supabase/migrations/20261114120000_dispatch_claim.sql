-- HOS-369 (Story 16.48) — atomic claim of recommendations to dispatch.
--
-- The dispatcher moves a row ready_to_push -> sent through a per-row
-- UPDATE ... WHERE id = :id AND status = 'ready_to_push' AND (lease free or
-- expired), so two workers (several Fly instances) never send the same alert.
--
-- dispatch_claimed_at : lease taken by the sending worker. A worker that dies
--                       after the claim leaves the row ready_to_push; it is
--                       re-claimed once the lease has expired (no stuck row).
-- dispatch_attempts   : number of claims. At the bound the row ends in the
--                       terminal status 'dispatch_failed' (typed event emitted).
-- status is unconstrained text: 'dispatch_failed' needs no constraint change.
--
-- ORM mirror: app/db/models.py StaffingRecommendation (Décision #16).

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS dispatch_claimed_at TIMESTAMPTZ;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS dispatch_attempts   INTEGER NOT NULL DEFAULT 0;

-- HOS-350 (Décisions #43, #44) — at most one reminder per recommendation,
-- before its point of no return, through the hotel's channel.
--
-- reminder_status: sent | skipped_answered | disabled | no_compliant_channel |
--                  failed | missed (commit point passed before a reminder went out)
-- A NULL status = not yet due. Silence after a reminder stays "no reply"
-- (Décision #6): nothing here ever records a decision.
--
-- ORM mirror: app/db/models.py StaffingRecommendation (Décision #16).

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reminder_status  TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reminder_channel TEXT;

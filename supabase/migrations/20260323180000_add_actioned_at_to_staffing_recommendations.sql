-- Story 4.3 (HOS-26): Action Logging Accept/Reject via Twilio Inbound Webhook
-- Extends the staffing_recommendations status lifecycle with:
--   dispatched → accepted | rejected
-- and records when and how the manager responded.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS actioned_at TIMESTAMPTZ;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS action VARCHAR(10);
-- accepted, rejected (null until the manager acts)

COMMENT ON COLUMN staffing_recommendations.actioned_at IS
    'Timestamp when the manager accepted or rejected this recommendation via SMS/WhatsApp.';
COMMENT ON COLUMN staffing_recommendations.action IS
    'Manager decision: accepted | rejected. NULL until actioned.';

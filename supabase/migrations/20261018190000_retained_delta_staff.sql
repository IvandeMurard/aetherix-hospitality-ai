-- HOS-344 (Décisions #40, #43) — the figure a manager kept when countering a
-- staffing recommendation.
--
-- A counter ("plutôt 2 extras") was recorded as status 'modified' with no
-- figure, so the learning loop could not tell what the hotel actually retained.
-- retained_delta_staff holds it when a host agent relays it over MCP
-- (submit_feedback_to_memory, outcome 'modified'): extra staff kept, negative
-- for fewer. NULL for every other decision, and for WhatsApp counters, which
-- carry no headcount today.
-- ORM mirror: app/db/models.py StaffingRecommendation.retained_delta_staff.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS retained_delta_staff INTEGER;

COMMENT ON COLUMN public.staffing_recommendations.retained_delta_staff IS
  'Counter (status modified) relayed over MCP: extra staff the hotel kept instead, negative = fewer. NULL otherwise (HOS-344).';

-- ADR-0007 §17 — decision provenance, agent reasons, recap opt-in, revision prompts.
--
-- 1. staffing_recommendations — who decided and why:
--      decided_by              human_whatsapp | human_via_host |
--                              host_agent_autonomous | timeout (reserved, never
--                              written today: no default action on expiry,
--                              Décision #6)
--      decided_by_caller       host caller identity for MCP decisions (token
--                              label or id) — per-caller informativeness signal
--      reason_code             closed enum (decision_provenance.REASON_CODES)
--      reason_detail           short free text, sanitised, <= 280 chars
--      reason_source           human | agent_inferred — a reason guessed by a
--                              host agent is never stored as the human's
--      reason_evidence         JSON list of {source, detail} the caller relied on
--      decision_policy_version decision policy in force when the decision was
--                              recorded (decision_policy.DEFAULT_POLICY today),
--                              so metrics can be split before/after a change
--    Backfill: rows decided through the WhatsApp capture of Décision #38
--    (decision_source set) were decided by a human on WhatsApp. Older decided
--    rows keep decided_by NULL = unattributed: they are not counted as a human
--    trust signal.
-- 2. restaurant_profiles.weekly_recap_opt_in (default false: no weekly push
--    without opt-in, interruption budget) + manager_locale (fr | en).
-- 3. manager_prompts.kind accepts 'decision_revision' ("corriger mardi" from the
--    recap goes through the same confirmation path).
--
-- Additive except the kind CHECK, which is widened. ORM mirror: app/db/models.py
-- (Décision #16). One ADD COLUMN per ALTER TABLE: the drift parser registers one
-- per statement.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decided_by              TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decided_by_caller       TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reason_code             TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reason_detail           TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reason_source           TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS reason_evidence         JSONB;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decision_policy_version TEXT;

ALTER TABLE staffing_recommendations DROP CONSTRAINT IF EXISTS staffing_recommendations_decided_by_check;
ALTER TABLE staffing_recommendations ADD CONSTRAINT staffing_recommendations_decided_by_check
    CHECK (decided_by IS NULL OR decided_by IN
           ('human_whatsapp', 'human_via_host', 'host_agent_autonomous', 'timeout'));

ALTER TABLE staffing_recommendations DROP CONSTRAINT IF EXISTS staffing_recommendations_reason_source_check;
ALTER TABLE staffing_recommendations ADD CONSTRAINT staffing_recommendations_reason_source_check
    CHECK (reason_source IS NULL OR reason_source IN ('human', 'agent_inferred'));

UPDATE staffing_recommendations
   SET decided_by = 'human_whatsapp'
 WHERE decided_by IS NULL
   AND decision_source IS NOT NULL
   AND status IN ('accepted', 'rejected', 'modified');

CREATE INDEX IF NOT EXISTS idx_staffing_recommendations_tenant_dispatched
    ON staffing_recommendations (tenant_id, dispatched_at);

ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS weekly_recap_opt_in BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS manager_locale      TEXT;

ALTER TABLE manager_prompts DROP CONSTRAINT IF EXISTS manager_prompts_kind_check;
ALTER TABLE manager_prompts ADD CONSTRAINT manager_prompts_kind_check
    CHECK (kind IN ('decision_confirmation', 'reason_request', 'decision_revision'));

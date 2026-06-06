-- HOS-206 (EVAL-2 / ADR-0007 §6.a, §6.e) — abstention + eval telemetry.
--
-- Extends agent_action_log (an abstention IS an agent event — ADR-0003 D1, no
-- dedicated table) with the abstention contract columns + eval-run linkage,
-- and adds the abstention_daily MV for PM dashboarding.
--
-- One ALTER per column: the schema-drift parser (scripts/ci/check_schema_drift.py)
-- registers a single ADD COLUMN per ALTER statement. ORM mirror:
-- app/db/models.py AgentActionLog (Décision #16).

ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS abstention_reason  TEXT;
ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS abstention_context JSONB;
ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS abstention_layer   TEXT;
ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS eval_run_id        UUID;
ALTER TABLE agent_action_log ADD COLUMN IF NOT EXISTS drift_score        JSONB;

CREATE INDEX IF NOT EXISTS agent_action_log_abstention_idx
    ON agent_action_log (abstention_reason, created_at)
    WHERE abstention_reason IS NOT NULL;

CREATE INDEX IF NOT EXISTS agent_action_log_eval_run_idx
    ON agent_action_log (eval_run_id, created_at)
    WHERE eval_run_id IS NOT NULL;

-- MV: per-hotel/day abstention frequency by layer + reason (ADR §6.e).
-- Refreshed nightly (APScheduler, ADR-0003 D8 pattern).
CREATE MATERIALIZED VIEW IF NOT EXISTS abstention_daily AS
SELECT
    hotel_id,
    DATE(created_at)   AS day,
    abstention_layer   AS layer,
    abstention_reason  AS reason,
    COUNT(*)           AS count
FROM agent_action_log
WHERE abstention_reason IS NOT NULL
GROUP BY hotel_id, DATE(created_at), abstention_layer, abstention_reason;

CREATE UNIQUE INDEX IF NOT EXISTS abstention_daily_unique_idx
    ON abstention_daily (hotel_id, day, layer, reason);

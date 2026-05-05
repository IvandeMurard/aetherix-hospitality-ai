-- HOS-150 AC4 — extend agent_action_log monthly partitions through 2027-05.
-- The original migration (20260418000100) only created partitions for April +
-- May 2026. From 2026-06-01 onwards every INSERT would have failed because
-- agent_action_log is PARTITION BY RANGE (created_at). This migration adds
-- the next 12 monthly partitions (2026-06 → 2027-05). A scheduled job
-- (`agent_action_log_partition_rotation`, registered in main.py) keeps the
-- horizon rolling forward each month at 02:00 UTC.
--
-- All statements are idempotent (CREATE TABLE IF NOT EXISTS) so this migration
-- is safe to re-run on environments that already have some of these partitions.

CREATE TABLE IF NOT EXISTS agent_action_log_2026_06
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_07
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_08
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_09
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_10
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_11
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2026_12
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2027_01
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2027_02
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2027_03
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2027_04
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');

CREATE TABLE IF NOT EXISTS agent_action_log_2027_05
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');

-- DOWN (manual, commented):
--   DROP TABLE IF EXISTS agent_action_log_2026_06;
--   ... (one DROP per partition above)
--   Caution: dropping a partition deletes the rows it contains.

-- ADR 0003 D1/D3 — agent_action_log: one row per MCP tool call, monthly partitioning.
-- Migration: 20260418000100

CREATE TABLE IF NOT EXISTS agent_action_log (
    id                   UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hotel_id             TEXT        NOT NULL,
    tool_name            TEXT        NOT NULL,
    scopes               TEXT[],
    status               TEXT        NOT NULL CHECK (status IN ('ok','auth_error','tool_error','rate_limited','rate_limit_fallback')),
    error_code           TEXT,
    latency_ms           INTEGER,
    embedding_latency_ms INTEGER,
    dedup_hit            BOOLEAN,
    top_similarity       REAL,
    request_id           TEXT        NOT NULL DEFAULT '',
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Initial monthly partitions (April + May 2026)
CREATE TABLE agent_action_log_2026_04
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE agent_action_log_2026_05
    PARTITION OF agent_action_log
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

-- Indexes: per-hotel time-ordered access (billing queries), tool-level rollup
CREATE INDEX IF NOT EXISTS idx_aal_hotel_created
    ON agent_action_log (hotel_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_aal_tool_status
    ON agent_action_log (tool_name, status, created_at DESC);

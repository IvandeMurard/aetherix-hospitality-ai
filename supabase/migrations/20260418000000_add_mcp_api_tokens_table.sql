-- Aetherix MCP Server v0 — bearer token table (ADR 0001 · HOS-71 · P1-2)
--
-- Opaque bearer tokens scoped to a single hotel_id. SHA-256 hash at rest.
-- Validation middleware looks up token_hash and injects hotel_id into the
-- request context. hotel_id is NEVER accepted as a client-supplied parameter.

CREATE TABLE IF NOT EXISTS mcp_api_tokens (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id      TEXT        NOT NULL,
    token_hash    TEXT        NOT NULL UNIQUE,
    token_prefix  TEXT        NOT NULL,  -- e.g. "atx_prod" — for display only
    scopes        TEXT[]      NOT NULL DEFAULT ARRAY['predict', 'recommend', 'feedback'],
    label         TEXT,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at  TIMESTAMPTZ,
    revoked_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS mcp_api_tokens_hotel_id_idx
    ON mcp_api_tokens (hotel_id);

CREATE INDEX IF NOT EXISTS mcp_api_tokens_token_hash_idx
    ON mcp_api_tokens (token_hash) WHERE revoked_at IS NULL;

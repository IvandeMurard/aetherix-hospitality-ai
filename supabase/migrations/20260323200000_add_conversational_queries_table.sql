-- Story 5.1 (HOS-28): Parse Conversational Inbound Queries
-- Creates the conversational_queries table for storing inbound natural-language
-- queries from managers (routed via Twilio / FR13).
--
-- Status lifecycle: pending → processing → answered
-- Idempotency enforced at the application layer (60 s dedup window on
-- from_number + body).

CREATE TABLE IF NOT EXISTS conversational_queries (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    property_id      UUID NOT NULL,
    from_number      TEXT NOT NULL,
    body             TEXT NOT NULL,
    recommendation_id UUID REFERENCES staffing_recommendations(id) ON DELETE SET NULL,
    status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'processing', 'answered')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for efficient tenant-scoped queries
CREATE INDEX IF NOT EXISTS idx_conv_queries_tenant_id     ON conversational_queries (tenant_id);
CREATE INDEX IF NOT EXISTS idx_conv_queries_property_id   ON conversational_queries (property_id);
-- Index used by the idempotency check (from_number + created_at range scan)
CREATE INDEX IF NOT EXISTS idx_conv_queries_from_created  ON conversational_queries (from_number, created_at DESC);

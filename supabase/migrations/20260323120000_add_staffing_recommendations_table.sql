-- Migration: add_staffing_recommendations_table
-- Story 3.3c (HOS-23): Format Staffing Recommendations for Dispatch

-- demand_anomalies table (prerequisite from stories 3.1 / 3.2 / 3.3a-b)
-- Created here so the foreign-key reference below is self-contained.
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS demand_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    property_id UUID NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    anomaly_type VARCHAR(50) NOT NULL,   -- surge | lull
    status VARCHAR(30) NOT NULL DEFAULT 'detected',
    -- roi_positive | ready_to_push | dispatched
    deviation_pct NUMERIC(6,2),
    expected_covers INT,
    predicted_covers INT,
    weather_factors JSONB,
    event_factors JSONB,
    roi_net NUMERIC(10,2),
    roi_labor_cost NUMERIC(10,2),
    headcount_delta INT,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staffing_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    property_id UUID NOT NULL,
    anomaly_id UUID NOT NULL REFERENCES demand_anomalies(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,           -- plain-text message for dispatch
    triggering_factor TEXT,               -- e.g. "Tech conference nearby"
    recommended_headcount INT,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    roi_net NUMERIC(10,2),
    roi_labor_cost NUMERIC(10,2),
    status VARCHAR(20) NOT NULL DEFAULT 'ready_to_push',  -- ready_to_push | dispatched
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(anomaly_id)  -- idempotency: one recommendation per anomaly
);

CREATE INDEX IF NOT EXISTS idx_staffing_recs_tenant ON staffing_recommendations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_staffing_recs_status ON staffing_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_demand_anomalies_tenant ON demand_anomalies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_demand_anomalies_status ON demand_anomalies(status);

ALTER TABLE staffing_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE demand_anomalies ENABLE ROW LEVEL SECURITY;

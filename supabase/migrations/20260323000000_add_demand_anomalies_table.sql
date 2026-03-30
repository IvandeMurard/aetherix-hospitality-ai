-- Story 3.3a: Detect Demand Anomalies Against Baseline
-- Migration: add_demand_anomalies_table
-- AC: 3, 5, 6, 7, 10

CREATE TABLE demand_anomalies (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    property_id         UUID NOT NULL REFERENCES properties(id),
    window_start        TIMESTAMPTZ NOT NULL,
    window_end          TIMESTAMPTZ NOT NULL,
    expected_demand     NUMERIC(10,2) NOT NULL,   -- projected F&B revenue for the window
    baseline_demand     NUMERIC(10,2) NOT NULL,   -- historical baseline for the same window type
    deviation_pct       NUMERIC(6,2) NOT NULL,    -- (expected - baseline) / baseline * 100
    direction           TEXT NOT NULL,             -- 'surge' | 'lull'
    triggering_factors  JSONB NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL DEFAULT 'detected',
        -- 'detected' -> 'roi_positive' (3.3b) -> 'ready_to_push' (3.3c) -> 'dispatched' (Epic 4)
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Fields populated by downstream stories (nullable until then):
    roi_revenue_opp     NUMERIC(10,2),
    roi_labor_cost      NUMERIC(10,2),
    roi_net             NUMERIC(10,2),
    recommendation_text TEXT,
    UNIQUE (tenant_id, property_id, window_start)
);

ALTER TABLE demand_anomalies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant Isolation" ON demand_anomalies
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));

CREATE INDEX idx_anomalies_property_status ON demand_anomalies (property_id, status);
CREATE INDEX idx_anomalies_window ON demand_anomalies (property_id, window_start);

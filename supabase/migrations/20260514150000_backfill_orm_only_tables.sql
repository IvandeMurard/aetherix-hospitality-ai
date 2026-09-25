-- Backfill missing ORM-only tables (Phase 0 deploy)
-- Auto-generated via scripts/generate_backfill_migration.py
-- Source of truth: backend/app/db/models.py
-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS

-- ============== demand_anomalies ==============
CREATE TABLE IF NOT EXISTS demand_anomalies (
	id UUID NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	property_id UUID NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	expected_demand NUMERIC(10, 2) NOT NULL, 
	baseline_demand NUMERIC(10, 2) NOT NULL, 
	deviation_pct NUMERIC(6, 2) NOT NULL, 
	direction VARCHAR NOT NULL, 
	triggering_factors JSON NOT NULL, 
	status VARCHAR NOT NULL, 
	detected_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	roi_revenue_opp NUMERIC(10, 2), 
	roi_labor_cost NUMERIC(10, 2), 
	roi_net NUMERIC(10, 2), 
	recommendation_text TEXT, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_demand_anomalies_tenant_id ON demand_anomalies (tenant_id);
CREATE INDEX IF NOT EXISTS ix_demand_anomalies_property_id ON demand_anomalies (property_id);

-- Fresh-replay convergence (added 2026-09-25, docs/context/migration-replay-drift.md).
-- On a fresh database 20260323000000 is skipped (no `tenants`/`properties`),
-- 20260323120000 creates demand_anomalies with an older column set, and the
-- CREATE TABLE IF NOT EXISTS above is then a no-op, so the columns the ORM and
-- the decision_ledger view (20260801100000) read were never created. These
-- statements bring a fresh replay to the ORM shape. This migration is already
-- in production's history, so Supabase never re-executes it there: production
-- is unchanged. Idempotent on any database that already has the columns.
-- One ADD COLUMN per ALTER TABLE: scripts/ci/check_schema_drift.py registers a
-- single ADD COLUMN per statement.
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS expected_demand NUMERIC(10, 2);
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS baseline_demand NUMERIC(10, 2);
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS direction TEXT;
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS triggering_factors JSONB DEFAULT '[]'::jsonb;
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS roi_revenue_opp NUMERIC(10, 2);
ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS recommendation_text TEXT;

DO $$
BEGIN
    -- The ORM never writes the legacy `anomaly_type` column created by
    -- 20260323120000; NOT NULL on it would reject every ORM insert.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = 'demand_anomalies'
           AND column_name = 'anomaly_type' AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE demand_anomalies ALTER COLUMN anomaly_type DROP NOT NULL;
    END IF;

    -- NOT NULL as in the ORM, only when it cannot fail (no rows to backfill).
    IF NOT EXISTS (SELECT 1 FROM demand_anomalies) THEN
        ALTER TABLE demand_anomalies ALTER COLUMN expected_demand SET NOT NULL;
        ALTER TABLE demand_anomalies ALTER COLUMN baseline_demand SET NOT NULL;
        ALTER TABLE demand_anomalies ALTER COLUMN deviation_pct SET NOT NULL;
        ALTER TABLE demand_anomalies ALTER COLUMN direction SET NOT NULL;
        ALTER TABLE demand_anomalies ALTER COLUMN triggering_factors SET NOT NULL;
    END IF;
END $$;

-- ============== staffing_recommendations ==============
CREATE TABLE IF NOT EXISTS staffing_recommendations (
	id UUID NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	property_id UUID NOT NULL, 
	anomaly_id UUID NOT NULL, 
	message_text TEXT NOT NULL, 
	triggering_factor TEXT, 
	recommended_headcount INTEGER, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	roi_net NUMERIC(10, 2), 
	roi_labor_cost NUMERIC(10, 2), 
	status VARCHAR NOT NULL, 
	dispatched_at TIMESTAMP WITH TIME ZONE, 
	dispatch_channel VARCHAR(10), 
	actioned_at TIMESTAMP WITH TIME ZONE, 
	action VARCHAR(10), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (anomaly_id), 
	FOREIGN KEY(anomaly_id) REFERENCES demand_anomalies (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_staffing_recommendations_property_id ON staffing_recommendations (property_id);
CREATE INDEX IF NOT EXISTS ix_staffing_recommendations_tenant_id ON staffing_recommendations (tenant_id);

-- ============== conversational_queries ==============
CREATE TABLE IF NOT EXISTS conversational_queries (
	id UUID NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	property_id UUID NOT NULL, 
	from_number VARCHAR NOT NULL, 
	body TEXT NOT NULL, 
	recommendation_id UUID, 
	status VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recommendation_id) REFERENCES staffing_recommendations (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_conversational_queries_property_id ON conversational_queries (property_id);
CREATE INDEX IF NOT EXISTS ix_conversational_queries_tenant_id ON conversational_queries (tenant_id);

-- ============== captation_baselines ==============
CREATE TABLE IF NOT EXISTS captation_baselines (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	avg_fb_revenue_per_room FLOAT NOT NULL, 
	dow_factors JSON NOT NULL, 
	monthly_factors JSON NOT NULL, 
	data_points_count INTEGER NOT NULL, 
	computed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES restaurant_profiles (tenant_id)
);

CREATE INDEX IF NOT EXISTS ix_captation_baselines_tenant_id ON captation_baselines (tenant_id);

-- ============== local_events ==============
CREATE TABLE IF NOT EXISTS local_events (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	event_id VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	rank INTEGER, 
	local_rank INTEGER, 
	phq_attendance INTEGER, 
	start_dt TIMESTAMP WITH TIME ZONE NOT NULL, 
	end_dt TIMESTAMP WITH TIME ZONE, 
	latitude FLOAT, 
	longitude FLOAT, 
	raw_labels JSON, 
	fetched_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_local_event UNIQUE (tenant_id, event_id), 
	FOREIGN KEY(tenant_id) REFERENCES restaurant_profiles (tenant_id)
);

CREATE INDEX IF NOT EXISTS ix_local_events_start_dt ON local_events (start_dt);
CREATE INDEX IF NOT EXISTS ix_local_events_tenant_id ON local_events (tenant_id);

-- ============== pms_sync_logs ==============
CREATE TABLE IF NOT EXISTS pms_sync_logs (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	sync_date DATE NOT NULL, 
	occupancy INTEGER, 
	fb_revenue FLOAT, 
	raw_payload_summary JSON, 
	status VARCHAR, 
	error_message VARCHAR, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES restaurant_profiles (tenant_id)
);

CREATE INDEX IF NOT EXISTS ix_pms_sync_logs_sync_date ON pms_sync_logs (sync_date);
CREATE INDEX IF NOT EXISTS ix_pms_sync_logs_tenant_id ON pms_sync_logs (tenant_id);

-- ============== recommendation_cache ==============
CREATE TABLE IF NOT EXISTS recommendation_cache (
	id SERIAL NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	target_date DATE NOT NULL, 
	prediction_data JSON, 
	reasoning_summary VARCHAR, 
	staffing_recommendation JSON, 
	is_pushed BOOLEAN, 
	pushed_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES restaurant_profiles (tenant_id)
);

CREATE INDEX IF NOT EXISTS ix_recommendation_cache_target_date ON recommendation_cache (target_date);
CREATE INDEX IF NOT EXISTS ix_recommendation_cache_tenant_id ON recommendation_cache (tenant_id);

-- ============== training_runs ==============
CREATE TABLE IF NOT EXISTS training_runs (
	id UUID NOT NULL, 
	property_id VARCHAR NOT NULL, 
	source VARCHAR NOT NULL, 
	records_count INTEGER NOT NULL, 
	mape_training FLOAT, 
	duration_ms INTEGER NOT NULL, 
	model_path VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_training_runs_property_id ON training_runs (property_id);


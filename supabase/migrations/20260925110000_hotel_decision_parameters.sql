-- ADR-0007 §18.3 (Décision #40) — per-hotel decision parameters.
--
-- Costs, labour constraints and commit offsets set by the hotel, never
-- invented: a missing parameter means no money is shown (qualitative risk
-- only). Append-only history: the value in force is the latest row per
-- (tenant_id, parameter); value NULL = cleared. Each row records who set it
-- (set_by), through which surface (set_via) and when (set_at). Money values
-- record the currency they were entered in; a value whose currency differs
-- from config.CURRENCY is ignored (no conversion).
--
-- Bounds are validated in app/services/hotel_parameters.py (catalog); the
-- CHECKs below are a backstop on the closed vocabularies.
-- ORM mirror: app/db/models.py HotelDecisionParameter (Décision #16).

CREATE TABLE IF NOT EXISTS hotel_decision_parameters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    parameter   TEXT NOT NULL,
    value       NUMERIC(12, 2),
    unit        TEXT NOT NULL CHECK (unit IN ('money', 'covers', 'staff', 'hours')),
    currency    TEXT,
    set_by      TEXT NOT NULL,
    set_via     TEXT NOT NULL CHECK (set_via IN ('dashboard_api', 'ops', 'proposal_approval')),
    note        TEXT,
    set_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hotel_decision_parameters_tenant_param
    ON hotel_decision_parameters (tenant_id, parameter, set_at);

-- Tenant-scoped: RLS on, backend service role only (same pattern as
-- 20260924120000).
ALTER TABLE public.hotel_decision_parameters ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hotel_decision_parameters_service_role_all ON public.hotel_decision_parameters;
CREATE POLICY hotel_decision_parameters_service_role_all ON public.hotel_decision_parameters
    FOR ALL TO service_role USING (true) WITH CHECK (true);

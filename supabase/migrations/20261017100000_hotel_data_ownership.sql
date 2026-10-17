-- HOS-346 (Décision #43) — the hotel owns its data; the Hive is opt-in and
-- always anonymized.
--
-- 1. hive_consents: a hotel's explicit opt-in to the Hive. Append-only, like
--    hotel_decision_parameters: the consent in force is the latest row per
--    tenant_id; each row records who set it (set_by), through which surface
--    (set_via) and when (set_at). No row = not opted in. Read by
--    app/services/hive_gate.py, the only path through which anything derived
--    from a hotel may enter a cross-hotel aggregate.
-- 2. hotel_decision_parameters.set_via gains 'hotel_system': a value read from
--    the hotel's own system (scheduling tool, SOP) keeps that provenance.
--
-- ORM mirror: app/db/models.py HiveConsent (Décision #16).

CREATE TABLE IF NOT EXISTS hive_consents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    opted_in    BOOLEAN NOT NULL,
    set_by      TEXT NOT NULL,
    set_via     TEXT NOT NULL CHECK (set_via IN ('dashboard_api', 'ops')),
    note        TEXT,
    set_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hive_consents_tenant
    ON hive_consents (tenant_id, set_at);

ALTER TABLE public.hive_consents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hive_consents_service_role_all ON public.hive_consents;
CREATE POLICY hive_consents_service_role_all ON public.hive_consents
    FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE public.hotel_decision_parameters
    DROP CONSTRAINT IF EXISTS hotel_decision_parameters_set_via_check;
ALTER TABLE public.hotel_decision_parameters
    ADD CONSTRAINT hotel_decision_parameters_set_via_check
    CHECK (set_via IN ('dashboard_api', 'ops', 'proposal_approval', 'hotel_system'));

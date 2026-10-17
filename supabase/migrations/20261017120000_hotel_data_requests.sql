-- HOS-349 (Décisions #43, #44) — hotel data through the hotel's own agent.
--
-- 1. hotel_data_requests: what the hotel's agent asked over MCP that only a
--    human may confirm — a deletion of all the hotel's data, or an opt-in to
--    the Hive. The owner confirms on WhatsApp with a one-time code that the
--    agent never sees (only its sha256 is stored). A confirmed deletion runs
--    after a delay and can be cancelled until then.
--    status: pending_confirmation | scheduled | executing | confirmed |
--            executed | cancelled | expired
-- 2. hive_consents.set_via gains 'mcp' (an opt-out by the hotel's agent is
--    immediate) and 'whatsapp' (an opt-in confirmed by the owner).
--
-- ORM mirror: app/db/models.py HotelDataRequest (Décision #16).

CREATE TABLE IF NOT EXISTS hotel_data_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           TEXT NOT NULL,
    kind                TEXT NOT NULL CHECK (kind IN ('deletion', 'hive_opt_in')),
    status              TEXT NOT NULL DEFAULT 'pending_confirmation',
    requested_by        TEXT NOT NULL,
    requested_via       TEXT NOT NULL CHECK (requested_via IN ('mcp')),
    code_hash           TEXT NOT NULL,
    confirm_expires_at  TIMESTAMPTZ NOT NULL,
    execute_after       TIMESTAMPTZ,
    confirmed_by        TEXT,
    confirmed_at        TIMESTAMPTZ,
    cancelled_by        TEXT,
    cancelled_at        TIMESTAMPTZ,
    executed_at         TIMESTAMPTZ,
    note                TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hotel_data_requests_tenant_status
    ON hotel_data_requests (tenant_id, status);

ALTER TABLE public.hotel_data_requests ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hotel_data_requests_service_role_all ON public.hotel_data_requests;
CREATE POLICY hotel_data_requests_service_role_all ON public.hotel_data_requests
    FOR ALL TO service_role USING (true) WITH CHECK (true);

ALTER TABLE public.hive_consents
    DROP CONSTRAINT IF EXISTS hive_consents_set_via_check;
ALTER TABLE public.hive_consents
    ADD CONSTRAINT hive_consents_set_via_check
    CHECK (set_via IN ('dashboard_api', 'ops', 'mcp', 'whatsapp'));

-- Décision #38 / ADR-0007 §16 — manager decision capture.
--
-- The manager's DECISION on a staffing recommendation (accepted | rejected |
-- modified) is arm C's ground truth. It must say how it was decided, and a
-- decision the system is unsure of must be confirmed before anything is written
-- (Décision #6, HITL). This migration adds:
--
--   1. staffing_recommendations.decision_source / decision_confidence
--      — which step decided (button | keyword | bare_ack_rule |
--        correction_pattern | model_auto | model_confirmed | keyword_confirmed |
--        bare_ack_confirmed) and with what confidence. Lets arm C separate an
--        explicit accept from an inferred one.
--   2. manager_prompts — pending HITL state: a confirmation question ("Je note
--      un refus, c'est bien ça ?") or an optional reason request. Nothing is
--      written to the recommendation until a confirmation is answered yes.
--      Unanswered after expires_at → status 'expired' (recorded as unconfirmed,
--      never as a decision).
--   3. inbound_reply_events — one row per inbound reply (plus one per expired
--      prompt): typed result, decision, source, confidence, typed `why` when
--      nothing is written, and the optional reason (typed route). Source of the
--      capture-rate / source-share / confirmation-rate metrics.
--
-- Independence rule (ADR-0007 §16.6): nothing here reads actual_covers. The
-- outcome never relabels a decision.
--
-- Additive, non-breaking. ORM mirror: app/db/models.py (Décision #16).
-- One ADD COLUMN per ALTER TABLE: the drift parser registers one per statement.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decision_source     TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decision_confidence NUMERIC(4, 3);

CREATE TABLE IF NOT EXISTS manager_prompts (
    id                UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id         TEXT        NOT NULL,
    property_id       UUID        NOT NULL,
    recommendation_id UUID        REFERENCES staffing_recommendations (id) ON DELETE SET NULL,
    kind              TEXT        NOT NULL CHECK (kind IN ('decision_confirmation', 'reason_request')),
    proposed_decision TEXT        CHECK (proposed_decision IN ('accepted', 'rejected', 'modified')),
    origin            TEXT,
    confidence        NUMERIC(4, 3),
    corrected_value   NUMERIC(10, 2),
    status            TEXT        NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'confirmed', 'declined', 'expired', 'answered', 'superseded')),
    expires_at        TIMESTAMPTZ NOT NULL,
    resolved_at       TIMESTAMPTZ,
    request_id        TEXT        NOT NULL DEFAULT '',
    PRIMARY KEY (id)
);

-- Backs "the pending prompt for this property" and the expiry sweep.
CREATE INDEX IF NOT EXISTS idx_manager_prompts_property_status
    ON manager_prompts (property_id, status, expires_at);

CREATE TABLE IF NOT EXISTS inbound_reply_events (
    id                      UUID        NOT NULL DEFAULT gen_random_uuid(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tenant_id               TEXT        NOT NULL,
    property_id             UUID,
    recommendation_id       UUID        REFERENCES staffing_recommendations (id) ON DELETE SET NULL,
    prompt_id               UUID        REFERENCES manager_prompts (id) ON DELETE SET NULL,
    request_id              TEXT        NOT NULL DEFAULT '',
    channel                 TEXT        NOT NULL CHECK (channel IN ('button', 'text', 'system')),
    result                  TEXT        NOT NULL,
    decision                TEXT,
    decision_source         TEXT,
    confidence              NUMERIC(4, 3),
    why                     TEXT,
    reason_text             TEXT,
    reason_route            TEXT,
    reason_route_confidence NUMERIC(4, 3),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_inbound_reply_events_tenant_created
    ON inbound_reply_events (tenant_id, created_at);

-- Tenant-scoped tables: RLS on, backend service role only (same pattern as
-- 20260515000000 / 20260619000000). reason_text is manager free text — same
-- regime as operational_memory notes (PII controls, DSAR scope).
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['manager_prompts', 'inbound_reply_events'] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_service_role_all', t);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR ALL TO service_role USING (true) WITH CHECK (true)',
            t || '_service_role_all', t
        );
    END LOOP;
END $$;

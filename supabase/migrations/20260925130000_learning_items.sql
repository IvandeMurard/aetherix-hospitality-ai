-- ADR-0007 §18.5 (Décision #40) — the learning loop's review queue.
--
-- Everything the outcome loop proposes lands here and is applied only when a
-- named person approves it (decided_by, decided_at, decision_note):
--   cost_parameter        proposed hotel parameter (revealed critical ratio,
--                         constraint rejections) → on approval written to
--                         hotel_decision_parameters with set_via =
--                         'proposal_approval' (reviewer: hotel or Ivan)
--   calibration           realised-outcome recalibration of a forecaster's
--                         uncertainty (canary + freeze rule passed) → on
--                         approval becomes the active calibration of the tenant
--                         (status 'applied'); rollback retires it and
--                         re-applies the previous one (reviewer: Ivan)
--   eval_case             case-set-routed override → becomes an eval case once
--                         a reviewer writes the expected output (reviewer: Ivan)
--   *_note                memory / decision_rule / policy / upstream_filter
--                         routed reasons, for review (route = model suggestion)
-- independent_actuals: false while actual covers are manager-declared (§16.6).
-- payload / evidence / decision_note may contain manager free text → DSAR.
-- RLS on, service role only. ORM mirror: app/db/models.py LearningItem.

CREATE TABLE IF NOT EXISTS learning_items (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            TEXT NOT NULL,
    kind                 TEXT NOT NULL CHECK (kind IN (
                             'cost_parameter', 'calibration', 'eval_case', 'memory_note',
                             'decision_rule_note', 'policy_note', 'upstream_filter_note')),
    subject              TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN (
                             'proposed', 'approved', 'rejected', 'superseded', 'applied', 'retired')),
    reviewer_role        TEXT NOT NULL CHECK (reviewer_role IN ('hotel', 'ivan')),
    payload              JSONB NOT NULL,
    evidence             JSONB,
    independent_actuals  BOOLEAN,
    source_ref           TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by           TEXT,
    decided_at           TIMESTAMPTZ,
    decision_note        TEXT,
    applied_ref          TEXT
);

CREATE INDEX IF NOT EXISTS idx_learning_items_tenant_kind_status
    ON learning_items (tenant_id, kind, status);

ALTER TABLE public.learning_items ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS learning_items_service_role_all ON public.learning_items;
CREATE POLICY learning_items_service_role_all ON public.learning_items
    FOR ALL TO service_role USING (true) WITH CHECK (true);

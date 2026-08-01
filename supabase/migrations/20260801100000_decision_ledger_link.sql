-- HOS-317 (Story 16.16) — Decision Ledger: close recommendation → override → outcome.
--
-- Finding C5/F6 of the external adversarial review (GPT, 2026-07-20). The audit
-- of the existing tables (see docs/context/decision-ledger.md §2) found that
-- **no new table is needed**: every leg of the loop is already persisted, but
-- one edge was missing — `operational_memory` rows (the manager's answer and the
-- measured outcome) carried the recommendation only as *text* inside
-- `reflection` (`[rec=<uuid>] outcome=...`), matched with a LIKE. That is not a
-- joinable key, so "for recommendation X, what did the manager answer and what
-- actually happened" could not be answered in SQL.
--
-- This migration adds the single missing edge + backfills it from the existing
-- text marker, and ships a read-only `decision_ledger` view that materialises
-- the end-to-end join (AC3).
--
-- Chain closed by this migration:
--   demand_anomalies            (source context: triggering_factors, deviation)
--     → staffing_recommendations (emitted recommendation, predicted_covers,
--                                 dispatch, dashboard accept/reject, actual_covers)
--       → operational_memory     (WhatsApp manager answer + ground-truth outcome)  ← NEW FK
--         → agent_action_log     (abstention/latency/guardrail trips, via request_id)
--
-- Décision #16 — the ORM (`backend/app/db/models.py`) mirrors this migration
-- exactly. `decision_ledger` is a VIEW, not a table: the drift gate parses
-- CREATE/ALTER TABLE only, and it is deliberately absent from the ORM.

-- ---------------------------------------------------------------------------
-- 1. The missing edge: operational_memory → staffing_recommendations
-- ---------------------------------------------------------------------------

ALTER TABLE operational_memory
    ADD COLUMN IF NOT EXISTS recommendation_id UUID;

-- ON DELETE SET NULL, never CASCADE: a manager's answer and a measured outcome
-- are audit evidence. They outlive the recommendation row they refer to.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_operational_memory_recommendation'
    ) THEN
        ALTER TABLE operational_memory
            ADD CONSTRAINT fk_operational_memory_recommendation
            FOREIGN KEY (recommendation_id)
            REFERENCES staffing_recommendations (id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- Backs the ledger lookup "all memory rows for recommendation X".
CREATE INDEX IF NOT EXISTS idx_operational_memory_recommendation
    ON operational_memory (recommendation_id)
    WHERE recommendation_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Backfill — recover the link already present as text
-- ---------------------------------------------------------------------------
-- 2.a Feedback rows written by tool_submit_feedback_to_memory carry the
--     `[rec=<uuid>]` marker at the head of `reflection`. The EXISTS guard skips
--     ids whose recommendation no longer exists (would violate the FK).

UPDATE operational_memory om
SET recommendation_id = sub.rec_id
FROM (
    SELECT
        id,
        NULLIF(substring(reflection FROM '\[rec=([0-9a-fA-F-]{36})\]'), '')::uuid AS rec_id
    FROM operational_memory
    WHERE recommendation_id IS NULL
      AND reflection LIKE '[rec=%'
) sub
WHERE om.id = sub.id
  AND sub.rec_id IS NOT NULL
  AND EXISTS (SELECT 1 FROM staffing_recommendations sr WHERE sr.id = sub.rec_id);

-- 2.b Ground-truth rows (ReceiptsService.persist_actual_covers) have no marker,
--     but share `request_id` with the feedback row written in the same inbound
--     turn (twilio_inbound._bg_receipt_feedback). Same hotel + same request_id
--     is the existing correlation contract (P2-2 / P3-10).

UPDATE operational_memory gt
SET recommendation_id = fb.recommendation_id
FROM operational_memory fb
WHERE gt.recommendation_id IS NULL
  AND gt.memory_type = 'ground_truth'
  AND gt.request_id <> ''
  AND fb.request_id = gt.request_id
  AND fb.hotel_id = gt.hotel_id
  AND fb.memory_type = 'feedback'
  AND fb.recommendation_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 3. decision_ledger — the end-to-end read surface (AC3)
-- ---------------------------------------------------------------------------
-- One row per emitted recommendation. Analyst / demo surface (HOS-310); the
-- runtime source of truth is `DecisionLedgerService`, which rebuilds the same
-- join portably (tests run on SQLite, which has no LATERAL).
--
-- security_invoker = true is REQUIRED: without it the view runs with the
-- owner's rights and silently bypasses the RLS enabled on the underlying
-- tables (migrations 20260515000000 / 20260515100000), which would turn a
-- per-tenant read into a cross-tenant leak.

DROP VIEW IF EXISTS decision_ledger;

CREATE VIEW decision_ledger
WITH (security_invoker = true) AS
SELECT
    sr.id                       AS recommendation_id,
    sr.tenant_id,
    sr.property_id,

    -- ── Source context + data quality ────────────────────────────────────
    da.id                       AS anomaly_id,
    da.triggering_factors,
    da.deviation_pct,
    da.direction,
    da.detected_at              AS context_detected_at,

    -- ── Recommendation emitted ───────────────────────────────────────────
    sr.created_at               AS recommended_at,
    sr.message_text,
    sr.recommended_headcount,
    sr.predicted_covers,
    sr.window_start,
    sr.window_end,
    sr.roi_net,
    sr.dispatched_at,
    sr.dispatch_channel,

    -- ── Manager response (dashboard column first, WhatsApp memory second) ─
    COALESCE(sr.action, fb.manager_feedback)        AS manager_response,
    COALESCE(sr.actioned_at, fb.created_at)         AS manager_responded_at,
    CASE
        WHEN sr.action IS NOT NULL THEN 'dashboard'
        WHEN fb.id     IS NOT NULL THEN 'whatsapp'
        ELSE NULL
    END                                             AS manager_response_channel,
    fb.id                       AS feedback_memory_id,
    fb.outcome                  AS feedback_outcome,
    fb.reflection               AS feedback_reflection,

    -- ── Measured outcome ─────────────────────────────────────────────────
    sr.actual_covers,
    sr.actual_covers_source,
    sr.actual_covers_at,
    gt.id                       AS outcome_memory_id,
    CASE
        WHEN sr.predicted_covers IS NULL
          OR sr.actual_covers    IS NULL
          OR sr.actual_covers    = 0 THEN NULL
        ELSE ROUND(
            ABS(sr.predicted_covers - sr.actual_covers) / sr.actual_covers * 100,
            2
        )
    END                                             AS abs_pct_error,

    -- ── Confidence / abstention telemetry (ADR-0003 · ADR-0007 §D6) ──────
    COALESCE(fb.request_id, gt.request_id)          AS request_id,
    aal.abstention_reason,
    aal.abstention_layer,
    aal.status                  AS agent_status,
    aal.error_code              AS agent_error_code

FROM staffing_recommendations sr
LEFT JOIN demand_anomalies da
       ON da.id = sr.anomaly_id

-- Latest manager answer for this recommendation.
LEFT JOIN LATERAL (
    SELECT om.*
    FROM operational_memory om
    WHERE om.recommendation_id = sr.id
      AND om.memory_type = 'feedback'
    ORDER BY om.created_at DESC
    LIMIT 1
) fb ON TRUE

-- Latest ground-truth observation for this recommendation.
LEFT JOIN LATERAL (
    SELECT om.*
    FROM operational_memory om
    WHERE om.recommendation_id = sr.id
      AND om.memory_type = 'ground_truth'
    ORDER BY om.created_at DESC
    LIMIT 1
) gt ON TRUE

-- The agent call that produced the manager's answer — carries the typed
-- abstention / guardrail-trip reason for that turn (NFR2, Décision #27).
LEFT JOIN LATERAL (
    SELECT al.*
    FROM agent_action_log al
    WHERE al.request_id = COALESCE(fb.request_id, gt.request_id)
      AND al.request_id <> ''
      AND al.hotel_id = sr.tenant_id
    ORDER BY al.created_at DESC
    LIMIT 1
) aal ON TRUE;

COMMENT ON VIEW decision_ledger IS
    'HOS-317 Decision Ledger — one row per emitted recommendation, joining source '
    'context, manager response (dashboard or WhatsApp) and measured outcome. '
    'Read-only. Runtime source of truth: DecisionLedgerService.';

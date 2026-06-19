-- HOS-216 (EVAL-1 gate / ADR-0007 §6.c, Décision #16) — eval baseline audit log.
--
-- The git-tracked eval/baselines/*.json files remain the RUNTIME source of truth
-- (the CI gate reads them directly). This table is a historical audit log: it
-- answers "what was our baseline on 2026-08-12 / which PR set it and why".
-- ORM mirror: app/db/models.py EvalBaseline.
-- Migration: 20260619010000

CREATE TABLE IF NOT EXISTS eval_baselines (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    layer           TEXT        NOT NULL,          -- forecast | parser | drift | latency | recall
    git_sha         TEXT        NOT NULL,
    baseline_json   JSONB       NOT NULL,          -- per-category metrics frozen
    reason          TEXT        NOT NULL,          -- why this baseline was set/reset
    pr_number       INTEGER,
    is_active       BOOLEAN     NOT NULL DEFAULT FALSE,
    superseded_by   UUID        REFERENCES eval_baselines(id)
);

-- At most one active baseline per layer.
CREATE UNIQUE INDEX IF NOT EXISTS eval_baselines_active_idx
    ON eval_baselines (layer)
    WHERE is_active = TRUE;

-- Audit data, non-tenant — but every public table is reachable via the Supabase
-- anon key by default; lock it to the backend service role.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_class
        WHERE relname = 'eval_baselines'
          AND relnamespace = 'public'::regnamespace
    ) THEN
        EXECUTE 'ALTER TABLE public.eval_baselines ENABLE ROW LEVEL SECURITY';

        EXECUTE 'DROP POLICY IF EXISTS eval_baselines_service_role_all ON public.eval_baselines';
        EXECUTE 'CREATE POLICY eval_baselines_service_role_all ON public.eval_baselines '
             || 'FOR ALL TO service_role USING (true) WITH CHECK (true)';
    END IF;
END $$;

-- ADR-0007 §18.1 (Décision #40) — point of no return per task class.
--
-- staffing_recommendations:
--   task_class         task_classes.TaskClassKey: staffing.add | staffing.reduce
--                      (food_prep.batch is catalogued, not recommended today)
--   commit_at          when the action commits = service start − commit offset
--                      (extra shift confirmed / staff notified). Before it the
--                      decision can still be changed cheaply; after it, only
--                      costly corrective actions remain.
--   correction_window  typed window: commit point, offset hours, offset basis
--                      (default_assumption | hotel_configured), status at issue
--                      time (open | closing | passed), catalog version.
--
-- Additive. Existing rows keep NULL (issued before the catalog existed).
-- ORM mirror: app/db/models.py (Décision #16). One ADD COLUMN per ALTER TABLE.

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS task_class        TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS commit_at         TIMESTAMPTZ;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS correction_window JSONB;

ALTER TABLE staffing_recommendations DROP CONSTRAINT IF EXISTS staffing_recommendations_task_class_check;
ALTER TABLE staffing_recommendations ADD CONSTRAINT staffing_recommendations_task_class_check
    CHECK (task_class IS NULL OR task_class IN ('staffing.add', 'staffing.reduce', 'food_prep.batch'));

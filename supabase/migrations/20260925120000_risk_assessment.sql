-- ADR-0007 §18.4 (Décision #40) — risk-based recommendation.
--
-- staffing_recommendations:
--   decision_rule    rule that produced recommended_headcount:
--                    newsvendor-v1 (critical-ratio quantile of the calibrated
--                    demand distribution, hotel costs) | deviation-scale-v1
--                    (previous ROI headcount scale, used whenever an input is
--                    missing — the missing inputs are listed in risk_assessment)
--   risk_assessment  typed per-option consequences (risk_assessment.SCHEMA):
--                    if accepted / if refused — extra shifts and their cost
--                    (only when configured), shortfall probability and
--                    expected shortfall (only when the forecaster is
--                    calibrated, with the calibration's provenance), else a
--                    qualitative band; interval at issue time (arm C coverage);
--                    parameters version; materiality (interruption budget).
--
-- Additive. ORM mirror: app/db/models.py (Décision #16).

ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS decision_rule   TEXT;
ALTER TABLE staffing_recommendations ADD COLUMN IF NOT EXISTS risk_assessment JSONB;

ALTER TABLE staffing_recommendations DROP CONSTRAINT IF EXISTS staffing_recommendations_decision_rule_check;
ALTER TABLE staffing_recommendations ADD CONSTRAINT staffing_recommendations_decision_rule_check
    CHECK (decision_rule IS NULL OR decision_rule IN ('newsvendor-v1', 'deviation-scale-v1'));

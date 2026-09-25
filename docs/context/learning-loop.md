# The learning loop — end to end

> Décision #40 · ADR-0007 §18.5 · status 25/09/2026: **Built, never run on real
> data** (0 real recommendation with a measured outcome). Vocabulary: the loop
> is *outcome-tracked with human-approved updates*. It is not "self-improving":
> nothing changes without a named person approving it (Décision #6).

## What is learned, from which signal

| What changes | Signal | Rule (code) | Proposed how often | Who approves | How it is evaluated | How it is rolled back |
|---|---|---|---|---|---|---|
| **Forecast uncertainty** of a forecaster, per hotel (the distribution risk statements rest on) | realised covers vs the forecast stored on each recommendation (`predicted_covers`, `actual_covers`) | `learning_loop.propose_realised_calibration`: split-conformal on the earlier two thirds, tested on the later third (disjoint in time), ≥ 60 points | weekly pass (Mon 03:40, `learning_loop_worker`) | **Ivan** (superuser) | canary: 3 identical recomputations; freeze rule: not under-covering by > 5 pp, and closer to nominal than the active calibration on the same test set; afterwards arm C interval coverage and risk-statement calibration, split by `calibration_version` | `POST …/learning/calibration/rollback`: the active version is retired, the previous one re-applied; no previous one → no calibration → qualitative statements |
| **Cost trade-off** (`lost_cover_value`) | human accept / reject decisions on calibrated newsvendor recommendations | `revealed_critical_ratio` (interval-censored, convex-loss bounds) → implied value with the observable `extra_shift_cost` held fixed; ≥ 10 decisions, ≥ 25 % change | weekly | **the hotel** (owner) or Ivan | a proposal shows its evidence (n, bounds violated, estimate); after approval, the next recommendations use it (the parameters version is stored on each) | set the previous value again (history is append-only: `GET …/decision-parameters/history`) |
| **Labour constraint** (`max_extra_staff`) | ≥ 3 human rejections with the human reason `staffing_constraint` of additions larger than any accepted one | `propose_cost_updates` (`constraint_rejections_v1`) | weekly | the hotel or Ivan | same | same |
| **Eval cases** | an override whose reason the model routed to `case_set` (≥ 0.7) | `route_override` → `eval_case` item | weekly | **Ivan**, who must write the expected output | the case joins `eval/golden_dataset.jsonl` (dated zone, author = reviewer) via `scripts/eval/export_case_candidates.py`, which re-validates the whole file | remove the line from the dataset (it is a reviewed file under version control) |
| **Memory / decision-rule / policy / upstream-filter notes** | routed reasons | `route_override` | weekly | memory and decision-rule notes: the hotel; policy and upstream filter: Ivan | acknowledgement only — no automatic effect | n/a |

Also produced every week, not a change: **arm C** calibration of the risk
statements (`risk_statement_calibration`: when the system said "≈25 %", did it
happen about 1 in 4?), per task class × decider × calibration version, with
Brier score, reliability bins and the realised frequency of each qualitative
band; and **arm B** — a miscalibrated group (n ≥ 30, gap > max(10 pp, 2 SE))
writes a typed trip (`agent_action_log`, `learning.risk_calibration`,
`risk_statement_miscalibrated`) and an ops anomaly. Read on demand:
`GET /api/v1/hotels/{tenant}/learning/report`.

## Where it lives

- Pure rules: `backend/app/services/learning_loop.py`
- Queue, approval, application, rollback, export: `backend/app/services/learning_store.py`, table `learning_items`
- Weekly pass: `backend/app/workers/learning_loop_worker.py`
- Review API (dashboard user; owner or superuser; Ivan-only kinds enforced): `backend/app/api/routes/learning.py`
- Inputs it relies on: `risk_assessment` stored at issue time (§18.4), hotel parameters (§18.3), calibrations (§18.2)

## Hygiene rules (tested in `tests/services/test_learning_loop.py`)

1. **Human and agent records stay separate.** Reports are split by decider
   group (`decided_by`); cost proposals read human decisions only; an
   autonomous agent's decision is never evidence of what a hotel wants.
2. **Agent-inferred reasons are never ground truth.** A reason with
   `reason_source = agent_inferred` is ignored by every reason-conditional rule.
3. **Outcomes never relabel decisions.** Proposals from decisions do not read
   outcomes (pinned by `test_outcomes_never_change_the_revealed_ratio`);
   outcomes feed calibration only.
4. **Manager-declared covers are not independent.** Every report and proposal
   carries `independent_actuals`, false until POS/PMS actuals exist; the
   reviewer sees it before approving.
5. **Routes are suggestions.** The route of a reason comes from the model; an
   item built from it is reviewed, never applied.
6. **Nothing is applied by the loop itself.** The worker only writes
   `proposed` items; application happens in `learning_store.decide`, called by
   a named approver, who is recorded (`decided_by`, `decided_at`, note).

## What is not measured (25/09/2026)

- No real recommendation has a realised outcome: every report is empty, no
  realised calibration exists, no cost proposal has been generated.
- The rules are tested on constructed data only.
- The revealed critical ratio assumes managers decide on costs, not on the
  forecast; reasons are used to exclude forecast disagreements, but a manager
  who gives no reason is taken at face value.
- Thresholds (n ≥ 30 / 60 / 10, 5 pp, 25 %) are defaults fixed before any data
  (HOS-316 spirit), open to Ivan (`open-decisions.md`).

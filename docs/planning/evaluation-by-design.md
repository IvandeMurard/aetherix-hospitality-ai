# Evaluation by Design — Aetherix Reliability Plan

**Status:** Product brief — input for Architect (ADR-0007) and SM (Linear story creation)
**Date:** 2026-06-04
**Owner:** PM (Ivan)
**Related:** `docs/adr/0007-evaluation-by-design-DRAFT.md`, CLAUDE.md Décision architecturale #22

---

## Why this document exists

Two triggers in the same week:

1. **Qonto talk "AI @ Qonto: shipper et évaluer l'IA en production"** (Marianne Borzic Ducournau, Head of AI Products) — surfaced explicit "Evaluation by design" framework with two non-negotiable takeaways: *"Working vs Reliable"* and *"Eval as a Contract"*.
2. **BMad-Method gap identified** — BMM's Dev Agent DoD (currently 7 steps in CLAUDE.md) treats *"CI green = done"*. For AI/ML products this is insufficient: a model can pass unit tests and still hallucinate, drift, or fail silently in production. Aetherix has solid post-deploy telemetry (`agent_action_log`, `memory_instrumentation_daily`) but **quasi-inexistent upstream eval**. The current MAPE 15.09% is a one-shot measurement, not a living regression gate.

This document is the **product brief** for closing that gap. It defines:
- Frameworks adopted (Qonto)
- Aetherix reliability pyramid
- Failure definitions per layer (the "contract")
- 6 stories to ship in Phase 3 (foundation + 5 reliability dimensions)
- 5 stories noted for Phase 4

---

## Frameworks adopted

### Framework A — "Working" vs "Reliable" (Qonto Takeaway 1)

> *"Working" is proven on a test set. "Reliable" is proven in production.*

5 reliability dimensions, one question each before ship:

| Dimension | Aetherix question |
|---|---|
| **Edge behavior** | Did we test on out-of-distribution inputs (unsupported language, weird manager replies, anomalous bookings, OTA cancellation wave)? Not just happy path? |
| **Graceful degradation** | When the agent doesn't know, does it say *"I don't know"* explicitly — or improvise a recommendation? Is the refusal path coded as a contract? |
| **Observability** | Do we have a dashboard showing what the model does in prod — not just server uptime? Can we detect failure before the manager complains? |
| **Reproducibility** | If a manager replies the same WhatsApp message tomorrow, do we generate the same recommendation? Temperature, seed, cache states — pinned? |
| **Distribution shift resilience** | Do we have an alert if input distribution (covers, weather, events, manager replies vocabulary) drifts from training set? |

### Framework B — "Eval as a Contract" (Qonto Takeaway 2)

> *Not after the bug — from the start. Before writing the first line of model code, answer: "How will we know it works?"*

- **Golden dataset first** — representative examples (incl. edges) before any training/coding
- **Define failure** — what is a bad output? at what threshold is it unacceptable?
- **For LLMs** — golden test sets + LLM-as-judge + human eval loops (3-prong)
- **Eval as a contract** — the eval dataset IS a spec, not an afterthought

### Framework C — ML "internal" vs ML "product" (Qonto context)

Aetherix is **ML "product"** by Qonto's definition — client-facing recommendations to hotel managers. Reliability bar = ship-or-fail, not "informs a decision". **Stricter than internal ML.**

---

## Aetherix reliability pyramid

```
Layer 5  ── Trust KPI ablation (US-7)              ← Phase 3 Track A (partial)
Layer 4  ── Memory recall relevance                 ← Phase 3 (EVAL-1 area, full coverage Phase 4)
Layer 3  ── Inbound feedback parser (Haiku)         ← Phase 3 (EVAL-4)
Layer 2  ── LLM reasoning quality                   ← Phase 4 (EVAL-6, EVAL-7)
Layer 1  ── Forecast accuracy (Prophet, MAPE)       ← Phase 3 (EVAL-1)
Base    ── Golden dataset + failure definitions    ← Phase 3 EVAL-0 (BLOCKING prerequisite)
```

---

## Failure definitions per layer ("the contract")

| Layer | "Bad output" definition | Unacceptable threshold |
|---|---|---|
| **Forecast (Prophet)** | MAPE deviates from baseline by > 3pp on any category, or > 22% rolling 7-day average | Rolling 7d > 22% triggers alert; > 25% triggers auto-disable of cold-start meta-learner (per ADR-0005) |
| **LLM reasoning** | Factually incorrect explanation (attributes spike to wrong cause, references non-existent event, invents numbers) | > 5% of recs flagged in human spot-check (Phase 4 EVAL-6) |
| **Inbound parser (Haiku)** | Misclassifies manager intent (accepted/rejected/modified) | accuracy < 90% on stratified eval set; precision per intent < 0.85 |
| **Memory recall** | No relevant hit returned when one exists in same hotel context; or returns hit with mean similarity below threshold | precision@5 < 0.7 on annotated eval set |
| **Cold-start meta-learner** | Day-1 MAPE > 25% on LOO backtest | Gate already in ADR-0005 — runtime auto-disable |
| **Latency** | Endpoint p95 > documented SLO | Prediction p95 > 8s · Recommendation p95 > 12s · Receipt generation p95 > 15s · Inbound parser p95 > 2s |
| **Distribution shift** | Input feature distribution drifts > 2σ vs training, or KS-test p-value < 0.01 on key features | Drift detected → alert WhatsApp + auto-disable cold-start meta-learner |

These thresholds are **the contract**. Updating them = explicit decision (PR + CLAUDE.md trace). Code changes that violate the contract = CI fails.

---

## Stories — Phase 3 (6 stories, foundation + 5 dimensions)

### EVAL-0 — Golden Dataset + Failure Definitions [BLOCKING PREREQ]

**Priority:** P0 — blocks EVAL-1 through EVAL-5
**Reliability dim:** Foundation for all 5

**Scope:**
1. Create `eval/golden_dataset.jsonl` — 40-60 representative scenarios. Categories minimum:
   - Normal day (15 examples) — typical occupancy, no events, normal weather
   - Event day (8) — local event with known covers spike
   - Weather anomaly (5) — heatwave reducing dinner, cold snap boosting room service
   - OTA cancellation wave (3) — late cancellations affecting Day J covers
   - Weekend vs weekday split (5)
   - Service stratification (5) — breakfast-heavy vs dinner-heavy properties
   - **OOD edges** (5) — unsupported language manager reply, weird booking pattern, missing PMS data day, anomalous occupancy spike, multi-event collision
   - **Manager reply intents** (15) — stratified by language (FR/EN), intent (accepted/rejected/modified), phrasing (terse/verbose/sarcastic/emoji)
2. Create `eval/FAILURE_THRESHOLDS.md` — copy the contract table above; this becomes the canonical reference
3. Create `eval/README.md` — documents the contract: any model/LLM/memory change requires updating the golden dataset
4. Update `CLAUDE.md` Dev Agent DoD with step 8 (Eval gate)

**Deliverable:** `eval/` directory committed with 3 files (`golden_dataset.jsonl`, `FAILURE_THRESHOLDS.md`, `README.md`) + CLAUDE.md amended.

**Effort:** ~2 days (data curation is the bulk; thresholds already drafted above)

**Dependencies:** None — this is THE prerequisite.

**DoD:**
- [ ] 40+ scenarios in `golden_dataset.jsonl`, all 8 categories covered, minimum counts respected
- [ ] Each scenario has: id, category, input payload, expected output (or accept-band), failure-trigger note
- [ ] Thresholds documented + linked from `CLAUDE.md` Décision #22
- [ ] PR review by SM + Architect

---

### EVAL-1 — Stratified MAPE + CI Regression Gate

**Priority:** P1 — pilot-blocking quality gate
**Reliability dim:** Edge behavior + Reproducibility (forecast layer)

**Scope:**
1. Refactor `scripts/ops/measure_mape_j1.py` to score MAPE **per category** from `golden_dataset.jsonl`
2. Output: `eval/reports/mape_YYYY-MM-DD.json` + markdown summary auto-generated
3. New CI script: `scripts/ci/check_eval_coverage.py` — if PR touches `app/services/forecast*` or `app/providers/`, run eval suite, fail if any category regresses > 3pp from baseline
4. Baseline: current MAPE 15.09% (run 2026-05-21) → freeze per category at first run

**Deliverable:** refactored script + CI workflow + first stratified report

**Effort:** ~1-1.5 days

**Dependencies:** EVAL-0 done

**DoD:**
- [ ] Per-category MAPE measurable and reproducible (seed=42)
- [ ] CI fails on regression > 3pp; passes on no-change
- [ ] Baseline frozen in `eval/baselines/mape_baseline.json`
- [ ] First report committed in `eval/reports/`

---

### EVAL-2 — "I Don't Know" Contract

**Priority:** P1 — pilot-blocking trust signal
**Reliability dim:** Graceful degradation

**Scope:**
1. Audit current code: identify all paths where the agent produces a recommendation without sufficient confidence (forecast service, recommendation service, receipt generator, parser fallback)
2. Implement explicit *"I don't know"* contract per path:
   - **Forecast service** : if cold-start AND no cohort match → return `null + reason="cold_start_no_cohort"`
   - **Recommendation service** : if `confidence < 0.5` → degrade to *context-only* mode (data shown, no recommendation, explanation about why agent abstained)
   - **WhatsApp Receipt** : explicit message variant for "I don't know" — *"Données insuffisantes ce matin — voici les données brutes. Aetherix n'a pas suffisamment de confiance pour recommander aujourd'hui."*
   - **Parser fallback** : already exists (auto-`modified` if confidence < 0.6, Décision #15) → reinforce + telemetry
3. Add 5+ "I don't know" scenarios to `golden_dataset.jsonl`
4. Telemetry: log every "I don't know" event with reason in `agent_action_log`

**Deliverable:** code changes + 5 test cases in golden dataset + telemetry field

**Effort:** ~1.5 days

**Dependencies:** EVAL-0

**DoD:**
- [ ] All 4 "I don't know" paths implemented and tested
- [ ] Each path emits structured log event
- [ ] WhatsApp variant copy validated by PM
- [ ] Eval scenarios pass: agent abstains correctly on OOD inputs

---

### EVAL-3 — Distribution Shift Detector

**Priority:** P2 — quality gate
**Reliability dim:** Distribution shift resilience

**Scope:**
1. Define training set distribution snapshots per key feature: covers, weather (temp, precipitation), events (count, type), occupancy
2. Online monitor: rolling 7-day distribution vs training set, alert if **KS-test p-value < 0.01** OR **>2σ shift** on key features
3. Alerting: WhatsApp to manager (data quality warning) + log; auto-disable cold-start meta-learner if drift on cohort features (per ADR-0005 runtime gate)
4. Dashboard: drift score per hotel via Supabase materialized view `distribution_shift_daily`

**Deliverable:** monitor service + alert path + MV + drift score dashboard

**Effort:** ~2 days

**Dependencies:** EVAL-0 (drift features = part of failure definition)

**DoD:**
- [ ] Training snapshots committed in `eval/distribution_snapshots/`
- [ ] Monitor runs daily, results in MV
- [ ] Alert path tested with synthetic drift injection
- [ ] Auto-disable hook on cold-start meta-learner verified

---

### EVAL-4 — Inbound Parser Haiku Accuracy

**Priority:** P1 — directly impacts feedback loop quality
**Reliability dim:** Edge behavior + Reproducibility (parser layer)

**Scope:**
1. Eval set: 200+ stratified manager replies (FR + EN), annotated by PM with intent (accepted/rejected/modified) + reference confidence label
2. Eval script: `scripts/eval/measure_parser_accuracy.py` → accuracy/precision/recall per intent + confusion matrix + markdown report
3. CI gate: if PR touches `app/services/inbound_parser*` or its prompt → run eval, fail if accuracy < 90% global OR precision per intent < 0.85
4. Production telemetry: log Haiku confidence + outcome (auto-`modified` if < 0.6 per Décision #15) — already partial, complete

**Deliverable:** eval set + script + CI gate + dashboard

**Effort:** ~1.5 days

**Dependencies:** EVAL-0 (parser examples nested in golden dataset)

**DoD:**
- [ ] 200+ annotated examples in `eval/golden_dataset.jsonl` under `parser_*` category
- [ ] Accuracy ≥ 90% on first measurement (or surface gap explicitly)
- [ ] CI gate active
- [ ] Confusion matrix in first report

---

### EVAL-5 — Latency SLO + Dashboard

**Priority:** P2 — observability completion
**Reliability dim:** Observability (completes existing telemetry)

**Scope:**
1. Define p50/p95/p99 targets per endpoint:
   - Prediction (`/api/v1/predictions/today`) : p95 < 8s
   - Recommendation (`/api/v1/recommendations/today`) : p95 < 12s
   - Receipt generation (background job) : p95 < 15s
   - Inbound parser (Haiku call) : p95 < 2s
   - MCP tool calls (`/mcp/v0/*`) : p95 < 5s
2. Instrumentation: latency metrics already in `agent_action_log` — extend if gaps
3. Dashboard: Supabase MV `latency_slo_daily` per endpoint + Notion or Grafana embed
4. Alerting: WhatsApp ops alert if p95 breached for > 5 consecutive minutes

**Deliverable:** SLO doc (`docs/ops/latency-slo.md`) + instrumentation + dashboard + alert path

**Effort:** ~1 day

**Dependencies:** EVAL-0 (latency is part of failure definitions)

**DoD:**
- [ ] SLO doc committed
- [ ] All 5 endpoints instrumented
- [ ] MV refreshed nightly
- [ ] Alert path tested

---

### Phase 3 totals

- **6 stories** : EVAL-0 (blocking) + EVAL-1 through EVAL-5 (parallel after EVAL-0)
- **Effort cumulé** : ~9-10 jours dev
- **Sequencing** :
  - Sprint N : EVAL-0 (blocks all)
  - Sprint N+1 : EVAL-1 + EVAL-2 + EVAL-4 (P1, pilot-blocking) en parallèle
  - Sprint N+2 : EVAL-3 + EVAL-5 (P2)
- **Pilot gate** : EVAL-0 + EVAL-1 + EVAL-2 + EVAL-4 minimum before design partner gets daily Receipts in prod

---

## Stories — Phase 4 (5 stories, full Qonto-style coverage)

Noted for context, full scoping in Phase 4 planning:

- **EVAL-6** — LLM-as-judge on reasoning quality (sample N recs/week, judge model evaluates explanation factual accuracy)
- **EVAL-7** — Human eval loops (sample manager replies → PM annotation queue → feed golden dataset; weekly)
- **EVAL-8** — Memory recall precision@k vs annotated truth (build annotated set of "ideal hit" per query, measure recall quality)
- **EVAL-9** — Adversarial probes extended (beyond prompt injection: anomalous data injection, weird timezone, broken PMS feed, malicious manager reply)
- **EVAL-10** — Cost per recommendation + A/B framework (track $ per Daily Receipt, compare prompts/providers head-to-head with statistical significance)

Tooling re-evaluation Phase 4 : if EVAL-6/EVAL-7 generate > 1000 eval runs/month, evaluate **Braintrust** (Anthropic-friendly, no LangChain lock-in). Until then, custom JSONL + Python.

---

## BMad meta-fix (cross-cutting)

The BMad-Method gap that surfaced this work merits explicit fix:

| Change | Where |
|---|---|
| Dev Agent DoD step 8 (Eval gate) | `CLAUDE.md` |
| Décision architecturale #22 (Eval-by-design gate CI) | `CLAUDE.md` |
| Workflow doc *"Eval-by-design extension for AI/ML BMad projects"* | `tools/bmad/eval-by-design-workflow.md` (Phase 4, after stories shipped) |
| Technical article (REX) | See follow-up section below |

---

## Follow-up: technical article (post-shipping)

Phase 3 Track B already includes a technical write-up deliverable. The eval-by-design extension provides a strong angle.

**Title candidates:**
- *"How we extended BMad-Method with Evaluation-by-Design for AI/ML products"*
- *"Closing the AI reliability gap in BMad: eval-as-a-contract for AI/ML products"*
- *"From 'tests pass' to 'reliable in production': eval-by-design for vertical AI products"*

**Audience:** AI product teams using BMad-Method, AI/ML engineers in domains where decisions have financial impact (fintech, hospitality, healthcare, supply chain).

**Outlets:** dev.to, Medium (Qonto Way analogue), LinkedIn long-form, BMad-Method community.

**Scope:** REX (retour d'expérience) — to be written **after EVAL-0 through EVAL-5 are shipped and the gate has caught its first regression in CI**. Real-world experience > theoretical framework. Cite Qonto talk as inspiration source; document what we adopted, what we adapted, what we discarded.

**Timing:** Phase 3 Track B technical write-up window — likely end of Phase 3 / start of Phase 4.

---

## Action plan (post-PM validation)

1. ✅ This document written (you are here)
2. ⏭ `docs/adr/0007-evaluation-by-design-DRAFT.md` — handoff Architect
3. ⏭ CLAUDE.md updates — Décision #22 + Dev Agent DoD step 8
4. ⏭ Mémoire `market_signals_2026Q2.md` — section Qonto framework + BMad gap
5. 🔮 Session Architect (cette semaine) — finaliser ADR-0007
6. 🔮 Session SM (après ADR) — créer 6 stories Linear depuis ce brief
7. 🔮 Sprint courant — EVAL-0 démarre (golden dataset = unblocking)
8. 🔮 Post EVAL-0..5 shipped — REX article rédigé (Phase 3 Track B)

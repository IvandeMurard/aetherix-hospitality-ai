# Failure Thresholds — "The Contract"

> **Source of truth** for what counts as a *bad output* per layer, and the
> threshold at which it is *unacceptable*. Copied from the PM brief
> (`docs/planning/evaluation-by-design.md` §"Failure definitions per layer")
> and ADR-0007 §D3/§D5. **Updating any threshold is an explicit decision** —
> requires a PR + a CLAUDE.md trace. Code changes that violate the contract
> fail CI (eval-by-design gate, Décision #22).

Created by HOS-204 (EVAL-0). Consumed by EVAL-1…EVAL-5.

---

## Per-layer failure definitions

| Layer | "Bad output" definition | Unacceptable threshold |
|---|---|---|
| **Forecast (Prophet)** | MAPE deviates from baseline by > 3pp on any category, or > 22% rolling 7-day average | Rolling 7d > 22% triggers alert; > 25% triggers auto-disable of cold-start meta-learner (per ADR-0005) |
| **LLM reasoning** | Factually incorrect explanation (attributes spike to wrong cause, references non-existent event, invents numbers) | > 5% of recs flagged in human spot-check (Phase 4 — EVAL-6) |
| **Inbound parser (Haiku)** | Misclassifies manager intent (accepted / rejected / modified) | accuracy < 90% on stratified eval set; precision per intent < 0.85 |
| **Memory recall** | No relevant hit returned when one exists in same hotel context; or returns hit with mean similarity below threshold | precision@5 < 0.7 on annotated eval set (full eval = Phase 4 EVAL-8; Phase 3 = smoke only) |
| **Cold-start meta-learner** | Day-1 MAPE > 25% on LOO backtest | Gate already in ADR-0005 — runtime auto-disable |
| **Latency** | Endpoint p95 > documented SLO | see SLO table below |
| **Distribution shift** | Input feature distribution drifts > 2σ vs training, or KS-test p-value < 0.01 on key features | Drift detected → WhatsApp ops alert + auto-disable cold-start meta-learner |

---

## Latency SLOs (p95) — ADR-0007 §5.e / brief EVAL-5

| Endpoint | p95 target |
|---|---|
| `POST /api/v1/predictions/today` | < 8 s |
| `POST /api/v1/recommendations/today` | < 12 s |
| Receipt generation (background job) | < 15 s |
| Inbound parser (Haiku call) | < 2 s |
| `/mcp/v0/*` tool calls | < 5 s |

Alert if p95 breached for > 5 consecutive minutes.

---

## Distribution-shift algorithm by feature — ADR-0007 §D5

| Feature(s) | Algorithm | Why |
|---|---|---|
| `covers_dinner`, `covers_breakfast`, `covers_lunch`, `occupancy` | KS-test (`scipy.stats.ks_2samp`) | Sensitive to tail shifts, robust low-N |
| `temperature`, `precipitation`, `weather_score` | Wasserstein distance | Penalises smooth shifts better than KS |
| `event_count`, `event_type` (one-hot), `manager_reply_lang` | PSI (Population Stability Index) | Standard for sparse/categorical |

**Severity cascade:**

| Severity | Trigger | Action |
|---|---|---|
| **WARN** | KS p < 0.05 · Wasserstein > 1σ baseline · PSI 0.1–0.2 | Log + WhatsApp ops daily digest |
| **FAIL** | KS p < 0.01 · Wasserstein > 2σ · PSI > 0.2 | WhatsApp ops immediate + `agent_action_log.status="drift_alert"` + auto-disable cold-start meta-learner |

Baseline = frozen training-set snapshot (`eval/distribution_snapshots/<feature>.json`, captured at EVAL-3). Reset only by explicit PR tagged `BASELINE_RESET` + CLAUDE.md entry.

---

## Coverage thresholds (eval gate — ADR-0007 §D3)

Coverage = % of taxonomy categories with ≥ 1 PASS scenario in the current run.

| Coverage | Result |
|---|---|
| ≥ 80% | PASS |
| 60–80% | WARN (exit 3, PR red flag, non-blocking) |
| < 60% | FAIL (exit 1, blocking) |

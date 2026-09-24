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
| **LLM reasoning** | Factually incorrect explanation (attributes spike to wrong cause, references non-existent event, invents numbers) | > 5% of recs flagged in human spot-check (Phase 4 — EVAL-6). **Judge calibration required first**: Cohen's kappa ≥ 0.8 vs human verdict on `eval/judge_calibration_set.jsonl`, 2 consecutive runs — see ADR-0007 §14 |
| **Inbound parser (Haiku)** | The **decision** the production path lands on for a free-text reply (written, or proposed for confirmation) differs from the manager's intent; or a decision is **written without confirmation** when the reply has two readings. "No decision" and a model error / schema failure are failures, never guesses (ADR-0007 §15, §16) | Graded on replies that **reach the model** only (keyword / bare-ack / covers replies are deterministic code, unit-tested and reported apart): decision accuracy < 90% (dev + heldout); precision per decision < 0.85 (a decision never landed on = breach); precision of **auto-written** decisions (confidence ≥ 0.85) < 0.85 per decision; **any** auto-write on a `parser_confirmation` case. **Graded only by the real backend** (`eval-parser-real.yml`); the fake backend in the PR gate is a plumbing check. **Not yet measured** as of 24/09/2026 |
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

## Feedback→training input bounds — HOS-250 (Epic 12 G-3)

Guards the manager-reported `actual_covers` at the ingestion chokepoint
(`receipts.persist_actual_covers`) before it reaches the training path. All
config-driven (`backend/app/core/config.py`) — no redeploy. Enforced via
`backend/app/services/feedback_guard.py`.

| Bound | Rule | Env var | Default |
|---|---|---|---|
| Lower | reject if `actual_covers < min` (catches negative / zero) | `FEEDBACK_COVERS_MIN` | `1` |
| Capacity ceiling | reject if `> total_seats × (turns_b+turns_l+turns_d) × mult` (per property) | `FEEDBACK_COVERS_CAPACITY_MULTIPLIER` | `1.5` |
| Historical sanity | **flag** (never reject) if `> historical_max × mult` while within capacity | `FEEDBACK_HISTORICAL_MULTIPLIER` | `3.0` |

| Knob | Env var | Default | Notes |
|---|---|---|---|
| Policy | `FEEDBACK_BOUNDS_POLICY` | `reject` | `reject` = value not ingested (hard pre-pilot guard); `flag` = ingested but tagged `implausible_flag` + source `manager_feedback_flagged` for downstream exclusion |

**On any breach**: a typed trip row is written to `agent_action_log`
(`status="tool_error"`, `error_code="implausible_feedback"`,
`tool_name="feedback.ingestion"`) and an ops alert is raised — `dispatch_error`
(reject) or `dispatch_anomaly` (flag). Never a silent ingestion. No migration
(capacity derived from existing `restaurant_profiles.total_seats` + turns).

**Degrade-open**: if the property/history lookup fails, the value is treated as
plausible (the guard never blocks legitimate feedback on an infra hiccup).

---

## Agent error-rate / LLM-timeout alerting — HOS-249 (Epic 12 G-2)

Turns `agent_action_log` from a passive register into an alarm. A rolling-window
monitor (`backend/app/workers/error_rate_monitor.py`, registered on the shared
scheduler) evaluates the last `ERROR_RATE_WINDOW_MIN` minutes on each poll and
trips an ops alert (Linear, via `ops_dispatcher.dispatch_anomaly`) on breach.
All config-driven (`backend/app/core/config.py`) — no redeploy.

| Signal | Rule | Env var | Default |
|---|---|---|---|
| Non-ok rate (AC1) | `count(status != "ok") / total` over window, **only when** `total ≥ min samples` | `ERROR_RATE_NONOK_THRESHOLD` | `0.20` |
| — min samples gate | rate check skipped below this many rows (low-volume false-alarm guard) | `ERROR_RATE_MIN_SAMPLES` | `20` |
| Tool failures (AC2) | absolute count of `status="tool_error"` over window | `ERROR_RATE_TOOL_FAILURE_THRESHOLD` | `10` |
| LLM timeouts (AC2) | absolute count of rows whose `error_code` matches the timeout substring | `ERROR_RATE_LLM_TIMEOUT_THRESHOLD` | `5` |
| — timeout match | case-insensitive substring identifying a timeout `error_code` | `ERROR_RATE_TIMEOUT_ERROR_SUBSTR` | `timeout` |

| Knob | Env var | Default | Notes |
|---|---|---|---|
| Poll interval | `ERROR_RATE_MONITOR_INTERVAL_MIN` | `15` | How often the window is evaluated |
| Window width | `ERROR_RATE_WINDOW_MIN` | `60` | Rolling window evaluated each poll |
| Alert debounce | `ERROR_RATE_ALERT_COOLDOWN_MIN` | `60` | Suppresses repeat alerts per metric (AC3) |

**On any breach**: a typed trip row is written to `agent_action_log`
(`status="tool_error"`, `error_code` ∈ {`error_rate_spike`, `tool_failure_spike`,
`llm_timeout_spike`}, `tool_name="monitor.error_rate"`, `hotel_id="_system"`) and a
`dispatch_anomaly` ops alert is raised (AC4 / NFR2). The monitor excludes its own
trip rows from the window so an alert can't feed back into the next evaluation.
The count checks fire regardless of volume (an absolute failure spike matters even
at low traffic); only the *rate* check is gated on min samples.

---

## Confidence-tiered forecast guardrail at dispatch — HOS-251 (Epic 12 G-4)

Generalizes the ADR-0005 cold-start auto-disable (degrade, don't extinguish) to
the dispatch path. **Never blanks a recommendation** (Décision #6 HITL-always) —
it produces a confidence *indicator*, not a switch. Enforced via
`backend/app/services/forecast_guardrail.py`, applied in
`aetherix_engine.get_forecast`. All config-driven (`backend/app/core/config.py`).

| Tier | Trigger | Behaviour | Env var | Default |
|---|---|---|---|---|
| Nominal | `confidence ≥ WARN` and `live_mape ≤ MAPE_CATASTROPHE` | recommendation dispatched as-is | — | — |
| **Tier 1** | `confidence < WARN` | dispatched **+ confidence caveat** (AgentAbstention flag `confidence_below_threshold`); covers unchanged | `FORECAST_CONFIDENCE_WARN` | `0.6` |
| **Tier 2** | `confidence < CATASTROPHE` **or** `live_mape > MAPE_CATASTROPHE` | **baseline fallback** (tagged), staffing recomputed on baseline; flag `cold_start_meta_learner_drift` | `FORECAST_CONFIDENCE_CATASTROPHE` / `FORECAST_MAPE_CATASTROPHE` | `0.4` / `35` |

Baseline source (Tier 2): `context["baseline_covers"]` → `context["recent_avg_covers"]`
→ `FORECAST_BASELINE_DEFAULT_COVERS` (default `0` = disabled) → degrade to the
Prophet point estimate (still delivered + tagged, never silent). The catastrophe
confidence floor sits below Prophet's `0.5` confidence floor by default, so Tier 2
is driven mainly by the live-MAPE breach; a richer trailing baseline + live-MAPE
feed are a follow-up once EVAL-3/5 latency/MAPE telemetry is wired in.

**On any non-nominal verdict**: a typed row is written to `agent_action_log`
(`status="tool_error"`, `error_code`/`abstention_reason` = the tier reason,
`abstention_layer="forecast"`, `tool_name="forecast.guardrail"`) so it feeds the
Epic 11 abstention metrics (NFR2). Tier 2 additionally raises a `dispatch_anomaly`
ops alert; Tier 1 is a routine manager caveat (no ops noise).

---

## Output sanity bounds on recommendations — HOS-252 (Epic 12 G-5)

Centralized guard ensuring a recommendation is *physically sane* before dispatch
(no "30 servers for 12 covers"). Enforced via
`backend/app/services/output_sanity.py`, applied in
`staffing_service.calculate_recommendation`. Out of bounds → clamp/flag + route
to human, never a silent dispatch (AC2). Shares the property-capacity ceiling
with G-3 (`feedback_guard.capacity_ceiling`). Config-driven.

| Bound | Rule | Env var | Default |
|---|---|---|---|
| Capacity | covers above `total_seats × turns × mult` are **clamped** to the ceiling + routed to human | `FEEDBACK_COVERS_CAPACITY_MULTIPLIER` (shared with G-3) | `1.5` |
| Headcount delta | headcount above `baseline × mult` → **flag** + route to human | `OUTPUT_SANITY_MAX_HEADCOUNT_DELTA_MULT` | `3.0` |
| Budget (absorbed) | projected daily labor cost above the daily budget → **flag** | `StaffingConfig.labor_budget_gbp_per_day` | `1200` |

The former ad-hoc budget alert in `staffing_service` is **absorbed** into this
guard (AC5 — single source, no double logic). On any breach a typed trip row is
written per flag to `agent_action_log` (`status="tool_error"`, `error_code` ∈
{`output_over_capacity`, `output_absurd_delta`, `labor_budget_exceeded`},
`tool_name="output.sanity"`) and a `dispatch_anomaly` ops alert is raised (AC3 /
NFR2). Capacity is only enforced when the property's seats are known
(degrade-open, same as G-3).

---

## Coverage thresholds (eval gate — ADR-0007 §D3)

Coverage = % of taxonomy categories with ≥ 1 PASS scenario in the current run.

| Coverage | Result |
|---|---|
| ≥ 80% | PASS |
| 60–80% | WARN (exit 3, PR red flag, non-blocking) |
| < 60% | FAIL (exit 1, blocking) |

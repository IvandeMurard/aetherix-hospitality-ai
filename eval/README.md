# Aetherix Eval-by-Design

Evaluation-as-a-contract for the AI/ML layers of Aetherix.
Foundation laid by **EVAL-0 (HOS-204)**; runners land in EVAL-1…EVAL-5.

> **Reference:** [ADR-0007](../docs/adr/0007-evaluation-by-design.md) ·
> CLAUDE.md Décision #22 · PM brief `docs/planning/evaluation-by-design.md`.

---

## The contract

**Any change that touches the model, the LLM, memory, providers, or prompts does
not merge without updating `eval/golden_dataset.jsonl` and a green eval run.**

This mirrors the schema-drift gate (Décision #16). The set of paths that trigger
it is defined in ADR-0007 §D2.a (`EVAL_TRIGGER_PATHS`) — forecasting/parser/
recommendation/memory services, `app/providers/`, `backend/app/prompts/`, and the
eval dataset + thresholds themselves.

Failure thresholds (the per-layer "bad output" definitions) live in
[`FAILURE_THRESHOLDS.md`](./FAILURE_THRESHOLDS.md). Changing a threshold is an
explicit decision: PR + CLAUDE.md trace.

### The gate (`scripts/ci/check_eval_coverage.py`) — HOS-216

The gate diffs the PR against `origin/main`, maps touched trigger paths to eval
layers (ADR §D2.b), skips on an `eval-exempt` label or a sha256 cache hit
(`eval/baselines/.cache_keys.json`), invokes `scripts/eval/run_all.py` for the
detected layers, and posts a sticky PR comment via `.github/workflows/eval-gate.yml`.

Exit codes (ADR §D2.f): `0` PASS · `1` FAIL (regression > 3pp **or** category
coverage < 60%) · `2` ERROR · `3` WARN (coverage 60–80%, or touched-but-not-
evaluated). Run it locally with `python scripts/ci/check_eval_coverage.py`.

**Rollout WARN → blocking (AC5).** The gate shipped non-blocking and was flipped
to blocking on 2026-07-04 (Décision #29): `eval-gate.yml` sets
`EVAL_GATE_BLOCKING: "true"`, so FAIL (1) and ERROR (2) block the merge; WARN (3)
does not. Emergency rollback = `"false"`.

### `eval-exempt` label (override)

A PR may carry the **`eval-exempt`** label to skip the gate. Authorised
exemptions (SM rejects abuse — human review, not an auto-check):

| Label | Scope |
|---|---|
| `refactor` | Pure rename / move, no model-logic change |
| `doc` | `*.md`, `docs/**` only |
| `infra` | `.github/`, `fly.toml`, `Dockerfile`, deploy scripts |
| `ci-only` | `scripts/ci/*` (except `check_eval_coverage.py` itself → full run) |
| `test-only` | `backend/tests/` only |

### Offline model-quality (must-eval) vs runtime guardrails (legitimately exempt)

The recurring case-by-case arbitration (HOS-274) is the **eval-by-design frontier**:
which code is *offline model quality* (Bras A — must carry eval coverage) versus
*runtime/online guardrails* (Bras B, Epic 12 / HOS-212 — legitimately `eval-exempt`).
The taxonomy is settled by ADR-0007 §13 (three-arm addendum) and Décision #22:

| Arm | What it measures | Lives in | Gate behaviour |
|---|---|---|---|
| **A — offline / dev-time** | Does the model still produce good outputs? (golden-dataset non-regression) | `EVAL_TRIGGER_PATHS` (forecast/parser/recommendation/memory services, `app/providers/`, `backend/prompts/`, the dataset + thresholds) | **Must-eval** — gate runs, no exemption without an authorised label |
| **B — runtime / online** | Is the *live* system behaving? (heartbeats, dead-man's switch, error-rate / latency monitors, dispatchers) | `app/services/heartbeat*`, dispatchers, `*_monitor.py`, scheduler/worker plumbing (Epic 12 / HOS-212) | **Legitimately `eval-exempt` (`infra`)** — no golden-dataset scenario applies; correctness is asserted by unit/integration tests, not MAPE |
| **C — outcome / downstream** | Was the output actioned and did it create value? (Trust-KPI) | Epic 10 instrumentation (`recommendation_acceptance_rate`, ablation) | Not yet on the offline substrate — HOS-275 (Phase 4) |

**Rule of thumb:** if a change can move a `golden_dataset.jsonl` metric, it is Bras A →
must-eval. If it only changes *when/whether* a job fires or an alert is sent, it is
Bras B → `eval-exempt` with the `infra` justification. Runtime guardrails do **not**
get a golden-dataset scenario; they are covered by their own tests + `HEARTBEAT_THRESHOLDS.md`.

---

## Dataset: `golden_dataset.jsonl`

One JSONL file, one scenario per line, poly-schema discriminated by `category`
(ADR-0007 §D1). Single file = trivial grep/diff in PR review + native git
versioning.

**Top-level fields (every line):**

| Field | Notes |
|---|---|
| `schema_version` | semver; bump = separate PR + migration script |
| `id` | kebab-case, unique, prefixed by layer (`fcst-`, `parser-`, `reco-`, `recpt-`, `drift-`, `lat-`) |
| `category` | one of the 11-category taxonomy (below) |
| `layer` | `forecast` \| `recommendation` \| `receipt` \| `parser` \| `drift` \| `latency` |
| `created_at` | ISO date added to the dataset |
| `author` | git user short |
| `input` | payload — shape depends on category/layer |
| `expected` | ground truth or accept-band |
| `failure_trigger` | human-readable condition that makes this scenario FAIL |
| `notes` | rationale / provenance |

### Category taxonomy (11 — ADR-0007 §D1)

| Code | Min (full) | Phase-3 EVAL-0 min |
|---|---|---|
| `normal_day` | 15 | 10 |
| `event_day` | 8 | 6 |
| `weather_anomaly` | 5 | 3 |
| `ota_cancellation_wave` | 3 | — (Sprint N+2) |
| `weekend_weekday_split` | 5 | — |
| `service_stratification` | 5 | — |
| `closure_day` | 3 | — |
| `holiday_eve` | 4 | — |
| `breakfast_dinner_mix_shift` | 3 | — |
| `ood_edge` | 5 | 3 (incl. abstention cases) |
| `parser_intent` | 15 | 12 |
| `parser_confirmation` | — (Décision #38) | — |
| `pos_anomaly` | 0 (forward-compat ADR-0006) | 0 |

**EVAL-0 ships the AC0.1 "unblocking minimum"** (6 categories ≥ 40 scenarios) —
enough to unblock EVAL-1 / EVAL-2 / EVAL-4. Full 71-scenario coverage (AC0.2) is
a Sprint N+2 milestone (blocks EVAL-3 / EVAL-5 only).

### Provenance of `expected` values

- **forecast** scenarios are grounded in **real** values from
  `backend/data/demo/prophet_training.json` (the synthetic 2025 training series:
  `ds`, `y` covers, `weather_score`, `event_impact`, `occupancy`). `expected.covers`
  is the actual `y` for that date — not invented. (The model predicts aggregate
  covers `y`; the `covers_dinner`/`covers_breakfast` split shown in the ADR
  example is a Phase-4 refinement once per-service data exists.)
- **parser_intent** scenarios are labelled with the **manager's decision**
  (`expected.decision`: accepted / rejected / modified; `expected.intent` kept as
  an alias) and with `expected.path`, the step that should decide it (`keyword`,
  `keyword_ambiguous`, `bare_ack`, `correction_pattern`, `model` — ADR-0007 §16).
  Only `model` cases grade the model; the others are a deterministic code check
  that fails if routing drifts. **parser_confirmation** cases (10, heldout) are
  two-reading replies: any decision written without asking the manager is a
  breach. The original 17 parser_intent cases are the `dev` split
  (the fake heuristic was written against them); the 30 `"split": "heldout"` cases
  are adversarial and were never used to tune anything. The PR gate runs the
  **fake backend — a plumbing check, not a quality measure**. Model quality comes
  only from the opt-in real run (`.github/workflows/eval-parser-real.yml`) and is
  **not yet measured**.
- **recommendation / receipt abstention** scenarios encode the `AgentAbstention`
  contract (ADR-0007 §D6) — the expected `abstention_reason` is the contract,
  implemented in EVAL-2 (HOS-206).

---

## Validate the dataset

```bash
python scripts/eval/validate_dataset.py
```

Checks: JSONL parses, schema fields present, `id` unique + kebab-case, `category`
in taxonomy, `layer` valid, and per-category minimum counts for the EVAL-0
milestone. Exit 0 = valid. Wired into CI (`eval-dataset` job).

---

## Parser on real LLMs — provider matrix (HOS-337, Décision #35 D3)

The PR gate scores the parser with the deterministic `FakeIntentClassifier`: it
evaluates no LLM. The real-model run is separate, manual, and never blocks a merge.

```bash
EVAL_PARSER_BACKEND=real EVAL_PARSER_TARGET=claude:claude-haiku-4-5-20251001 \
ANTHROPIC_API_KEY=... uv run --project backend python -m scripts.eval.run_all --layers parser \
  --json-out out/claude.json --md-out out/claude.md
python -m scripts.eval.compare_parser_targets out/claude.json out/gemini.json
```

Or run the **Eval — parser provider matrix** workflow (`workflow_dispatch`, needs
the `ANTHROPIC_API_KEY` and `GEMINI_API_KEY` secrets).

- **Target = exact model id, never a tier**, and the provider is called directly,
  never through the fallback: a failover mid-run would mix two models in one score.
- **Baselines** live in `eval/baselines/parser/<target>__<dataset version>.json`.
  The dataset version is a content hash of the scored cases (stand-in until HOS-339).
- **How to read it.** The run grades the production reply path (ADR-0007 §15-§16).
  Replies settled before the model (exact keywords, bare acknowledgement, covers
  pattern) are reported apart as the deterministic block and score the same on every
  provider; only the replies that reach the model are graded, so **decision accuracy
  on the model-graded cases** is the number comparable across providers. The model
  answers in a validated schema and there is no heuristic behind it: an API error or
  an answer that fails the schema is a miss, and is also reported as the **model
  failure rate**, where a formatting gap between providers shows up. (Merged
  25/09/2026: HOS-337's pinned targets on the §15-§16 production path.)

## Roadmap (ADR-0007 §8)

| Story | Adds |
|---|---|
| **EVAL-0** (this) | dataset + thresholds + validator + prompt extraction |
| EVAL-1 | `scripts/eval/eval_forecast.py` stratified MAPE + CI regression gate |
| EVAL-2 | `AgentAbstention` contract + WhatsApp variants + telemetry |
| EVAL-3 | distribution-shift detector + cold-start auto-disable hook |
| EVAL-4 | Parser eval on the production path (real model, opt-in workflow) + fake plumbing check — corrected 24/09/2026, ADR-0007 §15 |
| EVAL-5 | latency SLO bench + dashboard MV |

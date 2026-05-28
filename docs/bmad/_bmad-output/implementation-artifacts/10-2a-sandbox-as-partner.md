# Story 10.2a (P3-2a): Sandbox-as-partner — pipeline E2E + MAPE gate + assets démo

Status: ready-for-dev
Linear: [HOS-190](https://linear.app/hospitalityagent/issue/HOS-190) (Urgent, 3 pts)
Epic: HOS-174 (Phase 3) — also closes [HOS-145](https://linear.app/hospitalityagent/issue/HOS-145)
Blocks: [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176) (real-pilot deploy)
Branch: `ivandemurard/hos-190-story-102a-p3-2a-sandbox-as-partner-pipeline-e2e-mape-gate`

> **GATE NON-NÉGOCIABLE (Décision #14) :** AC3 MAPE J+1 ≤ 22%. Si > 22% → STOP. Ouvrir ticket pivot AVANT toute autre AC. Ne pas livrer AC4/AC5/AC6.
>
> **Prérequis :** [HOS-177](https://linear.app/hospitalityagent/issue/HOS-177) Done (Trust-KPI worker — sinon AC6 impossible).

---

## Story

As the Aetherix team,
I want to run the full pipeline on the Apaleo sandbox with synthetic 365-day data,
so that I can validate J+1 MAPE, prove the E2E pipeline, and produce demo assets that strengthen the design-partner recruitment kit ([HOS-175](https://linear.app/hospitalityagent/issue/HOS-175)).

---

## Acceptance Criteria (verbatim from Linear)

- [ ] **AC1 (HOS-145 absorbé)** : `GET /pms/mcp/probe` with real Apaleo sandbox credentials → `status: ok`, `tools_available > 0`, `mcp_latency_ms < 500`. Result documented in `docs/context/demo-apaleo.md`.
- [ ] **AC2** : 365-day synthetic dataset generated via `scripts/ops/generate_demo_data.py` (DEMO_MODE=true) and loaded into `backend/data/demo/prophet_training.json`.
- [ ] **AC3** : Prophet training pipeline executed on sandbox data (`POST /api/v1/predictions/train`) → MAPE J+1 computed and documented in `docs/context/mape-benchmark.md`. **Gate: if MAPE > 22% → pivot ticket before continuing (Decision #14)**.
- [ ] **AC4** : Daily Receipt delivered to Ivan's WhatsApp test number — Phase 2 format, including Trust-KPI line. Screenshot archived in `docs/demos/sandbox-receipt-screenshot.png`.
- [ ] **AC5** : 60-second screen recording of the full pipeline (probe → forecast → WhatsApp Receipt) archived in `docs/demos/` — usable as demo asset in [HOS-175](https://linear.app/hospitalityagent/issue/HOS-175).
- [ ] **AC6** : Trust-KPI worker ([HOS-177](https://linear.app/hospitalityagent/issue/HOS-177)) operational on `tenant_sandbox` — runs on simulated outcomes (5 accept / 2 reject synthétiques), `recommendation_acceptance_daily` populated.

---

## Tasks / Subtasks (sequenced)

### Phase A — Sandbox connectivity (AC1)

- [ ] **T1 — Apaleo sandbox credentials**
  - [ ] Set `APALEO_CLIENT_ID` + `APALEO_CLIENT_SECRET` in `backend/.env` (sandbox-issued, NOT prod)
  - [ ] Set `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` (per Décision §"Apaleo MCP direct" resolved 2026-03-31)
  - [ ] Verify `git diff` shows no `.env` content — secrets MUST NOT be committed (HOS-145 AC7)
- [ ] **T2 — Create `scripts/validate_apaleo_sandbox.py`** *(referenced by HOS-145 AC2, currently missing)*
  - [ ] Reads env vars, performs OAuth2 handshake (<2000ms), calls backend `GET /pms/mcp/probe` (existing endpoint at [backend/app/api/routes/pms.py:39](backend/app/api/routes/pms.py:39)), then calls `list_tools()` and one `APALEO_GET_OCCUPANCY_METRICS` tool
  - [ ] Exit codes per HOS-145 AC: `1=creds, 2=OAuth2, 3=probe, 4=MCP list_tools, 5=tool_call`
  - [ ] Prints structured JSON for archiving
- [ ] **T3 — Run probe + document**
  - [ ] `cd backend && uvicorn app.main:app --reload`
  - [ ] `python scripts/validate_apaleo_sandbox.py` → exit 0
  - [ ] Append a checked-off result section to [docs/context/demo-apaleo.md](docs/context/demo-apaleo.md) with: timestamp, `tools_available`, `mcp_latency_ms`, `OAuth2 token acquisition ms`. Truncate any secret-leaking field.

### Phase B — Synthetic dataset (AC2)

- [ ] **T4 — Regenerate demo dataset**
  - [ ] `python scripts/ops/generate_demo_data.py` (DEMO_DATA_SEED=42 default)
  - [ ] Verify output path. **NB:** the script header says `demo_data/prophet_training.json` (CWD-relative), but the AC requires `backend/data/demo/prophet_training.json`. Reconcile: run from `backend/` OR add a `--output` arg. Choose the simpler path (run from `backend/`) and document the command used.
  - [ ] Sanity-check: 365 rows, `ds` strictly increasing, `y` range plausible (~30–120 covers/day for a 78-cover restaurant with walk-ins)

### Phase C — Train + MAPE gate (AC3) — 🚦 GO/NO-GO

- [ ] **T5 — Issue an MCP bearer token with `predict` scope** *(prereq for `/predictions/train`)*
  - [ ] Use existing token issuance path. Grep `mcp_api_tokens` table + creation script under `scripts/` if any. If absent, mint a row directly in dev DB.
- [ ] **T6 — Run training**
  - [ ] `curl -X POST .../api/v1/predictions/train -H "Authorization: Bearer <token>" -d '{"data_source": "synthetic", "include_weather": true, "include_events": true, "include_occupancy": true}'`
  - [ ] Capture response JSON: `mape_training`, `records_processed`, `duration_ms`, `training_id`
- [ ] **T7 — Compute J+1 MAPE on held-out window**
  - [ ] `mape_training` from the endpoint is **in-sample** — NOT a valid gate metric on its own
  - [ ] Implement a quick holdout: re-train on days 1–335, predict days 336–365, compute MAPE of `predicted_covers` vs `y`. Add this as a one-shot script `scripts/ops/measure_mape_j1.py` OR run inline in a Python REPL and paste the numbers.
  - [ ] Persist both metrics (`mape_training` and `mape_j1_holdout`) — the gate is on `mape_j1_holdout`.
- [ ] **T8 — 🚦 GATE: MAPE ≤ 22%?**
  - [ ] **YES** → create `docs/context/mape-benchmark.md` with: synthetic seed, training duration, in-sample MAPE, holdout J+1 MAPE, feature toggles used, decision = PASS. Proceed to Phase D.
  - [ ] **NO** → STOP. Open Linear ticket `Pivot — MAPE gate fail (HOS-190 AC3)` under Epic HOS-174, mark HOS-190 blocked, link the metric file, notify SM (Bob). Do not work on AC4/AC5/AC6.

### Phase D — Receipt asset (AC4)

- [ ] **T9 — Trigger Daily Receipt to Ivan's WhatsApp**
  - [ ] Configure `notification_email` and `phone_number` on the sandbox tenant's restaurant profile (set `tenant_id='tenant_sandbox'` consistently)
  - [ ] Trigger via the existing receipts dispatcher worker (see [backend/app/workers/receipts_dispatcher.py](backend/app/workers/receipts_dispatcher.py)) — either wait for the cron or expose a manual `POST /receipts/dispatch?hotel_id=...` test hook if one exists
  - [ ] Confirm message includes the Trust-KPI line (depends on HOS-177 being done — see AC6 prerequisite below)
- [ ] **T10 — Capture screenshot**
  - [ ] `docs/demos/sandbox-receipt-screenshot.png` — crop tightly to the WhatsApp message, redact any phone number visible in the chat header

### Phase E — Recording (AC5)

- [ ] **T11 — 60-second screen recording**
  - [ ] Cover: terminal showing `validate_apaleo_sandbox.py` exit 0 → curl to `/predictions/train` returning MAPE → WhatsApp notification arriving on Ivan's phone
  - [ ] Save as `docs/demos/sandbox-pipeline-60s.mp4` (or `.mov` — keep one consistent format). Compress < 25 MB if possible.
  - [ ] Add a one-line README in `docs/demos/` listing the assets and what each shows

### Phase F — Trust-KPI on sandbox (AC6)

- [ ] **T12 — Seed simulated outcomes**
  - [ ] Insert 7 `operational_memory` rows for `hotel_id='tenant_sandbox'`, `memory_type='feedback'`, distributed: 5 `manager_feedback='followed'`, 2 `manager_feedback='rejected'`. Use yesterday's date so the daily worker picks them up. *(Naming mapping: public outcome `accepted/rejected/modified` → internal `followed/rejected/neutral` per [backend/app/mcp_server.py:259](backend/app/mcp_server.py:259) — confirmed in HOS-177 spec reconciliation.)*
  - [ ] Insert 7 matching `agent_action_log` rows with `tool_name='get_recommendations_with_memory_context'`, `status='ok'`, same `request_id` as each operational_memory row
- [ ] **T13 — Trigger the worker**
  - [ ] Either wait for the 02:30 UTC cron or call the worker function directly in a Python REPL (`from app.workers.kpi_aggregator import run_kpi_aggregator; await run_kpi_aggregator()`)
  - [ ] Verify `kpi_daily` has a row for `tenant_id='tenant_sandbox'`, `kpi_name='recommendation_acceptance_rate'`, `value ≈ 0.714` (5/7)
  - [ ] Verify the materialised view `recommendation_acceptance_daily` is populated

### Phase G — Close out

- [ ] **T14 — Move [HOS-145](https://linear.app/hospitalityagent/issue/HOS-145) to Done** (absorbed by AC1, per the ticket description)
- [ ] **T15 — Commit assets + scripts on the branch, open PR**
  - [ ] `.gitignore` check: confirm `backend/.env` is ignored. The `docs/demos/` binaries are fine to commit (intentional, small).
  - [ ] CI green (schema drift gate must pass — Décision #16)
  - [ ] PR to `main`. Linear HOS-190 → Done + PR URL.

---

## Dev Notes

### Architecture constraints

- **Hosting:** Sandbox runs against staging Fly.io `aetherix-backend.fly.dev` (Décision #17). Local dev OK for T1–T8 but T9–T13 should be validated on staging once green locally — the WhatsApp Twilio side is configured on staging secrets.
- **DEMO_MODE flag:** Already wired through `app.core.config` and `app.core.demo_events`. Verify the training endpoint honours it when `data_source=synthetic` (it should — read [predictions.py:248](backend/app/api/routes/predictions.py:248)).
- **MCP authentication:** `/predictions/train` requires a bearer token with the `predict` scope ([predictions.py:257](backend/app/api/routes/predictions.py:257)). hotel_id is bound to the token.
- **Schema drift gate (Décision #16):** No new tables here; HOS-177's `kpi_daily` migration is what gets exercised. If `kpi_aggregator` worker is registered in `main.py` lifespan, ensure staging restart picks it up.
- **Secrets hygiene:** Apaleo sandbox creds in `.env` only. Never in scripts, never in `docs/`. Validate with `git diff` before each commit (HOS-145 AC7).
- **ID convention:** use `tenant_sandbox` consistently as the `hotel_id`/`tenant_id` for this story's data. Avoid mixing with `hotel_p2` or other test IDs already in fixtures.

### What "MAPE J+1" actually means

The Linear ticket says "MAPE J+1". The training endpoint returns in-sample MAPE, which is **always optimistic** (it measured fit, not forecast skill). The honest gate metric is **out-of-sample MAPE on the last 30 days of the synthetic dataset**. This story makes that explicit in T7 — do not skip it. A 22% gate on in-sample MAPE is not meaningful.

### References

- [Source: CLAUDE.md Décision #11] — demo data hybrid strategy
- [Source: CLAUDE.md Décision #13] — Prophet pipeline gap closure (this story IS the orchestration debt repayment)
- [Source: CLAUDE.md Décision #14] — Phase 0 DoD amended; MAPE gate non-negotiable
- [Source: CLAUDE.md Décision #17] — Fly.io staging URL + secrets via flyctl
- [Source: docs/context/demo-apaleo.md] — full demo PRD (Hotel Kleber scenario)
- [Source: backend/app/api/routes/pms.py:39] — `/pms/mcp/probe` endpoint
- [Source: backend/app/api/routes/predictions.py:248] — `/predictions/train` endpoint signature
- [Source: scripts/ops/generate_demo_data.py] — synthetic dataset generator (output path discrepancy with AC2 — see T4)

---

## Open questions for dev (defer if not blocking)

1. **Output-path discrepancy** — `generate_demo_data.py` writes `demo_data/prophet_training.json` (CWD-relative); AC2 says `backend/data/demo/prophet_training.json`. Resolved in T4 (run from `backend/` and confirm) — but a one-line script edit to take `--output` would be cleaner if time permits.
2. **Token minting for `/predictions/train`** — confirm there's a CLI or script to mint a scoped token. If not, T5 documents the manual SQL insert.
3. **MAPE J+1 measurement script** — is there an existing eval harness under `backend/app/services/forecasting/` or `scripts/`? If yes, reuse instead of writing a new one.
4. **HOS-145 closure** — the existing AC list there is finer-grained than HOS-190 AC1. Confirm with SM that ticking AC1 + appending to `demo-apaleo.md` is enough to mark HOS-145 Done.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.6 (Dev session, 2026-05-21)

### Debug Log References
- Bash and PowerShell both unavailable during the session due to a harness-level
  `EEXIST mkdir 'C:\\Users\\ivand\\.claude\\session-env\\...'` error on every
  command invocation. This prevented running the MAPE gate script and the
  validator from within the session.
- All non-shell file operations (Read / Edit / Write / Glob / Grep) worked
  normally — static artifacts could be authored and committed.

### Completion Notes List
Branch created off latest `main` (`59c0315`, includes the merged HOS-177 PR #133).
Prerequisites verified: HOS-177 worker (`backend/app/workers/kpi_aggregator.py`,
`kpi_daily` table, `recommendation_acceptance_daily` MV) is on main.

**Shipped in this session:**
- `scripts/ops/measure_mape_j1.py` — holdout MAPE J+1 script (T7, the actual
  gate metric per the story pack's distinction between in-sample and
  out-of-sample MAPE). Self-contained — does not depend on the FastAPI
  app, no token minting required.
- `scripts/ops/seed_trust_kpi_sandbox.py` — AC6 fixture seed (5 followed / 2
  rejected `operational_memory` + 7 matching `agent_action_log` rows for
  `tenant_sandbox`, dated yesterday).
- `docs/context/mape-benchmark.md` — gate result template with PENDING markers
  ready to be filled in once the script is run.
- `docs/context/demo-apaleo.md` §6 — AC1 probe result template with PENDING
  markers.
- `docs/demos/README.md` — manifest for the screenshot + recording assets,
  privacy/redaction checklist.
- `docs/planning/hos-190-manual-runbook.md` — exact step-by-step procedure
  for AC1 + AC3 + AC4 + AC5 + AC6 + close-out, intended for Ivan to execute
  once on a working shell with sandbox credentials loaded.

**NOT shipped — blocked on a working shell and/or live credentials:**
- T7 actual run of `measure_mape_j1.py` → AC3 gate decision (PASS/FAIL).
  This is the single critical follow-up; everything downstream gates on it.
- T3 actual probe run + filled-in §6 of `demo-apaleo.md` → AC1.
- T9–T10 Daily Receipt WhatsApp screenshot → AC4.
- T11 60-second screen recording → AC5.
- T12–T13 actual seed + worker execution → AC6 verification.
- T14 closing HOS-145, T15 opening the PR.

`validate_apaleo_sandbox.py` already exists at `scripts/ops/` (from prior
work on HOS-145); the story-pack reference to `scripts/validate_apaleo_sandbox.py`
is a path slip — the canonical location is the one in use.

The `generate_demo_data.py` script writes to `backend/data/demo/prophet_training.json`
via an absolute path constant — no `cd backend` workaround needed. The header
comment in that script is the only thing stale (T4 open question).

### File List
- `scripts/ops/measure_mape_j1.py` *(new)*
- `scripts/ops/seed_trust_kpi_sandbox.py` *(new)*
- `docs/context/mape-benchmark.md` *(new)*
- `docs/context/demo-apaleo.md` *(modified — appended §6)*
- `docs/demos/README.md` *(new)*
- `docs/planning/hos-190-manual-runbook.md` *(new)*
- `docs/bmad/_bmad-output/implementation-artifacts/10-2a-sandbox-as-partner.md` *(modified — Dev Agent Record filled)*

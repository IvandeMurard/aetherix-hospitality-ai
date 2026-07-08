# HOS-190 — Manual runbook for ACs requiring live credentials / devices

> Companion to `tools/bmad/_bmad-output/implementation-artifacts/10-2a-sandbox-as-partner.md`.
> Lists the steps that **cannot** be executed by a headless dev agent — they
> require Apaleo sandbox credentials, a WhatsApp-paired phone, a screen recorder,
> and Fly.io secret access. Once these are executed by Ivan, the artifacts (and
> result blocks in the linked docs) close out HOS-190.

Branch: `ivandemurard/hos-190-story-102a-p3-2a-sandbox-as-partner-pipeline-e2e-mape-gate`

---

## 1. AC3 — MAPE J+1 gate (Décision #14, **non-negotiable**)

**Status from the dev session:** script shipped, measurement not yet run.

```bash
git checkout ivandemurard/hos-190-story-102a-p3-2a-sandbox-as-partner-pipeline-e2e-mape-gate
cd backend
# Regenerate dataset if needed (idempotent under fixed seed)
python ../scripts/ops/generate_demo_data.py
# Run the gate
python ../scripts/ops/measure_mape_j1.py --json-out ../docs/context/mape-benchmark-holdout.json
# Exit 0 = PASS, exit 3 = FAIL (pivot ticket)
```

Then paste the result table into `docs/context/mape-benchmark.md` and commit
both files. **If the script exits 3 — STOP, open a pivot ticket under
HOS-174 before continuing.**

---

## 2. AC1 — Apaleo sandbox probe

**Prereq:** sandbox `APALEO_CLIENT_ID` / `APALEO_CLIENT_SECRET` from Apaleo
console (https://app.apaleo.com / dev portal) — sandbox tenant only.

```bash
# Locally — populate backend/.env (DO NOT commit; .gitignore covers it)
echo "APALEO_CLIENT_ID=..."           >> backend/.env
echo "APALEO_CLIENT_SECRET=..."       >> backend/.env
echo "APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/" >> backend/.env

cd backend && uvicorn app.main:app --reload &
python ../scripts/ops/validate_apaleo_sandbox.py
# Expect exit 0; capture token/probe/MCP latencies
```

Then fill `docs/context/demo-apaleo.md` §6 "Result — run #1" and move
HOS-145 to Done.

**Staging variant (recommended for AC5 recording):** load the same creds as
Fly secrets, then call the staging probe.

```bash
flyctl secrets set APALEO_CLIENT_ID=... APALEO_CLIENT_SECRET=... \
  APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/
# Wait for redeploy (~30s), then:
AETHERIX_BACKEND_URL=https://aetherix-backend.fly.dev \
  python scripts/ops/validate_apaleo_sandbox.py
```

---

## 3. AC4 — Daily Receipt to WhatsApp + screenshot

**Prereq:** Twilio sandbox + Ivan's WhatsApp number paired (`whatsapp:+33...`),
`RestaurantProfile` row for `tenant_id='tenant_sandbox'` with
`notification_email` and `phone_number` configured, and AC6 seed already in
the DB so the Trust-KPI line renders.

Option A — wait for the daily cron (Phase 2 worker, see
`backend/app/workers/receipts_dispatcher.py`).

Option B — manual dispatch via a Python REPL on staging:

```bash
flyctl ssh console -a aetherix-backend
python
>>> import asyncio
>>> from app.workers.receipts_dispatcher import dispatch_daily_receipts
>>> asyncio.run(dispatch_daily_receipts())
```

Capture the resulting WhatsApp message → crop tightly → redact phone numbers
visible in the chat header → save as `docs/demos/sandbox-receipt-screenshot.png`.

---

## 4. AC5 — 60-second screen recording

Recording covers, in this exact order:
1. Terminal — `python ../scripts/ops/validate_apaleo_sandbox.py` → exit 0
2. Terminal — `curl -X POST /api/v1/predictions/train` returning the MAPE
   training response
3. WhatsApp — Daily Receipt notification arriving on Ivan's phone

Save as `docs/demos/sandbox-pipeline-60s.mp4`. Compress under 25 MB if
possible. The `docs/demos/README.md` already lists this file; just drop it in.

---

## 5. AC6 — Trust-KPI worker on sandbox

**Prereq:** HOS-177 (merged on main, confirmed). The seed script is shipped:

```bash
cd backend
# 1. Seed 5 followed + 2 rejected operational_memory rows for yesterday
python ../scripts/ops/seed_trust_kpi_sandbox.py

# 2. Run the worker in-process (or wait for the 02:30 UTC cron)
python -c "import asyncio; from app.workers.kpi_aggregator import run_kpi_aggregation; asyncio.run(run_kpi_aggregation())"

# 3. Verify
psql "$DATABASE_URL" -c "
  SELECT * FROM kpi_daily
   WHERE tenant_id='tenant_sandbox'
     AND kpi_name='recommendation_acceptance_rate';
"
# Expect: value ≈ 0.714, numerator=5, denominator=7
psql "$DATABASE_URL" -c "
  SELECT * FROM recommendation_acceptance_daily
   WHERE hotel_id='tenant_sandbox';
"
# Expect 2 rows: (followed, 5) and (rejected, 2)
```

Cleanup (when retiring): see footer of `scripts/ops/seed_trust_kpi_sandbox.py`.

---

## 6. Close-out

Once AC1–AC6 are green:

1. Commit assets + the populated result tables on the HOS-190 branch.
2. CI green (schema-drift gate — Décision #16).
3. Open PR to `main`. Title: `feat(sandbox): HOS-190 P3-2a — pipeline E2E + MAPE gate (closes HOS-145)`.
4. Move HOS-190 to Done in Linear, post PR URL.
5. Move HOS-145 to Done (absorbed by AC1).

# Runbook — Pre-Pilot (HOS-161)

Operational checklist and runbook for promoting an Aetherix release-candidate
build from the `main` branch to a real hotel design partner. This document is
the gate before opening Phase 3 (multi-hotel pilot).

Audience: PM (Ivan) + on-call operator.
Owner: Dev Agent (Amelia) — updated alongside each Epic 9 story.

---

## 1. Pré-requis

### 1.1 Variables d'environnement

The staging environment must export the following before the smoke test runs.
Anything marked `(secret)` must be sourced from the team password manager — do
not commit to git.

```
# Auth / hardening
AUTH_SECRET=<64-char hex>            # secret, len >= 32
APP_ENV=staging                      # never "production" during smoke
TWILIO_SKIP_SIGNATURE_VALIDATION=false

# Database (Supabase staging project)
DATABASE_URL=postgresql+asyncpg://...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<anon key>

# Providers
ANTHROPIC_API_KEY=sk-ant-...         # secret
MISTRAL_API_KEY=...                  # secret — embeddings 1024d
LLM_BACKEND=claude
EMBEDDING_BACKEND=mistral

# Apaleo sandbox
APALEO_CLIENT_ID=...                 # secret
APALEO_CLIENT_SECRET=...             # secret
APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/

# Twilio sandbox (only required for step 6)
TWILIO_ACCOUNT_SID=AC...             # secret
TWILIO_AUTH_TOKEN=...                # secret
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Redis (Upstash)
REDIS_URL=rediss://...               # secret

# Smoke test driver (see §2)
APP_BASE_URL=https://staging.aetherix.internal
SMOKE_MCP_TOKEN=<bearer with predict + memory_write + memory_read scopes>
SMOKE_HOTEL_ID=demo_hotel
```

Generate a 64-char AUTH_SECRET with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 1.2 Migrations

Apply all pending migrations before booting the staging app — the lifespan
`verify_schema` will refuse to start the server if anything critical is
missing.

```bash
# from repo root
alembic -c backend/alembic.ini upgrade head
```

If `alembic` is not wired (legacy migration era), run:
```bash
python scripts/check_schema_drift.py
```
and resolve any drift before retrying.

### 1.3 Seed data

The MCP API token used by the smoke test must exist in
`mcp_api_tokens` and carry the scopes `predict`, `memory_read`,
`memory_write`. Generate with:

```bash
python scripts/create_user.py --mcp-token \
  --hotel-id demo_hotel \
  --scopes predict,memory_read,memory_write
```

The script prints the raw token once — store it in the team password manager
and export as `SMOKE_MCP_TOKEN`.

Prophet model: ensure `demo_data/prophet_model.json` exists. If not,
trigger a one-shot training run:
```bash
curl -X POST "$APP_BASE_URL/api/v1/predictions/train" \
  -H "Authorization: Bearer $ADMIN_TRAIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"data_source": "synthetic"}'
```

---

## 2. Lancer le smoke test E2E

Run from the repo root with the env vars from §1.1 exported.

```bash
python scripts/smoke_test_e2e.py
```

Optional flags / env:
- `--skip 2,6` or `SMOKE_SKIP_STEPS=2,6` — skip steps that need credentials
  the local environment does not have.
- `--base-url` — override `$APP_BASE_URL`.

### Expected output (happy path)

One JSON line per step plus a final summary. All `status: "ok"` and
`exit_code: 0`:

```
{"step": 1, "name": "boot_validation", "status": "ok", "duration_ms": 412, "details": "workers=['anomaly_scan','dispatch']; schema_drift=clean"}
{"step": 2, "name": "apaleo_mcp_probe", "status": "ok", "duration_ms": 1843, "details": "tools_available=14"}
{"step": 3, "name": "prophet_predict", "status": "ok", "duration_ms": 731, "details": "covers=52 date=2026-05-15"}
{"step": 4, "name": "memory_feedback_roundtrip", "status": "ok", "duration_ms": 1206, "details": "recommendation_id=..."}
{"step": 5, "name": "auth_surface", "status": "ok", "duration_ms": 287, "details": "checked=4"}
{"step": 6, "name": "anomaly_dispatch_pipeline", "status": "ok", "duration_ms": 6512, "details": "anomaly=... dispatched_rows=1"}
{"total": 6, "passed": 6, "failed": 0, "skipped": 0, "exit_code": 0}
```

Exit code is the gate: 0 ⇒ proceed to §6; anything else ⇒ debug per §3.

---

## 3. Debugger chaque step en cas d'échec

### Step 1 — boot_validation

| Symptom | Probable cause | Action |
|---|---|---|
| `/health -> 500` | Lifespan crash | `journalctl -u aetherix-backend -n 200` — look for `SystemExit` from `_validate_startup_env` or `verify_schema` failures |
| `/health latency > 1s` | Cold start / DB pool exhaustion | Re-run after warm-up; if persistent, check `DATABASE_URL` pool size |
| `workers reports failing` | APScheduler job crashed at startup | Logs: `grep "register_.*_job" /var/log/aetherix.log` |
| `schema_drift exit=2` | Missing migration | `alembic upgrade head`, re-run script |

### Step 2 — apaleo_mcp_probe

| Symptom | Cause | Action |
|---|---|---|
| `probe -> 503 misconfigured` | Missing env var | Check `APALEO_CLIENT_ID/_SECRET/_MCP_SERVER_URL` |
| `probe -> 503 unreachable` | OAuth2 token fetch failed | Verify credentials in Apaleo dashboard; rotate if compromised |
| `tools_available=0` | MCP scope missing on Apaleo account | Re-activate MCP scope (code IIQJ — see §Décision ouverte Apaleo MCP) |

### Step 3 — prophet_predict

| Symptom | Cause | Action |
|---|---|---|
| `MCP error: ... Token missing scope: predict` | Token lacks the `predict` scope | Recreate token per §1.3 |
| `predicted_covers=0` | Prophet model not trained | Run training (§1.3) and retry |
| `MCP error: ... internal_error` | Engine raised — check `/var/log/aetherix.log` for stack trace tagged with the same `x-request-id` |

### Step 4 — memory_feedback_roundtrip

| Symptom | Cause | Action |
|---|---|---|
| `submit_feedback` rejects with unknown recommendation_id | Step 3 did not return one (engine path bypasses memory) | Look up a real recommendation: `SELECT id FROM staffing_recommendations WHERE hotel_id='demo_hotel' ORDER BY created_at DESC LIMIT 1` and re-run with `SMOKE_REC_ID` |
| Recall returns empty list | `operational_memory` empty for this tenant | Backfill via demo seed: `python scripts/seed_knowledge.py --hotel demo_hotel` |
| 3 rows not present in `agent_action_log` | Token validates but `db.commit` fails silently | Check Postgres logs for constraint violations on the partitioned table |

### Step 5 — auth_surface

Each endpoint must reject anonymous traffic with `401`/`403`. If any returns
`200` or `500`, the auth wiring has regressed. Inspect:

- `predictions/predict` → `_predict_auth` dependency (HOS-149)
- `predictions/train` → `_train_auth` dependency
- `webhooks/twilio/inbound` → `TWILIO_SKIP_SIGNATURE_VALIDATION` must be
  `false` in staging; the request body lacks `X-Twilio-Signature` so the
  validator must reject.
- `auth/register` → `REGISTRATION_ENABLED` must be `false`

### Step 6 — anomaly_dispatch_pipeline

| Symptom | Cause | Action |
|---|---|---|
| `DATABASE_URL not set` | The script must reach Supabase directly | Export the asyncpg DSN before running |
| `dispatch trigger -> 404` | Admin endpoint not present (only available in some builds) | Skip via `--skip 6`; replay manually via §4 |
| `no dispatched row` after 10s | Dispatch worker did not pick up the anomaly | `SELECT status, dispatched_at FROM staffing_recommendations WHERE anomaly_id=$1` to confirm state; check APScheduler logs |

---

## 4. Procédure DLQ replay Twilio

When a Twilio outbound message fails (timeout, 5xx from Twilio, signature
rejection at the inbound side), the dispatch worker logs a structured event
to `agent_action_log` with `status='tool_error'` and `error_code` carrying
the failure class. A manual replay is occasionally needed:

1. Identify failed dispatches in the last 24h:
   ```sql
   SELECT id, hotel_id, tool_name, error_code, request_id, created_at
   FROM agent_action_log
   WHERE status = 'tool_error'
     AND tool_name = 'twilio.send_whatsapp'
     AND created_at > now() - interval '24 hours'
   ORDER BY created_at DESC;
   ```

2. For each row, locate the originating `staffing_recommendation`:
   ```sql
   SELECT * FROM staffing_recommendations
   WHERE id = (SELECT (payload->>'recommendation_id')::uuid
               FROM agent_action_log WHERE id = '<row id>');
   ```

3. Replay manually with the operator account:
   ```bash
   python scripts/replay_twilio_dispatch.py --recommendation-id <uuid>
   ```
   (If the replay script is not yet shipped: re-trigger the dispatch worker
   with the recommendation reset to `status='detected'`.)

4. Verify the inbound webhook received the replay (Twilio dashboard →
   Programmable Messaging → Logs).

Tag a follow-up in `linear` if the same `error_code` recurs > 3× in a week —
that signals a class of failure that should be auto-retried rather than
manually replayed.

---

## 5. Procédure rotation partition `agent_action_log`

`agent_action_log` is monthly-partitioned (HOS-150 AC4). The
`agent_action_log_partition_rotation` cron job (registered at lifespan
startup) creates next month's partition on the 25th of the current month.

If rotation fails (job log shows `OperationalError`):

1. Confirm the job is registered:
   ```sql
   SELECT * FROM apscheduler_jobs WHERE id = 'agent_action_log_partition_rotation';
   ```

2. Manually create the missing partition (replace `2026_06` and the date
   bounds):
   ```sql
   CREATE TABLE agent_action_log_2026_06 PARTITION OF agent_action_log
   FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
   CREATE INDEX ON agent_action_log_2026_06 (hotel_id, created_at);
   ```

3. Re-run the job once to verify it no longer errors:
   ```python
   from app.workers.agent_action_log_partition_rotation import rotate
   import asyncio; asyncio.run(rotate())
   ```

4. Schedule a quarterly archive of partitions older than 90 days (cold
   storage → S3) if retention policy requires it. Not yet automated.

---

## 6. Pre-pilot checklist

Tick every box before opening access to a real hotel design partner.

### 6.1 Code & migrations
- [ ] All Epic 9 stories (9.0 → 9.12) merged into `main`
- [ ] `python scripts/check_schema_drift.py` exits 0 against staging DB
- [ ] `python -m pytest backend/tests -x` green in CI
- [ ] `python -m pytest backend/tests/smoke/ -x` green in CI

### 6.2 Smoke test
- [ ] `scripts/smoke_test_e2e.py` exits 0 against staging — all 6 steps `ok`
- [ ] Smoke test re-run 24h later, still exits 0 (catches flaky workers)

### 6.3 Auth & secrets
- [ ] `AUTH_SECRET` is 64 chars, not the placeholder, rotated within last 90d
- [ ] `TWILIO_SKIP_SIGNATURE_VALIDATION=false` in staging
- [ ] `REGISTRATION_ENABLED` unset or `false`
- [ ] MCP API token for the pilot tenant created with minimum scopes
- [ ] Old tokens with broader scopes revoked (`UPDATE mcp_api_tokens SET revoked_at=now() WHERE ...`)

### 6.4 Observability
- [ ] `/health/workers` reachable (or 404 — acceptable for now)
- [ ] `agent_action_log` partition for the current month + next month exists
- [ ] Logs shipping to the configured sink — `grep request_id` returns matched lines on a recent request
- [ ] Redis rate-limiter reachable — sample call to `check_rate_limit` succeeds

### 6.5 Provider quotas
- [ ] Anthropic API key has > 30d worth of headroom on the current month's quota
- [ ] Mistral embeddings: same check
- [ ] Apaleo OAuth2 client not nearing the 90d rotation deadline

### 6.6 Demo data
- [ ] `demo_data/prophet_model.json` exists, last trained within 30 days
- [ ] `operational_memory` has > 20 rows for the pilot tenant
- [ ] `fb_patterns` seeded — `python scripts/seed_knowledge.py` was run

### 6.7 Runbook & on-call
- [ ] This runbook reviewed by the on-call operator
- [ ] DLQ replay procedure (§4) tested at least once in staging
- [ ] Partition rotation procedure (§5) tested at least once in staging
- [ ] PM sign-off recorded in Linear (HOS-161 comment)

### 6.8 Pilot opening
- [ ] Design partner contract signed (legal)
- [ ] Pilot tenant `hotel_id` created with full data isolation verified
  (run `python scripts/audit_id_types.py` — no drift involving the pilot id)
- [ ] Receipts WhatsApp template approved by Twilio
- [ ] Rollback procedure documented (revert to previous main + redeploy)

When every box is checked, request final PM sign-off and announce the pilot
opening in the team Slack.

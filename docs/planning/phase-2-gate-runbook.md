# Phase 2 Track A Gate Runbook

> **Status**: Runbook v1 — 17 May 2026
> **Owner**: SM (Bob)
> **Spec**: `docs/planning/phase-2-agent-receipts.md §5`
> **Gate script**: `scripts/validate_phase2_gate.py`

---

## Overview

Phase 2 closes on **Track A** (technical-ship on Apaleo Sandbox).
Track B (trust-KPI `recommendation_acceptance_rate`) is deferred to Phase 3 entry — it requires a real pilot hotel.

This runbook walks through the four Track A acceptance criteria step-by-step.

---

## Prerequisites

| Requirement | Value |
|-------------|-------|
| Fly.io staging URL | `https://aetherix-backend.fly.dev` |
| Apaleo Sandbox account | Already configured (`APALEO_CLIENT_ID` / `APALEO_CLIENT_SECRET`) |
| Test WhatsApp number | Set `TWILIO_WHATSAPP_FROM` on Fly.io |
| MCP bearer token (receipts:read) | Generate via `POST /api/v1/auth/token` with `receipts:read` scope |
| Python 3.11+ (local) | For running the gate script |

---

## Step 0 — Automated pre-check (local)

Run the local checks first. These never require a live backend:

```bash
cd /path/to/aetherix-hospitality-ai/backend
python ../scripts/validate_phase2_gate.py \
  --hotel-id <your_hotel_tenant_id> \
  --skip-remote
```

Expected: `Track A: 4/4 checks passed` (AC1 + AC4 skipped in local mode).

---

## AC1 — Daily Receipt round-trip (US-1)

**What it validates**: The daily Receipt is composed, sent to WhatsApp + email, and the deep link works.

### Step 1.1 — Trigger a manual Receipt dispatch

```bash
# Replace with your staging hotel_id and a valid date
curl -X POST \
  "https://aetherix-backend.fly.dev/api/v1/receipts/demo_hotel/send?date=2026-05-17" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

> Note: If no `/send` endpoint exists yet, trigger by temporarily setting `RECEIPT_DISPATCH_HOUR`
> to the current UTC hour and waiting for the APScheduler cron to fire.

### Step 1.2 — Verify WhatsApp delivery

1. Check the test WhatsApp number receives a message.
2. Verify: message is ≤ 7 bullets, contains evidence-led bullets (OQ4 tone), ends with confidence + follow-up.
3. Verify: deep link `https://app.aetherix.io/receipts/<hotel_id>/<date>` is present.

### Step 1.3 — Verify email delivery

1. Check `SENDGRID_FROM_EMAIL` inbox or SendGrid activity feed.
2. Content must match the WhatsApp message (same payload).

### Step 1.4 — API check

```bash
TOKEN="<YOUR_RECEIPTS_READ_TOKEN>"
curl -H "Authorization: Bearer $TOKEN" \
  "https://aetherix-backend.fly.dev/api/v1/receipts/demo_hotel/2026-05-17"
```

Expected: HTTP 200 + JSON with `hotel_id`, `receipt_date`, `total_actions`, `lines`.

**Gate criterion**: Message sent + deep link functional + API returns 200.

---

## AC2 — Inbound feedback round-trip (US-3)

**What it validates**: A WhatsApp reply is classified, written to `operational_memory`, and cited in the next day's Receipt.

### Step 2.1 — Send a synthetic correction reply

From the test WhatsApp number, reply to the Receipt message:

```
dinner covers 180, not 140
```

### Step 2.2 — Verify DB write

```sql
-- Check operational_memory for the correction
SELECT hotel_id, reflection, manager_feedback, created_at
FROM operational_memory
WHERE hotel_id = 'demo_hotel'
ORDER BY created_at DESC
LIMIT 5;
```

Expected: a row with `reflection` containing `outcome=modified` and `notes=dinner covers 180, not 140`.

### Step 2.3 — Verify next-day Receipt cites the correction

Trigger the next day's Receipt (or wait for 18:00 dispatch) and verify the narrative references the correction. The `ReceiptPayload.lines` memory_hits should include the new row.

**Gate criterion**: DB write confirmed + next Receipt cites the correction.

---

## AC3 — Weekly digest (US-4): 4 consecutive Sundays

**What it validates**: The weekly digest cron runs 4 Sundays without manual intervention or crash.

### Step 3.1 — Verify scheduler registration (local)

Already covered by `scripts/validate_phase2_gate.py --skip-remote` (AC3 check).

### Step 3.2 — Manual trigger (optional)

To test before Sunday:

```python
# From a Django shell or pytest session against staging
from app.workers.receipts_dispatcher import _run_weekly_digest_job
import asyncio
asyncio.run(_run_weekly_digest_job())
```

Check logs for: `weekly_digest: complete job_id=... dispatched=1 skipped=0`.

### Step 3.3 — 4-Sunday gate

The gate requires 4 consecutive Sundays with zero crashes. Track via:

```sql
-- Check weekly_digest runs in APScheduler logs or agent_action_log
-- (no dedicated weekly_digest table -- monitor app logs on Fly.io)
flyctl logs --app aetherix-backend | grep "weekly_digest: complete"
```

**Gate criterion**: 4 consecutive Sundays with `dispatched >= 1, no FATAL errors`.

---

## AC4 — Web drill-down (US-5)

**What it validates**: The `/receipts/[hotel]/[date]` page loads, auth works, memory hits render.

### Step 4.1 — API auth check

```bash
# Without token -> 401
curl "https://aetherix-backend.fly.dev/api/v1/receipts/demo_hotel/2026-05-17"
# Expected: {"detail": "Missing Bearer token"}

# With wrong scope -> 403
curl -H "Authorization: Bearer <PREDICT_SCOPE_TOKEN>" \
  "https://aetherix-backend.fly.dev/api/v1/receipts/demo_hotel/2026-05-17"
# Expected: {"detail": "Token missing required scope: receipts:read"}

# With correct scope -> 200
curl -H "Authorization: Bearer <RECEIPTS_READ_TOKEN>" \
  "https://aetherix-backend.fly.dev/api/v1/receipts/demo_hotel/2026-05-17"
# Expected: 200 + ReceiptPayload JSON
```

### Step 4.2 — Frontend page

Open the deep link from the WhatsApp Receipt message in a mobile browser.

Verify:
- [ ] Page loads (no blank screen, no 500)
- [ ] Action timeline renders with status badges
- [ ] Memory hits section visible (if any hits exist)
- [ ] Page is readable on mobile (no horizontal overflow)

**Gate criterion**: 401 without token + 200 with valid token + page renders on mobile.

---

## Full automated check (remote)

Once the backend is live and you have a `receipts:read` token:

```bash
cd /path/to/aetherix-hospitality-ai/backend
python ../scripts/validate_phase2_gate.py \
  --base-url https://aetherix-backend.fly.dev \
  --hotel-id demo_hotel \
  --token <RECEIPTS_READ_TOKEN> \
  --date 2026-05-17
```

Expected: `Track A: 5/5 checks passed` (AC1 401, AC1 full, AC2 local, AC3 local, AC4 401).

---

## Track B — Deferred to Phase 3

| Criterion | Deferred because |
|-----------|-----------------|
| `recommendation_acceptance_rate` delta (AC5) | Requires real pilot hotel with live manager interactions |
| Pricing PM recommendation (AC6) | Requires 90+ days of `agent_action_log` from a real hotel |

Track B becomes the **Phase 3 entry criterion**. It is not a blocker for Phase 2 close.

---

## Sign-off checklist

- [ ] AC1: daily Receipt sent to WhatsApp + email + deep link functional
- [ ] AC2: synthetic feedback written to `operational_memory` + cited in next Receipt
- [ ] AC3: 4 consecutive Sunday digests with zero crashes
- [ ] AC4: drill-down 401 gate + page renders on mobile
- [ ] `scripts/validate_phase2_gate.py --skip-remote` exits 0
- [ ] PM sign-off: Ivan de Murard
- [ ] SM sign-off: Bob (SM)

# Phase 2 — Agent Receipts

> **Status**: Spec draft v1 — 18 April 2026
> **Owner**: SM (Bob) · **PM sign-off needed**: Ivan
> **Branch**: `claude/aetherix-market-analysis-5JiJ1` (or new `claude/phase-2-receipts-*` at kickoff)
> **Depends on**: Phase 1 shipped (MCP Server v0, memory instrumentation, ADR 0003 observability)

---

## 1. Product thesis

Phase 0/1 built the engine (forecasts, recommendations, memory, MCP). Managers still don't trust it — they can't see **what the agent did** and **why**. Receipts closes that loop:

> *"Every day, the agent shows me what it did, explains why, and asks what I changed — so I know it's getting better."*

**Receipts = the accountability + explainability layer.** Without it, Aetherix is a black box. With it, the manager is a collaborator, and the feedback signal loops back into `operational_memory` (ADR 0002 D7 dedup, P1-3 real embeddings).

This is the first surface where **managers talk back to the agent in plain language** — a product motion, not just a data display. WhatsApp-first (per CLAUDE.md), with a minimal web view for drill-downs.

---

## 2. User stories (manager's POV)

| # | As a F&B manager, I want to… | Acceptance signal |
|---|------------------------------|-------------------|
| US-1 | See today's agent actions in one WhatsApp message ("Receipts for 2026-04-20") | One message/day, ≤7 bullet lines, link to web view |
| US-2 | Understand why the agent predicted X covers for dinner | Reasoning bullet cites: weather, event, last-weekday baseline, memory hits |
| US-3 | Correct the agent in plain text ("No, there's a private event 80pax") | Reply text → feedback written to `operational_memory`, embedded, acknowledged in next day's Receipt |
| US-4 | See week-over-week: forecast MAPE, labor cost variance, incidents avoided | Weekly WhatsApp digest (Sunday 18:00) with the 3 Niveau-2 KPIs from CLAUDE.md |
| US-5 | Trust: see every memory hit that influenced a recommendation | Web drill-down: clickable hits with similarity score + source tag |

**Non-goals for v1:**
- Multi-hotel view (Phase 3)
- Voice interaction (CLAUDE.md decision #4 — opt-in only)
- Auto-push to POS/scheduling (CLAUDE.md decision #6)
- Rich UI customization — the receipt format is intentionally fixed

---

## 3. Technical architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Twilio WhatsApp webhook (existing, /webhook/twilio)         │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│ ReceiptsService — new in backend/app/services/receipts.py   │
│   - daily_receipt(hotel_id, date) → ReceiptPayload          │
│   - parse_inbound(text, hotel_id) → FeedbackIntent          │
│   - weekly_digest(hotel_id) → WeeklyDigestPayload           │
└───┬──────────────┬─────────────┬──────────────┬─────────────┘
    │              │             │              │
    ▼              ▼             ▼              ▼
┌────────┐ ┌──────────────┐ ┌─────────┐ ┌────────────────┐
│ agent_ │ │ operational_ │ │ predict │ │ LLMProvider    │
│ action_│ │ memory       │ │ ions    │ │ (Claude — nar- │
│ log    │ │ (memory hits)│ │ history │ │ rative compo-  │
└────────┘ └──────────────┘ └─────────┘ │ sition only)   │
                                         └────────────────┘
```

### 3.1 Data sources (all exist today)

- **`agent_action_log`** (ADR 0003 D1 · just shipped): what the agent did, when, latency, status, request_id
- **`operational_memory`** (ADR 0002): the feedback history that shaped recommendations — joined via the `request_id` in the reasoning chain
- **`predictions` table + `fb_patterns`**: the actual forecasts + pattern matches
- **WhatsApp message history** (Twilio webhook persistence): the conversation log

### 3.2 New code

| File | Purpose |
|------|---------|
| `backend/app/services/receipts.py` | `ReceiptsService` — daily + weekly composition |
| `backend/app/workers/receipts_dispatcher.py` | APScheduler 18:00 local daily + Sunday weekly |
| `backend/app/api/routes/receipts.py` | `GET /api/v1/receipts/{hotel_id}/{date}` web drill-down |
| `frontend/app/receipts/[hotel]/[date]/page.tsx` | Thin Next.js view — memory hits, reasoning, KPIs |

### 3.3 Inbound feedback parser (US-3)

Managers reply to a Receipt message in plain text. `ReceiptsService.parse_inbound` routes intent:

- **Structured correction** (`"dinner covers 180, not 140"`) → regex extract + `submit_feedback_to_memory` tool
- **Free-form** (`"private event tomorrow"`) → LLM classifier (lightweight Haiku call) → feedback or calendar-event
- **Acknowledge** (`"ok"`, `"thanks"`, emoji) → no DB write, just LLM sentiment hint for next day's tone

All feedback writes go through the same MCP tool (`submit_feedback_to_memory`) used by third-party agents — single path, single dedup, single embedding flow.

---

## 4. Story breakdown

| Story | Title | Effort | Depends on |
|-------|-------|--------|------------|
| P2-1 | `ReceiptsService` skeleton + `daily_receipt(hotel_id, date)` returning typed `ReceiptPayload` from `agent_action_log` only | S | — |
| P2-2 | Reasoning join — enrich Receipt with memory_hits from the original recommendation call via `request_id` backlink | M | P2-1 |
| P2-3 | WhatsApp daily dispatcher — APScheduler 18:00 local, Twilio template message, deep link to web drill-down | M | P2-1, Twilio already wired |
| P2-4 | Inbound feedback parser — regex for structured + Haiku classifier fallback, routes to `submit_feedback_to_memory` | L | P1-3 memory pipeline |
| P2-5 | Weekly KPI digest — Sunday 18:00, reads from `memory_instrumentation_daily` MV + `agent_action_log` aggregates | S | P2-3, ADR 0003 D8 MV refresh |
| P2-6 | Web drill-down — Next.js `/receipts/[hotel]/[date]`, shows memory hits + similarity, clickable source tags | M | P2-2 |
| P2-7 | Trust signal calibration — ablation: users with Receipts vs users without, measure `recommendation_acceptance_rate` lift (CLAUDE.md Niveau 3 KPI) | S | P2-3 deployed 2 weeks |

**Total**: 7 stories, ~3 sprint-weeks with Sonnet pairing.

---

## 5. Gate criteria — two-track split (locked 19/04/2026)

Apaleo Sandbox is the only environment available pre-pilot. `recommendation_acceptance_rate` cannot be measured without a real manager, so the gate is split:

### Track A — Technical-ship gate (Sandbox-achievable, blocks Phase 2 close)

1. **US-1 round-trip**: daily Receipt composed and sent to a test WhatsApp number AND an opt-in email (SendGrid) with identical content. One receipt/day, ≤7 bullets, deep link to web view.
2. **US-3 round-trip**: inbound WhatsApp reply → Haiku classifier → `submit_feedback_to_memory` → embedding written → next day's Receipt cites the correction by reference. End-to-end on Sandbox with synthetic manager replies.
3. **US-4 weekly digest**: P2-5 cron runs 4 consecutive Sundays on synthetic data, no manual intervention.
4. **Web drill-down**: `/receipts/[hotel]/[date]` loads, MCP bearer auth works with `receipts:read` scope, memory hits + similarity scores render.

### Track B — Trust-signal gate (deferred, becomes Phase 3 entry criterion)

5. **Trust KPI measured** (Phase 3 entry): `recommendation_acceptance_rate` delta vs pre-Receipts baseline on a real pilot hotel; directional lift is the minimum bar.
6. **Pricing decision unblocked** (Phase 3 entry): ≥1 pricing tier recommendation to PM backed by ≥90d of `agent_action_log` from a real hotel.

---

## 6. Resolved decisions (locked 19/04/2026)

- **OQ1 — Channel**: WhatsApp primary + email opt-in via SendGrid (fallback for async managers). Same payload rendered for both. Env vars `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL` already in `.env.example`.
- **OQ2 — Inbound LLM**: Claude Haiku (low cost, low latency, sufficient for 3-intent classification: `structured_correction | free_form | acknowledge`). Log classifier confidence in `agent_action_log.payload`. Auto-downgrade to `outcome=modified` when confidence <0.6 and prompt manager for confirmation via thumbs-up reply. Allows swap via `LLMProvider` abstract (CLAUDE.md Decision #9).
- **OQ3 — Web drill-down auth**: MCP bearer + new `receipts:read` scope in `mcp_core._TOOL_SCOPE`. Reuses existing token plumbing; no `fastapi-users` duplication.
- **OQ4 — Tone**: terse + sharp bullets + luxury feel — main driver, quantified evidence, historical comparative, confidence, proactive follow-up. Canonical example:

> **Why this recommendation?**
> • Main driver: PSG-Bayern match at 2.1km → expected capture rate of 29% (vs 18% on normal Wednesdays)
> • 84% occupancy forecasted, with 31 additional late arrivals expected after 22h
> • On the last 2 similar event nights, adding +2 servers reduced average wait time by 9 min and increased revenue by ~€4.2k
> **Confidence**: High
> Would you like me to simulate "What if the match ends later"?

Style rules: never 1st-person narrative ("I predicted…"), always evidence-led bullets, always ≥1 quantified comparative (vs baseline / similar nights), always explicit confidence (High/Medium/Low), always proactive follow-up offer.

- **OQ5 — Shipped gate**: two-track split (see §5). Most of Phase 2 must be deliverable on Apaleo Sandbox; trust-signal ablation deferred to first real pilot (Phase 3 entry).

---

## 7. Risks

| Risk | Severity | Mitigation |
|------|---------:|------------|
| Twilio throttling or template approval delays | High | Pre-submit templates before P2-3 code-complete |
| LLM classifier false positives (user says "no" meaning "ignore", agent marks as rejected feedback) | Medium | Log classifier confidence in `agent_action_log`; auto-mark `modified` when confidence <0.6; let manager confirm via thumbs-up reply |
| Feedback loop pollution (manager accidentally corrects true positives) | Medium | ADR 0002 D7 cosine dedup + weekly audit query over `operational_memory` for contradictory feedback |
| Receipt message fatigue (daily WhatsApp feels like spam) | High | OQ5 gate; opt-out via `STOP`; schedule allows hotel-local 17:00–20:00 window |
| Pricing decision delayed because metering data is thin (only 1 pilot hotel × 90d) | Medium | Ship P2-7 trust-KPI measurement as a proxy signal — real usage curves matter more than volume |

---

## 8. Kickoff checklist

- [x] PM sign-off on user stories + gate criteria (19/04/2026)
- [x] Resolve OQ1–OQ5 with PM (19/04/2026 — see §6)
- [ ] Linear epic HOS-75 "Phase 2 — Agent Receipts" + 7 child stories P2-1 to P2-7
- [ ] Twilio WhatsApp template pre-submitted for daily Receipt format (use OQ4 canonical example)
- [x] Pilot environment identified: **Apaleo Sandbox** (real pilot hotel deferred to Phase 3; impacts Track B of gate — see §5)
- [ ] Architect check: ADR 0004 needed for Receipts composition (LLM tone policy + memory-hits→prose render pipeline). Defer to P2-1 kickoff.

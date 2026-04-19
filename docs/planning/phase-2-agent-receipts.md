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

## 5. Gate criteria for "Phase 2 done"

1. **US-1 shipped in production**: at least one hotel receives daily Receipts in WhatsApp.
2. **US-3 round-trip works**: manager reply → embedding written → next day's Receipt shows "Thanks, noted — updated forecast uses your correction."
3. **Weekly digest running**: P2-5 cron job runs 4 consecutive Sundays without manual intervention.
4. **Trust KPI measured**: `recommendation_acceptance_rate` delta measured vs pre-Receipts baseline; directional lift (even if not significant) is the minimum bar.
5. **ADR 0003 metering data used**: pricing decision (CLAUDE.md open) is unblocked — at least one pricing tier recommendation to PM backed by 90 days of `agent_action_log` data.

---

## 6. Open questions (to resolve at kickoff)

- **OQ1** — Receipt channel: WhatsApp only (per CLAUDE.md push-first), or also email digest for managers who prefer async? WhatsApp costs €0.005/msg, email is free — the question is behavioral, not cost.
- **OQ2** — Inbound feedback LLM: Claude Haiku for the classifier (low cost, low latency) or reuse the singleton provider from `app.state.llm` (Sonnet — higher cost per call)? Recommendation: Haiku; cross-check with CLAUDE.md decision #9 (`LLMProvider` abstract allows swap).
- **OQ3** — Web drill-down auth: extend existing `fastapi-users` session, or reuse MCP bearer token scoped to `receipts:read`? MCP bearer is cleaner but requires new scope in `mcp_core._TOOL_SCOPE` mapping.
- **OQ4** — Receipt tone: terse/neutral ("Forecast 140, actual 155, memory hit from 2026-03-15") or narrative ("Tonight I predicted 140 covers — weather was wrong, I'll use the private event you flagged next time")? Recommendation: test both; narrative first, fallback to terse on churn.
- **OQ5** — Phase 2 gate for the PM check-in: when does Receipts count as "shipped"? Pilot hotel + 2 weeks + measurable US-3 round-trip, or earlier?

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

- [ ] PM sign-off on user stories + gate criteria
- [ ] Resolve OQ1–OQ5 with PM
- [ ] Linear epic HOS-75 "Phase 2 — Agent Receipts" + 7 child stories P2-1 to P2-7
- [ ] Twilio WhatsApp template pre-submitted for daily Receipt format
- [ ] Pilot hotel identified (reuse whichever one validates Phase 1 MCP Server v0)
- [ ] Architect check: does this need ADR 0004 (Receipts composition / LLM tone policy)? — probably yes if we keep OQ4 narrative tone; defer to kickoff

# Epic: WhatsApp Messaging Design System

**Team:** HOS | **Priority:** High | **Phase:** 1–2
**Branch:** `claude/whatsapp-agent-response-ui-iTTXk`
**Drafted:** 2026-04-06

---

## Problem

The Aetherix agent communicates with hotel managers exclusively via WhatsApp — it is the primary UX surface. Yet today, message formatting and tone are defined in 3 independent services with no shared standard:

- `whatsapp_service.py` — markdown + emojis + section dividers
- `recommendation_formatter.py` — plain English sentences, no formatting
- `explainability_service.py` — governed only by an informal Claude prompt comment

The agent has three different personalities depending on which code path fires. This creates an inconsistent, unprofessional experience that undermines manager trust — the single most important variable for adoption (recommendation acceptance rate target: >30%).

---

## Goal

Define and implement a unified design system for all agent-to-manager WhatsApp communications. Every message the agent sends — proactive alerts, on-demand forecasts, explanations, feedback acknowledgements, and visual charts — must feel like it comes from one coherent, trustworthy assistant.

---

## Scope

**In scope:**
- Tone of voice and formatting guidelines (documented spec)
- Canonical message templates for all alert and conversational flows
- Text sparklines for lightweight trend context (Phase 1)
- Feedback CTA and quick reply parsing (`✅` / `❌` / `why` / `chart`)
- On-demand chart delivery via WhatsApp media image (Phase 2)
- Consolidation of all string-building logic into a single `MessageFormatter`

**Out of scope:**
- WhatsApp template pre-approval process (Twilio production onboarding — separate ops task)
- Multi-language support (Phase 3+)
- Push notification scheduling logic (covered in alert dispatcher stories)
- Dashboard/UI rendering of the same data (separate frontend epic)

---

## Why this matters now

Phase 1 will scale proactive alerts to real hotel managers. First impressions of the agent happen via these messages. Shipping inconsistent formatting at scale makes the product feel like a prototype, not a tool a manager would trust with staffing decisions. This epic is a prerequisite to Phase 1 go-live.

Additionally, the on-demand chart story (Story 6) unlocks a key differentiator: a manager asking *"show me forecast accuracy this month"* and receiving a clean chart inline in WhatsApp — zero app switch, zero dashboard login required. This is the ambient, push-first UX that defines the product's positioning.

---

## Stories

| # | Title | Size | Phase |
|---|---|---|---|
| Story 1 | Define WhatsApp Response Guidelines & Tone of Voice | S | 1 |
| Story 2 | Standardize Proactive Alert Templates + Text Sparkline | M | 1 |
| Story 3 | Standardize Explainability & Conversational Replies | M | 1 |
| Story 4 | Implement Feedback CTA & Quick Reply Parsing | M | 1 |
| Story 5 | Formatter Audit & Consolidation | S | 1 |
| Story 6 | On-Demand Chart Delivery via WhatsApp Media | M | 2 |

---

## Story 1 — Define WhatsApp Response Guidelines & Tone of Voice
`Size: S | Phase: 1 | No dependency`

**Description:**
Produce `docs/whatsapp-messaging-guidelines.md` as the single source of truth for all WhatsApp output.

**Spec:**
- **Tone:** Confident, concise, never robotic. Hotel ops language, not tech language. Peer-level, not servile. Voice is always "Aetherix" (never "I").
- **Voice spectrum:** Proactive alert = directive + data-grounded. Reactive reply = conversational + explanatory. Never apologetic.
- **Length rules:** Alert ≤ 4 lines. Explanation ≤ 5 sentences. Chart caption ≤ 1 sentence. No wall of text.
- **Language:** English (Phase 0–2). Numbers always explicit. Currency = £ with 0 decimals. Times = 24h `HH:MM`. Dates = `Mon 14 Apr`.
- **Emoji rules:** Section headers only. Max 1 per message block. Approved set: `📊` forecast · `👥` staffing · `⚠️` alert · `💡` tip · `✅` confirmed · `❌` rejected · `📈` chart/trend.
- **Formatting:** WhatsApp markdown supported (`*bold*`, `_italic_`). Use bold for numbers and key metrics only. No dividers `━` in alert messages (reserved for interactive flows).

**Acceptance criteria:**
- [ ] `docs/whatsapp-messaging-guidelines.md` created and merged
- [ ] Referenced in `CLAUDE.md` under Fichiers clés
- [ ] PM sign-off before Story 2 begins

---

## Story 2 — Standardize Proactive Alert Templates + Text Sparkline
`Size: M | Phase: 1 | Depends: Story 1`

**Description:**
Refactor `recommendation_formatter.py` to use a shared `MessageFormatter` class with 3 canonical alert templates. Text sparkline included for trend context.

**Templates:**

Surge:
```
⚠️ *Staffing Alert — Dinner tonight*
Add *{n} staff* for {HH:MM}–{HH:MM}.
Covers: *{X}* (+{delta}% vs avg) · Revenue opp: *£{Y}*
Trigger: {factor}

✅ Accept  ❌ Dismiss  💡 Why?
```

Lull:
```
⚠️ *Staffing Alert — Lunch tomorrow*
Consider releasing *{n} staff* for {HH:MM}–{HH:MM}.
Covers: *{X}* (–{delta}% vs avg) · Labour saving: *£{Y}*
Trigger: {factor}

✅ Accept  ❌ Dismiss  💡 Why?
```

Forecast on-demand:
```
📊 *Forecast — Dinner {Mon DD MMM}*
Covers: *{X}* (range {low}–{high} · {conf}% confidence)
This week: {sparkline}
Drivers: {driver1}, {driver2}

📈 Full week chart? Reply *chart week*
```

**Sparkline spec:** 7-char Unicode bar `▁▂▃▄▅▆▇` mapped to covers relative to rolling 30-day avg. Computed server-side, no image required.

**Acceptance criteria:**
- [ ] `MessageFormatter` class created in `backend/app/services/message_formatter.py`
- [ ] `recommendation_formatter.py` delegates all string building to `MessageFormatter`
- [ ] Sparkline function implemented and unit tested (edge cases: all-equal values, single data point, missing days)
- [ ] All 3 templates rendered correctly in existing formatter tests
- [ ] No duplicate string-building logic remains in `alert_dispatcher.py`

---

## Story 3 — Standardize Explainability & Conversational Replies
`Size: M | Phase: 1 | Depends: Story 1`

**Description:**
Align `explainability_service.py` Claude prompt with the guidelines. Define canonical reply patterns for all conversational flows.

**Templates:**

"Why?" reply:
```
{2–3 sentences, data-grounded, specific numbers}
{1 sentence historical precedent if available in Private Memory}
Confirm? ✅ Accept  ❌ Dismiss
```

Accepted:
```
✅ *Accepted.* Staffing plan updated for {HH:MM}–{HH:MM}.
I'll track tonight's actual covers to improve next forecast.
```

Rejected:
```
❌ *Dismissed.* No changes made.
What was off? Reply *too high* · *wrong time* · *other*
```

Rejection reason acknowledged:
```
Got it — noted as feedback. This helps calibrate future recommendations for {hotel_name}.
```

Unknown input:
```
I didn't catch that. You can reply:
✅ to accept · ❌ to dismiss · *why* for reasoning · *chart week* for trends
```

**Claude system prompt update:**
```
You are Aetherix, an AI assistant for hotel F&B operations.
Write a plain-text reply (3–5 sentences max) that:
- Directly answers the manager's question using the data provided
- Uses specific numbers (£ values, %, cover counts) to build trust
- Avoids jargon — write as if texting a busy hotel manager
- Never uses markdown, bullet points, or headings
- Ends with a one-line action nudge (accept or dismiss)
Voice: Aetherix (never "I"). Tone: confident peer, not assistant.
```

**Acceptance criteria:**
- [ ] Claude system prompt updated in `explainability_service.py`
- [ ] All 5 conversational patterns implemented in `MessageFormatter`
- [ ] `whatsapp_service.handle_inbound_message()` routes to correct pattern
- [ ] Unit tests for each reply pattern (mock Claude response)
- [ ] "Unknown input" fallback tested with arbitrary strings

---

## Story 4 — Implement Feedback CTA & Quick Reply Parsing
`Size: M | Phase: 1 | Depends: Stories 2+3`

**Description:**
Every proactive alert ends with a CTA. Inbound replies are parsed, routed, and persisted. This is the feedback loop that feeds Private Memory.

**Parsing map:**

| Inbound text | Action |
|---|---|
| `✅` or `yes` or `accept` | `recommendation.action = accepted` |
| `❌` or `no` or `dismiss` | `recommendation.action = rejected` |
| `why` or `?` | Route to explainability service |
| `too high` / `wrong time` / `other` | Store rejection reason |
| `chart week` / `chart month` / `chart` | Route to chart service (Story 6) |
| anything else | Unknown input fallback (Story 3) |

**Technical notes:**
- Session state in Redis maps `phone_number → last_recommendation_id` (TTL 2h) for context threading
- Parser: regex + keyword matching, case-insensitive, strip whitespace + emoji variants

**Acceptance criteria:**
- [ ] Parser implemented in `whatsapp_service.py`
- [ ] `StaffingRecommendation.action` and `actioned_at` updated on accept/reject
- [ ] Rejection reasons stored (`rejection_reason` field)
- [ ] Redis session state implemented (phone → recommendation_id, TTL 2h)
- [ ] All parsing paths covered in unit tests
- [ ] Integration test: full inbound → DB update flow

---

## Story 5 — Formatter Audit & Consolidation
`Size: S | Phase: 1 | Depends: Stories 2–4`

**Description:**
Final cleanup pass after Stories 2–4 are merged. Single `MessageFormatter` used everywhere. No rogue string building.

**Acceptance criteria:**
- [ ] Grep for inline emoji string literals returns 0 results outside `MessageFormatter`
- [ ] `whatsapp_service.py`, `recommendation_formatter.py`, `alert_dispatcher.py` all import from `MessageFormatter`
- [ ] All existing tests still pass (no regressions)
- [ ] `MessageFormatter` has its own dedicated test file (`tests/test_message_formatter.py`)

---

## Story 6 — On-Demand Chart Delivery via WhatsApp Media
`Size: M | Phase: 2 | Depends: Story 4`

**Description:**
When a manager replies `chart week`, `chart month`, or `chart Q1`, the agent generates a visual chart and delivers it as an image inline in WhatsApp. Uses Twilio `MediaUrl`, Supabase Storage for hosting, and matplotlib for rendering. Claude generates a 1-sentence caption; the chart itself is rendered server-side.

**Supported intents:**

| Manager input | Chart rendered | Date range |
|---|---|---|
| `chart week` / `show this week` | Cover forecast vs actual (bar + line) | Mon–Sun current week |
| `chart month` | Daily covers + 7-day rolling avg | Current calendar month |
| `chart Q1` / `chart semester` | Weekly aggregated covers + trend line | YTD or last 6 months |
| `chart accuracy` | Forecast MAPE over time | Last 30 days |

**Technical flow:**
```
1. Intent parsed in whatsapp_service.py → ChartRequest(type, date_range, hotel_id)
2. ChartService.generate() called async:
   a. Fetch data from DB (covers_actual + covers_forecast for range)
   b. matplotlib renders PNG (800×400px, clean minimal style)
   c. PNG uploaded to Supabase Storage bucket `whatsapp-charts/`
   d. Signed URL generated (TTL: 1h)
3. TwilioClient.send_whatsapp(to, body=caption, media_url=signed_url)
4. Manager sees chart inline in WhatsApp
```

**Chart style spec:**
- Background: white `#FFFFFF`
- Forecast line: `#6366F1` (indigo) · Actual line: `#10B981` (green) · Avg reference: `#94A3B8` dashed
- Font: system sans-serif, 11px axis labels
- No chart title (caption delivered as message body)
- X-axis: date labels · Y-axis: cover count · Grid: subtle `#F1F5F9`
- Size: 800×400px, exported as PNG ≤ 200KB

**Caption generation (Claude prompt):**
```
Given this chart data summary: {json_summary}
Write exactly ONE sentence (max 15 words) highlighting the most notable trend.
Format: plain text, no markdown. Start with a number or percentage.
Example: "Forecast accuracy reached 91% this week, up from 74% last Monday."
```

**Fallback (insufficient data):**
```
📊 Not enough data yet for a {range} chart.
{n} more days of actuals needed to generate this view.
```

**Acceptance criteria:**
- [ ] `ChartService` implemented in `backend/app/services/chart_service.py`
- [ ] Intent parser in Story 4 routes `chart *` inputs to `ChartService`
- [ ] `TwilioClient.send_whatsapp()` extended with optional `media_url` param
- [ ] Supabase Storage bucket `whatsapp-charts` configured (signed URLs, TTL 1h)
- [ ] Chart renders correctly for all 4 intent types (tested with fixture data)
- [ ] PNG size enforced ≤ 200KB (compress if over)
- [ ] Fallback triggered when `len(actuals) < 3`
- [ ] Unit tests use `plt.switch_backend('Agg')` (no display in CI)
- [ ] Twilio sandbox tested manually on a real WhatsApp device before merge

---

## Definition of Done (Epic level)

- [ ] `docs/whatsapp-messaging-guidelines.md` exists and is referenced in `CLAUDE.md`
- [ ] Single `MessageFormatter` class handles all outbound message construction
- [ ] All alert, conversational, and chart flows use canonical templates
- [ ] Feedback loop persists `accepted` / `rejected` + reason to DB
- [ ] On-demand charts render and deliver via Twilio `MediaUrl` (tested on real device)
- [ ] All formatter tests green, no regressions
- [ ] PM sign-off on a test conversation covering the full manager flow end-to-end

---

## Success metrics (post-launch, 30 days)

- `recommendation_acceptance_rate` ≥ 30%
- Manager-initiated chart requests tracked as a distinct usage event
- Zero "unknown input" fallback triggered by a valid-intent message
- No manager feedback citing confusing or inconsistent message format

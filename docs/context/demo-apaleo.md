# Demo PRD — Aetherix x Apaleo

> **Audience:** Lennart Reents, AI Engineer @ Apaleo (Munich)
> **Goal:** End-to-end agentic F&B pipeline integrating the official Apaleo MCP Server — proof of concept for application
> **Deliverable:** 90-second Loom + public GitHub repo
> **Target date:** April 2026
> **Last updated:** 2026-04-13 — PM session

---

## §1 — Demo scenario and hotel choice

**Hotel:** Hotel Kleber *(fictional, representative of the Apaleo segment)*
- Independent 4-star, 118 rooms, Paris 16th arrondissement
- Restaurant "Le 16" — 78 covers max
- Apaleo client since 2024, experienced F&B Manager with no dedicated revenue or data team

**Event:** PSG vs. Bayern Munich, Champions League semi-final second leg
- Match date: Wednesday 6 May 2026, 21:00 (Parc des Princes)
- Announced 3 weeks ago at the draw — already in the agent's event calendar (PredictHQ)
- Stadium: 2.1 km from the hotel

**Demo moment:** Tuesday 5 May 2026, 14:00 (J-1 daily cycle)

**Operational realism:**
- Base staffing and initial provisions were planned 10-15 days ago
- Aetherix's role at J-1 14:00 is the **final adjustment**: refine exact expected covers, confirm additional server count, adjust mise en place based on latest signals (pickup rate, updated weather, direct restaurant reservations, last-minute cancellations)
- The manager makes a final call the evening before — Aetherix gives them the data to do it with precision

**Value demonstrated:** Even when an event is known weeks in advance, the **final precision and last-minute contextual adjustment** remain critical — walk-ins, no-shows, weather, match outcome uncertainty all shift the actual number.

---

### Anticipated questions and prepared answers

| Question | Answer |
|----------|--------|
| Why Hotel Kleber more than others? | Proximity to Parc des Princes (2.1 km, natural post-match route). Private Memory holds 3 previous CL home nights: +60% covers vs. Wednesday baseline, walk-in spike confirmed in all three. |
| Why this hotel size? | 100-150 room independents are the Apaleo sweet spot: large enough for F&B revenue to make +20 covers worth €3-6K, small enough to have no dedicated data team. That is exactly where Aetherix creates value. |
| Why an independent, not an Accor or Marriott? | Chains have centralised analytics teams. Apaleo targets tech-forward independents and small groups (2-20 properties). Hotel Kleber chose Apaleo precisely because it wants open APIs — Aetherix is the natural beneficiary. |
| Why not a known brand (Mama Shelter, 25hours)? | Fictional avoids IP and affiliation issues. The profile is identical to a 25hours Paris or a Hoxton. |
| Does the manager need to do anything to set this up? | No. Once onboarded (30-minute setup, property linked via Apaleo OAuth), the agent runs automatically. |
| What if the manager ignores the recommendation? | It is logged. MemoryService notes the pattern. After 2 consecutive ignored recommendations, the agent proactively asks what the manager observed — that feedback updates the capture rate profile. |

---

## §2 — Agentic flow (J-1 14:00 daily cycle)

**Trigger:** Internal cron at 14:00 J-1 for each active property. Manual alternative: `POST /api/v1/notifications/send-daily`. The cron fires automatically — no action required from the manager.

---

**Step 1 — MCP validation**

`GET /pms/mcp/probe`

- Verifies APALEO_CLIENT_ID, APALEO_CLIENT_SECRET, APALEO_MCP_SERVER_URL
- Acquires OAuth2 token (client_credentials flow)
- Opens a streamable-HTTP MCP session, calls `list_tools` (handshake)
- Returns: `{"status": "ok", "tools": 42, "latency_ms": 203}`
- On failure: transparent fallback to ApaleoPMSAdapter (raw REST) — pipeline never blocked

---

**Step 2 — PMS data fetch via MCP**

`POST /pms/sync?use_mcp=true`

Three MCP tool calls via ApaleoMCPAdapter:
- `APALEO_GET_OCCUPANCY_METRICS` — occupancy J (stayovers + expected arrivals): **81%, 94 guests**
- `APALEO_GET_RESERVATIONS` — confirmed restaurant bookings for dinner: **31**
- `APALEO_GET_REVENUE_METRICS` — revenue pace vs. J-7 / J-14 (momentum signal)

---

**Step 3 — External context**

- Weather (OpenWeatherMap): 17°C, clear — outdoor terrace viable
- Events (PredictHQ): PSG–Bayern, 21:00, 47,000 attendance, 2.1 km — confirmed in calendar, event score 0.94

---

**Step 4 — Historical capture rate (pgvector)**

Embedding query on `fb_patterns`:
*"Wednesday evening, CL home fixture, occupancy 81%, clear weather, Paris 16e"*

3 similar patterns retrieved (scores: 0.89, 0.84, 0.81):

| Date | Actual covers | Occupancy | Event |
|------|--------------|-----------|-------|
| Nov 2025 | 67 | 79% | PSG CL home |
| Mar 2025 | 71 | 83% | PSG CL home |
| Oct 2024 | 68 | 77% | PSG CL home |

Capture rate extracted from Private Memory:
- Wednesday baseline: **18%** of in-house guests dine at Le 16
- CL home night average: **29%** (+11 pts — 3 occurrences, consistent)

---

**Step 5 — Expected covers calculation**

```
In-house guests (forecast):   94
x Adjusted capture rate:      29%  (base 18% + CL delta +11pts)
= Internal demand:            27

Direct bookings (confirmed):  31
Walk-ins (CL pattern avg):   +16
─────────────────────────────────
Total expected:               74 covers  (capacity: 78)
```

---

**Step 6 — Prophet forecast**

`PredictionEngine.predict()` with regressors: occupancy, day_of_week, weather, event_proximity, event_attendance.

Output: **74 covers [68–80], confidence 83%** — consistent with capture rate calculation, signal coherence confirmed.

---

**Step 7 — Claude Sonnet reasoning**

`ReasoningService.generate_explanation()` receives pre-analyzed context:
- Prophet output
- 3 pgvector patterns with scores
- Capture rate calculation and its components
- MemoryService context (previous CL nights, manager feedback history)

Claude synthesises into:
- 3-line operational summary (for the WhatsApp message)
- Full chain-of-thought (served on "Why?" request)
- Mise en place signal with food cost delta (see Step 9)

---

**Step 8 — Staffing**

`StaffingService.calculate_recommendation(74)`

Output: **6 servers recommended** (planned: 5, delta: +1, estimated cost: +€85)

---

**Step 9 — WhatsApp message**

```
Aetherix | Tomorrow Wed 6 May

Forecast: 74 covers (capacity 78)
+60% vs normal Wednesday (base: 46)
Staff: 6 — you have scheduled 5

Mise en place: 74 covers
31 bookings + 27 residents + 16 walk-ins
(your last 3 CL home nights: 67, 71, 68 actual)

Prepping for 90 covers: ~€145 in unused food cost
if actuals stay within your historical range
(16 excess covers x €14 food cost x 65% waste conversion)

Reply Why? or What if the match is cancelled?
```

---

**Step 10 — Logging and memory**

- ActionLogger records the push (Architectural Decision #7 — all agent actions logged)
- MemoryService stores the recommendation for future feedback loop
- Manager response (confirm / reject / why) updates the capture rate profile on next cycle

---

### "Why?" flow

```
Manager replies: "Why?"
  |
POST /webhook/whatsapp  (Twilio inbound webhook)
  |
WhatsAppService.handle_inbound_message()
  |
MemoryService.log_interaction("explain_requested")
  |
ReasoningService — full chain-of-thought:
  - Prophet: +60% vs Wednesday baseline (event regressor active)
  - 3 similar CL nights: 67, 71, 68 actual covers (avg score 0.84)
  - Capture rate: 18% base + 11pts CL delta = 29% (3 occurrences, consistent)
  - Weather: 17°C, clear — terrace viable, historically +4% covers
  - Bookings pace: 31 confirmed vs 22 at same point for average Wednesday
  |
Twilio push — WhatsApp response to Sophie
```

---

### "What if?" flow

```
Manager replies: "What if the match is cancelled?"
  |
Claude parses intent: simulation, param=event_cancelled
  |
AetherixEngine.get_forecast() — rerun, event modifier removed
  |
Result: 52 covers (capture rate reverts to 18%, walk-ins drop to 4)
  |
Response: "Without the match: 52 covers estimated.
           Capture rate: 18% (no event modifier).
           Staff: 4 is sufficient. Delta vs. tonight's plan: -2 servers."
```

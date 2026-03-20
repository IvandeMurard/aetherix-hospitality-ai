# Roadmap: Now → Next → Later

**Last review:** March 20, 2026
**Current Phase:** Phase 3 — Dashboard MVP (active)
**Status:** Phases 1 + 2 complete. Next.js dashboard + FastAPI backend live in Docker.
**Market context:** ITB Berlin 2026 confirmed F&B ops forecasting as an uncontested gap in the agentic AI landscape.

---

## 🔥 NOW (Phase 3 — March 2026)

**Focus:** Ship the dashboard MVP. Make predictions visible, interactive, and trusted.

### Active work

- [ ] **Dashboard MVP — covers forecast view**
  - Day/Week/Month toggle
  - Confidence score display + colour coding
  - "Why this forecast?" expandable panel (Conversational Receipt)
  - Staff recommendation with ROI breakdown

- [ ] **Manager approval flow in dashboard**
  - Accept / Modify / Reject recommendation
  - State persisted to Supabase (pending → approved → actioned)
  - Audit log visible in UI

- [ ] **Push notification delivery**
  - Twilio WhatsApp trigger on anomaly detection
  - Inbound "Why?" reply → Conversational Receipt response
  - Under 3 minutes end-to-end (NFR2)

- [ ] **First pilot property onboarding**
  - Read-only Apaleo webhook live
  - Baseline captation rate established from historical data
  - First proactive push sent to a real manager

### Phase 3 success criteria

- ✅ Manager receives push notification without logging in
- ✅ "Why?" reply triggers Conversational Receipt in < 3s
- ✅ At least one pilot manager acts on a recommendation in first 2 weeks
- ✅ MAPE on cover predictions stays under 15% across 5 test scenarios
- ✅ Dashboard accessible at localhost:3000 with full Docker Compose boot

### Intelligence from veille — March 2026

**ITB Berlin 2026 signals:**
- Agentic AI dominant theme — "from suggest to execute" is the framing
- F&B operations forecasting gap confirmed: guest-facing (Bookboost) and room operations (Mews Flexkeeping) saturated; F&B ops uncontested
- Mews acquired DataChat (semantic layer) — validates our pgvector RAG architecture as the moat
- Bookboost AI Agent launched at ITB: 5-year training data, 5-sec response, CDP-powered — comparable architecture to Aetherix but guest-facing

**Piers Thackray field signal (LinkedIn, March 2026):**
- Hotel GM in France self-built an operational AI assistant using Claude Code in 2 days
- Built on: Cloudbeds PMS + Google Drive + Sheets + Calendar
- Day 2 result: full 30-day cleaning schedule from one sentence + proactive room conflict detection and autonomous resolution
- This is the demand signal: operators are self-building because no product exists → product window is open, closes in ~12–18 months

**Action from veille:** Prioritize first pilot contact. The self-build signal means the ICP is actively trying to solve this right now.

---

## ⏭️ NEXT (Phase 4 — April–June 2026)

**Focus:** Close the feedback loop. Make the model learn from outcomes. Add Cloudbeds.

### Accuracy tracking & feedback loop

- [ ] **Post-service actuals input**
  - Manager submits actual covers at end of service (in-app or WhatsApp reply)
  - Delta calculated vs prediction (MAPE tracked per property, per service type)
  - Rolling accuracy score visible in dashboard

- [ ] **Pattern reinforcement pipeline**
  - High-accuracy outcomes ingested back into Qdrant as validated patterns
  - Vector store grows from 495 → property-specific patterns over time
  - Accuracy trend shown to manager to build trust ("Model improved +3% this month")

- [ ] **Prediction explanation upgrade**
  - Show top 3 similar historical patterns with confidence scores
  - "This matches 3 similar Fridays with a nearby conference: average outcome was +22% covers"

### Cloudbeds integration (3rd PMS)

- [ ] **Cloudbeds OAuth2 + read-only sync**
  - Add to PMS integration layer alongside Apaleo + Mews
  - 400+ marketplace partners → validates as distribution channel
  - Signal: Piers Thackray (self-builder) uses Cloudbeds — ICP overlap confirmed

### Apaleo Agent Hub listing

- [ ] **Package Aetherix as an Apaleo Agent**
  - Apaleo announced Agent Hub at ITB Berlin 2026 — first AI agent marketplace for hospitality
  - Our MCP server architecture is already the right integration pattern
  - Listing = distribution to 2,000+ Apaleo properties without direct sales
  - Action: Reach out to Apaleo partnerships post-Phase 3

### Phase 4 success criteria

- ✅ MAPE trending downward over 4 weeks for at least one pilot property
- ✅ Pattern store grows automatically (no manual reseeding required)
- ✅ Cloudbeds integration live and tested
- ✅ Apaleo Agent Hub application submitted

### Potential additions from veille

- Trybe (spa/wellness scheduling) partnership — same methodology, adjacent department
- Juyo Analytics "Kassandra" watch: if they expand to F&B ops, re-evaluate differentiation
- Oracle Opera Cloud exploration: required for enterprise hotel groups (Phase 5 blocker)

---

## 📅 LATER (Phase 5 — Q3 2026+)

**Focus:** Expand scope. F&B agent becomes full operations layer.

### POS integration → menu & inventory intelligence

- [ ] **POS data ingestion** (manual CSV first, then API)
  - Actual menu mix per service (what sold vs what didn't)
  - Average cover spend per event type
  - High-demand item pre-positioning recommendations ("Order extra salmon for tech conferences")

- [ ] **Inventory procurement directive**
  - "Based on 3 similar Fridays with a conference: salmon sells out. Recommend ordering 15% more."
  - Procurement lead time factored into push timing

- [ ] **Menu price optimization suggestions**
  - High-demand + low-supply scenarios flagged for dynamic pricing
  - "Events crowd has historically spent 18% more on wine — consider promoting premium list tonight"

### Cross-department context

- [ ] **Front Desk ↔ F&B handoff**
  - Group check-ins flagged → F&B briefed on expected covers + dietary notes
  - "Conference group of 45 arriving at 6pm — 4 vegetarian, 2 gluten-free"
  - MCP cross-system signal passing (PMS → F&B context layer)

- [ ] **Housekeeping coordination**
  - Occupancy context shared with F&B (checkout patterns → breakfast demand)
  - Late checkouts → extended breakfast service trigger

### Multi-property & portfolio view

- [ ] **Portfolio dashboard** for Operations Directors
  - Aggregated accuracy metrics across properties
  - Top/bottom performing properties by MAPE
  - Chain-level event detection ("tech conference city-wide — alert all F&B managers")

- [ ] **White-label & embedded** offering
  - Aetherix F&B module embeddable in Mews / Apaleo dashboards
  - Revenue share model with PMS partners

### Voice input (re-evaluate)

- [ ] **Voice query via WhatsApp** (Phase 5 evaluation)
  - Manager sends voice note: "What's the forecast for Saturday dinner?"
  - Transcribed via Whisper → Conversational Receipt response
  - Note: noisy restaurant environments challenge accuracy — test carefully
  - Cost: ElevenLabs ~$225/month vs $6.65 Claude API — validate ROI first

### Agentic task auto-creation

- [ ] **From forecast to task**
  - Aetherix forecast confirmed → auto-creates tasks in hotel ops platform (Flexkeeping, etc.)
  - "Forecast confirmed: +2 servers needed. Task created: Call Sarah and Marco by 3pm."
  - Validated pattern from Apaleo + THE FLAG deployment at ITB 2026

### Phase 5 success criteria

- ✅ POS integration live with at least one property
- ✅ Cross-department data flowing (PMS → F&B → ops tasks)
- ✅ Portfolio dashboard with 3+ properties
- ✅ Agentic task creation live

---

## 📊 Progress log

### Week of January 6, 2026 (Phase 1 completion sprint)
- ✅ IVA-26–28: Backend environment, Demand Predictor skeleton, Enhanced context generation
- ✅ IVA-5–8: Core MVP capabilities
- 🔄 IVA-29: Contextual patterns bug (Christmas edge case)
- ⛔ IVA-30–33: Blocked on IVA-29

### January–February 2026 (Phase 2 completion)
- ✅ Phase 1 complete: Backend MVP, prediction + reasoning engines live
- ✅ RAG with 495 vector patterns (Qdrant)
- ✅ PMS integrations: Apaleo OAuth2 + Mews webhooks
- ✅ Supabase PostgreSQL + pgvector + RLS (tenant isolation)
- ✅ Security hardening (5 HIGH severity fixes)
- ✅ Docker Compose full stack (backend + frontend + DB + mailhog)

### March 2026 (Phase 3 — active)
- ✅ Repo cleaned and consolidated (single source of truth)
- ✅ Market intelligence brief compiled (ITB Berlin 2026, Hotel Yearbook 2026, Bookboost, Mews)
- ✅ MCP context layer framing documented (`docs/AI_CONTEXT_LAYER.md`)
- 🔄 Dashboard MVP (Next.js) — active development
- 🔄 First pilot property identification

---

## 🧠 Strategic notes

### Architecture principles (unchanged)

- ✅ **Dashboard-first, not voice-first** — industry requires visual transparency + EU AI Act explainability
- ✅ **Push model, not pull** — managers don't check dashboards; intelligence must arrive at decision moment
- ✅ **Read-only PMS** — zero-friction pilot, no IT approval required, no write risk
- ✅ **Explainability mandatory** — every recommendation exposes its reasoning (GDPR Article 22, EU AI Act)
- ✅ **Thin frontend / fat backend** — LLM orchestration belongs server-side; UI is presentation only
- ✅ **Data quality over model complexity** — our semantic layer (RAG) is the moat, not the LLM

### Competitive positioning — updated March 2026

| Player | Focus | Our gap vs them |
|---|---|---|
| Mews + DataChat | Semantic layer, rooming lists, agentic PMS ops | They won't build F&B-specific; too broad |
| Apaleo Agent Hub | Marketplace for hotel AI agents | Distribution channel, not competitor |
| Bookboost | Guest messaging AI (CDP-powered) | Guest-facing; we're ops-facing |
| Trybe | Spa/wellness scheduling | Same methodology, different department — potential partner |
| Juyo "Kassandra" | Revenue/demand sensing for GMs | Revenue management focus; we're staffing/ops |
| Sirma "Vela" | Front desk + housekeeping agent | Front of house; we're F&B |
| Self-builders (Thackray) | Claude Code + raw API duct-tape | We're the productized version of what they're building |

**The gap:** F&B operations forecasting + proactive push + staffing directives is uncontested at product level as of March 2026.

### Key learnings

- Christmas edge case = credibility test for any hospitality forecasting model
- Internal PMS data = 40% of prediction accuracy; external signals = 60%
- Pattern variation + explainability > raw prediction accuracy for manager trust
- Operators are self-building (Thackray signal) = product window is open, not permanent

### Decision framework for veille-driven additions

| Impact | Effort | Action |
|---|---|---|
| High | Low | Add to NOW |
| High | High | Plan for NEXT |
| Low | Any | Reject or defer to Later |

### Pivots to watch

- **Mews builds F&B module** → move fast on Apaleo Agent Hub listing; become embedded before they expand
- **Apaleo pivots to build-in-house** → direct sales motion, emphasize property-specific RAG differentiation
- **EU AI Act enforcement tightens** → our explainability-first design is already compliant; market it
- **New Claude capabilities (extended context, tool use)** → evaluate for Conversational Receipt quality uplift
- **Cloudbeds launches AI marketplace** → position there alongside Apaleo Agent Hub

---

## 📈 Milestones

| Milestone | Target | Status |
|---|---|---|
| Phase 1 MVP — Backend API + RAG | Jan 2026 | ✅ Done |
| Phase 2 — PMS integrations + Supabase | Feb 2026 | ✅ Done |
| Phase 3 — Dashboard MVP (Next.js) | Mar 2026 | 🔄 Active |
| First pilot property live | Apr 2026 | 🎯 Target |
| Cloudbeds integration | May 2026 | 🎯 Target |
| Apaleo Agent Hub listing | Jun 2026 | 🎯 Target |
| Phase 4 — Feedback loop + accuracy tracking | Q2 2026 | 📋 Planned |
| Phase 5 — POS + cross-dept + portfolio | Q3 2026 | 📋 Planned |

---

## 🔗 Links & resources

**Repository:** https://github.com/IvandeMurard/Hospitality-Operations-Agentic-AI-B2B
**Linear Project:** https://linear.app/ivanportfolio/project/fandb-agent-640279ce7d36

**Core documentation:**
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — Technical architecture (v0.2.0)
- [`docs/MARKET_INTELLIGENCE.md`](MARKET_INTELLIGENCE.md) — Market brief (ITB Berlin 2026)
- [`docs/AI_CONTEXT_LAYER.md`](AI_CONTEXT_LAYER.md) — MCP context layer framing
- [`docs/Problem_Statement.md`](Problem_Statement.md) — ICP and problem framing
- [`docs/Cost_Model.md`](Cost_Model.md) — Unit economics
- [`_ai_workspace/bmad-output/planning-artifacts/prd.md`](../_ai_workspace/bmad-output/planning-artifacts/prd.md) — Full PRD
- [`_ai_workspace/bmad-output/planning-artifacts/epics.md`](../_ai_workspace/bmad-output/planning-artifacts/epics.md) — Epic breakdown

**Veille sources:**
- HospitalityNet — industry news + AI coverage
- Hotel Yearbook — annual strategic framing
- PhocusWire — travel tech product announcements
- LinkedIn: Piers Thackray, Matthijs Welle (Mews CEO), Apaleo, Bookboost

---

**Last updated:** March 20, 2026 by Ivan de Murard
**Next review:** Monday, March 24, 2026

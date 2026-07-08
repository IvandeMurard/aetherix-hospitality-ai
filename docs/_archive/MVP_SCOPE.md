# Aetherix MVP Scope

## Core Value Proposition

Intelligent forecasting for F&B operations — value internal and external context, predict covers, understand why, and optimize staffing.

## Unified Phase Numbering

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Done | Backend MVP — Prediction + Reasoning engines |
| Phase 2 | ✅ Done | RAG — Vector search with 495 patterns |
| Phase 3 | 🔄 Now | Dashboard MVP — Aetherix UI |
| Phase 4 | 📋 Next | Feedback Loop — Accuracy tracking |
| Phase 5 | 📋 Later | Integrations — PMS, POS, voice |

---

## MVP Features (Phase 3)

### ✅ Delivered

- Day/Week/Month forecast views
- Confidence scoring with reasoning
- Factors panel ("Why this forecast?")
- Restaurant/Service context selector
- EN/FR internationalization

### 🔄 In Progress

- Feedback panel (pre/post service)
- Week/Month batch predictions
- Date picker navigation

### 📋 Phase 4 (Next)

- Accuracy tracking (predicted vs actual)
- History view with MAPE
- Restaurant profile configuration

### 📋 Phase 5 (Future)

- PMS integration (Mews, Opera)
- POS auto-sync
- Voice/Chat ambient interface
- What-if scenario modeling

---

## Out of Scope for MVP

- ❌ Voice-first interface (moved to Phase 5)
- ❌ Multi-property support
- ❌ Revenue management
- ❌ Inventory forecasting

---

## Scope Constraints

**Technical constraints:**
- 1 restaurant per instance (no multi-tenancy in Phase 3)
- Mock/simulated data acceptable for events and weather
- Desktop-first (mobile responsive = stretch goal)

**Time constraints:**
- Phase 3 target: February 2026
- Must be demo-able and portfolio-ready

**Resource constraints:**
- Solo developer
- Budget: <$50/month (APIs, hosting free tiers)

---

## Decision Framework

For each feature idea:

1. **Is it essential to demonstrate value?** YES → Consider for MVP / NO → Backlog
2. **Can I build it in <8 hours?** YES → Consider for MVP / NO → Break down or defer
3. **Does it need real APIs?** YES → Can I mock it? If yes, mock. If no, defer. / NO → Include in MVP
4. **Will stakeholders be impressed?** YES → Prioritize / NO → Backlog

---

## RÈGLE D'OR MVP

**"If it's not essential to demonstrate value, it's OUT OF SCOPE."**

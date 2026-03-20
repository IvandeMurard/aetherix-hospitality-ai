# Known Limitations

> Transparency document for demo and roadmap planning.
> Last updated: 2026-02-04

---

## Phase 1-2 (Completed)

### What Works

- ✅ **Prediction Engine** with confidence scoring
- ✅ **Reasoning Engine** with explainability
- ✅ **RAG vector search** (495 patterns, Qdrant Cloud)
- ✅ **API endpoints** (/predict, /predict/batch)
- ✅ Deployed on HuggingFace Spaces

### What's Limited

- ⚠️ **Mock data** derived from Kaggle (not real hotel data)
- ⚠️ **Staff Recommender** uses generic ratios (no PMS context)
- ⚠️ No reservation/event awareness from real systems
- ⚠️ HuggingFace cold start (~30s after inactivity)

---

## Phase 3 (Current)

### In Progress

- **Dashboard UI** (Aetherix) — Day/Week/Month views
- **Feedback panel** (pre/post service) — Backend ✅, frontend in progress
- **Week/Month batch views** — Batch API integration

### Known Issues

| Issue | Description |
|-------|-------------|
| Week/Month views | Batch API parsing (IVA-65) |
| Feedback panel | prediction_id detection |
| Cache invalidation | Stale data after prediction updates |

---

## Planned Improvements

| Issue | Phase | Description |
|-------|-------|-------------|
| Real hotel data | 4+ | Partner with design partner |
| PMS integration | 5 | Mews, Opera adapters |
| Continuous learning | 4 | Learn from feedback |
| Accuracy tracking (MAPE) | 4 | Post-service feedback pipeline |

---

## PM Decisions Documented

### Why mock data in Phase 1?

> "Ship fast, validate architecture, iterate with real data."

Phase 1 goal was to validate:
1. Multi-agent architecture ✅
2. Prediction → reasoning → staffing pipeline ✅
3. Explainability (AI Act compliance) ✅

Real integrations require hotel design partners.

### Why HuggingFace vs Render?

- Render free tier limited (1 project)
- HuggingFace = AI/ML signal for Mews portfolio
- Cold start acceptable for demo

### Why dashboard-first?

> "Backend-first proved the intelligence layer. Dashboard-first enables compliance and trust."

EU AI Act and GDPR require human-in-the-loop visibility. Phase 3 adds Aetherix UI.

---

## Resources

- **Live API:** https://ivandemurard-fb-agent-api.hf.space/docs
- **Live Dashboard:** https://aetherix.streamlit.app
- **Linear:** [F&B Agent Project](https://linear.app/ivanportfolio/project/fandb-agent)

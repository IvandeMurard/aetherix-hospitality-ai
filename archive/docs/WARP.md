# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**F&B Operations Agent** - An AI-powered staffing prediction system for restaurant and hospitality F&B managers.

### Core Problem
Transforms manual staffing forecasting (70% accuracy, 5-8h/week) into AI-powered predictions (85%+ accuracy, <2h/week) by integrating:
- Historical pattern analysis via vector similarity (Qdrant)
- Local events data (PredictHQ API)
- Weather forecasts
- Seasonal and temporal patterns

### Primary Persona
F&B/Operations Manager at mid-high end restaurants (80-150 covers/service), moderately tech-savvy, needs confident data-backed staffing decisions before major events.

### North Star Metric
**Staffing prediction accuracy:** 85%+ (vs 70% baseline with manual methods)
- Measured by comparing predicted covers vs actual POS data

## Approach

**Dashboard-first, voice-available** interface for F&B managers.

The agent provides a visual dashboard (Aetherix) as the primary interface, with voice/chat capabilities planned for Phase 5 integration with messaging platforms (WhatsApp, Slack).

### Why Dashboard-First?

1. **Regulatory compliance** - EU AI Act and GDPR require human-in-the-loop visibility
2. **Industry standard** - F&B managers expect visual dashboards
3. **Trust** - Building trust by showcasing the process
4. **Accessibility** - Works in noisy restaurant environments

## Architecture Vision

### Current Stack (Phase 1-3)

- **Dashboard:** Aetherix (Streamlit) — primary interface
- **LLM:** Claude Sonnet 4 (reasoning), Mistral Embed (embeddings)
- **Vector DB:** Qdrant (495 patterns, semantic search)
- **External APIs:** PredictHQ (events), Weather API (planned)
- **Data Source:** Kaggle-derived patterns, Supabase for feedback

### Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Done | Backend MVP — Prediction + Reasoning engines |
| Phase 2 | ✅ Done | RAG — Vector search with 495 patterns |
| Phase 3 | 🔄 Now | Dashboard MVP — Aetherix UI |
| Phase 4 | 📋 Next | Feedback Loop — Accuracy tracking |
| Phase 5 | 📋 Later | Integrations — PMS, POS, voice |

## Key Design Principles

### Explainable AI
Never use black-box predictions. Always show reasoning:
- Display 3-5 similar historical patterns
- Explain which factors influenced the prediction (events, weather, seasonality)
- Show confidence levels with predictions

### Augmented Human Decision-Making
Manager retains final control:
- Predictions are suggestions, not automatic actions
- One-click approval with manual adjustment capability
- Build trust through transparency

### Dashboard-First UX
- Primary interface: Aetherix Streamlit dashboard
- Day/Week/Month views, Factors panel, Feedback panel
- Voice/chat planned for Phase 5 (messaging integration)

### Hospitality-Specific
Not generic forecasting:
- Understands restaurant-specific patterns (day of week, service type)
- Factors in proximity-based event impact (5km radius)
- Accounts for guest behavior patterns unique to F&B

## Data Flow Architecture

### Prediction Pipeline
1. **Historical Pattern Retrieval:** Query Qdrant for similar past scenarios using vector embeddings (day type, season, occupancy)
2. **Event Enrichment:** PredictHQ API for concerts, festivals, sports events within 5km
3. **Weather Context:** Weather API for forecast conditions
4. **LLM Synthesis:** Claude generates prediction with confidence score and reasoning
5. **Manager Review:** Dashboard presents prediction with explainability
6. **Validation Loop:** Post-service feedback updates accuracy metrics

### Data Privacy
- No sensitive guest PII stored
- Only aggregate metrics (covers, timestamps, revenue bands)
- Manager identity and restaurant metadata kept minimal

## Development Notes

### Cost Optimization
Target <$10/restaurant/month for MVP viability:
- Prefer Mistral over OpenAI for embeddings
- Use Qdrant free tier (generous for single-restaurant use case)
- Cache weather/event data aggressively
- Batch POS data syncs (daily, not real-time)

### Accuracy Measurement
Implement systematic tracking:
- Store predictions with timestamps and confidence scores
- Compare against actual POS covers post-service
- Calculate rolling accuracy metrics (weekly, monthly)
- Flag prediction errors >20% for model refinement

### Event API Integration
PredictHQ critical for accuracy:
- Focus on attended events (concerts, sports) not virtual
- Use PHQ Rank/attendance estimates for weighting
- 5km radius configurable per restaurant location
- Cache events for cost control

### Vector Similarity Design
Qdrant embeddings should capture:
- Temporal features: day of week, month, holiday proximity
- Operational features: covers, service type, duration
- External features: event presence, weather conditions, season
- Use cosine similarity to find top 5 historical matches

## Testing Strategy

### Accuracy Validation
- Requires real historical POS data for meaningful testing
- Minimum 6 months of historical data for pattern recognition
- Test against known scenarios (major past events)
- Compare agent predictions vs manager's original decisions

### API Resilience
- Handle PredictHQ rate limits gracefully
- Cache weather forecasts (update 2x daily max)
- Fallback to historical-only predictions if APIs unavailable
- Never block manager workflow on external API failures

## Integration Points

### POS Systems (Future)
Target integrations for cover data:
- Toast, Square, Lightspeed, Clover (common mid-market)
- Daily batch sync sufficient (not real-time)
- Only need: covers count, timestamp, revenue band

### Scheduling Tools (Phase 5)
Post-MVP auto-push to:
- 7shifts, When I Work, Homebase
- Requires staffing ratio logic (covers → headcount)

### Manager Communication
- Dashboard primary (Aetherix Streamlit)
- Voice/chat secondary (Phase 5: WhatsApp, Slack, Teams)

## Current Repository State

- **Phase 1-2:** Backend and RAG complete, deployed on HuggingFace
- **Phase 3:** Dashboard (Aetherix) live at https://aetherix.streamlit.app
- **Next:** Feedback loop accuracy tracking, History view

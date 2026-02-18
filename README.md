---
title: F&B Agent API
emoji: 🍽️
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "4.0.0"
python_version: "3.11"
app_port: 7860
pinned: false
---

# Aetherix – F&B Ambient Agent  
**PMS-agnostic intelligence layer to anticipate staffing & F&B needs in hotels**

> (AI) Insights learn from and come to you (WhatsApp, Slack, Teams) instead of yet another dashboard to onboard.
> Contextual predictions + feedback loop + explainability, no vendor lock-in.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-Live-orange?logo=streamlit)](https://aetherix.streamlit.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HF Spaces](https://img.shields.io/badge/HuggingFace-Spaces-blueviolet)](https://huggingface.co/spaces/ivandemurard/fb-agent-api)

## 🎯 Philosophy: Human-in-the-Loop Copilot, not Autopilot

Aetherix is designed as an **intelligent assistant**, not an autonomous decision-maker.

| Autopilot (❌ Not us) | Copilot (✅ Aetherix) |
|-----------------------|----------------------|
| AI decides and acts alone | AI recommends, human validates |
| Black box predictions | Transparent reasoning with impact % |
| Replaces the manager | Augments the manager |
| "Trust me" | "Here's why, do you agree?" |
| Does not evolve | Learns from your context (POS/PMS/TMS) and feedback |

**Why this matters:**
> "In hospitality, the human must remain sovereign. Data is the advisor, not the ruler." - Industry validation

**The feedback loop:**
1. Aetherix predicts → "I expect 47 covers tomorrow"
2. Manager validates → "Looks right" or "Too low, there's an event"
3. Aetherix learns → Accuracy improves over time
4. Repeat

This approach ensures:
- **Accountability**: Human approval for all operational decisions
- **Trust**: Managers understand and can challenge predictions
- **Compliance**: Aligns with EU AI Act requirements for human oversight

---

**Live Dashboard (Phase 3, early prototype)** → https://aetherix.streamlit.app/

### Real Problem (Hospitality 2026)
Restaurant managers spend **5–8 hours/week** on manual forecasting with ~**70%** accuracy → over/under-staffing, food waste, operational stress.

### Solution: A new (AI) Colleague
or agent, that:
- **Anticipates** demand (covers, staffing, purchases) using RAG + external signals (weather, events, holidays, and real-time social sentiment)
- **Explains** its predictions (impact %, confidence score) for transparency and adoption
- **Learns** from your corrections and PMS data (feedback loop) for continuous and autonomous improvement
- **Delivers where you work**: WhatsApp/Slack for quick briefs, dashboard for adoption, config & deep dive
- **PMS-agnostic**: using a semantic layer connecting Mews, Opera, Apaleo, Cloudbeds, etc. without lock-in. Smart!

| Classic Dashboard            | Ambient Agent (Aetherix)              |
|------------------------------|----------------------------------------|
| You have to remember to check| Agent proactively sends you the brief |
| Painful context switching    | Integrated into your daily tools       |
| Feedback = separate step     | Natural correction in conversation     |
| PMS + external data silos    | Semantic unification + contextual RAG  |

### Architecture (3 Layers)

Voir le diagramme SVG ci-dessous dans la section Architecture.

---

## 💡 The solution I'm working on:

An **intelligence layer** for hotel managers that:
- **Connects to any PMS** through a semantic abstraction layer (Mews, Opera, Apaleo, Protel, Cloudbeds, ...)
- **Predicts demand** using RAG architecture with internal and external historical pattern matching
- **Explains reasoning** so managers can trust and correct predictions (transparency)
- **Learns from feedback** to improve accuracy over time (feedback loop)
- **Lives where you work** : via a dashboard for analytics, and messaging apps for daily operations

---

## 🏗️ Architecture: ML + LLM Hybrid

Aetherix uses a **hybrid architecture** separating calculation from explanation:

```
┌─────────────────────────────────────────────────────┐
│                    DATA LAYER                       │
│  Qdrant (patterns) + Weather API + Events API      │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│              PREDICTION ENGINE (ML)                 │
│                                                     │
│  Prophet (Meta) - Deterministic calculation         │
│  • Same input = same output (testable)             │
│  • No hallucination risk on numbers                │
│  • Handles seasonality automatically               │
│                                                     │
│  Output: { predicted: 47, range: [42, 52] }        │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│              REASONING ENGINE (LLM)                 │
│                                                     │
│  Claude (Anthropic) - Explanation only             │
│  • Receives the calculated number                  │
│  • Generates human-readable reasoning              │
│  • Never calculates, only explains                 │
│                                                     │
│  Output: "47 covers expected because..."           │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                 DELIVERY LAYER                      │
│  Dashboard (Next.js) • WhatsApp/Slack (planned)    │
│                                                     │
│  + FEEDBACK LOOP: Manager corrections → Model      │
└─────────────────────────────────────────────────────┘
```

**Why separate ML and LLM?**

| Concern | ML (Prophet) | LLM (Claude) |
|---------|--------------|--------------|
| **Numbers** | ✅ Deterministic, reliable | ❌ Can hallucinate |
| **Explanations** | ❌ Can't generate text | ✅ Natural language |
| **Reproducibility** | ✅ Same input = same output | ❌ May vary |
| **Auditability** | ✅ Traceable calculations | ❌ Black box |

> "LLMs are poets, not accountants. For forecasting, use deterministic ML models." - Audit feedback

<img src="https://raw.githubusercontent.com/IvandeMurard/Hospitality-Operations-Agentic-AI-B2B/main/docs/assets/architecture-value.svg" width="100%" alt="Aetherix Architecture Value Diagram showing layered architecture with feedback loop" loading="lazy">

---

## ✨ Key Features

**🧠 Contextual Predictions**
- Combines external signals (city events, weather, holidays, real-time social sentiment) with internal data (occupancy, past demand)
- Qdrant vector search finds similar historical patterns
- Claude AI generates explainable reasoning

**🔍 Transparent Reasoning**
- Every prediction shows WHY with a clear breakdown of impact percentages
- Confidence scoring based on pattern match quality

**🧮 Deterministic Predictions**
- ML-based calculation (Prophet) ensures reproducibility
- Same date + same conditions = same prediction
- No LLM hallucination risk on numbers
- Auditable and testable forecasts

**🔄 Learning Feedback Loop**
- Pre-service validation: "Does 26 covers look right to you?"
- Post-service feedback: Actual covers input
- Visible accuracy improvement: "Your feedback improved accuracy: 68% → 74%"

**🔗 PMS-Agnostic Integration**
- Semantic layer abstracts any PMS API
- No vendor lock-in, it will work with Mews, Opera, Protel, Cloudbeds
- Adding new PMS = new adapter, not agent rewrite

**📱 Ambient Experience**
- Dashboard-first design (Aetherix UI live)
- Dashboard for transparency, settings, analytics, and complex planning
- Voice/chat in messaging apps (WhatsApp, Slack, Teams) planned for Phase 5

---

## 📊 Data Sources & Signals

Aetherix combines **internal operations data**, **external signals**, and **reservation behavior** to generate accurate predictions.

### Internal Data (from PMS/POS)

| Signal | Description | Impact Example |
|--------|-------------|----------------|
| **Occupancy rate** | Hotel rooms booked vs available | 95% occupancy → +20% dinner covers |
| **Capture rate** | % of hotel guests eating at restaurant | 15% capture × 80 guests = 12 internal covers |
| **Guest segmentation** | Leisure vs Corporate vs Group | Corporate = low lunch, high breakfast |
| **Historical covers** | Past performance by day/season | "Last Tuesday = 42 covers" |
| **Restaurant profile** | Capacity, breakeven, staff ratios | Breakeven = 35 → below = alert |

### External Signals (from APIs)

| Signal | Source | Impact Example |
|--------|--------|----------------|
| **Weather** | OpenWeather API | Rain → +15% dinner (guests stay in) |
| **City events** | PredictHQ API | Fashion Week → -20% lunch, +30% late dinner |
| **Holidays** | Calendar API | Bank holiday → +25% brunch |
| **Transport disruptions** | Manual signal | RATP strike → -external, +internal capture |
| **Social buzz** | Manual signal | Viral post → +10% walk-ins |

### No-Show Prediction Factors

| Factor | Description | Impact on No-Show Rate |
|--------|-------------|------------------------|
| **Reservation source** | TheFork -50% vs Concierge | Discount = higher no-show risk |
| **Lead time** | Days between booking and date | 3 months ahead = higher risk |
| **Credit card guarantee** | Deposit taken via Zenchef/SevenRooms | Guarantee → no-show ≈ 0% |
| **Weather forecast** | Heavy rain predicted | Rain → +30% external no-shows |
| **Transport forecast** | Strike announced | Strike → massive no-show spike |

### Data Flow

```
INTERNAL (PMS)          EXTERNAL (APIs)         RESERVATIONS (TMS)
     │                        │                        │
     ├─ Occupancy             ├─ Weather               ├─ Source (TheFork, etc.)
     ├─ Capture rate          ├─ Events                ├─ Lead time
     ├─ Segmentation          ├─ Holidays              ├─ Guarantee status
     ├─ Historical            ├─ Disruptions           └─ Party size
     └─ Profile               └─ Buzz signals
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     │
                                     ▼
                        ┌────────────────────────┐
                        │   PREDICTION ENGINE    │
                        │   (Prophet + Claude)   │
                        └────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            Covers Prediction               No-Show Prediction
            "47 covers expected"            "12% no-show risk"
                    │                                 │
                    └────────────────┬────────────────┘
                                     ▼
                        ┌────────────────────────┐
                        │   RECOMMENDATIONS      │
                        │   Staff: 3 servers     │
                        │   Overbooking: +5      │
                        └────────────────────────┘
```

### Current Status

| Data Source | Status | Notes |
|-------------|--------|-------|
| Historical patterns (Qdrant) | ✅ Live | 495 patterns from Kaggle dataset |
| Weather API | ✅ Live | OpenWeather integration |
| Events API | ✅ Live | PredictHQ integration |
| PMS integration | 🔜 Planned | Mews connector in roadmap |
| TMS integration | 🔜 Planned | Zenchef/SevenRooms planned |
| Social signals | 🔜 Planned | Manual input first, API later |
| No-show prediction | 🔜 Planned | Separate module (IVA-91) |

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | REST API, orchestration |
| **Prediction (ML)** | Prophet (Meta) | Deterministic demand forecasting |
| **Reasoning (LLM)** | Claude Sonnet 4 (Anthropic) | Explanation generation (no calculation) |
| **Embeddings** | Mistral Embed | Vector embeddings for semantic search |
| **Vector DB** | Qdrant Cloud | Semantic pattern search (495 patterns) |
| **Database** | Supabase (PostgreSQL) | Profiles, predictions, feedback, accuracy |
| **Cache** | Redis (Upstash) | Session state, conversation context |
| **Frontend** | Streamlit (MVP) / Next.js (v2) | Dashboard interface |
| **Deployment** | HuggingFace Spaces (Docker) | Cloud hosting |

---

## 🔒 Privacy & Compliance

**Data handling:**
- All predictions use **aggregated patterns**, not individual guest data
- No PII (Personally Identifiable Information) is sent to LLM APIs
- Historical patterns are anonymized before vectorization

**GDPR compliance:**
- Data minimization: Only operational data required for predictions
- Right to explanation: Every prediction includes transparent reasoning
- Human oversight: Manager validation required for operational decisions

**EU AI Act alignment:**
- Human-in-the-loop design (Copilot, not Autopilot)
- Explainable AI: Impact factors visible for every prediction
- No fully automated decisions affecting individuals

---

## 🚀 Live Demo

**Primary dashboard:** [https://aetherix.streamlit.app](https://aetherix.streamlit.app) (Streamlit Cloud)  
**Also:** [https://ivandemurard-fb-agent-api.hf.space](https://ivandemurard-fb-agent-api.hf.space) (HuggingFace Space: dashboard + API; API docs at `/docs`)

### Deployment

| Component | Status | URL |
|-----------|--------|-----|
| **Dashboard (primary)** | ✅ Live | [aetherix.streamlit.app](https://aetherix.streamlit.app) |
| HF Space (dashboard + API) | ✅ Live | [ivandemurard-fb-agent-api.hf.space](https://ivandemurard-fb-agent-api.hf.space) |
| Vector DB | ✅ Live | Qdrant Cloud (495 patterns) |

**Sync:** One push to `main` updates both: a GitHub Action syncs `main` → `master`, so Streamlit Cloud (on `master`) and the HF Space (on `main`) deploy the same code.

**Docker:** The default `Dockerfile` runs API (port 8000) + Streamlit dashboard (port 7860) for the HF Space. For API-only deployment use `Dockerfile.api`.

---

## 📈 Roadmap

### ✅ Phase 1 - Backend API (Complete)

Delivered:
- Multi-agent system (Demand Predictor, Staff Recommender, Reasoning Engine)
- Context-aware prediction with mock patterns
- Confidence scoring + explainable reasoning
- HuggingFace Spaces deployment

### ✅ Phase 2 - RAG Implementation (Complete)

Delivered:
- Kaggle Hotel Booking dataset processed (119K reservations → 495 F&B patterns)
- Qdrant vector database with Mistral embeddings
- Semantic similarity search powering predictions
- Live API with real vector search

### 🔄 Phase 3 - Dashboard & Feedback Loop (Current)

In progress:
- **Restaurant Profile**: Capacity, breakeven, staff ratios configuration
- **Post-service Feedback**: Actual covers input to close the loop
- **Accuracy Tracking**: Real MAPE calculation, visible learning progress
- **UI Anti-Slop**: Factor visibility, human context, contextual recommendations
- **Data Sources UI**: Transparent architecture roadmap in Settings

Linear issues: IVA-52, IVA-53, IVA-54, IVA-55, IVA-56

### 📋 Phase 4 - Feedback Loop + Accuracy (Next)

Planned:
- **Post-service Feedback**: Actual covers input to close the loop
- **MAPE Tracking**: Real accuracy calculation and display
- **Prediction History**: Accuracy history view
- **Continuous Learning**: Pipeline from feedback to model improvement

### 🔮 Phase 5 - Integrations (Future)

Vision:
- **PMS Connectors**: Mews, Opera, Protel adapters
- **POS Auto-sync**: Real cover data from Toast, Square, etc.
- **Voice/Chat Interface**: WhatsApp, Slack, Teams (ambient AX)
- **What-if Scenario Modeling**

---

## ⚙️ Configuration

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...          # Claude AI
QDRANT_API_KEY=...                    # Vector database
QDRANT_URL=https://...                # Qdrant cluster URL
MISTRAL_API_KEY=...                   # Embeddings generation

# Database
SUPABASE_URL=...                      # PostgreSQL
SUPABASE_KEY=...                      # Database auth

# Optional (for enhanced features)
REDIS_URL=...                         # Session cache
PREDICTHQ_API_KEY=...                 # Events data
OPENWEATHER_API_KEY=...               # Weather data
ELEVENLABS_API_KEY=...                # Voice interface
```

### Tech Stack

- **Backend**: FastAPI · Python 3.11
- **Prediction (ML)**: Prophet (Meta)
- **Reasoning (LLM)**: Claude Sonnet 4 (Anthropic) · Mistral Embeddings
- **Vector DB**: Qdrant Cloud (495 patterns indexed)
- **Storage**: Supabase (PostgreSQL) · Redis (cache & sessions)
- **Frontend MVP**: Streamlit · (Next.js planned for v2)
- **Deploy**: Hugging Face Spaces (Docker)

## **Looking for**  
- **Feedback on project** DM me on X @ivandemurard or [Book a call](https://cal.com/ivandemurard/30min)
- Beta hotels or restaurants (currently using mock data to start)
- Tips
- A product / AI role in hospitality tech SaaS

**Say Hi!**

Built with ❤️ by Ivan de Murard for hotels, restaurants, and those who love them
[Portfolio](https://ivandemurard.com) · [X](https://x.com/ivandemurard) · [LinkedIn](https://linkedin.com/in/ivandemurard) · ivandemurard@gmail.com

MIT License


---
title: F&B Operations Agent
emoji: 🍽️
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "4.0.0"
python_version: "3.11"
pinned: false
---

# F&B Operations Agent

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Active%20Development-green)](https://github.com/yourusername/fb-agent)
[![Deployment](https://img.shields.io/badge/Deployed-HuggingFace-FF9D00?logo=huggingface&logoColor=white)](https://huggingface.co/spaces/IvandeMurard/fb-agent-api)

> **An intelligence layer that lives WHERE you work, not another dashboard to check.**
>
> AI-powered demand forecasting for hotel F&B operations. With easy connect to any PMS through a semantic abstraction, delivering insights where managers actually work: dashboard, WhatsApp, Slack, or PMS.

---

## 🎯 Vision

Most hotel tech adds another screen to check. The F&B Operations Agent takes a different approach:

| Traditional Dashboard | Ambient Agent |
|----------------------|---------------|
| Manager must remember to check | Agent comes to the manager |
| Context switch required | Lives in existing workflows |
| Passive data consumption | Active dialogue & continuous learning |
| Feedback is an extra step | Feedback is a natural reply |

**The goal:** An agent that feels like a knowledgeable colleague who messages you with tomorrow's forecast, learns from your corrections, and gets smarter over time, learning from your context.

---

## 🎯 Problem

Restaurant managers in hotels spend **5-8 hours/week** manually forecasting staffing needs with **~70% accuracy**, correlating data across siloed systems (PMS, event calendars, weather apps). This results in:
- Over/under-staffing → operational stress & revenue loss
- No integrations between the external context and the internal operations
- Food waste from inaccurate demand predictions
- Missed customer experience improvement opportunities

---

## 💡 The solution I'm working on:

An **intelligence layer** for hotel managers that:
- **Connects to any PMS** through a semantic abstraction layer (Mews, Opera, Apaleo, Protel, Cloudbeds, ...)
- **Predicts demand** using RAG architecture with internal and external historical pattern matching
- **Explains reasoning** so managers can trust and correct predictions (transparency)
- **Learns from feedback** to improve accuracy over time (feedback loop)
- **Lives where you work** : via a dashboard for analytics, and messaging apps for daily operations

---

## 🏗️ Architecture

### Flow View

<img src="docs/assets/architecture-flux.svg" width="100%" alt="Aetherix Architecture Flow Diagram showing Semantic, Intelligence, and Delivery layers" loading="lazy">

### Concentric View

<img src="docs/assets/architecture-concentric.svg" width="80%" alt="Aetherix Architecture Concentric Diagram showing hotel systems, semantic layer, intelligence layer, and delivery channels" loading="lazy">
---

## ✨ Key Features

**🧠 Contextual Predictions**
- Combines external signals (city events, weather, holidays, real-time social sentiment) with internal data (occupancy, past demand)
- Qdrant vector search finds similar historical patterns
- Claude AI generates explainable reasoning

**🔍 Transparent Reasoning**
- Every prediction shows WHY with a clear breakdown of impact percentages
- Confidence scoring based on pattern match quality

**🔄 Learning Feedback Loop**
- Pre-service validation: "Does 26 covers look right to you?"
- Post-service feedback: Actual covers input
- Visible accuracy improvement: "Your feedback improved accuracy: 68% → 74%"

**🔗 PMS-Agnostic Integration**
- Semantic layer abstracts any PMS API
- No vendor lock-in — works with Mews, Opera, Protel, Cloudbeds
- Adding new PMS = new adapter, not agent rewrite

**📱 Ambient Experience**
- Dashboard-first design (Aetherix UI live)
- Dashboard for transparency, settings, analytics, and complex planning
- Voice/chat in messaging apps (WhatsApp, Slack, Teams) planned for Phase 5

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.11 | REST API, multi-agent orchestration |
| **AI/ML** | Claude Sonnet 4 (Anthropic) | Reasoning engine, natural language explanations |
| **Embeddings** | Mistral Embed | Vector embeddings for semantic search (1024 dim) |
| **Vector DB** | Qdrant Cloud | Semantic pattern search (495 patterns) |
| **Database** | Supabase (PostgreSQL) | Restaurant profiles, predictions, feedback, accuracy |
| **Cache** | Redis (Upstash) | Session state, conversation context |
| **Frontend** | Streamlit (MVP) / Next.js (v2) | Dashboard interface |
| **Deployment** | HuggingFace Spaces (Docker) | Cloud hosting, auto-scaling |

---

## 🚀 Live Demo

🔗 **Live Dashboard:** [https://aetherix.streamlit.app](https://aetherix.streamlit.app)  
🔗 **API:** [https://ivandemurard-fb-agent-api.hf.space](https://ivandemurard-fb-agent-api.hf.space)  
🔗 **API Docs:** [https://ivandemurard-fb-agent-api.hf.space/docs](https://ivandemurard-fb-agent-api.hf.space/docs)

### Current Status

- ✅ Phase 1: Backend MVP (prediction engine, reasoning)
- ✅ Phase 2: RAG with Qdrant (495 patterns, semantic search)
- 🔄 Phase 3: Dashboard MVP (Aetherix)

### Deployment

| Component | Status | URL |
|-----------|--------|-----|
| Dashboard | ✅ Live | [aetherix.streamlit.app](https://aetherix.streamlit.app) |
| API | ✅ Live | [HuggingFace Spaces](https://ivandemurard-fb-agent-api.hf.space) |
| Vector DB | ✅ Live | Qdrant Cloud (495 patterns) |

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

---

## 📂 Project Structure

```
fb-agent/
├── backend/
│   ├── agents/                  # Intelligence Layer
│   │   ├── coordinator.py       # Request routing
│   │   ├── demand_predictor.py  # Qdrant vector search + prediction
│   │   ├── staff_recommender.py # Staffing calculations
│   │   └── reasoning_engine.py  # Claude explanations
│   ├── semantic_layer/          # PMS Abstraction (Phase 4)
│   │   ├── schemas.py           # Unified data models
│   │   ├── base_adapter.py      # PMSAdapter ABC
│   │   └── adapters/            # Mews, Opera, Protel
│   ├── api/
│   │   └── routes.py            # FastAPI endpoints
│   ├── models/                  # Pydantic schemas
│   ├── scripts/                 # Data processing
│   │   ├── derive_covers.py     # Kaggle → F&B patterns
│   │   └── seed_qdrant.py       # Patterns → Qdrant
│   ├── data/
│   │   ├── raw/                 # Source datasets
│   │   └── processed/           # 495 patterns
│   └── tests/
├── frontend/
│   └── app.py                   # Streamlit dashboard
├── docs/
│   ├── ARCHITECTURE.md
│   └── CASE_STUDY.md
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 💼 Portfolio Context

With this project, I reinforce:

**Product Thinking**
- Problem framing from real hospitality pain points
- MVP scoping with a clear value hypothesis
- Roadmap driven by user value (ICE scoring)
- Build in a public approach

**Technical Execution**
- RAG architecture with production vector database
- Multi-agent system with explainable AI
- PMS-agnostic design (semantic layer pattern)
- API-first, integration-ready architecture

**Industry Knowledge**
- Hospitality operations understanding (hands-on experience, PMS landscape)
- Competitive analysis (Mews, Apaleo, IDeaS, Duetto)
- Market positioning (intelligence layer, not replacement)

**Open for Product Manager - Builder roles**

**Full Case Study:** [ivandemurard.com](https://ivandemurard.com)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

---

## 📬 Contact

**Ivan de Murard**  
AI Zero-to-One Product Manager

- 📅 Book a Call: [cal.com](https://cal.com/ivandemurard/30min)
- 🌐 Portfolio: [ivandemurard.com](https://ivandemurard.com)
- 💼 LinkedIn: [linkedin.com/in/ivandemurard](https://linkedin.com/in/ivandemurard)
- 🐦 Twitter/X: [@ivandemurard](https://twitter.com/ivandemurard)
- 📧 Email: ivandemurard@gmail.com

---

**Built with ❤️ for the hospitality industry**

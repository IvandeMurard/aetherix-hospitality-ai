# F&B Operations Agent

> AI-powered demand forecasting for hotel Food & Beverage operations,
> built on the Model Context Protocol (MCP).

Built for the **Pioneers AILab Hackathon** · Qdrant Track

---

## The Problem

Hotel F&B managers make staffing and procurement decisions 24–48 hours
in advance, with no tools that combine their PMS data, local events, and
weather into a single actionable forecast. The result: chronic
over-staffing on quiet nights and under-staffing when a concert or
conference spills into the restaurant.

This project solves that with an AI agent that pulls all three signals
through a single protocol (MCP) and delivers a structured operational
recommendation in plain English.

---

## Architecture

```
User query (date + location)
        │
        ▼
  Agent Router  ──────────────────────────────────────────────┐
        │                                                      │
   ANTHROPIC_API_KEY set?                                      │
        │ yes                                                  │ no
        ▼                                                      ▼
  MCP Agent (Claude)                             Autonomous Agent (Mistral)
        │ MCP protocol                                    │ direct calls
        ▼                                                      ▼
  Hotel Context Layer                               agents/ modules
  (hotel_context_server.py)                     ┌──────────────────────┐
  ┌──────────────────────────────────┐           │ Analyzer             │
  │  PMS Server  ←→  Apaleo API      │           │ PatternSearch(Qdrant)│
  │  Events Server ← PredictHQ       │           │ Predictor (Mistral)  │
  │  Weather Server ← OpenWeather    │           │ Voice (ElevenLabs)   │
  │  Pattern Memory ← Qdrant         │           └──────────────────────┘
  └──────────────────────────────────┘
```

Both paths produce the same structured output: expected covers,
recommended staff count, confidence score, and key factors.

**The MCP path is the primary architecture.** The direct path is a
graceful fallback when Claude / MCP servers are unavailable.

---

## Key Design Decisions

**MCP as the hotel integration layer.**
Each hotel system (PMS, events, weather, memory) is a standalone MCP
server. The AI agent discovers and calls tools through the protocol —
zero hardcoded integrations. Adding a new system means shipping a new
MCP server, not editing the agent.

**Apaleo PMS integration.**
`mcp_servers/pms_server.py` calls the Apaleo Booking and Inventory APIs
via OAuth2 client credentials. Token is cached and refreshed
automatically. Falls back to mock data when credentials are not set,
so the demo always works.

**Pattern memory in Qdrant.**
Historical F&B scenarios (actual covers, staffing, outcome) are stored
as embeddings. At query time, the agent retrieves the 3 most similar
past events by cosine similarity to anchor its prediction.

**Vendor-agnostic by design.**
The routing layer (`agent_router.py`) picks the best available path at
runtime. Swapping the LLM or any hotel system requires only a registry
update, not code changes.

---

## Repository Structure

```
.
├── api.py                        FastAPI REST endpoint (/predict)
├── mcp_agent.py                  Claude MCP agent (primary path)
├── agent_router.py               Routes between MCP and direct paths
├── autonomous_agent.py           Mistral-based fallback agent
├── demo_app.py                   Streamlit demo UI
├── seed_data.py                  Seeds Qdrant with historical scenarios
├── setup_qdrant.py               Creates Qdrant collection
│
├── mcp_servers/
│   ├── hotel_context_server.py   Unified MCP server (all tools)
│   ├── pms_server.py             PMS tools — Apaleo API or mock
│   ├── events_server.py          Local events — PredictHQ API or mock
│   ├── weather_server.py         Weather — OpenWeatherMap API or mock
│   └── registry.py               Server registry and availability checks
│
├── agents/
│   ├── analyzer.py               Parses query into structured features
│   ├── pattern_search.py         Qdrant vector search
│   ├── predictor.py              LLM reasoning → structured prediction
│   ├── events_fetcher.py         PredictHQ client
│   ├── weather_fetcher.py        OpenWeatherMap client
│   └── mock_data_fetcher.py      Offline fallback data
│
├── tests/
│   ├── test_full_pipeline.py     End-to-end pipeline tests
│   └── test_scenarios.py         Scenario-based agent tests
│
├── docs/
│   ├── quick_start.md            5-minute setup guide
│   ├── demo_script.md            Live demo walkthrough
│   ├── integration_report.md     API integration details
│   ├── validation_report.md      Test results and validation
│   ├── roadmap.md                Development roadmap
│   └── presentation.md           Full project presentation
│
├── .env.example                  Credential template (copy → .env)
└── requirements.txt
```

---

## Setup

### 1. Install dependencies

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
# Fill in your keys — see .env.example for all variables
```

Required for the MCP path (Claude agent):
```
ANTHROPIC_API_KEY=...
```

Required for the direct path (Mistral agent):
```
MISTRAL_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
```

Optional — activates real data instead of mock:
```
APALEO_CLIENT_ID=...          # Apaleo PMS (reservations)
APALEO_CLIENT_SECRET=...
APALEO_PROPERTY_ID=MUC        # 3-letter property code
PREDICTHQ_API_KEY=...         # Local events
OPENWEATHER_API_KEY=...       # Weather forecast
ELEVENLABS_API_KEY=...        # Voice output
```

Every integration falls back to realistic mock data when its key is
absent — the agent always produces a usable output.

### 3. Seed pattern memory

```bash
python seed_data.py
```

### 4. Run

**MCP agent (recommended):**
```bash
python agent_router.py --date 2025-12-24 --location "Paris, France"
```

**REST API:**
```bash
uvicorn api:app --reload --port 8000
# POST http://localhost:8000/predict
```

**Streamlit demo:**
```bash
streamlit run demo_app.py
```

---

## Sample Output

```
Date: Saturday 2025-12-24 | Location: Paris, France

DEMAND FORECAST
  Expected covers:      94
  Recommended staff:    6
  Confidence:           87%

KEY FACTORS
  · Christmas Eve — strong in-house dining demand
  · Weather: clear, 4°C — no outdoor seating, indoor fully utilized
  · 2 corporate groups confirmed (38 guests, full-board)
  · Pattern match: "Dec 24 2023 — 91 covers, 6 staff" (similarity 0.91)

ACTIONS
  · Open private dining room by 18:00
  · Pre-prep for 95+ covers as buffer
  · Assign dedicated sommelier — VIP guests × 4
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Primary LLM | Claude (Anthropic) |
| Fallback LLM | Mistral AI |
| Vector memory | Qdrant |
| PMS | Apaleo (OAuth2 client credentials) |
| Events | PredictHQ |
| Weather | OpenWeatherMap |
| Voice | ElevenLabs |
| Protocol | Model Context Protocol (MCP) |
| API | FastAPI |
| Demo UI | Streamlit |

---

## Credential Security

- `.env` is in `.gitignore` — credentials never committed
- `.env.example` ships with placeholder values only
- Each integration degrades gracefully to mock when its key is absent
- See `.env.example` for the full list of expected variables

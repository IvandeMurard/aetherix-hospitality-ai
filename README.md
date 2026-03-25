
<h1 align="center">Aetherix</h1>
<p align="center">
  <em>Helping Hotel Managers predict their property's operational needs.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=next.js&logoColor=white" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?style=flat&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat&logo=postgresql&logoColor=white" alt="PostgreSQL 17" />
  <img src="https://img.shields.io/badge/Claude-Anthropic-D97706?style=flat&logo=anthropic&logoColor=white" alt="Claude AI" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-22C55E?style=flat" alt="License MIT" />
</p>

## Overview

Aetherix is an Agentic AI solution designed to copilot staff and Food & Beverage forecasting for hotel and restaurant managers.

The tool adapts to the client's IT stack, uses a proactive, UI-less "push" model, and delivers the right insights at the right time.
It synthesizes internal context and property data (occupancy, bookings, PMS, POS, ...) with an external semantic layer, incorporating local events, weather, and reputation.

**Key insight:** The agent models each property's historical capture rate and applies contextual demand to generate recommendations that align with each property's reality.

The result: Contextualized intelligence, helping reduce food waste (hotels waste ~25% of food produced), labor costs, and, most importantly, giving more time to managers to focus on their customers.

### The Problem vs. The Aetherix Solution

| Feature | The Problem (Traditional "Pull") | The Solution (Proactive "Push") |
| :--- | :--- | :--- |
| **Data Interaction** | Requires manual login & dashboard checks | Proactive alerts via Slack, WhatsApp, or Email |
| **Forecasting** | Guesswork based on static historical reports | Contextualized ML/LLM predictions calibrated per property |
| **Explainability** | Leaves manager to decipher the "So What?" | Delivers clear, high-ROI operational directives with risk level + Conversational ("Why?", "What if -10% occupancy?")|
| **Context** | Siloed PMS data | Synthesized internal (PMS + capture rate) + external (weather, events) data |
| **Demand modeling** | Occupancy rate used as proxy for covers | Property-specific capture rate × contextual modifiers |
| **Integration model** | Full WFM platform replacement | Additive layer on top of existing tools |

---

## Key Features & Innovation

*   **Semantic Reasoning Engine:** Mathematical translation of chaotic external data (weather, events, real-time social sentiment) into specific, high-ROI operational directives (revenue opportunity vs. labor cost). Output example: *"Dinner covers +22% tonight - concert nearby + high occupancy. Recommendation: add 1 server, prep +18% portions. Risk: High if unchanged."*
*   **Conversational Receipts (Zero-Dashboard Trust):** If a manager questions a recommendation (e.g., replies "Why?"), Aetherix responds instantly with a clear and immediately scannable breakdown with historical context. Trust is built by clearly explaining contextualised business decisions in an adapted language.
*   **Property-Calibrated Demand Modeling:** Aetherix learns each property's real capture rate (% of in-house guests who dine on-site), not a theoretical industry ratio. A property in Paris with 10% capture behaves fundamentally differently from a mountain resort at 80%. The model adapts.
*   **Painless Pilot & 1-Way Sync:** Designed for zero-friction integration. Aetherix requires only a read-only webhook/API key from legacy or modern PMS systems (Mews, Apaleo, etc.) to begin establishing baselines.

---

## How Aetherix Differs from WFM Tools

Aetherix operates on a **forecast-first** paradigm. The schedule is the manager's job. Aetherix answers the question that comes before:

> **"How busy will (...) actually be, what should be adjusted, and why?"**

---

## Built with the BMAD Methodology

Aetherix was conceived, structured, and validated using the rigorous **BMAD (Business, Market, Architecture, Design)** methodology. This ensures the project is not just a technical proof-of-concept, but a viable SaaS product.

*   **Business Justification:** Clear financial ROI and metrics for success (e.g., Target MAPE < 15%, Labor Cost reduction).
*   **Domain Compliance:** Explicit architectural decisions to handle GDPR (anonymized PII) and European Labor Laws (calculating penalty pay into recommendations).
*   **Traceable Architecture:** Documented logic separating business requirements from technical implementation layers.

Roadmap hosted on [Linear](https://linear.app/hospitalityagent/team/HOS/all)
---

## Architecture & Technical Strategy

The architecture adheres to a strict "Thin Frontend / Fat Backend" philosophy. The intelligence stack has four distinct layers working in sequence to produce a single actionable recommendation.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'edgeLabelBackground': '#1e1e2e', 'lineColor': '#6b7280'}}}%%
graph TD
    subgraph EXT["📡 External Integrations"]
        PMS["Mews/Apaleo PMS\n(Read-Only)"]
        Weather["Weather API"]
        Events["PredictHQ Events"]
    end

    subgraph BACK["⚙️ Fat Backend — FastAPI + Python"]
        Sync["PMS Sync\n+ Captation Rate"]
        Semantic["Semantic Reasoning\n+ Anomaly Detection"]
        RAG["Claude Sonnet\nReasoning Engine"]
        Explain["Explainability\nService"]
    end

    subgraph DATA["🗄️ Intelligence Layers"]
        DB[("Supabase PostgreSQL\nOperational data")]
        Vector[("Qdrant Cloud\nF&B patterns · 495+")]
        Memory[("pgvector · operational_memory\nPer-hotel feedback loop\n→ Backboard.io (Phase 3)")]
    end

    subgraph DELIVERY["🚀 Delivery & UI"]
        Push["WhatsApp / SMS / Email\n(UI-less, push-first)"]
        Frontend["Next.js Dashboard\n(verification layer)"]
    end

    PMS -- "Webhooks/API" --> Sync
    Weather --> Semantic
    Events --> Semantic
    Sync --> DB
    Semantic --> Vector
    DB --> RAG
    Vector --> RAG
    Memory --> RAG
    RAG --> Explain
    Explain -- "Recommendation + Why?" --> Push
    Explain -- "Typed API (openapi-fetch)" --> Frontend
    RAG -- "Learn from feedback" --> Memory

    classDef external  fill:#0f2744,stroke:#3b82f6,stroke-width:2px,color:#bfdbfe
    classDef backend   fill:#2d1b69,stroke:#a855f7,stroke-width:2px,color:#e9d5ff
    classDef db        fill:#052e16,stroke:#22c55e,stroke-width:2px,color:#bbf7d0
    classDef delivery  fill:#431407,stroke:#f97316,stroke-width:2px,color:#fed7aa

    class PMS,Weather,Events external
    class Sync,Semantic,RAG,Explain backend
    class DB,Vector,Memory db
    class Push,Frontend delivery
```

### The Four Intelligence Layers

| Layer | Technology | Role |
| :--- | :--- | :--- |
| **1. Numerical Forecast** | Prophet (time-series) | Predicts covers volume from PMS + occupancy + regressors |
| **2. Semantic Patterns** | Qdrant Cloud (495+ vectors) | Matches current context against similar historical service scenarios |
| **3. Cognitive Memory** | pgvector → Backboard.io (Ph. 3) | Two-layer design. **1. Private Memory** (per hotel, Phase 0–1): ultra-specific idiosyncrasies - what works *only* for this property (real capture rate, manager preferences, non-generalizable local patterns). **2. Hive Memory** (anonymized cross-hotel, Phase 3 via Backboard): patterns grouped by tags (city/resort/airport, clientele type, segment, restaurant size) - enriches predictions with cross-property proof of impact. Each hotel benefits from its own learning *and* collective wisdom, never sharing raw data. |
| **4. Reasoning & Explanation** | Claude Sonnet (Anthropic) | Synthesizes the three layers into a directive with natural-language explanation |

### Tech Stack

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **Frontend (UI)** | Next.js (App Router), Tailwind CSS, shadcn/ui | Verification and oversight layer — not the primary interaction surface |
| **Backend (AI/Logic)** | Python, FastAPI, APScheduler | LLM orchestration, async jobs, push dispatch |
| **Operational DB** | Supabase (PostgreSQL) + RLS | Multi-tenant data isolation, actuals tracking |
| **Pattern Store** | Qdrant Cloud | Vector similarity search for F&B scenario patterns |
| **Cognitive Memory** | pgvector `operational_memory` → Backboard.io (Ph. 3) | Phase 0–1: per-hotel feedback loop via `MemoryProvider` interface. Phase 3: Backboard adds structured insights + anonymized cross-hotel pattern generalization (by segment, location, clientele type). |
| **Delivery** | Twilio (WhatsApp/SMS), SendGrid | UI-less push notifications; inbound "Why?" reply handling |
| **Client-Server Contract** | OpenAPI, `openapi-fetch` | End-to-end type safety |

---

## Project Structure

```text
aetherix/
├── backend/                 # FastAPI — AI orchestration & business logic
│   └── app/
│       ├── api/             # HTTP routes (auth, pms, predictions, reports)
│       ├── db/              # PostgreSQL models & session
│       ├── services/        # Reasoning engine, RAG, PMS sync, WhatsApp…
│       └── integrations/    # External tools: Obsidian (knowledge base), Linear (issues)
├── frontend/                # Next.js App Router UI
│   └── src/
│       ├── app/             # Pages: dashboard, settings, auth
│       ├── components/      # shadcn/ui + feature components
│       └── lib/             # openapi-fetch generated API client
├── docs/                    # Architecture, roadmap, BMAD methodology
├── scripts/                 # Dev & ops utility scripts
├── supabase/                # DB migrations
├── local-shared-data/       # OpenAPI spec shared between backend & frontend
├── docker-compose.yml       # Local dev: backend + frontend + postgres + mailhog
└── archive/                 # Legacy code (pre-FastAPI era) — not used in production
```

---
Made with ❤️ for hotels, restaurants, and those who love them. Ivan de Murard
---
*Aetherix - Contextual Intelligence for Hospitality Operations.* 

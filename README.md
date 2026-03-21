
<h1 align="center">Aetherix</h1>
<p align="center">
  <em>Proactive, Agentic AI for Hospitality F&B Forecasting.</em>
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

Aetherix is an Agentic AI solution designed to solve the manual, anxiety-inducing process of Food & Beverage forecasting for hotel and restaurant managers. 

By transitioning from traditional, static "pull" dashboards to a proactive "push" model, Aetherix anticipates operational load. It synthesizes internal property data (occupancy, bookings) with an external semantic layer—incorporating local events, weather, and real-time social sentiment. 

The result? Contextualized intelligence delivered directly to departmental managers when they need it, empowering them to focus on exceptional customer experiences while reducing food waste and optimizing labor costs.

### The Problem vs. The Aetherix Solution

| Feature | The Problem (Traditional "Pull") | The Solution (Aetherix "Push") |
| :--- | :--- | :--- |
| **Data Interaction** | Requires manual login & dashboard checks | Proactive alerts via SMS, WhatsApp, or Email |
| **Forecasting** | Guesswork based on static historical reports | Contextualized ML/LLM predictions |
| **Actionability** | Leaves manager to decipher the "So What?" | Delivers clear, high-ROI operational directives |
| **Context** | Siloed PMS data | Synthesized internal + external (weather, events) data |

---

## Key Features & Innovation

*   **Semantic Reasoning Engine:** Mathematical translation of chaotic external data (weather, events, traffic) into specific, high-ROI operational directives (revenue opportunity vs. labor cost).
*   **Conversational Receipts (Zero-Dashboard Trust):** If a manager questions a recommendation (e.g., replies "Why?"), Aetherix instantly responds with the mathematical breakdown and historical context. Trust is built via immediate, conversational Q&A, not complex dashboards.
*   **Painless Pilot & 1-Way Sync:** Designed for zero-friction integration. Aetherix requires only a read-only webhook/API key from legacy or modern PMS systems (Mews, Apaleo) to begin establishing baselines.

---

## Built with the BMAD Methodology

Aetherix was conceived, structured, and validated using the rigorous **BMAD (Business, Market, Architecture, Design)** methodology. This ensures the project is not just a technical proof-of-concept, but a viable SaaS product.

*   **Business Justification:** Clear financial ROI and metrics for success (e.g., Target MAPE < 15%, Labor Cost reduction).
*   **Domain Compliance:** Explicit architectural decisions to handle GDPR (anonymized PII) and European Labor Laws (calculating penalty pay into recommendations).
*   **Traceable Architecture:** Documented logic separating business requirements from technical implementation layers.

---

## Architecture & Technical Strategy

The architecture adheres to a strict "Thin Frontend / Fat Backend" philosophy, optimizing for robust LLM orchestration and strict data segregation.

```mermaid
%%{init: {'theme': 'dark', 'themeVariables': {'edgeLabelBackground': '#1e1e2e', 'lineColor': '#6b7280'}}}%%
graph TD
    subgraph EXT["📡 External Integrations"]
        PMS["Mews/Apaleo PMS\n(Read-Only)"]
        Weather["Weather API"]
        Events["PredictHQ Events"]
    end

    subgraph BACK["⚙️ Fat Backend — FastAPI + Python"]
        Sync["PMS Sync Service"]
        Semantic["Semantic Reasoning Engine"]
        RAG["LLM Orchestrator"]
    end

    subgraph DATA["🗄️ Data Storage"]
        DB[("Supabase PostgreSQL")]
        Vector[("pgvector")]
    end

    subgraph DELIVERY["🚀 Delivery & UI"]
        Frontend["Next.js App Router UI"]
        Push["WhatsApp / SMS / Email"]
    end

    subgraph OPS["📋 Ops & Knowledge"]
        Linear["Linear\n(Issue Tracker)"]
        Obsidian["Obsidian Vault\n(OneDrive sync)"]
    end

    PMS -- "Webhooks/API" --> Sync
    Weather --> Semantic
    Events --> Semantic
    Sync --> DB
    Semantic --> Vector
    Vector --> RAG
    DB --> RAG
    RAG -- "Conversational Receipts" --> Push
    RAG -- "Typed API (openapi-fetch)" --> Frontend
    Frontend -- "Typesafe Contract" --> RAG
    RAG -- "Auto-create issues" --> Linear
    RAG -- "Write runbooks/reports" --> Obsidian

    classDef external  fill:#0f2744,stroke:#3b82f6,stroke-width:2px,color:#bfdbfe
    classDef backend   fill:#2d1b69,stroke:#a855f7,stroke-width:2px,color:#e9d5ff
    classDef db        fill:#052e16,stroke:#22c55e,stroke-width:2px,color:#bbf7d0
    classDef delivery  fill:#431407,stroke:#f97316,stroke-width:2px,color:#fed7aa
    classDef ops       fill:#3b2800,stroke:#eab308,stroke-width:2px,color:#fef08a

    class PMS,Weather,Events external
    class Sync,Semantic,RAG backend
    class DB,Vector db
    class Frontend,Push delivery
    class Linear,Obsidian ops
```

### Tech Stack Breakdown

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **Frontend (UI)** | Next.js (App Router), Tailwind CSS, shadcn/ui | "Thin Frontend" presentation and dashboarding. |
| **Backend (AI/Logic)** | Python, FastAPI | "Fat Backend" for LLM chains and async webhook processing. |
| **Data & Reasoning** | Supabase (PostgreSQL), `pgvector` | RAG, similarity search, and tenant isolation (RLS). |
| **Delivery** | Twilio, SendGrid/Postmark | Orchestrating multi-channel push notifications. |
| **Client-Server Contract** | OpenAPI, `openapi-fetch` | End-to-end type safety preventing integration bugs. |
| **Knowledge Base** | Obsidian vault (OneDrive sync) | Runbooks, SOPs, and AI-generated operational reports — local-first, Markdown native. |
| **Issue Tracking** | Linear GraphQL API | Maintenance requests and ops alerts created automatically by the LLM Orchestrator. |

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

---
*Aetherix - Contextual Intelligence for Hospitality.* 

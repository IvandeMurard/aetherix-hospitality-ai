<p align="center">
  <img src="docs/images/banner.png" alt="Aetherix MVP Logo" width="400" style="display: block; margin: auto; padding-bottom: 20px;">
</p>
<h1 align="center">Aetherix</h1>
<p align="center">
  <em>Proactive, Agentic AI for Hospitality F&B Forecasting.</em>
</p>

## Overview

Aetherix is an Agentic AI solution designed to solve the manual, anxiety-inducing process of Food & Beverage forecasting for hotel and restaurant managers. 

By transitioning from traditional, static "pull" dashboards to a proactive "push" model, Aetherix anticipates operational load. It synthesizes internal property data (occupancy, bookings) with an external semantic layer—incorporating local events, weather, and real-time social sentiment. 

The result? Contextualized intelligence delivered directly to departmental managers when they need it, empowering them to focus on exceptional customer experiences while reducing food waste and optimizing labor costs.

### The Problem vs. The Aetherix Solution

*   **The Problem:** Traditional scheduling relies on "pull" mechanics—a manager must log into a dashboard, stare at historical data, and guess the future.
*   **The Solution:** Aetherix pushes clear, highly reliable, and actionable predictions directly to managers via SMS, WhatsApp, or email, exactly when needed.

#### 💡 "The Surge Save" (Core Use Case)
1. **The Context:** It's Tuesday morning. The hotel is at a quiet 45% occupancy. No extra staff scheduled for the evening.
2. **The Intelligence:** Aetherix detects a tech conference relocated next door. Historical data shows similar local events cause a 25% bump in external walk-ins.
3. **The Push:** Aetherix alerts the F&B Manager via WhatsApp: *"Anticipating an extra £1,200 in F&B revenue tonight (6 PM - 9 PM) due to nearby conference. Recommend calling 2 servers and 1 prep cook (est. labor cost: £180). Target: 14 total staff."*
4. **The Action:** The manager secures the staff, captures the external revenue, and avoids a dinner service meltdown.

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

The architecture adheres to a strict "Thin Frontend / Fat Backend" philosophy, optimizing for robust LLM orchestration and data segregation.

*   **Frontend (UI):** Next.js App Router (React), Tailwind CSS, and shadcn/ui.
*   **Backend (AI/Orchestration):** Python + FastAPI. Fully asynchronous to handle long-running LLM chains and webhook processing.
*   **Data & Reasoning:** Supabase (PostgreSQL) integrated with `pgvector` for fast similarity search, retrieval-augmented generation (RAG), and tenant segregation (Row-Level Security).
*   **Delivery Layer:** Push notifications managed via Twilio (SMS/WhatsApp) and SendGrid/Postmark (Email).
*   **Type Safety:** End-to-end type safety between the Python backend and TypeScript frontend using OpenAPI Client generation (`openapi-fetch`).

---

## Project Structure

The repository is structured as a monorepo separating the frontend and backend concerns cleanly:

```text
aetherix-mvp/
├── nextjs-frontend/         # The React/Next.js UI Application
│   ├── src/app/             # App Router pages (Dashboard, Settings)
│   ├── src/components/      # UI components (shadcn/ui)
│   └── src/lib/             # openapi-fetch generated client API
├── fastapi-backend/         # The Python AI/Orchestration Application
│   ├── app/api/             # strictly HTTP presentation routes
│   ├── app/db/              # Supabase/pgvector models
│   └── app/services/        # Business logic, AI reasoning, and PMS Sync
└── docker-compose.yml       # Local dev orchestration
```

---

## Quick Start (Local Development)

The MVP is built on top of the robust [Next.js FastAPI Template](https://github.com/vintasoftware/nextjs-fastapi-template).

**Prerequisites:**
- [Docker](https://www.docker.com/) and Docker Compose.
- [Node.js](https://nodejs.org/) (useful for local frontend linting, but Docker handles execution).

**Bootstrapping the Environment:**

1. **Clone the repository:**
   ```bash
   git clone <repository_url>
   cd aetherix-mvp
   ```

2. **Configure Environment Variables:**
   Copy the `.env.example` templates and fill in the required keys for Supabase/LLM APIs.
   ```bash
   cp fastapi-backend/.env.example fastapi-backend/.env
   cp nextjs-frontend/.env.local.example nextjs-frontend/.env.local
   ```

3. **Start the containers:**
   ```bash
   docker compose up --build
   ```

4. **Access the application:**
   - Frontend: `http://localhost:3000`
   - Backend API Docs (Swagger): `http://localhost:8000/api/docs`

---
*Aetherix - Contextual Intelligence for Hospitality.* 

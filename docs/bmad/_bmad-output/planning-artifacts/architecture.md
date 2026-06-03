---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments: []
workflowType: 'architecture'
project_name: 'Aetherix'
user_name: 'IVAN'
date: '2026-03-10T10:39:12+01:00'
lastStep: 8
status: 'complete'
completedAt: '2026-03-10T12:08:00+01:00'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
I found 21 functional requirements organized into 5 categories. Architecturally, this requires a decoupling of data ingestion (1-way read from PMS) from the AI reasoning engine and the multi-channel push notification system (WhatsApp/SMS/Email). The "Conversational Receipts" requirement specifically mandates a two-way, low-latency interactive layer built on top of the push delivery mechanism.

**Non-Functional Requirements:**
I found 6 core NFRs driving the architecture:
- **Integration Reliability:** Graceful handling of up to 60s PMS downtime/rate-limiting requires queueing or retry mechanisms.
- **Latency & Performance:** Delivery of alerts within 3 minutes; Conversational responses within 3 seconds (P95).
- **Security & Compliance:** Strict GDPR separation (PII stripping) and AES-256 encryption.

**Scale & Complexity:**
The project represents a shift from a Phase 3 single-tenant dashboard to a Phase 4/MVP multi-tenant B2B Agentic SaaS. The scale is substantial due to external semantic integrations (PredictHQ, weather) operating across multiple tenants in near real-time.

- Primary domain: Agentic AI / Backend Orchestration
- Complexity level: Medium-High
- Estimated architectural components: 6 core components (PMS Sync, Semantic Engine, RAG/Reasoning, Feedback DB, Multi-channel Delivery, Multi-tenant RBAC)

### Technical Constraints & Dependencies

- **API Dependencies:** Heavy reliance on external APIs (Mews/Apaleo PMS, PredictHQ for events, Twilio/WhatsApp/SendGrid, Claude AI, Qdrant).
- **Budget/Resource:** Utilizing free/cheap tiers (Render, Supabase, Qdrant Cloud) whilst establishing a logical multi-tenant data model is critical to stay within previous budget constraints.
- **Data Isolation:** Need strict row-level security (RLS) or logical separation in the database so competitive PMS data does not leak between properties.

### Cross-Cutting Concerns Identified

- **Explainable AI (Trust):** All reasoning must be traceable to the manager.
- **Multi-Tenancy & RBAC:** Data segregation affecting the DB, API layer, and frontend.
- **Resilience/Fault Tolerance:** Handling upstream PMS disconnects and rate-limiting robustly.

## Starter Template Evaluation

### Primary Technology Domain

Web application / Backend Orchestration (Agentic AI SaaS) based on project requirements analysis.

### Starter Options Considered

- **`vintasoftware/nextjs-fastapi-template`**: An open-source, production-ready template that tightly integrates Next.js (frontend) and FastAPI (backend). It features end-to-end type safety via OpenAPI, Docker support, and pre-configured tools like UV, Ruff, and Vercel CLI.
- **`fastapi-fullstack` (CLI-based)**: Installable via pip, heavily focused on AI/LLM integrations with PydanticAI and Celery/Redis but potentially heavier than needed for a tightly scoped MVP constrained by budget.
- **Vercel's Next.js FastAPI Starter**: Lightweight, specifically tailored for streaming AI completions, but lacks the robust end-to-end type safety and DB integrations out-of-the-box compared to the Vinta template.

### Selected Starter: `vintasoftware/nextjs-fastapi-template`

**Rationale for Selection:**
This template perfectly bridges the gap between the required front-end (Next.js/React/shadcn for rapid UI scaling) and the heavy Python AI backend (FastAPI/Claude API/Qdrant) documented in your Phase 3 Architecture. The end-to-end type safety (via openapi-fetch) is critical for minimizing integration bugs between the UI and the agentic backend. Furthermore, it explicitly supports Vercel deployment and Docker, aligning with your zero/low-budget constraint for the MVP.

**Initialization Command:**

```bash
cookiecutter https://github.com/vintasoftware/nextjs-fastapi-template.git
```
*(Note: As it is a template repository, you can also use "Use this template" directly on GitHub or clone it and remove the `.git` folder).*

**Architectural Decisions Provided by Starter:**

**Language & Runtime:**
- **Frontend:** TypeScript + Next.js (App Router likely).
- **Backend:** Python + FastAPI (Async ready).

**Styling Solution:**
- Tailwind CSS + shadcn/ui (Pre-configured for rapid, accessible UI development).

**Build Tooling & Dependencies:**
- **Backend:** `uv` (extremely fast Python dependency manager replacing pip/poetry).
- **Frontend:** `npm`/`pnpm` with standard Next.js build optimization.
- **Infrastructure:** Docker & Docker Compose for normalized local development.

**Testing Framework:**
- **Backend:** Setup for `pytest` testing framework.

**Code Organization:**
- Strict separation of concerns (monorepo style with distinct frontend/backend directories).
- Automated OpenAPI schema export from FastAPI feeding directly into Next.js typed clients.

**Development Experience:**
- Pre-commit hooks via `Ruff` (Python) and `ESLint` (JS/TS) for instant code formatting.
- Hot-reloading synced across both stacks.
- MailHog for local email capture (useful for testing notifications).

**Note:** Project initialization using this template should be the first implementation story.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data Architecture (Database & Vector Storage)
- Authentication & Security
- API & Communication Patterns

**Important Decisions (Shape Architecture):**
- Frontend Route Structure
- Infrastructure & Deployment Options

### Data Architecture

**Decision: Database & Vector Storage**
- **Selected:** Supabase (PostgreSQL) with `pgvector` enabled.
- **Rationale:** Strongly optimizes for speed (solo-developer constraint) by unifying relational data, conversational memory, and pattern embeddings into a single Postgres backend. It simultaneously preserves strict algorithmic control over the mathematical similarity scoring (unlike managed APIs like Backboard.io) and aligns with the <$50/mo budget constraint.
- **Provided by Starter:** Partial (Starter provides SQLAlchemy/Postgres via Docker; Supabase cloud will replace the local Postgres instance).
- **Affects:** Prediction Engine, RAG/Reasoning Engine, Feedback Loop.

### Frontend Architecture

**Decision: Frontend Framework & UI Library**
- **Selected:** Next.js (React) + Tailwind CSS + shadcn/ui.
- **Rationale:** While Streamlit is excellent for pure Python prototyping, Next.js provides the necessary foundation for a production B2B SaaS. It allows for rich, responsive mobile UI (critical for managers on the floor) and complex state management. The `openapi-fetch` integration ensures the frontend always stays perfectly typed and in sync with the FastAPI backend, eliminating an entire class of integration bugs.
- **Provided by Starter:** Yes, fully configured via the `vintasoftware/nextjs-fastapi-template`.
- **Affects:** Dashboard UI, Form validation, Client-side routing.

### Infrastructure & Deployment

**Decision: Hosting & Infrastructure Strategy**
- **Selected:** Split Deployment (Vercel for Frontend, Render/Railway for FastAPI Backend via Docker).
- **Rationale:** Protects against the "cold start" and strict execution timeout problems inherent to serverless Python environments (like Vercel). By containerizing the FastAPI backend and deploying it to a traditional PaaS (Render/Railway), the `BackgroundTasks` required for the Twilio webhooks and Claude API calls have the necessary persistent execution time ensuring no dropped messages, while maintaining a strict <$50/mo lean budget.
- **Provided by Starter:** The template explicitly supports Dockerizing the FastAPI backend, making deployment to Render/Railway straightforward.
- **Affects:** CI/CD Pipelines, Environment Variables, Docker configuration.

### Decision Impact Analysis

**Implementation Sequence:**
1. Initialize `vintasoftware/nextjs-fastapi-template`.
2. Provision Supabase Project (Postgres + Auth) and enable `pgvector`.
3. Configure `fastapi-users` to point to Supabase and establish strict Row Level Security (RLS) policies for tenant data isolation.
4. Build the core FastAPI `BackgroundTasks` router to handle Twilio webhooks asynchronously.
5. Deploy FastAPI container to Render/Railway.
6. Deploy Next.js frontend to Vercel.

**Cross-Component Dependencies:**
- Webhook endpoints deeply depend on the fast ingestion of data into Supabase to maintain state before the async `BackgroundTask` fires.
- Frontend Auth state (Next.js) must perfectly sync with FastAPI's JWT validation, which in turn relies on Supabase for the database-level RLS.
- **Affects:** Prediction Engine, RAG/Reasoning Engine, Feedback Loop.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
3 areas where AI agents could make different choices resulting in broken integrations.

### Naming Patterns

**API & Data Boundary Casing (Pydantic <-> TypeScript):**
- **Rule:** Python Backend internal logic and PostgreSQL must strictly use `snake_case`. TypeScript Frontend must strictly use `camelCase`.
- **Enforcement:** The FastAPI backend MUST configure Pydantic models to automatically alias and output `camelCase` for all API JSON responses.
- **Example (Backend):** `class UserProfile(BaseModel): tenant_id: str`
- **Example (Frontend):** `const user = useQuery(); console.log(user.tenantId);`

### Structure Patterns

**Business Logic Location:**
- **Rule:** "Fat Backend / Thin Frontend" orchestration. All business rules, AI prompting, context retrieval, and data validation MUST occur in the FastAPI backend or database RLS.
- **Enforcement:** Next.js Server Actions and React Components are strictly presentational. They may not contain branching logic for access control or formatting prompts for Claude.
- **Anti-Pattern:** A Next.js API route formatting a message and calling the Claude API directly. (This fractures the AI orchestration layer away from FastAPI).

### Process Patterns

**Error Handling & Fallbacks:**
- **Rule:** Standardized Problem Details (RFC 7807) for all HTTP exceptions.
- **Enforcement:** FastAPI must use a custom exception handler that catches all errors (including upstream Twilio/Claude timeouts) and formats them into a predictable JSON structure containing `type`, `title`, `status`, and `detail`.
- **Example:**
```json
{
  "type": "https://aetherix.io/errors/llm-timeout",
  "title": "LLM Timeout",
  "status": 504,
  "detail": "The prediction engine took too long to respond."
}
```

### Enforcement Guidelines

**All AI Agents MUST:**
- Never assume the casing of a JSON payload without checking the OpenAPI generated types.
- Put LLM prompting and routing logic *only* in the Python backend.
- Catch HTTP exceptions on the frontend by looking for the `RFC 7807` formatted JSON, not by parsing generic string errors.

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
aetherix-mvp/
├── nextjs-frontend/         # The React/Next.js UI Application
│   ├── src/
│   │   ├── app/                     # App Router pages
│   │   │   ├── (auth)/              # Login/Signup forms
│   │   │   ├── dashboard/           # Main manager view
│   │   │   └── settings/            # Agent configuration view
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui primitives
│   │   │   └── features/            # Complex views (e.g., PredictionChart.tsx)
│   │   ├── lib/
│   │   │   └── api-client.ts        # openapi-fetch generated client (Type safety boundary)
│   ├── .env.local
│   ├── package.json
│   └── tailwind.config.ts
├── fastapi-backend/         # The Python AI/Orchestration Application
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/              # EXPLICIT BOUNDARY: HTTP presentation only
│   │   │   │   ├── auth.py          # fastapi-users integration
│   │   │   │   ├── webhooks.py      # Twilio incoming messages
│   │   │   │   └── dashboard.py     # Data fetching for Next.js
│   │   ├── core/                    # EXPLICIT BOUNDARY: System config
│   │   │   ├── config.py
│   │   │   └── security.py
│   │   ├── db/                      # EXPLICIT BOUNDARY: Supabase/pgvector models
│   │   │   └── models.py
│   │   ├── services/                # EXPLICIT BOUNDARY: Business & AI Logic
│   │   │   ├── pms_sync.py          # Apaleo/Mews ingestion
│   │   │   ├── aetherix_engine.py   # Claude Orchestration
│   │   │   └── prediction_math.py   # Vector math
│   ├── .env
│   ├── pyproject.toml               # Built via uv
│   └── Dockerfile
├── docker-compose.yml       # Local dev orchestration (DB + Backend)
└── .github/workflows/       # CI/CD configs
```

### Architectural Boundaries

**API Boundaries:**
- The frontend (`nextjs-frontend/`) NEVER talks to the database directly. It MUST communicate via the autogenerated `api-client.ts` typed client to the FastAPI backend.
- Third-party webhooks (Twilio) MUST ONLY hit the `api/routes/webhooks.py` endpoints.

**Component/Service Boundaries:**
- The backend API routes (`app/api/routes/`) MUST NEVER contain business logic or DB calls. They only parse inputs via Pydantic and immediately pass logic to the `app/services/` layer.
- Next.js React Components MUST be strictly presentational. Complex state and AI prompts are forbidden in the UI layer.

### Requirements to Structure Mapping

**Epic/Feature Mapping:**
- **PMS Sync:** `fastapi-backend/app/services/pms_sync.py`
- **Semantic Engine:** `fastapi-backend/app/services/prediction_math.py` & `fastapi-backend/app/db/models.py` (pgvector)
- **Reasoning Engine:** `fastapi-backend/app/services/aetherix_engine.py`
- **Multi-channel Delivery:** `fastapi-backend/app/api/routes/webhooks.py` (Parsing) & `fastapi-backend/app/services/aetherix_engine.py` (Outbound Generation)

**Cross-Cutting Concerns:**
- **Authentication:** `fastapi-backend/app/api/routes/auth.py` (fastapi-users) & `nextjs-frontend/src/app/(auth)/`
- **Tenant Isolation (RLS):** Governed by Supabase directly, instantiated via JWTs passed from the `nextjs-frontend` to `fastapi-backend`.

## LLM Provider Abstraction Layer (Epic 0 — Phase 0.5)

_Added: 2026-04-07 — End-of-Epic architecture review, HOS-118._

### Context

Epic 0 introduces a provider abstraction so business services are decoupled from any specific AI vendor. The epic is **design-complete / ready-for-dev** as of the review date. The `backend/app/providers/` package does not yet exist in the codebase.

### Design Decision: `typing.Protocol` over ABC

**Selected:** `@runtime_checkable` Protocol (structural subtyping).

**Rationale:**
- Concrete providers (Claude, Mistral, future Gemini) do not share a base class — inheritance would couple unrelated vendor wrappers.
- Test mocks are plain classes; no inheritance required.
- `isinstance(provider, LLMProvider)` works at runtime for factory validation.

**Rejected alternatives:**
- `ABC` — forces inheritance at class definition time; tightly couples vendor implementations to our codebase.
- DI framework (Dependency Injector, injector) — overkill for 2 provider types at this scale; FastAPI's `app.state` + `lifespan` is sufficient.

**Known limitation:** `@runtime_checkable` `isinstance()` only checks attribute names, not async signatures. A sync `complete()` would pass the check. Mitigated by documentation; a mypy Protocol check catches this at static analysis time.

### Directory Structure

```
backend/app/providers/
├── __init__.py
├── base.py              # LLMProvider + EmbeddingProvider Protocol definitions
├── claude_provider.py   # ClaudeProvider(LLMProvider) — primary, wraps AsyncAnthropic
├── mistral_provider.py  # MistralEmbeddingProvider(EmbeddingProvider) — primary, wraps Mistral
└── factory.py           # get_llm_provider() + get_embedding_provider() — construction only

backend/app/services/
├── reasoning_service.py      # accepts LLMProvider via __init__ DI
├── explainability_service.py # accepts LLMProvider via __init__ DI
├── rag_service.py            # accepts EmbeddingProvider via __init__ DI
└── memory_service.py         # accepts EmbeddingProvider via __init__ DI
```

### Protocol Definitions

```python
# backend/app/providers/base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.3,
        system: str | None = None,
    ) -> str: ...

    @property
    def model_id(self) -> str: ...

@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    @property
    def dimensions(self) -> int: ...
```

### Provider Lifecycle — Singleton via FastAPI `lifespan` (ADR #10)

**Critical constraint:** `factory.py` is a construction function only — it must NOT be called repeatedly at request time. `AsyncAnthropic` holds an `httpx.AsyncClient` connection pool internally; per-request instantiation exhausts file descriptors under load.

**Correct pattern:**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from app.providers.factory import get_llm_provider, get_embedding_provider

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.llm = get_llm_provider()
    app.state.embedding = get_embedding_provider()
    yield
    # Clean shutdown — releases httpx connection pool
    if hasattr(app.state.llm, "aclose"):
        await app.state.llm.aclose()

app = FastAPI(lifespan=lifespan)
```

Services receive the singleton at instantiation from `app.state`, not by calling `get_llm_provider()` themselves.

**Required:** `ClaudeProvider` must expose `async def aclose()` wrapping `await self._client.aclose()` (httpx client cleanup). `MistralEmbeddingProvider` uses a sync client in executor — no async close needed, but the executor threadpool is GC'd automatically.

### Embedding Dimension — Confirmed 1024

Mistral `mistral-embed` outputs **1024-dimensional** vectors. The current `rag_service.py:23` declares `_EMBEDDING_DIM = 1536` — this is incorrect and will cause pgvector schema mismatches. The `vector(1024)` column definition must be verified in the DB migration before Epic 0 stories 0.3–0.4 run. `MistralEmbeddingProvider.dimensions` returns `1024`.

### Async Executor Pattern for Mistral

The sync `Mistral` client must be wrapped via:

```python
loop = asyncio.get_running_loop()  # NOT get_event_loop() — deprecated in Python 3.10+
result = await loop.run_in_executor(None, self._client.embeddings.create, ...)
```

### Fallback Providers (Gemini, OpenAI) — Phase 2

The epic correctly scopes only the interface and primary providers (Claude + Mistral). **Gemini/OpenAI providers are not part of Epic 0.** The factory raises `NotImplementedError` for unimplemented backends — this is intentional and correct. Adding a second provider in future requires: 1 new file in `providers/`, 1 new branch in `factory.py`, zero changes to `services/`.

`gemini-2.0-flash` is the recommended fallback candidate when Phase 2 implements it, but requires explicit handling of Gemini's differing API contract (system instructions via `system_instruction=` config, not a system message role).

### Pre-Phase-1 Blockers Identified

| # | Issue | Severity | File |
|---|-------|----------|------|
| B1 | `rag_service.py` has two concatenated implementations (duplicate `from __future__ import annotations`) | BLOCKER | `services/rag_service.py` |
| B2 | `memory_service.py` same corruption — two implementations merged | BLOCKER | `services/memory_service.py` |
| B3 | `_EMBEDDING_DIM = 1536` vs Mistral 1024d — pgvector column mismatch | BLOCKER | `services/rag_service.py:23` |
| B4 | `main.py` has duplicate import blocks + two `on_shutdown` handlers | RISK | `main.py` |
| B5 | Provider factory must be wired as singleton in `lifespan`, not called per-request | RISK | `providers/factory.py` |

Blockers B1–B3 must be resolved as part of Stories 0.4 (prerequisite cleanup). B4–B5 resolved in Story 0.2 `main.py` wiring task.

### Configuration via Environment Variables

```
LLM_BACKEND        — "claude" (default) | future: "gemini" | "openai"
LLM_MODEL          — "claude-sonnet-4-6" (default)
EMBEDDING_BACKEND  — "mistral" (default) | future: "openai"
EMBEDDING_MODEL    — "mistral-embed" (default)
```

Existing `ANTHROPIC_API_KEY` and `MISTRAL_API_KEY` unchanged.

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
High. The `vintasoftware/nextjs-fastapi-template` perfectly bridges Next.js, FastAPI, and Docker. Supabase with `pgvector` natively integrates with Python API services, establishing a highly compatible end-to-end B2B SaaS stack without conflicting dependencies. 

**Pattern Consistency:**
High. The implementation patterns correctly enforce boundary separation. The decision to cast `snake_case` (Backend) to `camelCase` (Frontend) natively via Pydantic cleanly addresses the highest-risk conflict point between TS/Python AI agents.

**Structure Alignment:**
High. The Next.js/FastAPI monorepo physically enforces the architectural boundaries (Thin Frontend / Fat Backend) by strictly isolating business logic within the `fastapi-backend/app/services` layer.

### Requirements Coverage Validation ✅

**Epic/Feature Coverage:**
All 6 Core architectural Epics identified in Phase 3 are mapped precisely to the Next.js/FastAPI components.
- *PMS Sync*, *Semantic Engine*, and *Reasoning Engine* are covered by the FastAPI `BackgroundTasks` & `services` layer.
- *Multi-channel Delivery* is covered by the FastAPI webhook routers.
- *Feedback DB* and *Multi-tenant RBAC* are covered by Supabase + RLS.

**Non-Functional Requirements Coverage:**
- **Integration Reliability (60s downtime):** Supported via FastAPI `BackgroundTasks` decoupled from immediate HTTP 200 responses.
- **Latency (<3s conversational):** Supported via direct API integration to Claude and fast vector math via `pgvector` stored procedures.
- **Security (GDPR/AES-256):** Supported natively via Supabase RLS policies and managed Postgres encryption.

### Implementation Readiness Validation ✅

**Decision Completeness:**
All critical path decisions (Stack, Database, Auth, Deployment) are fully specified and block implementation no further.

**Structure & Pattern Completeness:**
Project directories, file boundaries, caching rules, and HTTP error standards (RFC 7807) are fully documented. An AI agent reading this document has exact instructions for where to place code and what naming conventions to use.

### Gap Analysis Results

There are no critical gaps blocking Phase 4 MVP implementation. 

**Minor Gap (For Future Enhancement):**
- *Testing Strategy Formulation:* While the architecture establishes *where* tests live (`tests/`), specific AI-driven testing protocols (e.g., how to simulate Mews/Apaleo webhooks locally) will need to be defined during the Implementation phase.

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** HIGH - The architecture leans heavily into stable, proven B2B abstractions (FastAPI, Next.js App Router, Postgres RLS) while retaining the flexibility required for Agentic AI orchestration.

**First Implementation Priority:**
Initialize the monorepo via:
`cookiecutter https://github.com/vintasoftware/nextjs-fastapi-template.git`

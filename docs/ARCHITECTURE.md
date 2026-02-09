# F&B Operations Agent - Technical Architecture

**Version:** 0.2.0 (Phase 3)  
**Last Updated:** February 2026  
**Author:** Ivan de Murard

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Data Flow](#data-flow)
4. [Technology Stack](#technology-stack)
5. [API Specifications](#api-specifications)
6. [Integration Strategy](#integration-strategy)
7. [Data Models](#data-models)
8. [Security & Compliance](#security--compliance)
9. [Scalability Path](#scalability-path)
10. [Key Architecture Decisions](#key-architecture-decisions)

---

## Overview

The F&B Operations Agent is an AI-powered staffing forecasting system designed for restaurant operations managers.
The architecture follows an **agentic-first experience** built on **API-first infrastructure**:

- **Agentic layer:** AI agent autonomously predicts staffing needs, generates reasoning, 
  and recommends actions. Manager approves rather than executes manually (human-in-the-loop).
- **API layer:** RESTful APIs enable seamless integration with PMS systems (Mews, Apaleo) 
  and external services (PredictHQ, ElevenLabs, Claude AI).

This dual approach aligns with hospitality's evolution toward **autonomous agent-driven operations** (as championed by Mews Operations Agent and Apaleo's AI-powered platform) while maintaining **interoperability** through open APIs.

**Agentic-first = User experience paradigm** (agents do work autonomously)  
**API-first = Infrastructure paradigm** (systems integrate seamlessly)

**Core Principles:**
- **Human-in-the-loop:** Manager approves all predictions (augmented, not automated)
- **Explainable AI:** Reasoning always visible (trust-building critical in hospitality)
- **Dashboard-first:** Aetherix UI as primary interface; voice/chat planned for Phase 5
- **PMS-agnostic:** Compatible with Mews, Apaleo, and any API-first PMS

---

## System Architecture

### High-Level Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  Aetherix Dashboard (Streamlit) │ Future: WhatsApp/Slack    │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│                    INTELLIGENCE LAYER                        │
│  Prediction Engine │ Reasoning Engine │ Staff Recommender    │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│                      SEMANTIC LAYER                          │
│  RAG (Qdrant) │ Context Enrichment │ PMS Adapters (future)  │
└────────────────────────────────┬────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────┐
│                       DATA LAYER                             │
│  Patterns DB │ Feedback DB │ Restaurant Profiles             │
└─────────────────────────────────────────────────────────────┘
```

### Architecture Diagrams

**Flow View** - Sequential data flow through layers:
<img src="assets/architecture-flux.svg" width="100%" alt="Aetherix Architecture Flow Diagram showing Semantic, Intelligence, and Delivery layers" loading="lazy">

**Value View** - Layered architecture with feedback loop:
<img src="assets/architecture-value.svg" width="100%" alt="Aetherix Architecture Value Diagram showing layered architecture with feedback loop" loading="lazy">

### Component Status

| Component | Phase | Status |
|-----------|-------|--------|
| Prediction Engine | 1 | ✅ Production |
| Reasoning Engine | 1 | ✅ Production |
| RAG/Qdrant | 2 | ✅ Production |
| Dashboard (Aetherix) | 3 | 🔄 MVP |
| Feedback Loop | 3-4 | 🔄 Backend done |
| PMS Adapters | 5 | 📋 Planned |
| Voice Interface | 5 | 📋 Planned |

### Component Breakdown

**Frontend (Phase 3: Streamlit)**
- **Aetherix Dashboard:** Streamlit app — Day/Week/Month views, Factors panel, Feedback panel
- **Deployment:** Streamlit Cloud (https://aetherix.streamlit.app)
- **Future (Phase 5):** Next.js 14, Command Palette, Voice widget (ElevenLabs)

**Backend (FastAPI)**
- **Multi-agent architecture:** Coordinator dispatches to specialized agents
- **Async operations:** Fast response times (<3s target)
- **Logging:** Structured JSON logs (INFO: requests, ERROR: failures)
- **Deployment:** Render.com or Railway (Docker container)

**AI/ML Layer**
- **Claude Sonnet 4:** Primary reasoning engine + embeddings
- **Qdrant Cloud:** Vector database for pattern similarity search
- **ElevenLabs:** Voice synthesis + transcription (opt-in)

**Data Layer**
- **Supabase:** PostgreSQL + real-time subscriptions
- **Redis (Upstash):** Session state, conversation context (TTL 1h)

---

## Data Flow

### End-to-End: Prediction Request
```
1. MANAGER INPUT
   ├─ Option A: Voice → "Predict Saturday dinner"
   │  └─ ElevenLabs STT → Text transcription
   ├─ Option B: Keyboard → Type in search bar
   └─ Option C: Command Palette → ⌘K → Select action
                    ↓
2. FRONTEND PROCESSING
   ├─ Parse request → {date: "2024-11-30", service_type: "dinner"}
   ├─ POST /api/predict
   └─ Loading state (skeleton UI)
                    ↓
3. BACKEND: COORDINATOR AGENT
   ├─ Validate request (date format, service type)
   ├─ Check Redis cache (duplicate request?)
   └─ Dispatch to specialized agents
                    ↓
4. DEMAND PREDICTOR AGENT
   ├─ Fetch external context:
│  ├─ PMS API (Mews/Apaleo) → Hotel occupancy rate
│  │  (80% occupancy = higher restaurant demand)
│  ├─ PredictHQ API → Events within 5km radius
│  └─ Weather API → Forecast for service date
   │
   ├─ Generate embedding:
   │  ├─ Claude API → Create vector representation
   │  │  Input: "Saturday dinner, Coldplay concert 3.2km, 70% rain"
   │  └─ Vector: [0.123, -0.456, 0.789, ...] (1536 dimensions)
   │
   ├─ Search similar patterns:
   │  ├─ Qdrant vector search → Top 3 similar patterns
   │  │  Query: embedding vector + filters (service_type)
   │  └─ Results: [
   │       {pattern_id, date, covers, similarity: 0.94},
   │       {pattern_id, date, covers, similarity: 0.91},
   │       {pattern_id, date, covers, similarity: 0.87}
   │     ]
   │
   └─ Calculate prediction:
      ├─ Weighted average: (142*0.94 + 151*0.91 + 138*0.87) / (0.94+0.91+0.87)
      └─ Output: {predicted_covers: 145, confidence: 0.88}
                    ↓
5. REASONING ENGINE AGENT
   ├─ Generate explanation:
   │  ├─ Claude API → Reasoning prompt:
   │  │  "Based on these 3 patterns, explain why 145 covers (88% confidence)"
   │  └─ Output: "Similar Saturday dinners with nearby concerts historically 
   │             averaged 144 covers. Weather impact minimal for indoor seating."
   │
   └─ Structure response:
      {
        "prediction": 145,
        "confidence": 0.88,
        "reasoning_summary": "88% confidence based on similar Saturday dinners...",
        "patterns": [
          {id, date, event, covers, similarity},
          ...
        ]
      }
                    ↓
6. STAFF RECOMMENDER AGENT
   ├─ Calculate staffing needs:
   │  ├─ Base ratio: 1 server per 18 covers
   │  ├─ 145 covers ÷ 18 = 8.05 → 8 servers
   │  └─ Add hosts (2) + kitchen (3)
   │
   └─ Compare vs usual:
      {
        "servers": {current: 8, usual: 7, delta: +1},
        "hosts": {current: 2, usual: 2, delta: 0},
        "kitchen": {current: 3, usual: 3, delta: 0}
      }
                    ↓
7. BACKEND RESPONSE
   ├─ Save to Supabase:
   │  └─ predictions table (for historical accuracy tracking)
   │
   ├─ Store in Redis:
   │  └─ Session cache (key: prediction_id, TTL: 1h)
   │
   └─ Return JSON:
      {
        "prediction_id": "pred_abc123",
        "service_date": "2024-11-30",
        "service_type": "dinner",
        "predicted_covers": 145,
        "confidence": 0.88,
        "reasoning": {...},
        "staff_recommendation": {...},
        "patterns_used": [...]
      }
                    ↓
8. FRONTEND DISPLAY
   ├─ Update UI (remove loading, show prediction)
   ├─ Render components:
   │  ├─ PredictionCard: 145 covers, 88% confidence badge
   │  ├─ ReasoningSection: Collapsible (default: summary only)
   │  └─ StaffRecommendation: 8 servers (+1), 2 hosts (=), 3 kitchen (=)
   │
   └─ Enable actions:
      ├─ [Approve] → POST /api/feedback {action: "approved"}
      ├─ [Adjust] → Open modal, manager inputs custom covers
      └─ [Reject] → POST /api/feedback {action: "rejected"}
                    ↓
9. MANAGER ACTION (Approve)
   ├─ POST /api/feedback
   │  {prediction_id, action: "approved", actual_covers: null}
   │
   ├─ Backend saves feedback:
   │  └─ Supabase feedback table (for learning loop Phase 3)
   │
   └─ UI confirmation:
      └─ Toast notification: "✓ Prediction approved"
```

**Response Time Targets:**
- Voice transcription: <1s (ElevenLabs)
- Backend processing: <2s (Claude + Qdrant + calculations)
- Total end-to-end: <3s (P95 latency)

---

## Technology Stack

### Frontend Stack

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **Next.js** | 14.1.0 | React framework | SSR for fast loads, App Router for modern patterns, Vercel deployment optimized |
| **TypeScript** | 5.x | Type safety | Catch bugs at compile-time, better DX with autocomplete |
| **shadcn/ui** | Latest | UI components | Copy-paste components (no NPM bloat), accessible by default, Tailwind-native |
| **Tailwind CSS** | 3.3+ | Styling | Utility-first, consistent design tokens, fast prototyping |
| **Vercel** | - | Hosting | Free tier generous (100GB bandwidth), auto-deploy from GitHub, CDN included |

**Why Next.js over alternatives:**
- ✅ React SPA (Vite): Next.js adds SSR (better SEO, faster initial load)
- ✅ Vue/Svelte: Smaller ecosystem, less relevant for Mews PM audience
- ✅ Remix: Less mature tooling, Vercel deployment not as smooth

**Why shadcn/ui over component libraries:**
- ✅ Material-UI / Ant Design: Too opinionated, harder to customize
- ✅ Chakra UI: Good but NPM dependencies add bundle size
- ✅ shadcn/ui: Copy-paste = full control, Tailwind-native, accessible

---

### Backend Stack

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| **FastAPI** | 0.109+ | Web framework | Async support, auto-generated docs (OpenAPI), Pydantic validation, fast |
| **Python** | 3.11 | Language | Best AI/ML library ecosystem (Claude SDK, Qdrant client), quick prototyping |
| **Pydantic** | 2.5+ | Data validation | Type-safe request/response models, auto JSON schema generation |
| **Uvicorn** | 0.27+ | ASGI server | High-performance async server, production-ready |
| **Render.com** | - | Hosting | Free tier (sleep after 15min inactivity OK for MVP), Docker support, GitHub auto-deploy |

**Why FastAPI over alternatives:**
- ✅ Django: Overkill for API-only backend, slower, more boilerplate
- ✅ Flask: No async support, less modern, manual OpenAPI docs
- ✅ Node.js (Express): Weaker AI/ML ecosystem (Claude SDK less mature)

**Why Python over other languages:**
- ✅ Best AI/ML library support (Anthropic SDK, Qdrant client, embeddings)
- ✅ Familiar to data science teams (easier handoff if scales)
- ✅ Quick prototyping (MVP speed critical)

---

### AI/ML Stack

| Technology | Cost | Purpose | Rationale |
|------------|------|---------|-----------|
| **Claude Sonnet 4** | $3/MTok input, $15/MTok output | Reasoning + embeddings | Better reasoning than Mistral, 200K context window, artifacts support, ~$0.003/prediction |
| **Qdrant Cloud** | Free tier <1GB | Vector database | Fast similarity search (<100ms), cloud-native, generous free tier vs Pinecone ($70/mo) |
| **ElevenLabs** | $5/mo Starter | Voice I/O | Best voice quality, conversational AI widget, 10K chars/month sufficient for MVP |

**Why Claude over alternatives:**
- ✅ OpenAI GPT-4: More expensive ($20/MTok vs $3/MTok input), Claude reasoning better for explainability
- ✅ Mistral: Cheaper ($1/MTok) but weaker reasoning, smaller context (32K vs 200K)
- ✅ Google Gemini: API less mature, pricing less predictable

**Why Qdrant over alternatives:**
- ✅ Pinecone: $70/month minimum (vs Qdrant free <1GB)
- ✅ Weaviate: More complex setup, overkill for MVP
- ✅ PostgreSQL pgvector: Slower search, no cloud hosting

**Why ElevenLabs over alternatives:**
- ✅ Google STT/TTS: Less natural voice quality, no conversational widget
- ✅ Deepgram: Good but more expensive at scale
- ✅ OpenAI Whisper: Self-hosted complexity, no TTS

---

### Data Stack

| Technology | Tier | Purpose | Rationale |
|------------|------|---------|-----------|
| **Supabase** | Free | PostgreSQL + Auth + Real-time | <500MB free, PostgREST API auto-generated, real-time subscriptions, managed backups |
| **Redis (Upstash)** | Free | Session state | Serverless Redis, <10K requests/day free, fast in-memory, simple key-value |

**Why Supabase over alternatives:**
- ✅ MongoDB: Relational data fits SQL better (predictions, patterns, feedback)
- ✅ Firebase: Vendor lock-in, less SQL flexibility
- ✅ Raw PostgreSQL: Supabase adds Auth + real-time + hosting managed

**Why Redis over alternatives:**
- ✅ In-memory Python dict: Lost on server restart, not scalable
- ✅ Memcached: Less features, no persistence option
- ✅ Redis: Industry standard, persistence optional, pub/sub support

---

## API Specifications

### Base URL
```
Development: http://localhost:8000
Production: https://fbagent-api.render.com (or Railway)
```

### Authentication
**MVP:** None (single-user demo)  
**Production:** JWT tokens via Supabase Auth

---

### Endpoints

#### **POST /api/predict**

Generate staffing prediction for a service.

**Request:**
```json
{
  "restaurant_id": "resto_123",
  "service_date": "2024-11-30",
  "service_type": "dinner"
}
```

**Response (200 OK):**
```json
{
  "prediction_id": "pred_abc123",
  "service_date": "2024-11-30",
  "service_type": "dinner",
  "predicted_covers": 145,
  "confidence": 0.88,
  "reasoning": {
    "summary": "88% confidence based on similar Saturday dinners with events nearby",
    "patterns_used": [
      {
        "pattern_id": "pat_001",
        "date": "2023-11-18",
        "event_type": "Concert (Coldplay)",
        "actual_covers": 142,
        "similarity": 0.94,
        "details": {
          "day_of_week": "Saturday",
          "distance_km": 3.2,
          "weather": "Clear"
        }
      },
      {
        "pattern_id": "pat_002",
        "date": "2024-06-15",
        "event_type": "Concert (U2)",
        "actual_covers": 151,
        "similarity": 0.91,
        "details": {
          "day_of_week": "Saturday",
          "distance_km": 3.2,
          "weather": "Partly cloudy"
        }
      },
      {
        "pattern_id": "pat_003",
        "date": "2024-10-12",
        "event_type": "Rainy Saturday",
        "actual_covers": 138,
        "similarity": 0.87,
        "details": {
          "day_of_week": "Saturday",
          "distance_km": null,
          "weather": "Rain"
        }
      }
    ]
  },
  "staff_recommendation": {
    "servers": {
      "recommended": 8,
      "usual": 7,
      "delta": 1,
      "rationale": "1 server per 18 covers (145 ÷ 18 = 8.05)"
    },
    "hosts": {
      "recommended": 2,
      "usual": 2,
      "delta": 0
    },
    "kitchen": {
      "recommended": 3,
      "usual": 3,
      "delta": 0
    }
  },
  "created_at": "2024-12-02T17:30:00Z"
}
```

**Error Responses:**
```json
// 400 Bad Request
{
  "error": "invalid_date",
  "message": "Service date must be in future"
}

// 500 Internal Server Error
{
  "error": "prediction_failed",
  "message": "Claude API timeout after 10s"
}
```

---

#### **GET /api/patterns**

Retrieve historical patterns for transparency.

**Query Parameters:**
- `restaurant_id` (required): Restaurant identifier
- `limit` (optional, default 20): Number of patterns to return
- `event_type` (optional): Filter by event type

**Request:**
```
GET /api/patterns?restaurant_id=resto_123&limit=10&event_type=concert
```

**Response (200 OK):**
```json
{
  "patterns": [
    {
      "pattern_id": "pat_001",
      "date": "2023-11-18",
      "service_type": "dinner",
      "event_type": "Concert (Coldplay)",
      "actual_covers": 142,
      "confidence": 0.94,
      "metadata": {
        "weather": "Clear",
        "day_of_week": "Saturday",
        "distance_km": 3.2
      }
    },
    // ... more patterns
  ],
  "total_count": 47,
  "average_confidence": 0.86
}
```

---

#### **POST /api/feedback**

Submit manager feedback on prediction (approve/reject/adjust).

**Request:**
```json
{
  "prediction_id": "pred_abc123",
  "action": "approved",  // "approved" | "rejected" | "adjusted"
  "actual_covers": null,  // null if not yet known, number if post-service
  "adjusted_covers": null,  // only if action = "adjusted"
  "notes": "Looks accurate, approved"
}
```

**Response (200 OK):**
```json
{
  "feedback_id": "fb_xyz789",
  "message": "Feedback recorded successfully",
  "created_at": "2024-12-02T17:35:00Z"
}
```

---

#### **GET /api/health**

Health check endpoint for monitoring.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "dependencies": {
    "claude_api": "ok",
    "qdrant": "ok",
    "supabase": "ok",
    "redis": "ok"
  },
  "uptime_seconds": 3600
}
```

---

## Integration Strategy

### PMS Integration Philosophy

**API-First, PMS-Agnostic Design**

The agent is designed to integrate with any modern PMS that provides:
1. **Booking/Reservation API** (read occupancy data)
2. **Finance API** (write F&B charges to guest folios)
3. **Webhook support** (real-time notifications)

**Target PMS Platforms:**
- **Primary:** Mews (Operations Agent vision alignment)
- **Secondary:** Apaleo (API-first MACH architecture)
- **Future:** Oracle Opera Cloud, Protel, others with open APIs

---

### Mews Integration (Primary Target)

**Why Mews:**
- ✅ Operations Agent vision (autonomous AI agents)
- ✅ API-first architecture
- ✅ Marketplace for 3rd-party apps
- ✅ Webhook support (real-time data sync)

**Integration Points (Phase 2):**
```
F&B Agent → Mews API

READ (Enhance predictions):
├─ GET /api/reservations → Occupancy forecast
│  Use case: 80% occupancy tomorrow + concert → higher covers prediction
│
├─ GET /api/guests/{id} → Guest dining preferences
│  Use case: VIP guest prefers Italian → recommend specific menu
│
└─ GET /api/events → Hotel events (conferences, weddings)
│   Use case: 200-person conference → F&B high demand
│   
├─ GET /api/reservations → Occupancy forecast
│  Use case: 80% occupancy tomorrow + concert → 145 covers (confidence boosted)
│  Logic: High occupancy = more in-house dining demand
│  Formula: Base prediction × (1 + occupancy_rate × 0.15)
│  Example: 130 covers base × (1 + 0.80 × 0.15) = 145 covers

WRITE (Future - auto-actions):
└─ POST /api/finance/charges → Post F&B charges to folios
   Use case: Room service order → auto-charge guest room
```

**Authentication:**
- OAuth 2.0 with Mews
- API keys stored in environment variables (not committed)

**Webhooks (real-time updates):**
```
Mews → F&B Agent

Event: reservation.created
Payload: {guest_id, check_in, check_out, room_type}
Action: Update occupancy forecast → trigger new prediction
```

---

### Apaleo Integration (Secondary/Fallback)

**Why Apaleo:**
- ✅ API-first MACH architecture (aligned with our design)
- ✅ Sandbox environment (free developer testing)
- ✅ Apaleo Store (alternative distribution channel if Mews declines)
- ✅ Extensive API documentation (self-service API keys)

**Integration Points (Phase 2):**
```
F&B Agent → Apaleo API

READ:
├─ GET /booking/v1/reservations → Occupancy data
├─ GET /inventory/v1/properties → Property setup
└─ Webhook API → Real-time notifications

WRITE (Future):
└─ POST /finance/v1/folios/{id}/charges → F&B charges
```

**Sandbox Testing (Phase 1.5):**
1. Create Apaleo developer account (free)
2. Provision sandbox with sample data
3. Test API integration (2-3 days effort)
4. Document compatibility in case study

**Strategic Value:**
- Demonstrates interoperability (not vendor lock-in)
- Backup distribution channel (Apaleo Store if Mews declines)
- Enterprise angle (Apaleo targets hotel chains)

---

### Integration Architecture Pattern

**Phase 1 (MVP):** Direct API calls
```
Backend → PMS API (point-to-point)
```

**Phase 2 (Production):** Event-driven
```
Backend → Message Queue (RabbitMQ/Kafka) → Workers
                                              ↓
                                          PMS APIs
```

**Benefits event-driven:**
- Fault tolerance (retry failed API calls)
- Scalability (100+ restaurants, 1000s requests/day)
- Decoupling (add new PMS without backend changes)

---

## Data Models

### Database Schema (Supabase PostgreSQL)
```sql
-- Predictions table
CREATE TABLE predictions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  restaurant_id VARCHAR(50) NOT NULL,
  service_date DATE NOT NULL,
  service_type VARCHAR(20) NOT NULL, -- 'lunch' | 'dinner' | 'brunch'
  predicted_covers INTEGER NOT NULL,
  confidence DECIMAL(3,2) NOT NULL, -- 0.00 to 1.00
  reasoning JSONB NOT NULL, -- Full reasoning object
  staff_recommendation JSONB NOT NULL,
  approved BOOLEAN DEFAULT NULL, -- NULL = pending, TRUE = approved, FALSE = rejected
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Patterns table (vector embeddings stored in Qdrant)
CREATE TABLE patterns (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  restaurant_id VARCHAR(50) NOT NULL,
  service_date DATE NOT NULL,
  service_type VARCHAR(20) NOT NULL,
  event_type VARCHAR(100), -- 'Concert', 'Holiday', 'Weather', etc.
  actual_covers INTEGER NOT NULL,
  embedding_id VARCHAR(100) NOT NULL, -- Reference to Qdrant vector
  metadata JSONB, -- Weather, distance, day_of_week, etc.
  created_at TIMESTAMP DEFAULT NOW()
);

-- Feedback table (learning loop)
CREATE TABLE feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prediction_id UUID REFERENCES predictions(id),
  manager_action VARCHAR(20) NOT NULL, -- 'approved' | 'rejected' | 'adjusted'
  actual_covers INTEGER, -- NULL if not yet known
  adjusted_covers INTEGER, -- Only if action = 'adjusted'
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_predictions_restaurant_date ON predictions(restaurant_id, service_date);
CREATE INDEX idx_patterns_restaurant_type ON patterns(restaurant_id, service_type);
CREATE INDEX idx_feedback_prediction ON feedback(prediction_id);
```

---

### Qdrant Collections
```python
# Pattern embeddings collection
collection_name = "fb_patterns"

vector_config = {
    "size": 1536,  # Claude embedding dimensions
    "distance": "Cosine"  # Similarity metric
}

payload_schema = {
    "pattern_id": "string",
    "restaurant_id": "string",
    "service_date": "string",
    "service_type": "string",
    "event_type": "string",
    "actual_covers": "integer",
    "metadata": {
        "weather": "string",
        "day_of_week": "string",
        "distance_km": "float"
    }
}
```

---

## Security & Compliance

### MVP (Phase 1-3)

**Authentication:**
- No auth (single-user demo)
- API keys in `.env` (not committed to GitHub)

**Data Protection:**
- HTTPS everywhere (TLS 1.3)
- API keys stored in environment variables
- No PII stored (restaurant data only, no guest names)

**CORS:**
```python
# FastAPI CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://fbagent.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Production (Phase 3+)

**Authentication & Authorization:**
- JWT tokens (Supabase Auth)
- Role-Based Access Control (RBAC):
  - `manager`: Create predictions, approve/reject
  - `owner`: View analytics, manage settings
  - `admin`: Full access, multi-property management

**Data Encryption:**
- At rest: Supabase built-in encryption (AES-256)
- In transit: HTTPS/TLS 1.3 mandatory
- API keys: Encrypted in database (not plaintext)

**Privacy Compliance:**
- GDPR-ready: Data deletion endpoints, consent tracking
- CCPA-ready: User data export, opt-out mechanisms
- Data residency: Supabase EU region for European customers

**Security Monitoring:**
- Rate limiting: 100 requests/minute per IP (prevent abuse)
- API logs: All requests logged (CloudWatch or Datadog)
- Error tracking: Sentry integration (catch crashes)

**Backups:**
- Supabase: Automatic daily backups (7-day retention)
- Qdrant: Snapshot exports weekly (S3 storage)

---

## Scalability Path

### MVP → 10 Restaurants

**Current architecture sufficient:**
- Single FastAPI server (Render free tier)
- Qdrant free tier <1GB (50 patterns × 10 restaurants = 500 patterns)
- Supabase free tier <500MB database

**Bottlenecks to monitor:**
- Claude API rate limits (10 requests/min free tier → upgrade if needed)
- Backend CPU (Render free tier sleeps after 15min → upgrade to $7/mo always-on)

---

### 10 → 100 Restaurants

**Required changes:**

1. **Backend horizontal scaling:**
   - Deploy 2-3 FastAPI instances (load balancer)
   - Upgrade Render to Starter ($7/mo) or Pro ($25/mo)

2. **Database scaling:**
   - Supabase Pro tier ($25/mo) for >500MB
   - Add read replicas if analytics queries slow

3. **Vector database:**
   - Qdrant Starter ($25/mo) for >1GB (5,000 patterns)
   - Optimize embeddings (quantization to reduce size)

4. **Caching:**
   - Redis caching layer (prevent duplicate API calls)
   - Cache predictions for 5 minutes (reduce Claude API costs)

---

### 100 → 1,000 Restaurants (Enterprise)

**Architecture evolution:**
```
Current: Monolith FastAPI
         ↓
Future: Microservices + Event-Driven

┌─────────────────────────────────────────┐
│         API Gateway (Kong/Traefik)      │
└─────────────────────────────────────────┘
              ↓         ↓         ↓
     [Prediction    [Patterns   [Feedback
       Service]      Service]    Service]
              ↓         ↓         ↓
         [Message Queue: RabbitMQ/Kafka]
              ↓         ↓         ↓
     [Claude      [Qdrant     [Supabase
      Worker]      Worker]     Worker]
```

**Additional components:**
- **Kubernetes:** Container orchestration (auto-scaling)
- **Message queue:** RabbitMQ or Kafka (async processing)
- **CDN:** CloudFront (cache static assets)
- **Monitoring:** Datadog or Prometheus + Grafana

**Cost at scale (1,000 restaurants):**
- Backend: $200/mo (Kubernetes cluster)
- Database: $199/mo (Supabase Team tier)
- Vector DB: $95/mo (Qdrant Scale tier)
- AI/ML: $150/mo (Claude API, 50K predictions/mo)
- **Total:** ~$650/mo → $0.65/restaurant/mo

---

## Key Architecture Decisions

### Decision 1: Claude over Mistral

**Context:** Need reasoning engine for predictions + explainability

**Decision:** Use Claude Sonnet 4 (not Mistral)

**Rationale:**
- **Better reasoning:** Claude excels at explanation generation (critical for trust)
- **Longer context:** 200K tokens vs Mistral 32K (future: multi-day context)
- **Artifacts:** Native structured output support
- **Cost acceptable:** $0.003/prediction (3x Mistral but worth it for quality)

**Trade-off:** Higher cost vs better reasoning → Quality wins for MVP

---

### Decision 2: Qdrant for Vector Search

**Context:** Need fast similarity search for pattern matching

**Decision:** Use Qdrant Cloud (not Pinecone or pgvector)

**Rationale:**
- **Free tier generous:** <1GB free (Pinecone $70/mo minimum)
- **Fast search:** <100ms latency (pgvector slower on large datasets)
- **Cloud-native:** No self-hosting complexity
- **Python client mature:** Well-documented, stable

**Trade-off:** Vendor lock-in risk → Mitigated by exporting vectors to S3 backup

---

### Decision 3: Voice-Available (not Voice-First)

**Context:** Discovery flagged voice unreliable in noisy environments

**Decision:** Voice opt-in (floating mic button), keyboard primary

**Rationale:**
- **Risk mitigation:** If voice fails in demo, keyboard works
- **User choice:** Managers decide when voice useful (not forced)
- **Accessibility:** Keyboard-first ensures no exclusion

**Trade-off:** Less "wow factor" vs more reliable UX → Reliability wins

---

### Decision 4: Reasoning Collapsible

**Context:** Discovery showed detailed reasoning can be "too complex"

**Decision:** Reasoning default = 1-line summary, expandable on demand

**Rationale:**
- **Cognitive load:** Most managers want confidence score, not 3 patterns
- **Progressive disclosure:** Power users can expand details
- **Faster UX:** Less visual clutter on dashboard

**Trade-off:** Less transparency by default vs cleaner UI → Balance with expand option

---

### Decision 5: No Auto-Actions (MVP)

**Context:** Trust-building critical in hospitality (63% want human-first)

**Decision:** Manager approves ALL predictions (no auto-push to 7shifts)

**Rationale:**
- **Trust:** Managers need control during learning phase
- **Safety:** Wrong prediction = revenue loss, over-staffing cost
- **Adoption:** Easier to adopt tool if feels safe (augmented not automated)

**Trade-off:** Manual approval step vs full automation → Trust wins for MVP

---

### Decision 6: PMS-Agnostic Design

**Context:** Avoid vendor lock-in, maximize market reach

**Decision:** Design for Mews + Apaleo + any API-first PMS

**Rationale:**
- **Market reach:** Mews + Apaleo = 1000s hotels addressable
- **Risk mitigation:** If Mews declines, pivot to Apaleo Store
- **Enterprise appeal:** Hotel chains want flexibility (not locked to 1 PMS)

**Trade-off:** Generic integration vs deep Mews-specific features → Generic wins for MVP

---

## Appendix

### Useful Links

- **Figma Mockups (Code):** https://github.com/[username]/FbOperationsAgent2
- **Cost Model:** [Google Sheet Link](https://docs.google.com/spreadsheets/d/1K2AZVUdOeTxWzZQb5FaFIbh_nJXkuGvjTrcNk0Z_OPQ/edit)
- **Problem Statement:** `docs/Problem_Statement.md`
- **MVP Scope:** `docs/MVP_SCOPE.md`

### Technology Documentation

- **Claude API:** https://docs.anthropic.com/
- **Qdrant:** https://qdrant.tech/documentation/
- **Supabase:** https://supabase.com/docs
- **FastAPI:** https://fastapi.tiangolo.com/
- **Next.js:** https://nextjs.org/docs

### PMS APIs

- **Mews API:** https://mews-systems.gitbook.io/connector-api/
- **Apaleo API:** https://apaleo.dev/

---

**Document Version:** 0.1.0  
**Last Updated:** December 2, 2025  
**Next Review:** Phase 3 completion (post-dashboard MVP)
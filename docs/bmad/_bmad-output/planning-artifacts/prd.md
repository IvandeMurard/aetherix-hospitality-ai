---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
  - step-09-functional
  - step-10-nonfunctional
  - step-11-polish
  - step-v-validation-fixes
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-Aetherix-2026-03-09.md
  - docs/ARCHITECTURE.md
  - docs/Cost_Model.md
  - docs/DEPLOYMENT.md
  - docs/HUGGINGFACE_ENV_SETUP.md
  - docs/IMPROVEMENT_RECOMMENDATIONS.md
  - docs/MVP_SCOPE.md
  - docs/NEXTJS_MIGRATION_PROMPT.md
  - docs/PHASE_0_REVIEW.md
  - docs/Problem_Statement.md
  - docs/ROADMAP_NOW_NEXT_LATER.md
  - docs/STREAMLIT_CLOUD_SETUP.md
  - docs/TROUBLESHOOTING.md
documentCounts:
  briefCount: 1
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 12
classification:
  projectType: saas_b2b
  domain: general
  complexity: medium
  projectContext: brownfield
workflowType: 'prd'
---

# Product Requirements Document - Aetherix

**Author:** IVAN
**Date:** 2026-03-09

## Executive Summary

Aetherix is an Agentic AI solution designed to solve the manual, anxiety-inducing process of F&B forecasting for hotel and restaurant managers. By transitioning from traditional, static "pull" dashboards to a proactive "push" model, Aetherix anticipates operational load. It synthesizes internal property data with an external semantic layer—incorporating local events, weather, booking pace, and real-time social sentiment—to deliver contextualized intelligence directly to departmental managers. This empowers them to shift their focus from wrestling with spreadsheets to delivering exceptional customer experiences, while simultaneously reducing food waste and optimizing labor costs.

### What Makes This Special

Aetherix differentiates itself through seamless integration and intelligent, timely delivery. Rather than requiring users to learn another complex dashboard, it pushes clear, highly reliable, and actionable predictions exactly when they are needed. The core innovation is the application of LLM reasoning across disparate data sources, transforming raw external and internal data into synthesized, human-in-the-loop operational guidance.

## Success Criteria

Aetherix's success is measured across three dimensions: prediction accuracy, operational trust, and financial impact.

### Forecast Accuracy
- **MAPE Target:** Occupancy, F&B covers, and staffing requirement prediction errors consistently below 10–15%.

### Operational Adoption & Trust
- **Agent Influence Rate:** ≥ 60% of staffing recommendations actively followed/approved by managers within the first 90 days of pilot.
- **Proactive Engagement:** ≥ 70% of managers consult the Aetherix forecast before scheduling by end of month 3.
- **Trust Attrition:** Managers who reject 2+ consecutive recommendations without engaging the Conversational Receipt ("Why?") function stays below 10%.

### Financial & Operational Impact
- **Labor Cost Variance:** Actual vs. budgeted labor costs reduced by -3% to -8% within 6 months of full deployment.
- **Idle Labor Hours:** Measurable reduction in paid hours during unpredicted quiet periods vs. pre-Aetherix baseline.

### MVP Pilot Gate
- PMS webhook trigger processed into a WhatsApp/SMS notification within 3 minutes.
- At least one pilot manager explicitly acts upon an Aetherix recommendation within the first 2 weeks.

---

## Project Classification

- **Project Type:** B2B SaaS (Agentic AI / Backend focused)
- **Domain:** Hospitality / F&B Operations
- **Complexity:** Medium (PMS integration, Semantic Data orchestration)
- **Context:** Brownfield (Integrating with existing property tech stacks)

## User Journeys

### 1. The F&B Manager (Primary User) - The "Surge" Save (Core Path)
**Background:** Sarah is the F&B Manager. She builds schedules every Thursday based on Mews 14-day forecasts. She hates Thursday afternoons because it’s 3 hours of manual Excel work.
**The Journey:**
- **Opening:** It's Tuesday morning. The hotel is sitting at a quiet 45% occupancy. Sarah hasn't scheduled any extra staff for the evening.
- **Rising Action:** At 10:00 AM, Sarah receives a WhatsApp ping from Aetherix: *"Alert: A tech conference relocated next door. While occupancy is 45%, historical captation rates during similar local events show a 25% bump in external walk-ins. Anticipating an extra £1,200 in F&B revenue tonight between 6 PM - 9 PM."*
- **Climax:** Sarah taps "View Details" to see the historical captation data Aetherix pulled. The message includes an actionable recommendation: *"Recommend calling in 2 additional servers and 1 prep cook (est. labor cost: £180). Target: 14 total F&B staff to capture the £1,200 revenue."*
- **Resolution:** Sarah immediately texts her on-call pool, secures the staff by 11:30 AM. She captures the external revenue that would have otherwise walked away due to long wait times, and her team avoids a dinner service meltdown. 

### 2. The Front Office Manager (Primary User) - The "False Alarm" (Edge Case)
**Background:** David is the Front Office Manager, highly skeptical of AI "hallucinations" and highly protective of his labor budget. 
**The Journey:**
- **Opening:** David gets an email alert from Aetherix on Friday morning: *"Severe weather warning (Thunderstorms) for Saturday afternoon. Mews currently shows 80% occupancy. Expect higher than normal room-service requests and earlier return times from guests."*
- **Rising Action:** David checks his native Mews dashboard—it shows nothing about weather, just the 80% static figure. He is skeptical and doesn't want to authorize overtime for extra room-service runners.
- **Climax:** David reads the "Explainability" section of the Aetherix email: *"Historical correlation shows that when PM thunderstorms hit during >75% occupancy weekends, in-room dining spikes by 60% compared to baseline."* 
- **Resolution:** The explanation convinces David. He approves the extra runner. When the storm hits at 3 PM and the phones light up, the team handles it effortlessly. His skepticism of the AI converts to operational trust.

### 3. The Director of Operations (Secondary User) - The Friday Audit
**Background:** Marcus oversees 3 properties. He doesn't make schedules, but he holds Sarah and David accountable for their P&L.
**The Journey:**
- **Opening:** It's Friday morning, time for his weekly financial review. Historically, he had to chase 3 different managers for their Excel sheets to figure out why labor was over budget last week.
- **Rising Action:** Marcus opens his inbox to find a weekly wrap-up email from Aetherix.
- **Climax:** The email clearly outlines: *"Property A followed 85% of staffing recommendations, resulting in a 4% labor cost reduction vs target. Property B ignored a weather-surge warning on Tuesday, resulting in £400 of uncaptured F&B revenue due to extreme wait times."*
- **Resolution:** Marcus now has objective, data-backed conversation starters for his 1:1s with his managers, rather than relying on their subjective memories of "how busy it felt."

### 4. The IT Director (Technical Journey) - The Painless Pilot
**Background:** Elena is the IT Director. She is exhausted by "innovative startups" pitching tools that require 6 months of active database integration.
**The Journey:**
- **Opening:** The GM tells her they are piloting Aetherix. She groans, expecting a massive integration headache.
- **Rising Action:** Elena joins the onboarding call. The Aetherix team requests a read-only webhook/API key from Apaleo. No custom middleware, no 2-way write risks. 
- **Climax:** She provisions the key in 10 minutes. Aetherix instantly begins ingesting historical data to establish baselines. 
- **Resolution:** Elena is thrilled. The product lives up to its "easy to integrate" differentiator, and she doesn't have to devote any engineering hours to maintain it.

### Journey Requirements Summary
- **Mews/Apaleo 1-Way Sync:** Required for Elena's journey and to feed Sarah/David's baselines.
- **Semantic Event/Weather Engine:** Required to generate the "Surge" and "False Alarm" notifications.
- **Captation & Revenue Engine:** Required to calculate historical external/internal capture rates and estimate financial impact vs. labor cost.
- **Explainability Logging:** Required to convert David's skepticism into trust.
- **Multi-Channel Delivery (Push):** The system must support WhatsApp, SMS, and Email delivery logic.
- **Aggregation/Reporting Engine:** Needed to compile Marco's weekly summary emails based on actioned vs. unactioned alerts.

## Domain-Specific Requirements

### Compliance & Regulatory
- **GDPR / Data Privacy (Guests):** To comply with stringent EU data protection laws, Aetherix must operate on *anonymized, aggregated booking/occupancy counts* rather than processing Personally Identifiable Information (PII) of individual guests.
- **Labor Law & Union Compliance:** In many operational jurisdictions (especially the EU), altering schedules within 24–48 hours requires premium pay, penalty rates, or explicit union/employee consent. Aetherix's "cost" estimations for shift changes must eventually factor in these localized penalties.

### Technical Constraints
- **Integration Reliability:** Relying on read-only API access to legacy/modern PMS systems (Mews/Apaleo), which necessitates robust error handling for connection drops.
- **API Rate Limiting:** While not a primary hurdle, the architecture should cache data appropriately to avoid aggressive rate-limiting penalties from upstream PMS providers.

### Future Scope Considerations (Post-MVP)
- **Agentic Staff Selection (Labor Law Aware):** Moving beyond simply suggesting *"add 2 servers"*, the agent must eventually analyze the specific day of the week, the required skill level for the workload, and individual employee constraints (overtime tracking, labor law mandated rest periods, union seniority rules) to suggest *which specific members of staff* to call in—effectively acting as a compliance filter for the manager.

## Innovation & Novel Patterns

### Detected Innovation Areas
**Contextual Revenue/Labor Arbitrage:** Aetherix's true innovation is not "push notifications." It is the mathematical translation of chaotic external semantic data (weather, events, traffic) into specific, high-ROI operational directives. It identifies real-time arbitrage opportunities (e.g., spending £180 on reactive labor to capture £1,200 of external walk-in revenue, while factoring in potential labor-law penalty pay).

### Market Context & Competitive Landscape
Existing scheduling solutions (Planday, Quinyx) and PMS native tools (Mews) rely entirely on "pull" mechanics—a manager must log into a dashboard, stare at historical data, and guess the future. Aetherix flips this paradigm into a proactive "push" model, acting as an ambient co-pilot rather than a static tool.

### Validation Approach
**Operational Trust Metric:** The innovation is validated not by forecast accuracy (MAPE) alone, but by the "Trust Attrition" rate. Validation requires tracking the percentage of Aetherix recommendations that are explicitly approved and actioned by the manager, minus the percentage of regretted decisions. 

### Risk Management & Vendor Lock-In
1. **Trust Attrition (The "Boy Who Cried Wolf" Risk):** Providing a traditional dashboard to "explain" the AI's math defeats the core vision of a "push" agent. Mitigation: **"Conversational Receipts"**. When a manager replies "?" or "Why?" to a recommendation via WhatsApp/SMS, Aetherix instantly responds with the mathematical breakdown (e.g., *"3 identical tech conferences in the last 2 years resulted in +25% F&B captation in our venue"*). Trust is built via immediate, conversational Q&A.
2. **PMS Vendor Lock-In:** Mitigation requires abstracting the data ingestion layer so Aetherix can plug into legacy systems (Opera) as easily as cloud systems (Mews/Apaleo).

## B2B SaaS Specific Requirements

### Technical Architecture Considerations

**Multi-Tenant Model & Data Governance**
To respect stringent data governance and isolated environments, Aetherix will employ a hybrid multi-tenant architecture. 
- *Data Isolation:* Each hotel property's PMS data (Mews/Apaleo) will be strictly siloed at the database row-level (Logically Isolated) to ensure no cross-contamination of competitive booking data.
- *Semantic Layer Aggregation:* Unlike internal PMS data, the external Semantic Layer (weather, city-wide events, flight data) is globally shared. A single semantic pipeline will serve all tenants, reducing API costs, while the context is applied locally per tenant.
- *Portfolio Roll-up:* For features like Marco's "Friday Audit", data from siloed properties under the same management umbrella will be aggregated at the application layer, not the database layer.

**Permission Model (RBAC)**
The security and role model will be explicitly defined (not flattened) for the MVP.
- *Strict Departmental Silos:* An F&B Manager (Sarah) will only receive and have access to F&B specific surge alerts and analytics. She cannot view Front Office (David) alerts, maintaining departmental focus and preventing alert fatigue across the property.

**Subscription Tiers (Monetization)**
- **MVP Tier:** Free to install and use during the pilot phase to eliminate friction and build the necessary historical baselines for the AI.
- **Growth Tiers (Post-MVP):** Monetization will hinge on value-based metrics rather than simple "seat licenses." Pricing will scale based on Data Integration Volume (connecting POS systems like Zelty/Lightspeed + PMS + Booking.com) and the complexity of the semantic usage.

**Integrations Stack**
The architecture must support robust API integrations across three distinct layers:
1. **Property Data (Internal):** Mews/Apaleo (PMS), extending to POS systems (Zelty, L'Addition, Lightspeed, Zenchef) post-MVP.
2. **Semantic Data (External):** Weather APIs, Event APIs (PredictHQ), Flight Arrivals, and Real-Time Social Sentiment data scraping.
3. **Distribution Data (External/Internal):** OTAs (Booking.com) to cross-reference with direct PMS bookings.
4. **Delivery Layer:** Twilio (SMS), WhatsApp Business API, and SendGrid/Postmark (Email).

**Data Retention Strategy**
- **Raw API Logs:** Retained for a maximum of 30 days for debugging.
- **Anonymized Baselines:** Aggregated occupancy and revenue data (stripped of guest PII) will be retained indefinitely to train and improve the localized AI models.
- **Audit/Explainability Logs:** The "Conversational Receipts" logic (why a recommendation was made) will be retained indefinitely to prove regulatory compliance in case of labor-law/union disputes regarding short-notice scheduling.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy
**MVP Approach:** "Trust & Arbitrage Validation." The MVP is exclusively focused on proving that Aetherix can ingest semantic data, push a high-ROI staffing recommendation via WhatsApp/SMS, and have a manager explicitly action it. 

### MVP Feature Set (Phase 1: Validation)
**Core User Journeys Supported:**
- The F&B Manager (The "Surge" Save)
- The Front Office Manager (The "False Alarm")
- The IT Director (The Painless Pilot)

**Must-Have Capabilities (The Deal-Breakers):**
- 1-way read sync with Mews/Apaleo (Occupancy & Revenue baselines).
- Semantic Event Engine (PredictHQ) & Weather API integration.
- The "Push" Engine (WhatsApp/SMS delivery + Conversational Receipts for explainability).
- Logical Multi-Tenancy (from our Step 7 discussion).

### Post-MVP Features

**Phase 2: Growth (Monetization & Complexity)**
- POS Integrations (Zelty, L'Addition, Lightspeed) for highly granular F&B tracking.
- Flight Arrival APIs and real-time social sentiment scraping.
- The "Friday Audit" Reporting Engine for the Director of Operations.

**Phase 3: Expansion (Full Automation)**
- Agentic Staff Selection (Labor Law Aware): The agent moves from "Add 2 servers" to "Call Sarah and Mike, they haven't hit overtime."
- 2-Way PMS Write Sync.


## Functional Requirements

### Data Ingestion & Baseline Sync
- **FR1:** The system can ingest anonymized occupancy and historical revenue data from Apaleo and Mews.
- **FR2:** The system can sync read-only data from the PMS every 15 minutes (or in near-real-time via webhook) without requiring manual imports.
- **FR3:** The system can calculate historical baseline captation rates for F&B and Room Service based on past occupancy and external data.

### Semantic Reasoning Engine
- **FR4:** The system can ingest local weather forecast data within a configurable geographic radius (default: 5km from the property's registered GPS coordinates).
- **FR5:** The system can ingest local event data (conferences, concerts, sports events) within a configurable geographic radius (default: 5km from the property's registered GPS coordinates).
- **FR6:** The system can cross-reference upcoming occupancy with weather and event data to identify anomalies in historical captation patterns.
- **FR7:** The system can calculate an estimated financial ROI (revenue opportunity vs labor cost) for identified anomalies.
- **FR8:** The system can generate specific staffing recommendations (e.g., "Add 2 servers") based on the calculated ROI and expected operational load.

### Notification & Delivery (The "Push" Engine)
- **FR9:** The system can push actionable alerts to specific users via WhatsApp.
- **FR10:** The system can push actionable alerts to specific users via SMS.
- **FR11:** The system can push actionable alerts to specific users via Email.
- **FR12:** The system can format alerts to include the context (e.g., event name, weather condition) and the specific staffing recommendation.

### Explainability & Audit (Conversational Receipts)
- **FR13:** A user can reply to a push notification with a query (e.g., "?", "Why?").
- **FR14:** The system can parse a manager's inbound query and return the specific mathematical and historical context used to generate the recommendation within 3 seconds for the 95th percentile of requests (Zero-Dashboard Trust).
- **FR15:** A user can explicitly accept or reject a staffing recommendation via the push channel.
- **FR16:** The system can log all manager responses (acceptances, rejections) to staffing recommendations.
- **FR17:** *[Phase 2]* The system can generate a weekly aggregated report of actioned vs unactioned alerts and their estimated financial impact.
- **FR18:** *[Phase 2]* The system can send the weekly aggregated report to designated secondary users (e.g., Director of Operations).

### Tenant Management & RBAC
- **FR19:** The system can logically partition data so that users can only access information pertaining to their assigned property (Tenant ID).
- **FR20:** The system can restrict alerts so that users only receive notifications relevant to their department (e.g., F&B vs Front Office).
- **FR21:** The system can aggregate data across multiple properties within the same portfolio for upper-management reporting.

## Non-Functional Requirements

### Integration & Reliability
- **NFR1:** The system must gracefully handle up to 60 seconds of downtime or API rate-limiting from upstream PMS providers (Mews/Apaleo) by retrying without dropping the synchronization sequence.
- **NFR2:** Message delivery latency (WhatsApp/SMS) from the moment an anomaly is detected by the semantic engine must be under 3 minutes.

### Security & Compliance
- **NFR3:** The system must completely strip and hash all Guest Personally Identifiable Information (PII) before it is committed to the Aetherix database to ensure GDPR compliance, as verified by automated test suite coverage and quarterly data audits.
- **NFR4:** All API keys and Webhook secrets used to communicate with PMS partners must be encrypted at rest using AES-256.

### Scalability & Performance
- **NFR5:** The global Semantic Engine (weather/events) must process data for up to 50 individual hotel tenants within the same geographic radius within a 5-second processing time limit.
- **NFR6:** The Conversational Receipt endpoint (answering "Why?" queries) must respond to the manager's WhatsApp/SMS message within 3 seconds for the 95th percentile of requests.

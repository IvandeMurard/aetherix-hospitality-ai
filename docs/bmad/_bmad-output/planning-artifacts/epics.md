---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
---

# Aetherix - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Aetherix, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

- FR1: The system can ingest anonymized occupancy and historical revenue data from Apaleo and Mews.
- FR2: The system can sync read-only data from the PMS every 15 minutes (or in near-real-time via webhook) without requiring manual imports.
- FR3: The system can calculate historical baseline captation rates for F&B and Room Service based on past occupancy and external data.
- FR4: The system can ingest local weather forecast data within a configurable geographic radius (default: 5km from the property's registered GPS coordinates).
- FR5: The system can ingest local event data (conferences, concerts, sports events) within a configurable geographic radius (default: 5km from the property's registered GPS coordinates).
- FR6: The system can cross-reference upcoming occupancy with weather and event data to identify anomalies in historical captation patterns.
- FR7: The system can calculate an estimated financial ROI (revenue opportunity vs labor cost) for identified anomalies.
- FR8: The system can generate specific staffing recommendations (e.g., "Add 2 servers") based on the calculated ROI and expected operational load.
- FR9: The system can push actionable alerts to specific users via WhatsApp.
- FR10: The system can push actionable alerts to specific users via SMS.
- FR11: The system can push actionable alerts to specific users via Email.
- FR12: The system can format alerts to include the context (e.g., event name, weather condition) and the specific staffing recommendation.
- FR13: A user can reply to a push notification with a query (e.g., "?", "Why?").
- FR14: The system can parse a manager's inbound query and return the specific mathematical and historical context used to generate the recommendation within 3 seconds for the 95th percentile of requests (Zero-Dashboard Trust).
- FR15: A user can explicitly accept or reject a staffing recommendation via the push channel.
- FR16: The system can log all manager responses (acceptances, rejections) to staffing recommendations.
- FR17: [Phase 2] The system can generate a weekly aggregated report of actioned vs unactioned alerts and their estimated financial impact.
- FR18: [Phase 2] The system can send the weekly aggregated report to designated secondary users (e.g., Director of Operations).
- FR19: The system can logically partition data so that users can only access information pertaining to their assigned property (Tenant ID).
- FR20: The system can restrict alerts so that users only receive notifications relevant to their department (e.g., F&B vs Front Office).
- FR21: The system can aggregate data across multiple properties within the same portfolio for upper-management reporting.

### NonFunctional Requirements

- NFR1: The system must gracefully handle up to 60 seconds of downtime or API rate-limiting from upstream PMS providers (Mews/Apaleo) by retrying without dropping the synchronization sequence.
- NFR2: Message delivery latency (WhatsApp/SMS) from the moment an anomaly is detected by the semantic engine must be under 3 minutes.
- NFR3: The system must completely strip and hash all Guest Personally Identifiable Information (PII) before it is committed to the Aetherix database to ensure GDPR compliance, as verified by automated test suite coverage and quarterly data audits.
- NFR4: All API keys and Webhook secrets used to communicate with PMS partners must be encrypted at rest using AES-256.
- NFR5: The global Semantic Engine (weather/events) must process data for up to 50 individual hotel tenants within the same geographic radius within a 5-second processing time limit.
- NFR6: The Conversational Receipt endpoint (answering "Why?" queries) must respond to the manager's WhatsApp/SMS message within 3 seconds for the 95th percentile of requests.

### Additional Requirements

- **Starter Template Constraint**: Epic 1 Story 1 MUST be initializing `vintasoftware/nextjs-fastapi-template` for the Next.js frontend and FastAPI backend.
- Database: Establish Supabase (PostgreSQL) with `pgvector` enabled and handle strict Row-Level Security (RLS) for tenant data isolation.
- Infrastructure: Implement a split deployment strategy—Vercel for the Next.js frontend and Render/Railway for the Dockerized FastAPI backend.
- Background Processing: FastAPI must utilize `BackgroundTasks` decoupled from immediate HTTP 200 responses to safely handle Twilio webhooks and external API (Claude) calls, avoiding cold start and timeout issues.
- Integration Targets: Direct hookups to Mews/Apaleo platforms for PMS, PredictHQ for events, Twilio for communication, SendGrid for Email, and Claude for LLM features.
- Naming convention alignment: Internal Python representations and database models must strictly use `snake_case`, mapped to output `camelCase` for the Next.js TypeScript frontend using Pydantic aliases.
- Shared Error Handling: Standardized Problem Details (RFC 7807) formatting must be utilized for all HTTP exceptions thrown by the FastAPI backend.

### FR Coverage Map

- FR19: Epic 1 - Establish Database with Tenant Isolation
- FR20: Epic 1 - User Registration & Routing
- FR1: Epic 2 - Operations Baseline (PMS Data Sync)
- FR2: Epic 2 - Operations Baseline (PMS Data Sync)
- FR6: Epic 3 - Story 3.3a (Anomaly Detection)
- FR7: Epic 3 - Story 3.3b (ROI Calculation)
- FR8: Epic 3 - Story 3.3c (Recommendation Formatting)

## Epic List

### Epic 1: Workspace & Identity (The Foundation)
Initialize the tenant workspace, user identity, and the core application structure so that managers can securely access their isolated property data.
**FRs covered:** FR19, FR20

### Epic 2: Operations Baseline (PMS Data Sync)
Securely ingest and sync historical and future hotel occupancy data from Apaleo/Mews so that Aetherix has an accurate baseline of business volume to work from.
**FRs covered:** FR1, FR2, FR3

### Epic 3: The Semantic Anomaly Engine
Ingest localized weather and event data to cross-reference with the baseline, identifying actionable F&B surges or lulls.
**FRs covered:** FR4, FR5, FR6 *(Story 3.3a)*, FR7 *(Story 3.3b)*, FR8 *(Story 3.3c)*

### Epic 4: Proactive "Push" Delivery & Action Logging
Push the calculated staffing recommendations directly to the managers via their preferred channels (WhatsApp/SMS/Email) and record their accept/reject decisions.
**FRs covered:** FR9, FR10, FR11, FR12, FR15, FR16

### Epic 5: Conversational Receipts (Trust & Explainability)
Allow managers to reply "Why?" to any alert and instantly receive the mathematical/historical context behind the AI's recommendation, fostering operational trust.
**FRs covered:** FR13, FR14

### Epic 6: Cross-Property Intelligence & Reporting (Phase 2)
Aggregate actioned vs. unactioned recommendations across multiple tenant properties to provide Directors of Operations with weekly financial impact reports.
**FRs covered:** FR17, FR18, FR21

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Workspace & Identity (The Foundation)

Initialize the tenant workspace, user identity, and the core application structure so that managers can securely access their isolated property data.

### Story 1.1: Initialize Project using Next.js/FastAPI Template

As a Technical Lead,
I want to initialize the project using the `vintasoftware/nextjs-fastapi-template`,
So that the Next.js frontend and Python FastAPI backend are established with type safety and Docker support.

**Acceptance Criteria:**

**Given** the repository is empty
**When** the template is initialized
**Then** the Next.js frontend and FastAPI backend directories exist
**And** the project can be spun up locally using Docker Compose without errors
**And** the API client generation from OpenAPI schema is configured between backend and frontend
**And** the FastAPI app is configured to use RFC 7807 Problem Details for HTTP errors

### Story 1.2: Establish Supabase Database with Tenant Isolation (RLS)

As a System Administrator,
I want the Supabase database to be configured with Row-Level Security (RLS) linked to Tenant IDs,
So that no hotel property can ever query another property's data (FR19).

**Acceptance Criteria:**

**Given** a Supabase PostgreSQL instance
**When** the core tables (users, properties, events) are migrated
**Then** `pgvector` extension must be enabled
**And** Row-Level Security (RLS) policies must be applied ensuring queries only return rows where `tenant_id` matches the authenticated user
**And** Python backend models must use `snake_case` mapped to `camelCase` for outputs

### Story 1.3: User Registration & Routing

As an F&B or Front Office Manager,
I want to securely log into my property's workspace,
So that I can configure my specific department's alert preferences (FR20).

**Acceptance Criteria:**

**Given** a manager has an account
**When** they log in via the Next.js frontend
**Then** they are authenticated against Supabase Auth
**And** their session token correctly identifies their `tenant_id` and `department_role` (F&B vs Front Office)
**And** they are routed to the main dashboard

## Epic 2: Operations Baseline (PMS Data Sync)

Securely ingest and sync historical and future hotel occupancy data from Apaleo/Mews so that Aetherix has an accurate baseline of business volume to work from.

### Story 2.1: Establish PMS API Connection & Auth

As a System Administrator,
I want to securely store and use Mews/Apaleo API credentials for my property,
So that Aetherix can authenticate with the PMS securely (NFR4).

**Acceptance Criteria:**

**Given** a manager provides an API key
**When** they save it in the Next.js dashboard
**Then** it is transmitted securely to the FastAPI backend
**And** it is encrypted at rest using AES-256 in the Supabase database
**And** the FastAPI backend can retrieve and decrypt the key to establish a successful ping to the PMS sandbox

### Story 2.2: Initial Historical Data Ingestion

As a Data Pipeline,
I want to pull historical occupancy and F&B revenue data from the PMS and strip all PII,
So that we can establish mathematical baselines safely (FR1, NFR3).

**Acceptance Criteria:**

**Given** a valid PMS API connection
**When** the initial sync is triggered
**Then** historical reservation and revenue data is requested
**And** all Guest Personally Identifiable Information (name, email, phone) is immediately stripped/hashed before inserting into Supabase
**And** the data is associated with the correct `tenant_id`

### Story 2.3: Continuous Sync via Webhook/Polling

As a Data Pipeline,
I want to continuously ingest new occupancy data every 15 minutes or via webhook, with retry logic,
So that the baseline stays accurate even if the PMS goes down briefly (FR2, NFR1).

**Acceptance Criteria:**

**Given** an active tenant
**When** a webhook is received or the 15-minute polling interval hits
**Then** new PMS data is ingested (PII stripped)
**And** this ingestion process is handled asynchronously via FastAPI `BackgroundTasks`
**And** if the PMS API rate-limits or times out, the system automatically retries with exponential backoff for up to 60 seconds before failing gracefully

### Story 2.4: Calculate Baseline Captation Rates

As the Reasoning Engine,
I want to calculate the property's historical captation rates (occupancy vs. F&B walk-ins or room service orders),
So that I have a standard baseline to compare future anomalies against (FR3).

**Acceptance Criteria:**

**Given** historical occupancy and revenue data in Supabase
**When** the baseline calculation is triggered
**Then** it calculates the average F&B revenue per occupied room
**And** it calculates the average room service orders per occupied room
**And** both F&B and room service baseline metrics are stored securely against the `tenant_id`
**And** baseline metrics are segmented by day-of-week to account for weekly demand patterns

## Epic 3: The Semantic Anomaly Engine

Ingest localized weather and event data to cross-reference with the baseline, identifying actionable F&B surges or lulls.

### Story 3.1: Ingest Localized Weather Data

As the Semantic Engine,
I want to ingest local weather forecast data for a property,
So that I can identify weather patterns that historically impact F&B or Room Service demand (FR4).

**Acceptance Criteria:**

**Given** a property has configured GPS coordinates
**When** the 12-hour weather sync runs
**Then** weather forecast data within a 5km radius is ingested into Supabase
**And** the data is associated with the correct `tenant_id` and normalized for cross-referencing

### Story 3.2: Ingest Localized Event Data from PredictHQ

As the Semantic Engine,
I want to ingest local event data (conferences, concerts) for a property via PredictHQ,
So that I can identify external factors driving sudden occupancy or walk-in surges (FR5).

**Acceptance Criteria:**

**Given** a property has configured GPS coordinates
**When** the daily event sync runs
**Then** upcoming events within a 5km radius are ingested into Supabase
**And** the events are categorized (e.g., tech conference, sports) for historical pattern matching

### Story 3.3a: Detect Demand Anomalies Against Baseline

As the Reasoning Engine,
I want to cross-reference upcoming occupancy, weather, and event data against historical baselines,
So that I can identify periods where demand is expected to significantly deviate from normal (FR6).

**Acceptance Criteria:**

**Given** active weather/event data and a calculated historical baseline for a tenant
**When** the anomaly detection engine runs (within the <5s global processing limit - NFR5)
**Then** it compares expected demand for each upcoming 4-hour time window against the historical baseline
**And** it flags windows where expected demand deviates by more than a configurable threshold (default: 20%)
**And** each anomaly is saved to the database with the triggering factors (weather event, external event, occupancy level) and `tenant_id`
**And** the entire anomaly scan across all active tenants completes within 5 seconds (NFR5)

### Story 3.3b: Calculate Financial ROI for Detected Anomalies

As the Reasoning Engine,
I want to calculate the estimated financial ROI for each detected anomaly,
So that I can quantify the revenue opportunity vs. the cost of extra staffing (FR7).

**Acceptance Criteria:**

**Given** a flagged anomaly in the database
**When** the ROI calculation runs
**Then** it calculates the estimated additional revenue opportunity (based on captation rate × expected walk-ins × average spend)
**And** it calculates the estimated labor cost of the recommended additional staff (headcount × hourly rate)
**And** it computes a net ROI figure (revenue opportunity minus labor cost)
**And** if the net ROI is positive, the anomaly is marked as `roi_positive` and eligible for recommendation dispatch
**And** the ROI breakdown (revenue opportunity, labor cost, net ROI) is saved alongside the anomaly record

### Story 3.3c: Format Staffing Recommendations for Dispatch

As the Reasoning Engine,
I want to format ROI-positive anomalies into specific, plain-text staffing recommendations,
So that the Push Delivery engine has a ready-to-dispatch message for the manager (FR8).

**Acceptance Criteria:**

**Given** an anomaly flagged as `roi_positive`
**When** the recommendation formatter runs
**Then** it generates a specific plain-text staffing directive (e.g., "Add 2 servers and 1 prep cook to capture an estimated £800 in walk-in revenue tonight between 6–9 PM")
**And** the recommendation includes the triggering factor (e.g., "Tech conference relocated nearby")
**And** the recommendation includes the estimated labor cost of the change (e.g., "Est. additional labor cost: £180")
**And** the formatted recommendation is saved to the database flagged as `ready_to_push`, linked to the originating anomaly and `tenant_id`

## Epic 4: Proactive "Push" Delivery & Action Logging

Push the calculated staffing recommendations directly to the managers via their preferred channels (WhatsApp/SMS/Email) and record their accept/reject decisions.

### Story 4.1: Integrate Twilio/WhatsApp/SendGrid Outbound APIs

As a System Administrator,
I want the application to connect to Twilio (SMS/WhatsApp) and SendGrid (Email),
So that the system can push notifications to managers without requiring a custom app (FR9, FR10, FR11).

**Acceptance Criteria:**

**Given** valid API keys
**When** the backend is initialized
**Then** it successfully connects to Twilio and SendGrid
**And** a test message can be dispatched via each channel (SMS, WhatsApp, Email) without errors

**Given** a manager is logged into the Next.js settings page
**When** they configure their notification preferences
**Then** the UI provides fields for: preferred delivery channel (SMS, WhatsApp, or Email), phone number (for SMS/WhatsApp), and email address
**And** the UI provides a field for their property's GPS coordinates (latitude, longitude) used by the Semantic Engine
**And** all preferences are saved to the manager's profile in Supabase, associated with their `tenant_id` and `department_role`
**And** a test notification can be triggered from the UI to confirm delivery

### Story 4.2: Format & Dispatch Alerts

As the Delivery Engine,
I want to format the AI's plain-text recommendation into a channel-appropriate message and dispatch it,
So that managers receive the alert within 3 minutes of the anomaly being detected (FR12, NFR2).

**Acceptance Criteria:**

**Given** a "Ready to Push" recommendation in the database
**When** the polling worker picks it up
**Then** it generates the final message including the contextual factor (e.g., "Thunderstorms")
**And** it dispatches the message via the manager's preferred channel
**And** the message is successfully delivered within 3 minutes of the initial anomaly detection (NFR2)

### Story 4.3: Action Logging (Accept/Reject)

As an F&B Manager,
I want to be able to reply "Accept" or "Reject" to the alert,
So that my decisions are logged for later accountability (FR15, FR16).

**Acceptance Criteria:**

**Given** an inbound Webhook from Twilio (manager replied)
**When** the reply is precisely "Accept" or "Reject"
**Then** the FastAPI Webhook router parses it
**And** it updates the status of the recommendation in the Supabase database to reflect the manager's choice

## Epic 5: Conversational Receipts (Trust & Explainability)

Allow managers to reply "Why?" to any alert and instantly receive the mathematical/historical context behind the AI's recommendation, fostering operational trust.

### Story 5.1: Parse Conversational Inbound Queries

As the Delivery Engine,
I want to route non-action inbound replies (like "Why?" or specific questions) to the AI reasoning engine,
So that we can handle natural language queries from managers via Twilio webhooks (FR13).

**Acceptance Criteria:**

**Given** an inbound Webhook from Twilio
**When** the text is a question (not a strict "Accept/Reject")
**Then** the FastAPI router kicks off a `BackgroundTask`
**And** it identifies the `tenant_id` and the specific recommendation being queried based on the sender's phone number

### Story 5.2: Generate LLM-powered Explainability Receipt

As the Reasoning Engine,
I want to use Claude to instantly read the math behind the recommendation and explain it clearly to the manager,
So that I can build trust by explaining the data (FR14, NFR6).

**Acceptance Criteria:**

**Given** an inbound question
**When** passed to the Claude API
**Then** Claude is provided the specific historical data (e.g., "3 tech conferences resulted in +25% F&B captation") used to make the prediction
**And** Claude generates a friendly, concise explanation
**And** the reply is dispatched back via Twilio within 3 seconds (P95) of the initial inbound query (NFR6)

## Epic 6: Cross-Property Intelligence & Reporting (Phase 2)

Aggregate actioned vs. unactioned recommendations across multiple tenant properties to provide Directors of Operations with weekly financial impact reports.

### Story 6.1: Cross-Property Data Aggregation

As a Director of Operations,
I want to view aggregated data across all properties in my portfolio,
So that I can monitor portfolio-wide compliance and performance without logging into individual properties (FR21).

**Acceptance Criteria:**

**Given** a Director user account linked to multiple `tenant_id`s
**When** they log into the dashboard
**Then** the system queries ONLY data belonging to `tenant_id`s explicitly linked to that Director's account (RBAC boundary — no cross-portfolio data leakage)
**And** they can view an aggregated list of all staffing recommendations made across those properties over the last 7 days
**And** the data clearly shows which recommendations were "Actioned" vs "Ignored"
**And** a Director cannot access or view recommendation data from properties not linked to their account

### Story 6.2: Weekly ROI Calculation

As the Reporting Engine,
I want to calculate the theoretical financial impact of actioned vs. unactioned alerts for a property,
So that I can provide an objective ROI metric for the week (FR17).

**Acceptance Criteria:**

**Given** a week of logged recommendations
**When** the weekly cron job runs
**Then** it calculates the estimated labor cost saved (or revenue captured) for "Actioned" alerts
**And** it calculates the "Missed Opportunity" cost for "Ignored" alerts
**And** it generates a summary report formatted for email delivery

### Story 6.3: Automated Report Delivery

As a Director of Operations,
I want to automatically receive the weekly financial impact report via email on Friday mornings,
So that I have data-backed conversation starters for my 1:1s with managers (FR18).

**Acceptance Criteria:**

**Given** a generated weekly ROI report
**When** it is 8:00 AM on Friday (local property time)
**Then** the FastAPI `BackgroundTask` triggers sending the email via SendGrid
**And** the email contains clear, high-level summaries of trust attrition (ignored alerts) and financial impact

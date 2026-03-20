# Story 1.2: Establish Supabase Database with Tenant Isolation (RLS)

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a System Administrator,
I want the Supabase database to be configured with Row-Level Security (RLS) linked to Tenant IDs,
So that no hotel property can ever query another property's data (FR19).

## Acceptance Criteria

1. **Given** a Supabase PostgreSQL instance, **When** the core tables (users, properties, events) are migrated, **Then** `pgvector` extension must be enabled.
2. **Given** a Supabase PostgreSQL instance, **When** the core tables (users, properties, events) are migrated, **Then** Row-Level Security (RLS) policies must be applied ensuring queries only return rows where `tenant_id` matches the authenticated user.
3. **Given** a Python backend interacting with the database, **Then** Python models must use `snake_case` mapped to `camelCase` for outputs.

## Tasks / Subtasks

- [ ] Task 1: Initialize local Supabase instance (AC: #1, #2)
  - [ ] Run `npx supabase init` at the project root `aetherix-mvp`
  - [ ] Add `supabase/` to `.gitignore` if not already ignored securely
  - [ ] Set up `supabase start` workflow alongside the existing Docker Compose structure (if Supabase local CLI is used, note how it interacts with the backend's `DATABASE_URL`)

- [ ] Task 2: Create initial database schema migration (AC: #1, #2)
  - [ ] Generate a migration file: `supabase migration new init_schema`
  - [ ] In the migration, enable the `vector` extension (`CREATE EXTENSION IF NOT EXISTS vector;`)
  - [ ] Create the `tenants` table (id, name, created_at)
  - [ ] Create the `users` table extending or linking to auth (id, tenant_id, role, email)
  - [ ] Create the `properties` table (id, tenant_id, gps_lat, gps_lng)

- [ ] Task 3: Implement Row-Level Security (RLS) (AC: #2)
  - [ ] In the migration file, enable RLS on all tables (`ALTER TABLE name ENABLE ROW LEVEL SECURITY;`)
  - [ ] Create RLS policies forcing `tenant_id` matching on `users` and `properties` tables based on the `auth.uid()` or similar custom claim injection

- [ ] Task 4: Define SQLAlchemy / SQLModel backend definitions (AC: #3)
  - [ ] In `fastapi_backend/app/db/models.py`, define the ORM equivalents of the tables using `snake_case`
  - [ ] Ensure Pydantic response schemas (in `schemas.py`) are configured with `alias_generator` to output `camelCase` for the Next.js frontend

- [ ] Task 5: Verify configurations with automated test
  - [ ] Write a `pytest` that simulates two distinct tenants and verifies User A cannot read User B's property data simulating the RLS boundary

## Dev Notes

### Technology Stack
- **Database:** Supabase (Local CLI for development, hosted PostgreSQL for prod)
- **Backend ORM:** SQLAlchemy or SQLModel (depending on template preference)
- **Extensions:** `pgvector` MUST be enabled in the first migration for Epic 3 compatibility

### RLS and Tenant Isolation (MANDATORY Architecture Constraint)
Row-Level Security is non-negotiable. Every table (except the `tenants` root table) MUST have a `tenant_id` column.
Every RLS policy MUST enforce that the current user's session token maps to that `tenant_id`.

Example basic RLS policy for Postgres:
```sql
CREATE POLICY "Tenant Isolation Policy" ON properties
    FOR ALL
    USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));
```
*(Refine this based on exactly how fastapi-users integrates with Supabase auth JWTs in this project).*

### Casing Convention
- Backend / DB: `snake_case` exclusively (e.g., column `tenant_id`)
- API Output JSON: `camelCase` (e.g., `tenantId`)
- Frontend TS: `camelCase` exclusively

### Project Structure Notes
- The Supabase CLI will likely create a `supabase/migrations/` folder at the project root `aetherix-mvp/`.
- Backend DB models belong in `aetherix-mvp/fastapi_backend/app/db/models.py`.

### References
- Epics Document: `_bmad-output/planning-artifacts/epics.md` [Source: Story 1.2, FR19]
- Architecture Casing Rules: `_bmad-output/planning-artifacts/architecture.md#Naming-Patterns`
- Architecture Database Rules: `_bmad-output/planning-artifacts/architecture.md#Data-Storage-Patterns`

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

# Story 7.1: Supabase RLS Audit — Verify hotel_id Isolation on All Tables

Status: ready-for-dev

**GitHub Issue:** [#47](https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/47)
**Epic:** Epic 7 — Security & Trust Foundation
**Priority:** Critical — must complete before any live data ingestion

## Story

As a System Administrator,
I want a verified audit confirming every Supabase table enforces `hotel_id`/`tenant_id` Row-Level Security,
So that no hotel property can ever query, read, or write another property's data — even if the application layer has a bug.

## Acceptance Criteria

1. **Given** the live Supabase instance, **When** the audit script runs, **Then** it produces a complete inventory of all tables listing RLS status, policies, and scoping column for each.
2. **Given** the table inventory, **When** reviewed, **Then** every table containing hotel/tenant data has `ROW LEVEL SECURITY ENABLED` and at least one policy enforcing `hotel_id` or `tenant_id` matching. Any intentionally public table (e.g., shared `fb_patterns`) is explicitly documented with rationale.
3. **Given** two distinct test tenants (Hotel A and Hotel B), **When** a request authenticated as Hotel A queries Hotel B's data, **Then** the result is zero rows (or 403). This test runs in `pytest` and must remain green.
4. **Given** any FastAPI route that queries operational data, **When** the handler executes, **Then** `hotel_id` is explicitly filtered at the service layer as defense-in-depth (not only relying on RLS).
5. **Given** `fb_patterns` and `operational_memory` pgvector tables, **When** a hotel queries its vectors, **Then** the query is scoped to that hotel's namespace — confirmed by test or architectural design.

## Tasks / Subtasks

- [ ] Task 1: Run RLS inventory query (AC: #1, #2)
  - [ ] Execute `SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';`
  - [ ] Execute `SELECT * FROM pg_policies;` and map policies to tables
  - [ ] Identify tables added since Story 1.2 without RLS: `operational_memory`, `action_logs`, `recommendations`, `anomalies`

- [ ] Task 2: Harden unprotected tables (AC: #2)
  - [ ] Write RLS policies for any table found without enforcement
  - [ ] Document intentionally public tables (e.g., shared semantic `fb_patterns`) with written rationale

- [ ] Task 3: Cross-tenant penetration test (AC: #3)
  - [ ] Write `pytest` test creating two distinct test tenants
  - [ ] Assert Hotel A cannot read Hotel B's rows across all tenant-scoped tables
  - [ ] Add test to CI — must remain green

- [ ] Task 4: Service-layer defense-in-depth audit (AC: #4)
  - [ ] Review all 25 service files in `backend/app/services/` for explicit `hotel_id` filter in queries
  - [ ] Add `hotel_id` assertion where missing
  - [ ] Add code review checklist item to PR template for new routes

- [ ] Task 5: pgvector namespace isolation (AC: #5)
  - [ ] Confirm `memory_service.py` includes `hotel_id` filter in all vector queries
  - [ ] Confirm `rag_service.py` scopes semantic search to hotel context
  - [ ] Write targeted test or document by-design isolation

## Dev Notes

### RLS Policy Template
```sql
CREATE POLICY "Tenant Isolation Policy" ON <table_name>
    FOR ALL
    USING (hotel_id = (SELECT hotel_id FROM users WHERE id = auth.uid()));
```

### Key Files to Audit
- `supabase/migrations/` — verify every `CREATE TABLE` has corresponding `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
- `backend/app/services/memory_service.py` — `operational_memory` table (HOS-99)
- `backend/app/services/rag_service.py` — `fb_patterns` vector search
- `backend/app/core/security.py` — confirms how `hotel_id`/`tenant_id` is extracted from JWT

### Cross-Tenant Test Pattern
```python
def test_cross_tenant_isolation(client_hotel_a, client_hotel_b):
    # Hotel A tries to read Hotel B's recommendations
    response = client_hotel_a.get(f"/recommendations?hotel_id={hotel_b_id}")
    assert response.json()["data"] == []  # Empty — not an error
```

## References

- Story 1.2 (initial RLS): `docs/bmad/_bmad-output/implementation-artifacts/1-2-establish-supabase-database-with-tenant-isolation-rls.md`
- Architecture: `docs/bmad/_bmad-output/planning-artifacts/architecture.md#Data-Storage-Patterns`
- GitHub Issue: https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/47

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

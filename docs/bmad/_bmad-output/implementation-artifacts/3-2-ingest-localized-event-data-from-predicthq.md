# Story 3.2: Ingest Localized Event Data from PredictHQ

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Semantic Engine,
I want to ingest local event data (conferences, concerts, sports, festivals) for a property via PredictHQ,
so that I can identify external factors driving sudden occupancy or walk-in surges (FR5).

## Acceptance Criteria

1. **GPS Configuration Prerequisite:** Given a property has GPS coordinates (latitude, longitude) stored in the `properties` table, the event sync resolves the target location without additional manual input.
2. **Scheduled Sync:** When the daily event sync job runs, upcoming events within a 5km radius of the property's GPS coordinates and within the next 14 days are fetched from PredictHQ.
3. **Data Persistence:** The fetched event data is stored in Supabase in a dedicated `local_events` table, associated with the correct `tenant_id`.
4. **Normalization:** Ingested events are normalized into a standard schema (category, title, start/end datetime, predicted_attendance, impact_score, rank) suitable for cross-referencing with demand baselines in Epic 3.3a.
5. **Categorization:** Events are tagged with a normalized `category` value (e.g., `conference`, `concert`, `sports`, `festival`, `community`, `other`).
6. **Tenant Isolation:** RLS policies on `local_events` ensure a query from one tenant cannot return rows belonging to another tenant.
7. **Error Handling:** If the PredictHQ API returns an error or times out, the failure is logged and the sync retries with exponential backoff (up to 3 attempts); the failure does NOT crash the background task or affect other tenants.
8. **Idempotency:** Re-running the sync for the same property and time window does not create duplicate rows (upsert by `tenant_id` + `property_id` + `predicthq_event_id`).
9. **API Key Security:** The PredictHQ API key is stored as an environment variable and never exposed in API responses or logs.

## Tasks / Subtasks

- [ ] Task 1: Configure PredictHQ API client (AC: 1, 2, 9)
  - [ ] Add `PREDICTHQ_API_KEY` and `PREDICTHQ_API_BASE_URL` to `fastapi-backend/.env` and `core/config.py` via Pydantic `Settings`.
  - [ ] Use `httpx.AsyncClient` (already used for PMS + weather clients) — no new HTTP library required.
  - [ ] Set default base URL: `https://api.predicthq.com`.
  - [ ] Add `Authorization: Bearer {PREDICTHQ_API_KEY}` header to all requests.

- [ ] Task 2: Create `local_events` database migration (AC: 3, 4, 5, 6)
  - [ ] Generate migration: `supabase migration new add_local_events_table`
  - [ ] Schema:
    ```sql
    CREATE TABLE local_events (
        id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id            UUID NOT NULL REFERENCES tenants(id),
        property_id          UUID NOT NULL REFERENCES properties(id),
        predicthq_event_id   TEXT NOT NULL,
        title                TEXT NOT NULL,
        category             TEXT NOT NULL,         -- normalized: conference, concert, sports, festival, community, other
        phq_category         TEXT,                  -- raw PredictHQ category for debugging
        start_dt             TIMESTAMPTZ NOT NULL,
        end_dt               TIMESTAMPTZ,
        predicted_attendance INTEGER,
        impact_score         NUMERIC(5,2),          -- PHQ rank normalized 0-100
        rank                 SMALLINT,              -- PHQ rank 0-100
        location_lat         NUMERIC(9,6),
        location_lng         NUMERIC(9,6),
        raw_payload          JSONB,                 -- full API response for debugging
        ingested_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (tenant_id, property_id, predicthq_event_id)
    );
    ALTER TABLE local_events ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Tenant Isolation" ON local_events
        FOR ALL
        USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));
    CREATE INDEX idx_local_events_property_start ON local_events (property_id, start_dt);
    ```
  - [ ] Add SQLAlchemy / SQLModel ORM model in `fastapi-backend/app/db/models.py` (`LocalEvent`).
  - [ ] Add Pydantic response schema in `fastapi-backend/app/schemas/events.py` with `camelCase` alias generator.

- [ ] Task 3: Implement `EventIngestionService` (AC: 2, 4, 5, 7, 8)
  - [ ] Create `fastapi-backend/app/services/event_ingestion.py`.
  - [ ] Method `fetch_events(lat: float, lng: float, radius_km: float = 5.0, days_ahead: int = 14) -> list[dict]`:
    - Calls PredictHQ `GET /v1/events/` with query params:
      - `within={radius_km}km@{lat},{lng}`
      - `start.gte={today}` and `start.lte={today + days_ahead}`
      - `sort=rank` (highest impact first)
      - `limit=100`
      - `active.gte={today}` to exclude past events
    - Returns list of raw event dicts from response `results`.
  - [ ] Method `normalize(raw_event: dict) -> EventNormalized`: Maps PredictHQ categories to internal `category` values (see Dev Notes mapping table).
  - [ ] Method `upsert_events(db: AsyncSession, tenant_id: UUID, property_id: UUID, events: list[...])`: Bulk upsert using `INSERT ... ON CONFLICT (tenant_id, property_id, predicthq_event_id) DO UPDATE SET title=..., impact_score=..., rank=..., ingested_at=NOW()`.
  - [ ] Wrap the full fetch → normalize → upsert pipeline in a `sync_events_for_property(property_id, tenant_id)` coroutine.
  - [ ] Implement retry logic: `tenacity` library, `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=2, max=10)`.
  - [ ] Log (at WARNING level) any events where `predicted_attendance` is null — PredictHQ only provides attendance for premium tiers.

- [ ] Task 4: Create background scheduler task (AC: 2, 7)
  - [ ] In `fastapi-backend/app/workers/event_sync.py`, create a daily sync job that:
    - Queries all active `properties` (where `is_active=True`).
    - Calls `sync_events_for_property` for each in parallel using `asyncio.gather`.
    - Runs once daily at 06:00 UTC (cron: `0 6 * * *`).
  - [ ] Register the scheduler on FastAPI `startup` event in `main.py` alongside the weather sync job.

- [ ] Task 5: Expose API endpoint for manual trigger (AC: 3)
  - [ ] `POST /api/v1/events/sync` — triggers an immediate event sync for the authenticated user's property.
  - [ ] Route belongs in `fastapi-backend/app/api/routes/events.py`.
  - [ ] Returns `202 Accepted` immediately; sync runs as `BackgroundTask`.
  - [ ] Protect with `Depends(current_active_user)`.

- [ ] Task 6: Tests (AC: 2, 4, 5, 6, 7, 8)
  - [ ] Unit test `normalize()` covering all 6 category mappings (conference, concert, sports, festival, community, other/fallback).
  - [ ] Unit test `upsert_events()` for idempotency — calling twice with same `predicthq_event_id` must update, not duplicate.
  - [ ] Integration test `POST /api/v1/events/sync` with mocked PredictHQ HTTP response (use `respx` for `httpx` mocking).
  - [ ] Integration test simulating two distinct tenants — verify RLS prevents cross-tenant event leakage.
  - [ ] Unit test retry logic — mock a 429/503 response and verify `tenacity` retries up to 3 times.

## Dev Notes

### Architecture Alignment
- **Fat Backend / Thin Frontend:** All event ingestion logic lives in `fastapi-backend/app/services/`. No PredictHQ calls from the Next.js layer.
- **BackgroundTasks pattern:** The `POST /sync` endpoint MUST return `202 Accepted` immediately; event fetching runs asynchronously.
- **Casing:** Internal Python/DB uses `snake_case`. API JSON outputs use `camelCase` via Pydantic alias generator.
- **RFC 7807 errors:** Any `HTTPException` raised must be formatted as Problem Details.
- **API key in logs:** Never log the raw `Authorization` header. Use `httpx` event hooks to redact if needed.

### PredictHQ Category → Internal `category` Mapping
| PredictHQ Category         | Internal `category` |
|----------------------------|---------------------|
| `conferences`              | `conference`        |
| `concerts`                 | `concert`           |
| `sports`                   | `sports`            |
| `festivals`                | `festival`          |
| `community`, `public-holidays`, `observances` | `community` |
| `expos`, `politics`, `academic`, `school-holidays`, `daylight-savings`, `airport-delays`, `severe-weather`, `terror`, `disasters` | `other` |

Full PredictHQ category list: https://docs.predicthq.com/resources/categories

### PredictHQ API Reference
- Base URL: `https://api.predicthq.com`
- Auth: `Authorization: Bearer {PREDICTHQ_API_KEY}` (OAuth token or API key)
- Endpoint: `GET /v1/events/`
- Key query params:
  - `within=5km@{lat},{lng}` — geo filter
  - `start.gte={YYYY-MM-DD}` — events starting on or after today
  - `start.lte={YYYY-MM-DD}` — events starting within 14 days
  - `sort=rank` — highest-impact events first
  - `limit=100` — max per page (use `next` cursor for pagination if needed)
- Response: `{ count, next, previous, results: [ { id, title, category, start, end, phq_attendance, rank, location: [lng, lat], ... } ] }`
- Note: `phq_attendance` (predicted attendance) is only available on paid plans. Log as null on free tier — still ingest event for categorization purposes.
- Rate limits: vary by plan. Default free tier: 100 req/day. Handle `429 Too Many Requests` with `tenacity`.

### Source Tree Components
```
fastapi-backend/
├── app/
│   ├── api/routes/events.py           # POST /api/v1/events/sync
│   ├── db/models.py                   # LocalEvent ORM model (append)
│   ├── schemas/events.py              # Pydantic schemas (camelCase output)
│   ├── services/event_ingestion.py    # Core ingestion service
│   └── workers/event_sync.py         # APScheduler daily cron (06:00 UTC)
supabase/migrations/
└── <timestamp>_add_local_events_table.sql
```

### Dependency on Epic 2 / Story 3.1
- `properties` table (with `gps_lat`, `gps_lng`, `tenant_id`, `is_active`) must exist — delivered by Story 1.2.
- `tenant_id` RLS pattern follows the same policy template established in `weather_forecasts` (Story 3.1).
- `tenacity` retry library introduced in Story 3.1 — already available as a dependency.

### NFR5 Compliance Note
This story covers data *ingestion* only. The <5s cross-tenant processing constraint (NFR5) applies to anomaly detection in Story 3.3a. Ingestion runs asynchronously on a daily schedule, fully decoupled from the request path.

### Free Tier Limitation
PredictHQ's free plan (`Free Tier`) provides access to public events and basic categories but limits `phq_attendance`. For MVP, ingest all available fields and store `null` where attendance is unavailable. Upgrade path: switch to `Essential` or `Premium` plan to unlock full attendance data.

## References
- [PRD FR5](../planning-artifacts/prd.md#functional-requirements) — external event ingestion requirement
- [Architecture: BackgroundTasks pattern](../planning-artifacts/architecture.md#infrastructure--deployment)
- [Architecture: Project Structure](../planning-artifacts/architecture.md#project-structure--boundaries)
- [Epics: Story 3.2](../planning-artifacts/epics.md#story-32-ingest-localized-event-data-from-predicthq)
- [PredictHQ API Docs](https://docs.predicthq.com)
- [PredictHQ Events API](https://docs.predicthq.com/api/events)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

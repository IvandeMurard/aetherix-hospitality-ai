# Story 3.3a: Detect Demand Anomalies Against Baseline

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Reasoning Engine,
I want to cross-reference upcoming occupancy, weather, and event data against historical baselines,
so that I can identify periods where demand is expected to significantly deviate from normal (FR6).

## Acceptance Criteria

1. **Prerequisite Data:** Given that `weather_forecasts`, `local_events`, occupancy data, and baseline captation rates all exist for a tenant, the anomaly engine can run without additional manual input.
2. **4-Hour Window Scan:** When the anomaly detection engine runs, it evaluates each upcoming 4-hour time window (for the next 14 days) against the property's historical baseline captation rate.
3. **Deviation Threshold:** A window is flagged as an anomaly when expected demand deviates from the baseline by more than a configurable threshold (default: 20%).
4. **Direction:** Each anomaly is classified as either `surge` (demand > baseline) or `lull` (demand < baseline).
5. **Triggering Factors:** Each flagged anomaly is saved with a `triggering_factors` JSON array listing the specific contributing signals (e.g., `{ "type": "event", "event_id": "...", "category": "conference", "impact": "+30%" }`, `{ "type": "weather", "condition": "thunderstorm", "impact": "-15%" }`).
6. **Tenant Isolation:** Each anomaly is stored with its `tenant_id`; RLS policies prevent cross-tenant reads.
7. **Idempotency:** Re-running the scan for the same property and time window does not create duplicate anomaly rows (upsert by `tenant_id` + `property_id` + `window_start`).
8. **NFR5 — Global Performance:** The full anomaly scan across all active tenants (up to 50) completes within 5 seconds end-to-end.
9. **Manual Trigger:** A `POST /api/v1/anomalies/scan` endpoint triggers an immediate scan for the authenticated user's property and returns `202 Accepted`.
10. **Status Lifecycle:** Newly detected anomalies are saved with `status = 'detected'`; this status field will be updated by subsequent stories (3.3b sets `roi_positive`, 3.3c sets `ready_to_push`).

## Tasks / Subtasks

- [ ] Task 1: Create `demand_anomalies` database migration (AC: 3, 5, 6, 7, 10)
  - [ ] Generate migration: `supabase migration new add_demand_anomalies_table`
  - [ ] Schema:
    ```sql
    CREATE TABLE demand_anomalies (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id           UUID NOT NULL REFERENCES tenants(id),
        property_id         UUID NOT NULL REFERENCES properties(id),
        window_start        TIMESTAMPTZ NOT NULL,
        window_end          TIMESTAMPTZ NOT NULL,
        expected_demand     NUMERIC(10,2) NOT NULL,   -- projected F&B revenue for the window
        baseline_demand     NUMERIC(10,2) NOT NULL,   -- historical baseline for the same window type
        deviation_pct       NUMERIC(6,2) NOT NULL,    -- (expected - baseline) / baseline * 100
        direction           TEXT NOT NULL,             -- 'surge' | 'lull'
        triggering_factors  JSONB NOT NULL DEFAULT '[]',
        status              TEXT NOT NULL DEFAULT 'detected',
            -- 'detected' → 'roi_positive' (3.3b) → 'ready_to_push' (3.3c) → 'dispatched' (Epic 4)
        detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- Fields populated by downstream stories (nullable until then):
        roi_revenue_opp     NUMERIC(10,2),
        roi_labor_cost      NUMERIC(10,2),
        roi_net             NUMERIC(10,2),
        recommendation_text TEXT,
        UNIQUE (tenant_id, property_id, window_start)
    );
    ALTER TABLE demand_anomalies ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Tenant Isolation" ON demand_anomalies
        FOR ALL
        USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));
    CREATE INDEX idx_anomalies_property_status ON demand_anomalies (property_id, status);
    CREATE INDEX idx_anomalies_window ON demand_anomalies (property_id, window_start);
    ```
  - [ ] Add SQLAlchemy / SQLModel ORM model `DemandAnomaly` in `fastapi-backend/app/db/models.py`.
  - [ ] Add Pydantic schemas in `fastapi-backend/app/schemas/anomalies.py` with `camelCase` alias generator.

- [ ] Task 2: Implement demand modifier logic (AC: 2, 3, 4, 5)
  - [ ] Create `fastapi-backend/app/services/demand_modifiers.py`.
  - [ ] Function `weather_modifier(condition_code: str) -> float`: Returns a demand multiplier offset based on weather condition:
    | `condition_code`  | Modifier |
    |-------------------|----------|
    | `thunderstorm`    | -0.20    |
    | `rain`, `showers` | -0.10    |
    | `snow`            | -0.15    |
    | `fog`             | -0.05    |
    | `clear`           | +0.05    |
    | `partly_cloudy`   | 0.00     |
  - [ ] Function `event_modifier(events: list[LocalEvent]) -> float`: Returns a cumulative demand multiplier offset based on nearby events:
    | `category`   | Modifier per event (capped at +0.50 total) |
    |--------------|---------------------------------------------|
    | `conference` | +0.25                                       |
    | `concert`    | +0.20                                       |
    | `sports`     | +0.15                                       |
    | `festival`   | +0.20                                       |
    | `community`  | +0.05                                       |
    | `other`      | +0.05                                       |
  - [ ] Both functions must also return a structured `triggering_factor` dict for persistence.

- [ ] Task 3: Implement `AnomalyDetectionService` (AC: 1, 2, 3, 4, 5, 7)
  - [ ] Create `fastapi-backend/app/services/anomaly_detection.py`.
  - [ ] Method `generate_windows(start: datetime, days_ahead: int = 14) -> list[tuple[datetime, datetime]]`:
    - Generates non-overlapping 4-hour windows from `start` for `days_ahead` days.
    - Returns list of `(window_start, window_end)` tuples aligned to UTC hours 0, 4, 8, 12, 16, 20.
  - [ ] Method `detect_for_property(db: AsyncSession, property_id: UUID, tenant_id: UUID) -> list[DemandAnomalyCreate]`:
    1. Load the property's baseline captation rates (from `captation_rates` table, segmented by day-of-week — Story 2.4).
    2. For each upcoming 4-hour window:
       a. Get occupancy for that window from PMS data.
       b. Get weather forecast covering that window (nearest `forecast_timestamp`).
       c. Get active events whose `start_dt` / `end_dt` overlaps the window.
       d. Calculate `expected_demand = baseline_demand × (1 + weather_modifier + event_modifier)`.
       e. Calculate `deviation_pct = (expected_demand - baseline_demand) / baseline_demand × 100`.
       f. If `abs(deviation_pct) >= threshold` (default 20%), record as anomaly.
    3. Bulk upsert detected anomalies using `INSERT ... ON CONFLICT (tenant_id, property_id, window_start) DO UPDATE`.
  - [ ] Load `ANOMALY_DEVIATION_THRESHOLD` from `core/config.py` (default: `20.0`).

- [ ] Task 4: Implement full-scan runner with NFR5 compliance (AC: 8)
  - [ ] Create `fastapi-backend/app/workers/anomaly_scan.py`.
  - [ ] Async function `run_full_scan(db: AsyncSession)`:
    - Queries all `properties` where `is_active = True`.
    - Calls `detect_for_property` for all properties in parallel via `asyncio.gather(*tasks)`.
    - Logs total elapsed time at INFO level; raises a WARNING log if elapsed > 4.5s (early alert before 5s NFR5 breach).
  - [ ] Schedule scan to run every 4 hours (cron: `0 */4 * * *`) via APScheduler, registered on FastAPI `startup` in `main.py` alongside weather and event sync jobs.

- [ ] Task 5: Expose API endpoint for manual trigger (AC: 9)
  - [ ] `POST /api/v1/anomalies/scan` in `fastapi-backend/app/api/routes/anomalies.py`.
  - [ ] Returns `202 Accepted` immediately; scan runs as `BackgroundTask`.
  - [ ] Protect with `Depends(current_active_user)`; scans only the authenticated user's property.
  - [ ] `GET /api/v1/anomalies` — returns paginated list of anomalies for the authenticated user's property, ordered by `window_start` desc.

- [ ] Task 6: Tests (AC: 2, 3, 4, 5, 6, 7, 8)
  - [ ] Unit test `generate_windows()` — verify correct 4-hour window boundaries over a 14-day range.
  - [ ] Unit test `weather_modifier()` and `event_modifier()` for all documented condition/category values.
  - [ ] Unit test `detect_for_property()` with mocked DB data:
    - Scenario A: no events/weather → no anomaly (deviation < 20%).
    - Scenario B: thunderstorm + conference → surge anomaly detected.
    - Scenario C: lull scenario (no events, rainy) → lull anomaly detected.
  - [ ] Unit test idempotency — running `detect_for_property` twice for the same window must not produce duplicate rows.
  - [ ] Integration test `POST /api/v1/anomalies/scan` returns `202` and triggers background task.
  - [ ] Integration test two tenants — verify RLS prevents cross-tenant anomaly leakage.
  - [ ] Performance test `run_full_scan()` with 50 mocked properties — verify completion under 5 seconds.

## Dev Notes

### Architecture Alignment
- **Fat Backend / Thin Frontend:** All anomaly detection logic lives in `fastapi-backend/app/services/`. No detection logic in Next.js.
- **BackgroundTasks pattern:** `POST /api/v1/anomalies/scan` MUST return `202 Accepted` immediately; detection runs asynchronously.
- **Casing:** Internal Python/DB uses `snake_case`. API JSON output uses `camelCase` via Pydantic alias generator.
- **RFC 7807 errors:** All `HTTPException`s must use Problem Details format.
- **Status field design:** `demand_anomalies.status` is intentionally owned by this story but written by downstream stories (3.3b, 3.3c, Epic 4). The ORM model must define all valid values as a Python `Enum` or `Literal` to prevent invalid transitions.

### Modifier Capping Rules
- Total combined modifier (weather + events) is capped at `[-0.50, +0.75]` to prevent extreme projections from edge cases (e.g., 5 simultaneous conferences).
- The cap should be applied in `detect_for_property` after summing modifiers, before computing `expected_demand`.

### NFR5 Strategy
The 5-second constraint (NFR5) is met through:
1. `asyncio.gather` for parallel per-property scans (I/O-bound DB queries, not CPU-bound).
2. Efficient indexed queries on `weather_forecasts` and `local_events` using `property_id + timestamp` composite indexes (created in 3.1 and 3.2).
3. Bulk upsert in a single SQL statement per property (not row-by-row inserts).

If the performance test reveals individual property scans are slow, add a `EXPLAIN ANALYZE` section to the debug notes and optimize query patterns before marking this story done.

### Dependencies on Prior Stories
- `captation_rates` table (segmented by day-of-week) — delivered by Story 2.4.
- `weather_forecasts` table with `condition_code`, `forecast_timestamp` — delivered by Story 3.1.
- `local_events` table with `category`, `start_dt`, `end_dt`, `impact_score` — delivered by Story 3.2.
- `tenacity` retry library — already available (introduced in Story 3.1).
- APScheduler — already registered in `main.py` (introduced in Story 3.2).

### Source Tree Components
```
fastapi-backend/
├── app/
│   ├── api/routes/anomalies.py             # POST /scan, GET /
│   ├── db/models.py                        # DemandAnomaly ORM model (append)
│   ├── schemas/anomalies.py                # Pydantic schemas (camelCase output)
│   ├── services/
│   │   ├── anomaly_detection.py            # Core detection service
│   │   └── demand_modifiers.py             # Weather/event modifier functions
│   └── workers/anomaly_scan.py             # APScheduler 4h cron job
supabase/migrations/
└── <timestamp>_add_demand_anomalies_table.sql
```

### Downstream Story Contracts
This story creates the `demand_anomalies` table that Stories 3.3b and 3.3c will write back to:
- **Story 3.3b** reads `status = 'detected'` anomalies and writes `roi_revenue_opp`, `roi_labor_cost`, `roi_net`, sets `status = 'roi_positive'`.
- **Story 3.3c** reads `status = 'roi_positive'` anomalies and writes `recommendation_text`, sets `status = 'ready_to_push'`.
- **Epic 4** reads `status = 'ready_to_push'` for dispatch.

Do NOT remove or rename any columns in `demand_anomalies` without a coordinated migration across all downstream stories.

## References
- [PRD FR6](../planning-artifacts/prd.md#functional-requirements) — anomaly detection requirement
- [PRD NFR5](../planning-artifacts/prd.md#non-functional-requirements) — <5s global processing constraint
- [Architecture: BackgroundTasks pattern](../planning-artifacts/architecture.md#infrastructure--deployment)
- [Architecture: Project Structure](../planning-artifacts/architecture.md#project-structure--boundaries)
- [Epics: Story 3.3a](../planning-artifacts/epics.md#story-33a-detect-demand-anomalies-against-baseline)
- [Story 3.1](./3-1-ingest-localized-weather-data.md) — weather_forecasts table
- [Story 3.2](./3-2-ingest-localized-event-data-from-predicthq.md) — local_events table

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

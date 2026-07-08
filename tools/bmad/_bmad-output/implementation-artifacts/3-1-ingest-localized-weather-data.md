# Story 3.1: Ingest Localized Weather Data

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Semantic Engine,
I want to ingest local weather forecast data for a property,
so that I can identify weather patterns that historically impact F&B or Room Service demand (FR4).

## Acceptance Criteria

1. **GPS Configuration Prerequisite:** Given a property has GPS coordinates (latitude, longitude) stored in the `properties` table, the weather sync is able to resolve the target location without additional manual input.
2. **Scheduled Sync:** When the 12-hour weather sync job runs, weather forecast data within a 5km radius of the property's GPS coordinates is fetched from the external weather API.
3. **Data Persistence:** The fetched forecast data is stored in Supabase in a dedicated `weather_forecasts` table, associated with the correct `tenant_id`.
4. **Normalization:** Ingested weather records are normalized into a standard schema (condition code, temperature, precipitation probability, wind speed, timestamp) suitable for cross-referencing with demand baselines in Epic 3.3a.
5. **Tenant Isolation:** RLS policies on `weather_forecasts` ensure a query from one tenant cannot return rows belonging to another tenant.
6. **Error Handling:** If the external weather API returns an error or times out, the failure is logged and the sync retries with exponential backoff (up to 3 attempts); the failure does NOT crash the background task or affect other tenants.
7. **Idempotency:** Re-running the sync for the same property and time window does not create duplicate rows (upsert by `tenant_id` + `forecast_timestamp`).

## Tasks / Subtasks

- [ ] Task 1: Select and configure weather API client (AC: 1, 2)
  - [ ] Choose provider: Open-Meteo (free, no key required for MVP) as primary; document fallback to OpenWeatherMap if needed.
  - [ ] Add `httpx` (already used for PMS client) as the HTTP dependency — no new library required.
  - [ ] Store `WEATHER_API_BASE_URL` in `fastapi-backend/.env` and `core/config.py` via Pydantic `Settings`.

- [ ] Task 2: Create `weather_forecasts` database migration (AC: 3, 4, 5)
  - [ ] Generate migration: `supabase migration new add_weather_forecasts_table`
  - [ ] Schema:
    ```sql
    CREATE TABLE weather_forecasts (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id     UUID NOT NULL REFERENCES tenants(id),
        property_id   UUID NOT NULL REFERENCES properties(id),
        forecast_timestamp TIMESTAMPTZ NOT NULL,
        condition_code     TEXT NOT NULL,          -- e.g. "thunderstorm", "clear"
        temperature_c      NUMERIC(5,2),
        precipitation_prob SMALLINT,               -- 0-100 %
        wind_speed_kmh     NUMERIC(6,2),
        raw_payload        JSONB,                  -- full API response for debugging
        ingested_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (tenant_id, property_id, forecast_timestamp)
    );
    ALTER TABLE weather_forecasts ENABLE ROW LEVEL SECURITY;
    CREATE POLICY "Tenant Isolation" ON weather_forecasts
        FOR ALL
        USING (tenant_id = (SELECT tenant_id FROM users WHERE id = auth.uid()));
    ```
  - [ ] Add SQLAlchemy / SQLModel ORM model in `fastapi-backend/app/db/models.py` (`WeatherForecast`).
  - [ ] Add Pydantic response schema in `fastapi-backend/app/schemas/weather.py` with `camelCase` alias generator.

- [ ] Task 3: Implement `WeatherIngestionService` (AC: 2, 4, 6, 7)
  - [ ] Create `fastapi-backend/app/services/weather_ingestion.py`.
  - [ ] Method `fetch_forecast(lat: float, lng: float, radius_km: float = 5.0) -> list[WeatherForecastRaw]`:
    - Calls Open-Meteo `/v1/forecast` with `latitude`, `longitude`, hourly variables (temperature_2m, precipitation_probability, weathercode, windspeed_10m), `forecast_days=7`.
  - [ ] Method `normalize(raw: dict) -> list[WeatherForecastNormalized]`: Maps Open-Meteo WMO weather codes to internal `condition_code` strings (see Dev Notes).
  - [ ] Method `upsert_forecasts(db: AsyncSession, tenant_id: UUID, property_id: UUID, records: list[...])`: Bulk upsert using `INSERT ... ON CONFLICT (tenant_id, property_id, forecast_timestamp) DO UPDATE`.
  - [ ] Wrap the full fetch → normalize → upsert pipeline in a `sync_weather_for_property(property_id, tenant_id)` coroutine.
  - [ ] Implement retry logic: `tenacity` library, `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=2, max=10)`.

- [ ] Task 4: Create background scheduler task (AC: 2, 6)
  - [ ] In `fastapi-backend/app/workers/weather_sync.py`, create an APScheduler (or `asyncio` + `BackgroundTasks`) job that:
    - Queries all active `properties` (where `is_active=True`).
    - Calls `sync_weather_for_property` for each in parallel using `asyncio.gather`.
    - Runs every 12 hours (cron: `0 */12 * * *`).
  - [ ] Register the scheduler on FastAPI `startup` event in `main.py`.

- [ ] Task 5: Expose API endpoint for manual trigger (AC: 3)
  - [ ] `POST /api/v1/weather/sync` — triggers an immediate sync for the authenticated user's property.
  - [ ] Route belongs in `fastapi-backend/app/api/routes/weather.py`.
  - [ ] Returns `202 Accepted` immediately; sync runs as `BackgroundTask`.
  - [ ] Protect with `Depends(current_active_user)`.

- [ ] Task 6: Tests (AC: 2, 4, 5, 6, 7)
  - [ ] Unit test `normalize()` with representative WMO codes covering: clear, cloudy, rain, thunderstorm, snow.
  - [ ] Unit test `upsert_forecasts()` for idempotency — calling twice with same data must not duplicate rows.
  - [ ] Integration test `POST /api/v1/weather/sync` with mocked Open-Meteo HTTP response (use `respx` for `httpx` mocking).
  - [ ] Integration test simulating two distinct tenants — verify RLS prevents cross-tenant leakage.

## Dev Notes

### Architecture Alignment
- **Fat Backend / Thin Frontend:** All weather ingestion logic lives in `fastapi-backend/app/services/`. No weather API calls from the Next.js layer.
- **BackgroundTasks pattern:** The `POST /sync` endpoint MUST return `202 Accepted` immediately; weather fetching runs asynchronously to comply with the BackgroundTasks architecture constraint.
- **Casing:** Internal Python/DB uses `snake_case` (`forecast_timestamp`). API JSON outputs use `camelCase` (`forecastTimestamp`) via Pydantic alias generator.
- **RFC 7807 errors:** Any `HTTPException` raised (e.g. weather API unreachable after retries) must be formatted as Problem Details.

### WMO Weather Code → `condition_code` Mapping (subset)
| WMO Code | `condition_code`   |
|----------|--------------------|
| 0        | `clear`            |
| 1–3      | `partly_cloudy`    |
| 45, 48   | `fog`              |
| 51–67    | `rain`             |
| 71–77    | `snow`             |
| 80–82    | `showers`          |
| 95–99    | `thunderstorm`     |

Full reference: [Open-Meteo WMO codes](https://open-meteo.com/en/docs#weathervariables)

### Source Tree Components
```
fastapi-backend/
├── app/
│   ├── api/routes/weather.py        # POST /api/v1/weather/sync
│   ├── db/models.py                 # WeatherForecast ORM model (append)
│   ├── schemas/weather.py           # Pydantic schemas (camelCase output)
│   ├── services/weather_ingestion.py # Core ingestion service
│   └── workers/weather_sync.py      # APScheduler 12h cron job
supabase/migrations/
└── <timestamp>_add_weather_forecasts_table.sql
```

### External API: Open-Meteo
- Base URL: `https://api.open-meteo.com`
- No API key required for MVP usage (generous free tier).
- Endpoint: `GET /v1/forecast?latitude={lat}&longitude={lng}&hourly=temperature_2m,precipitation_probability,weathercode,windspeed_10m&forecast_days=7&timezone=auto`
- Rate limit: 10,000 req/day (free). With 50 tenants syncing every 12h = 100 req/day → well within limit.

### Dependency on Epic 2
- `properties` table (with `gps_lat`, `gps_lng`, `tenant_id`) must exist — delivered by Story 1.2.
- `tenant_id` RLS pattern is established — follow the same policy template as `properties` table.

### NFR5 Compliance Note
This story covers data *ingestion* only. The <5s cross-tenant processing limit (NFR5) applies to the *anomaly detection* step in Story 3.3a, which consumes the data ingested here. Ingestion is decoupled and runs asynchronously on its own 12h schedule.

## References
- [PRD FR4](../planning-artifacts/prd.md#functional-requirements) — weather ingestion requirement
- [Architecture: BackgroundTasks pattern](../planning-artifacts/architecture.md#infrastructure--deployment)
- [Architecture: Project Structure](../planning-artifacts/architecture.md#project-structure--boundaries)
- [Epics: Story 3.1](../planning-artifacts/epics.md#story-31-ingest-localized-weather-data)
- [Open-Meteo API Docs](https://open-meteo.com/en/docs)

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

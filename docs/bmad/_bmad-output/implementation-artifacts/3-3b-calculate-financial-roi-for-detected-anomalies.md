# Story 3.3b: Calculate Financial ROI for Detected Anomalies

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the Reasoning Engine,
I want to calculate the estimated financial ROI for each detected anomaly,
so that I can quantify the revenue opportunity versus the cost of extra staffing and filter only actionable signals (FR7).

## Acceptance Criteria

1. **Input Scope:** Given anomalies with `status = 'detected'` in the `demand_anomalies` table, the ROI engine processes each one.
2. **Revenue Opportunity:** For each anomaly, the engine calculates the estimated additional revenue opportunity: `captation_rate × expected_additional_covers × average_spend_per_cover`.
3. **Labor Cost:** The engine calculates the estimated labor cost of the recommended additional headcount: `recommended_headcount × hourly_rate × window_duration_hours`.
4. **Net ROI:** The engine computes `net_roi = revenue_opportunity - labor_cost`.
5. **ROI-Positive Flag:** If `net_roi > 0`, the anomaly's `status` is updated to `roi_positive`; if `net_roi <= 0`, status remains `detected` and the anomaly is excluded from dispatch.
6. **Persistence:** `roi_revenue_opp`, `roi_labor_cost`, and `roi_net` are written back to the `demand_anomalies` row.
7. **Configurable Rates:** `average_spend_per_cover` and `hourly_rate` are configurable per property (stored in `properties` table); the engine falls back to system-wide defaults from `core/config.py` if property values are not set.
8. **Idempotency:** Re-running the ROI calculation on an already-processed anomaly updates the ROI fields but does not create duplicate records.
9. **Automatic Trigger:** The ROI calculation runs automatically after each anomaly scan cycle completes (chained from `anomaly_scan.py`).
10. **Manual Trigger:** A `POST /api/v1/anomalies/roi` endpoint triggers ROI calculation for all `detected` anomalies belonging to the authenticated user's property, returning `202 Accepted`.

## Tasks / Subtasks

- [ ] Task 1: Add property-level ROI configuration fields (AC: 7)
  - [ ] Generate migration: `supabase migration new add_roi_config_to_properties`
  - [ ] Add columns to `properties` table:
    ```sql
    ALTER TABLE properties
        ADD COLUMN avg_spend_per_cover  NUMERIC(8,2),   -- e.g. 45.00 (£ per cover)
        ADD COLUMN staff_hourly_rate    NUMERIC(8,2);   -- e.g. 15.00 (£ per hour)
    ```
  - [ ] Update `Property` ORM model in `fastapi-backend/app/db/models.py`.
  - [ ] Add system-wide defaults to `fastapi-backend/app/core/config.py`:
    ```python
    DEFAULT_AVG_SPEND_PER_COVER: float = 40.0   # £
    DEFAULT_STAFF_HOURLY_RATE: float = 14.0      # £
    ```

- [ ] Task 2: Implement headcount recommendation logic (AC: 3)
  - [ ] Create `fastapi-backend/app/services/roi_calculator.py`.
  - [ ] Function `recommended_headcount(deviation_pct: float, direction: str) -> int`:
    - Surges only — lulls do not require extra staffing (headcount = 0 for `direction = 'lull'`).
    - Headcount scale for surges:
      | `deviation_pct` range | Recommended extra headcount |
      |----------------------|-----------------------------|
      | 20–35%               | 1                           |
      | 35–55%               | 2                           |
      | 55–80%               | 3                           |
      | > 80%                | 4 (maximum)                 |
  - [ ] Function `expected_additional_covers(baseline_demand: float, deviation_pct: float, avg_spend: float) -> float`:
    - Returns `(baseline_demand × deviation_pct / 100) / avg_spend`.
    - Represents the projected incremental covers above baseline.

- [ ] Task 3: Implement `ROICalculationService` (AC: 1, 2, 3, 4, 5, 6, 8)
  - [ ] In `fastapi-backend/app/services/roi_calculator.py`.
  - [ ] Method `calculate_for_anomaly(db: AsyncSession, anomaly: DemandAnomaly, property: Property) -> DemandAnomaly`:
    1. Resolve `avg_spend` from `property.avg_spend_per_cover` or `settings.DEFAULT_AVG_SPEND_PER_COVER`.
    2. Resolve `hourly_rate` from `property.staff_hourly_rate` or `settings.DEFAULT_STAFF_HOURLY_RATE`.
    3. Compute `window_hours = (anomaly.window_end - anomaly.window_start).seconds / 3600`.
    4. Compute `extra_covers = expected_additional_covers(anomaly.baseline_demand, anomaly.deviation_pct, avg_spend)`.
    5. Compute `revenue_opp = extra_covers × avg_spend`.
    6. Compute `headcount = recommended_headcount(anomaly.deviation_pct, anomaly.direction)`.
    7. Compute `labor_cost = headcount × hourly_rate × window_hours`.
    8. Compute `net_roi = revenue_opp - labor_cost`.
    9. Update anomaly fields: `roi_revenue_opp`, `roi_labor_cost`, `roi_net`.
    10. Set `anomaly.status = 'roi_positive'` if `net_roi > 0`, else leave as `'detected'`.
    11. Commit and return the updated anomaly.
  - [ ] Method `process_all_detected(db: AsyncSession, property_id: UUID, tenant_id: UUID)`:
    - Queries all `demand_anomalies` where `status = 'detected'` and `property_id` matches.
    - Calls `calculate_for_anomaly` for each; logs count of `roi_positive` and skipped anomalies.

- [ ] Task 4: Chain ROI calculation after anomaly scan (AC: 9)
  - [ ] In `fastapi-backend/app/workers/anomaly_scan.py`, after `run_full_scan()` completes:
    - For each property that had anomalies detected, call `process_all_detected` as part of the same background job.
    - The full chain (detect → ROI) must still complete within 5 seconds total per NFR5.
    - If adding ROI calculation causes the total to exceed 5s in the performance test, process ROI in a separate immediately-chained `BackgroundTask` (fire-and-forget after scan completes).

- [ ] Task 5: Expose API endpoint for manual trigger (AC: 10)
  - [ ] `POST /api/v1/anomalies/roi` in `fastapi-backend/app/api/routes/anomalies.py`.
  - [ ] Returns `202 Accepted` immediately; calculation runs as `BackgroundTask`.
  - [ ] Protect with `Depends(current_active_user)`; scopes to the authenticated user's property only.

- [ ] Task 6: Tests (AC: 1, 2, 3, 4, 5, 6, 7, 8)
  - [ ] Unit test `recommended_headcount()` for all four deviation bands + lull direction (expects 0).
  - [ ] Unit test `expected_additional_covers()` with known inputs — verify formula accuracy.
  - [ ] Unit test `calculate_for_anomaly()`:
    - Scenario A: surge +30%, net ROI positive → status = `roi_positive`, ROI fields populated.
    - Scenario B: surge +22%, high labor cost → net ROI negative → status remains `detected`.
    - Scenario C: lull −25% → headcount = 0, labor_cost = 0, net_roi = 0, status = `detected`.
  - [ ] Unit test property-level rate override — verify property's `avg_spend_per_cover` takes precedence over system default.
  - [ ] Unit test idempotency — calling `calculate_for_anomaly` twice on the same anomaly must not change `status` to an invalid value or create a new row.
  - [ ] Integration test `POST /api/v1/anomalies/roi` returns `202` and triggers background calculation.
  - [ ] Integration test two tenants — verify ROI calculation for tenant A does not read or modify tenant B's anomalies.

## Dev Notes

### Architecture Alignment
- **Fat Backend / Thin Frontend:** All ROI logic lives in `fastapi-backend/app/services/`. No ROI math in Next.js.
- **BackgroundTasks pattern:** `POST /api/v1/anomalies/roi` MUST return `202 Accepted` immediately.
- **Casing:** `snake_case` internally, `camelCase` on API output via Pydantic alias generator.
- **RFC 7807 errors:** All `HTTPException`s must use Problem Details format.

### Financial Model Assumptions (MVP)
These are intentional simplifications for the MVP pilot:
- **No occupancy weighting:** The model uses `deviation_pct` relative to the full-day baseline. A future enhancement could weight by actual occupancy forecast for the specific window.
- **Flat headcount scale:** The 4-tier headcount table is a conservative heuristic. It will be validated against real F&B staffing data during the pilot.
- **Lull exclusions:** Lulls (negative demand deviations) are not dispatched as staffing recommendations in MVP. They may be surfaced as informational alerts in a future story.
- **Single department scope:** ROI is calculated for F&B only in MVP. Room Service is scoped to Phase 2.

### NFR5 Impact
Adding ROI calculation to the scan chain introduces additional DB writes per anomaly. Mitigation:
1. Use a single bulk `UPDATE` SQL statement for all anomalies in a property instead of row-by-row commits.
2. If the combined scan + ROI chain exceeds 4.5s in the performance test, decouple into two sequential `BackgroundTask` calls with the second triggered immediately after the first completes.

### Status Transition Map
```
'detected'   ──(net_roi > 0)──▶  'roi_positive'
'detected'   ──(net_roi <= 0)──▶ 'detected'  (excluded from dispatch)
'roi_positive' ──(Story 3.3c)──▶ 'ready_to_push'
'ready_to_push' ──(Epic 4)──────▶ 'dispatched'
```

### Source Tree Components
```
fastapi-backend/
├── app/
│   ├── api/routes/anomalies.py             # POST /roi (append to existing file)
│   ├── core/config.py                      # DEFAULT_AVG_SPEND_PER_COVER, DEFAULT_STAFF_HOURLY_RATE
│   ├── db/models.py                        # Property model (add avg_spend_per_cover, staff_hourly_rate)
│   ├── services/roi_calculator.py          # ROICalculationService + headcount/cover functions
│   └── workers/anomaly_scan.py             # Chain ROI after scan (append)
supabase/migrations/
└── <timestamp>_add_roi_config_to_properties.sql
```

### Dependency on Story 3.3a
- `demand_anomalies` table with `status`, `deviation_pct`, `direction`, `baseline_demand`, `window_start`, `window_end` — delivered by Story 3.3a.
- `captation_rates` table (for `baseline_demand` reference) — delivered by Story 2.4.
- `properties` table — delivered by Story 1.2. This story appends `avg_spend_per_cover` and `staff_hourly_rate` columns.

### Downstream Contract for Story 3.3c
Story 3.3c reads anomalies where `status = 'roi_positive'` and expects these fields to be populated:
- `roi_revenue_opp` — used in recommendation message ("capture an estimated £X")
- `roi_labor_cost` — used in recommendation message ("Est. additional labor cost: £Y")
- `roi_net` — used for ranking/prioritizing dispatches

## References
- [PRD FR7](../planning-artifacts/prd.md#functional-requirements) — ROI calculation requirement
- [PRD NFR5](../planning-artifacts/prd.md#non-functional-requirements) — <5s global processing constraint
- [Architecture: BackgroundTasks pattern](../planning-artifacts/architecture.md#infrastructure--deployment)
- [Epics: Story 3.3b](../planning-artifacts/epics.md#story-33b-calculate-financial-roi-for-detected-anomalies)
- [Story 3.3a](./3-3a-detect-demand-anomalies-against-baseline.md) — demand_anomalies table + status lifecycle

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

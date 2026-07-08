# Story: Forecasting & Alert Service Risk Fixes

Status: ready-for-dev

**Surfaced by:** Architecture coherence audit, 2026-04-07
**Priority:** High (Risk — silent failures, type mismatches, async contract violations)
**Note:** Linear issues to be created when MCP reconnects. ACs defined here for dev agent.

---

## Problem Summary

Six risk-level bugs identified across the forecasting and alert pipeline that can cause silent failures, wrong data types returned to callers, or crashes in non-async contexts.

---

## R1 — `prediction_engine.py:88` — Silent mock when model untrained

**File:** `backend/app/services/prediction_engine.py`, lines 88-97

**Issue:** When Prophet model is not yet trained, `predict()` returns hardcoded values (`predicted=45`, `confidence=0.85`) with no indication they are fake. Callers — including `AetherixEngine` and the `/predict` API route — treat these as real predictions. A hotel going live before training completes will receive and act on fabricated forecasts.

**Current code:**
```python
if not self.is_trained:
    logger.warning("Prophet model not trained. Returning mock prediction for pilot.")
    return PredictionResult(predicted=45, lower=38, upper=52, confidence=0.85, ...)
```

### Acceptance Criteria

1. **Given** `PredictionEngine.is_trained == False`,
   **When** `predict()` is called,
   **Then** the returned `PredictionResult` has `is_mock=True` and `predicted` is clearly marked (e.g., via the flag, not by value).

2. **Given** the `/predict` API route receives a `PredictionResult` with `is_mock=True`,
   **When** it serialises the response,
   **Then** the JSON includes `"is_mock": true` so the frontend and WhatsApp formatter can display a warning.

3. **Given** `is_mock=True` in the result,
   **When** `ReasoningService.generate_explanation()` is called,
   **Then** the explanation prompt explicitly notes the model is not yet trained (prevents Claude generating false-confidence language).

### Tasks
- [ ] Add `is_mock: bool = False` field to `PredictionResult` dataclass/model
- [ ] Set `is_mock=True` in the untrained branch
- [ ] Propagate `is_mock` through `AetherixEngine.get_forecast()` response dict
- [ ] Add `is_mock` to the `/predict` Pydantic response schema
- [ ] Update `_build_prompt()` in `ReasoningService` to include a warning line if `is_mock`

---

## R2 — `anomaly_detection.py:300` — DB errors silently return baseline 1000.00

**File:** `backend/app/services/anomaly_detection.py`, lines 300-305

**Issue:** Any exception in `_get_baseline_demand()` — including production DB connection failures — is caught by a bare `except Exception` and silently returns `Decimal("1000.00")`. A DB outage becomes invisible: anomaly detection continues running against a wrong baseline, generating false alerts or missing real ones.

**Current code:**
```python
except Exception:
    logger.debug("captation_rates lookup failed for property %s — using fallback", property_id)
return Decimal("1000.00")
```

### Acceptance Criteria

1. **Given** the `captation_rates` table does not exist (dev/test SQLite),
   **When** `_get_baseline_demand()` is called,
   **Then** it catches `sqlalchemy.exc.ProgrammingError` specifically and returns the fallback at DEBUG level — not a silent catch-all.

2. **Given** the database is unreachable (connection refused),
   **When** `_get_baseline_demand()` is called,
   **Then** it logs at ERROR level (not DEBUG) and raises `AnomalyDetectionError` — it does NOT silently return 1000.00.

3. **Given** `AnomalyDetectionError` is raised in `detect_for_property()`,
   **When** the anomaly scan worker processes a property,
   **Then** the property scan is skipped with an ERROR log and the worker moves to the next property — not a total scan failure.

### Tasks
- [ ] Replace bare `except Exception` with `except sqlalchemy.exc.ProgrammingError` for the table-not-found case
- [ ] Add a separate `except Exception` that logs at ERROR and raises `AnomalyDetectionError`
- [ ] Add `AnomalyDetectionError(Exception)` to `app/core/exceptions.py`
- [ ] In `anomaly_scan.py` worker: catch `AnomalyDetectionError` per-property, log, continue

---

## R3 — `anomaly_detection.py:189` — Return type mismatch

**File:** `backend/app/services/anomaly_detection.py`, lines 189, 389-433

**Issue:** `detect_for_property()` is annotated `-> List[DemandAnomaly]` but `_bulk_upsert()` returns `List[str]` (UUIDs from the RETURNING clause). Any caller expecting ORM instances will get AttributeError when accessing fields.

**Current code:**
```python
async def detect_for_property(...) -> List[DemandAnomaly]:
    upserted = await self._bulk_upsert(db, anomalies_to_upsert)
    return upserted  # returns List[str], not List[DemandAnomaly]
```

### Acceptance Criteria

1. **Given** `detect_for_property()` completes successfully,
   **When** the caller iterates the returned list,
   **Then** each element is a `DemandAnomaly` ORM instance with `.id`, `.window_start`, `.status` attributes accessible without error.

2. **Given** `_bulk_upsert()` returns a list of UUID strings,
   **When** `detect_for_property()` uses those IDs,
   **Then** it fetches the full ORM instances via a SELECT before returning.

3. **Given** the return type annotation,
   **When** `mypy` runs on this file,
   **Then** no type error is reported for the return value.

### Tasks
- [ ] After `_bulk_upsert()` returns `List[str]` (UUIDs), fetch ORM instances: `SELECT * FROM demand_anomalies WHERE id = ANY(:ids)`
- [ ] Return the fetched `List[DemandAnomaly]`
- [ ] Update `_bulk_upsert` return type annotation to `List[str]`

---

## R6 — `staffing_service.py:16` — Labor budget time scale ambiguous

**File:** `backend/app/services/staffing_service.py`, lines 16-17

**Issue:** `labor_budget_gbp: float = 1200.0` is commented "Weekly or daily target" — ambiguous. If the constant is daily but used as weekly (or vice versa), the budget alert fires at the wrong threshold.

### Acceptance Criteria

1. **Given** `StaffingConfig`,
   **When** it is inspected,
   **Then** the field is named `labor_budget_gbp_per_day` (or `per_week`) — ambiguity eliminated.

2. **Given** the alert message generated when budget is exceeded,
   **When** a manager reads it,
   **Then** the time unit is explicit (e.g., "Projected daily labor cost £X exceeds daily budget of £Y").

### Tasks
- [ ] Rename `labor_budget_gbp` → `labor_budget_gbp_per_day` in `StaffingConfig`
- [ ] Update all references (alert message, delta calculation)
- [ ] Add a comment confirming the time unit assumption: `# Daily budget; compare against total_shifts * avg_shift_cost for one service`

---

## R7 — `staffing_service.py:41` — `asyncio.ensure_future()` in sync context

**File:** `backend/app/services/staffing_service.py`, line 41

**Issue:** `calculate_recommendation()` is a synchronous function that calls `asyncio.ensure_future()` to fire-and-forget a budget alert coroutine. This raises `RuntimeError: no running event loop` in any non-async context (sync tests, management commands). It also means the alert may be dropped if the event loop is not running when GC collects the future.

**Current code:**
```python
asyncio.ensure_future(self._dispatch_budget_alert(...))
```

### Acceptance Criteria

1. **Given** `calculate_recommendation()` is called from a synchronous test (no running event loop),
   **When** the predicted covers exceed the budget threshold,
   **Then** it does NOT raise `RuntimeError` — the alert is either queued or skipped gracefully.

2. **Given** `calculate_recommendation()` is called from within a FastAPI async request handler,
   **When** budget threshold is exceeded,
   **Then** the budget alert coroutine is scheduled and executes.

3. **Given** a unit test for `calculate_recommendation()`,
   **When** the test runs without an event loop,
   **Then** the test passes without patching `asyncio`.

### Tasks
- [ ] Make `calculate_recommendation()` async — rename to `async def calculate_recommendation()`
- [ ] Replace `asyncio.ensure_future(...)` with `await self._dispatch_budget_alert(...)`
- [ ] Update all callers (check `AetherixEngine` and any route that calls it directly) to await
- [ ] Update existing unit tests to use `pytest.mark.asyncio`

---

## R8 — `recommendation_formatter.py:316` — Non-atomic transaction

**File:** `backend/app/services/recommendation_formatter.py`, lines 316-361

**Issue:** Recommendation INSERT and anomaly status UPDATE (`'ready_to_push'`) happen in two separate statements with no wrapping transaction. A crash between them leaves a recommendation row without the corresponding status transition, causing the formatter to attempt formatting the same anomaly again on next run.

The `ON CONFLICT (anomaly_id) DO NOTHING` prevents duplicate rows but the anomaly stays stuck in `roi_positive` status.

### Acceptance Criteria

1. **Given** a process crash after the recommendation INSERT but before the anomaly UPDATE,
   **When** the formatter runs again on the next cycle,
   **Then** the anomaly is NOT formatted again (idempotent).

2. **Given** `format_and_store()` executes successfully,
   **When** the DB transaction commits,
   **Then** both the recommendation row and the anomaly status update are committed atomically — either both succeed or both roll back.

3. **Given** a DB error during the anomaly status UPDATE,
   **When** the transaction rolls back,
   **Then** the recommendation INSERT is also rolled back (no orphaned recommendation).

### Tasks
- [ ] Wrap both SQL statements in a single explicit transaction block using `async with db.begin()` (or ensure they share the same transaction)
- [ ] Add `ON CONFLICT (anomaly_id) DO UPDATE SET status = 'ready_to_push'` to handle the re-run idempotency case (so a stuck anomaly self-heals on next run)
- [ ] Write a unit test that simulates a crash between the two statements and verifies re-run is safe

---

## Definition of Done (this story)

- [ ] `grep "ensure_future" backend/app/services/staffing_service.py` → 0 results
- [ ] `grep "except Exception" backend/app/services/anomaly_detection.py` → 0 results (replaced with typed catches)
- [ ] `prediction_engine.py` — `PredictionResult` has `is_mock` field
- [ ] `detect_for_property()` return type verified: `isinstance(result[0], DemandAnomaly)` in tests
- [ ] All existing `pytest` tests pass

## References
- Architecture coherence audit: `docs/bmad/_bmad-output/planning-artifacts/architecture.md`
- `backend/app/services/prediction_engine.py`
- `backend/app/services/anomaly_detection.py`
- `backend/app/services/staffing_service.py`
- `backend/app/services/recommendation_formatter.py`

## Dev Agent Record
### Agent Model Used
_TBD_
### Completion Notes
_TBD_
### Files Modified
_TBD_

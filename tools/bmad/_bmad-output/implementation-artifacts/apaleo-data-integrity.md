# Story: Apaleo Data Integrity Fixes

Status: ready-for-dev

**Surfaced by:** Architecture coherence audit, 2026-04-07
**Severity:** CRITICAL — data corruption in sync logs, incomplete training data, broken MCP audit trail
**Blocks:** All forecasting epics (predictions trained on poisoned/incomplete data)

---

## Problem

Four independent bugs in the Apaleo integration corrupt the data pipeline silently:

1. **Dead code in MCP client** (`apaleo_mcp_client.py:171`) — an early `return result` makes the entire JSON parsing, error handling, and agent action logging block unreachable. MCP sync returns raw unparsed objects; audit trail is never written.

2. **No pagination loop** (`apaleo_adapter.py:139`) — `get_historical_data()` fetches only page 1 of Apaleo stay records. For a 90-day range, Apaleo paginates at ~50 records/page; the system trains Prophet on ~10% of actual data.

3. **Silent defaults on 429/5xx** (`apaleo_adapter.py:84,123`) — when Apaleo returns rate-limit or server errors, the adapter silently returns `occupancy=85` and `revenue=0.0` and these values are saved to `pms_sync_logs` as real data, poisoning the captation baseline.

4. **Broken test fixture** (`test_apaleo_readonly_logging.py:193`) — `ApaleoMCPClient` is instantiated with `auth_mode="bearer"` which is not a valid constructor parameter. Write-guard tests never run.

---

## Acceptance Criteria

### AC 1 — Dead code fixed
**Given** `apaleo_mcp_client.py` after this story,
**When** `call_tool()` returns a successful result,
**Then** the result is JSON-parsed from `result.content[0].text`, the call is logged to `_agent_logger` with `duration_ms` and `result_summary`, and the parsed dict is returned (not the raw MCP result object).

### AC 2 — Pagination implemented
**Given** `get_historical_data()` called with a 90-day date range,
**When** Apaleo returns a response with `pageInfo.hasNext = true`,
**Then** all pages are fetched in a loop and the full dataset is returned as a single list.

### AC 3 — 429/5xx raises instead of returning defaults
**Given** Apaleo returns HTTP 429 or 5xx,
**When** `get_occupancy()` or `get_revenue()` is called,
**Then** the method raises `ApaleoSyncError` with the status code — it does NOT return `85` or `0.0`.
**And** the background task in `pms.py` catches `ApaleoSyncError` and logs it at ERROR level without writing the partial result to `pms_sync_logs`.

### AC 4 — Test fixture corrected
**Given** `test_apaleo_readonly_logging.py`,
**When** `pytest tests/test_apaleo_readonly_logging.py -v` is run,
**Then** all tests collect and execute (zero skipped due to fixture error).

### AC 5 — OAuth2 retry
**Given** Apaleo identity endpoint returns 503 on first attempt,
**When** `_authenticate()` is called,
**Then** it retries up to 3 times with exponential backoff before raising.

---

## Tasks

### apaleo_mcp_client.py
- [ ] Remove the early `return result` at line 171
- [ ] Parse JSON from `result.content[0].text` in the success path
- [ ] Call `_agent_logger.log(tool, params, mode=mode, duration_ms=..., result_summary=...)` before returning
- [ ] Wrap in try/except: on `Exception`, log to `_agent_logger` with `error=str(e)` then re-raise

### apaleo_adapter.py — pagination
- [ ] Inspect Apaleo `/reports/v1/stay-records` response shape for `pageInfo` or `nextCursor`
- [ ] Implement pagination loop: fetch pages until `hasNext == False` or no cursor
- [ ] Log total records fetched at INFO level
- [ ] Add `ApaleoSyncError(Exception)` custom exception to this module

### apaleo_adapter.py — silent defaults
- [ ] In `get_occupancy()`: replace silent `return 85` on non-200 with `raise ApaleoSyncError(f"HTTP {status}")`
- [ ] In `get_revenue()`: replace silent `return 0.0` with same
- [ ] In `get_historical_data()`: replace `return []` on non-200 with `raise ApaleoSyncError`
- [ ] Update `pms.py` background task to catch `ApaleoSyncError` and log without writing to DB

### apaleo_adapter.py — OAuth2 retry
- [ ] Add tenacity retry to `_authenticate()`: `retry_if_exception_type(httpx.HTTPStatusError)`, max 3 attempts, wait `wait_exponential(multiplier=1, min=1, max=10)`

### test_apaleo_readonly_logging.py
- [ ] Remove `auth_mode="bearer"` from the `configured_client` fixture (line 198)
- [ ] Run `pytest tests/test_apaleo_readonly_logging.py -v` and confirm all tests pass

---

## Dev Notes

- **Read-only constraint preserved**: this story only touches error handling and pagination — no write paths are changed. `ApaleoWriteBlockedError` logic untouched.
- **Apaleo pagination docs**: check `GET /reports/v1/stay-records` → response body likely has `{"stayRecords": [...], "pageInfo": {"hasNext": bool, "nextPageToken": str}}`. Confirm against actual Apaleo API response in sandbox before implementing.
- **Existing callers of `get_occupancy` / `get_revenue`**: `PMSSyncService.sync_daily_data()` is the only caller. That function is called via `background_tasks.add_task(...)` in `pms.py` — it should catch `ApaleoSyncError` and log, not raise to the HTTP layer.

## References
- Architecture coherence audit: `docs/bmad/_bmad-output/planning-artifacts/architecture.md`
- `backend/app/integrations/apaleo_mcp_client.py`
- `backend/app/services/apaleo_adapter.py`
- `backend/tests/test_apaleo_readonly_logging.py`

## Dev Agent Record
### Agent Model Used
_TBD_
### Completion Notes
_TBD_
### Files Modified
_TBD_

# Story: WhatsApp & Alert Pipeline Production Hardening

Status: ready-for-dev

**Surfaced by:** Architecture coherence audit, 2026-04-07
**Severity:** CRITICAL — messages silently lost, hardcoded pilot values, no sender verification
**Blocks:** Any pilot deployment with real managers

---

## Problem

Seven independent bugs make the WhatsApp/alert pipeline unsafe for production:

1. **Hardcoded Twilio sandbox number** (`whatsapp_service.py:20`) — if `TWILIO_WHATSAPP_NUMBER` is not set, messages are sent from Twilio's shared sandbox number instead of the business number.
2. **Hardcoded mock credentials** (`whatsapp_service.py:18-19`) — if `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN` are not set, API calls use `AC_MOCK_SID`/`MOCK_TOKEN`, fail silently with 401.
3. **Hardcoded `"pilot_hotel"` tenant ID** (`whatsapp_service.py:40,50,65,80`) — all inbound messages attributed to one hotel; breaks multi-tenant and makes wrong hotel's memory learn from unrelated feedback.
4. **No sender verification** (`whatsapp_service.py:29`) — any WhatsApp number can trigger manager feedback and memory learning without authentication.
5. **Status marked `"answered"` even if Twilio failed** (`explainability_service.py:245`) — if the Twilio send fails silently, the manager's question is permanently marked resolved with no retry.
6. **Alert sends to empty phone number** (`alert_dispatcher.py:147`) — `profile.phone_number or ""` passes empty string to Twilio; Twilio rejects, exception swallowed, recommendation loops in `ready_to_push` forever.
7. **No E.164 format validation** (`alert_dispatcher.py:147`, `explainability_service.py:59`) — invalid phone numbers accepted, Twilio rejects, exception swallowed.

---

## Acceptance Criteria

### AC 1 — No hardcoded credentials or fallback numbers
**Given** `TWILIO_WHATSAPP_NUMBER`, `TWILIO_ACCOUNT_SID`, or `TWILIO_AUTH_TOKEN` is not set,
**When** `WhatsAppService` is instantiated,
**Then** it raises `NotConfiguredError` with a clear message — it does NOT use sandbox/mock defaults.

### AC 2 — Tenant ID resolved from sender phone number
**Given** an inbound WhatsApp message from phone number `+33612345678`,
**When** `WhatsAppService.handle_inbound()` processes it,
**Then** it looks up `RestaurantProfile.phone_number = "+33612345678"` and uses that profile's `tenant_id` — NOT the hardcoded `"pilot_hotel"`.
**And** if no matching profile is found, the message is logged at WARNING and ignored (no memory update, no forecast call).

### AC 3 — Sender verification
**Given** an inbound message from a phone number not in any `RestaurantProfile`,
**When** `handle_inbound()` processes it,
**Then** the message is discarded without triggering any learning or forecast operations.

### AC 4 — `"answered"` only set on confirmed Twilio success
**Given** `ExplainabilityService.generate_and_send()` completes,
**When** `_send_twilio_reply()` returns a non-2xx status or raises,
**Then** `cq.status` is NOT updated to `"answered"` — the query remains in its current state for retry.
**And** the failure is logged at ERROR with `query_id` and Twilio status code.

### AC 5 — Phone number validated before Twilio send
**Given** `profile.phone_number` is `None`, empty, or not E.164 format (does not start with `+`),
**When** `alert_dispatcher.dispatch_one()` is called,
**Then** it raises `NotConfiguredError("Invalid or missing phone_number for profile {id}")` instead of sending to Twilio.
**And** the recommendation status transitions to `"config_error"` (not retried automatically).

### AC 6 — No infinite retry on permanent errors
**Given** a recommendation with a permanently invalid phone number,
**When** `run_pending()` runs on the next dispatch cycle,
**Then** recommendations with status `"config_error"` are skipped.

---

## Tasks

### whatsapp_service.py
- [ ] Add `NotConfiguredError(Exception)` to `app/core/exceptions.py` (or reuse existing)
- [ ] In `WhatsAppService.__init__`: raise `NotConfiguredError` if `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, or `TWILIO_WHATSAPP_NUMBER` are missing — remove all mock/sandbox defaults
- [ ] Replace hardcoded `"pilot_hotel"` with a DB lookup: `RestaurantProfile.phone_number = sender` → `profile.tenant_id`
- [ ] If no profile found for sender: log warning, return early — no memory/forecast operations
- [ ] Extract sender lookup into `_resolve_tenant(sender: str, db: AsyncSession) -> Optional[RestaurantProfile]`

### explainability_service.py
- [ ] Refactor `_send_twilio_reply()` to return `bool` (True = 2xx, False = error) instead of swallowing exceptions
- [ ] In `generate_and_send()`: only set `cq.status = "answered"` if `_send_twilio_reply()` returns `True`
- [ ] Same fix for the fallback reply path (line 218-226)
- [ ] Add Twilio status code to the error log

### alert_dispatcher.py
- [ ] Add E.164 validation helper: `def _validate_phone(number: str) -> bool: return bool(number and number.startswith("+") and len(number) >= 8)`
- [ ] In `dispatch_one()`: validate phone before calling Twilio; raise `NotConfiguredError` if invalid
- [ ] Add `"config_error"` as a valid `StaffingRecommendation.status` value (migration if needed)
- [ ] In `run_pending()`: filter out `status = "config_error"` in the query

### DB migration (if needed)
- [ ] Check if `staffing_recommendations.status` column has a CHECK constraint limiting values
- [ ] If yes: add `"config_error"` to the allowed values in the migration

---

## Dev Notes

- **`NotConfiguredError`**: if it doesn't already exist in `app/core/exceptions.py`, create it there. It should be a plain `Exception` subclass — not an `HTTPException`.
- **Multi-tenant lookup**: the `_resolve_tenant` helper needs an `AsyncSession`. The background task path in `whatsapp_service.py` currently doesn't take a session — introduce `AsyncSessionLocal()` context manager there (same pattern as `memory_service.py`).
- **Backward compatibility**: `"pilot_hotel"` references in seeds/fixtures should be replaced with a real `RestaurantProfile` in tests. Check `tests/` for any fixtures that rely on this value.
- **Twilio WhatsApp format**: `from_number` comes in as `whatsapp:+33612345678` from Twilio. Strip the prefix before DB lookup: `sender.removeprefix("whatsapp:")`.

## References
- Architecture coherence audit: `docs/bmad/_bmad-output/planning-artifacts/architecture.md`
- `backend/app/services/whatsapp_service.py`
- `backend/app/services/explainability_service.py`
- `backend/app/services/alert_dispatcher.py`

## Dev Agent Record
### Agent Model Used
_TBD_
### Completion Notes
_TBD_
### Files Modified
_TBD_

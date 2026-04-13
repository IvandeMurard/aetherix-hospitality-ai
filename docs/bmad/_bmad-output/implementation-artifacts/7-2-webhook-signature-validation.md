# Story 7.2: Webhook Signature Validation — HMAC Verification for Twilio + Apaleo/Mews

Status: ready-for-dev

**GitHub Issue:** [#48](https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/48)
**Epic:** Epic 7 — Security & Trust Foundation
**Priority:** Critical — must complete before any live webhook integration

## Story

As the FastAPI backend,
I want to cryptographically verify the signature of every inbound webhook request (Twilio, Apaleo, Mews),
So that spoofed or replayed webhook calls cannot trigger AI recommendations, log false manager actions, or execute unauthorized operations.

## Acceptance Criteria

1. **Given** an inbound POST to any Twilio webhook endpoint, **When** the request arrives, **Then** `X-Twilio-Signature` is validated using `twilio.request_validator.RequestValidator`. Invalid/missing signature = HTTP 403, logged immediately before any business logic runs.
2. **Given** an inbound POST to the Apaleo webhook endpoint, **When** the request arrives, **Then** the Apaleo HMAC-SHA256 signature is validated. Failure = HTTP 403. Webhook secret stored in env var, never hardcoded.
3. **Given** an inbound POST to the Mews webhook endpoint (Phase 3), **When** the request arrives, **Then** Mews webhook secret is validated per their documented mechanism. Failure = HTTP 403 + logged.
4. **Given** a valid webhook request, **When** the same body + signature is replayed after 5 minutes, **Then** the handler rejects it. Configurable via `WEBHOOK_REPLAY_WINDOW_SECONDS` (default: 300).
5. **Given** the validation middleware, **When** the `pytest` suite runs, **Then** tests cover: valid accepted, invalid rejected (403), missing rejected (403), replayed valid rejected (403).

## Tasks / Subtasks

- [ ] Task 1: Audit current webhook routes (AC: all)
  - [ ] Document current state of `backend/app/api/routes/webhook.py` and `webhooks.py`
  - [ ] Confirm no validation currently exists

- [ ] Task 2: Implement Twilio validation (AC: #1)
  - [ ] Add `twilio` SDK if not present: `pip install twilio`
  - [ ] Create `backend/app/middleware/webhook_auth.py` with `verify_twilio_webhook` FastAPI dependency
  - [ ] Apply to all Twilio routes (inbound SMS, WhatsApp reply handlers)

- [ ] Task 3: Implement Apaleo webhook validation (AC: #2)
  - [ ] Check Apaleo docs for their signing mechanism (HMAC-SHA256 or header-based secret)
  - [ ] Implement `verify_apaleo_webhook` dependency in `webhook_auth.py`
  - [ ] Add `APALEO_WEBHOOK_SECRET` to config and `.env.example`

- [ ] Task 4: Replay attack prevention (AC: #4)
  - [ ] Extract timestamp from webhook payload or header
  - [ ] Compare to `datetime.now()` within `WEBHOOK_REPLAY_WINDOW_SECONDS`
  - [ ] Add `WEBHOOK_REPLAY_WINDOW_SECONDS` to config (default: 300)

- [ ] Task 5: Logging rejected requests (AC: #1, #2, #3)
  - [ ] Log: timestamp, IP, endpoint, reason for rejection — via `action_logger.py`
  - [ ] Do NOT log the raw webhook body before validation

- [ ] Task 6: Write pytest tests (AC: #5)
  - [ ] Valid Twilio signature: 200
  - [ ] Invalid Twilio signature: 403
  - [ ] Missing signature header: 403
  - [ ] Replayed valid request after window: 403

## Dev Notes

### Twilio Validation Pattern
```python
# backend/app/middleware/webhook_auth.py
from twilio.request_validator import RequestValidator
from fastapi import Request, HTTPException, Depends

async def verify_twilio_webhook(request: Request) -> None:
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")
    form_data = await request.form()
    url = str(request.url)
    if not validator.validate(url, dict(form_data), signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

# Apply to route:
@router.post("/twilio/inbound")
async def handle_inbound(_: None = Depends(verify_twilio_webhook)):
    ...
```

### Environment Variables to Add
```
TWILIO_AUTH_TOKEN=...          # Already should exist for outbound
APALEO_WEBHOOK_SECRET=...      # New — from Apaleo developer console
WEBHOOK_REPLAY_WINDOW_SECONDS=300
```

### Important Notes
- Never log raw webhook body before signature validation (risk: logging attacker-controlled content)
- For Apaleo: check `community.apaleo.com` for current signing mechanism — may differ from HMAC
- For Mews (Phase 3): defer to Phase 3 sprint when Mews integration is implemented

## References

- Webhook routes: `backend/app/api/routes/webhook.py`, `webhooks.py`
- Action logger: `backend/app/services/action_logger.py`
- Twilio signature validation docs: https://www.twilio.com/docs/usage/webhooks/webhooks-security
- GitHub Issue: https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/48

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

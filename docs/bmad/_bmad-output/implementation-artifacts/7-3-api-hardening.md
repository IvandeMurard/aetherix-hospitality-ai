# Story 7.3: API Hardening — Rate Limiting, CORS Policy, Security Headers (FastAPI)

Status: ready-for-dev

**GitHub Issue:** [#49](https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/49)
**Epic:** Epic 7 — Security & Trust Foundation
**Priority:** High — required before any customer-facing deployment

## Story

As the FastAPI backend,
I want all public-facing API routes to be protected by rate limiting, a strict CORS policy, and standard security headers,
So that the API surface is hardened against abuse, enumeration attacks, and common browser-based vulnerabilities.

## Acceptance Criteria

1. **Given** any public API endpoint, **When** a single IP exceeds `RATE_LIMIT_PER_MINUTE` (default: 60) requests/min, **Then** the API returns HTTP 429 with `Retry-After` header. Rate limits are Redis-backed and configurable per tier: `auth` (10/min), `webhooks` (120/min), `general` (60/min).
2. **Given** a browser cross-origin request, **When** the `Origin` is not in `CORS_ALLOWED_ORIGINS`, **Then** the CORS middleware rejects the preflight. `allow_credentials=True` set only on auth routes, not globally.
3. **Given** any API response, **When** sent, **Then** it includes: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Request-ID: <uuid>`.
4. **Given** any POST/PUT endpoint, **When** body exceeds `MAX_REQUEST_BODY_KB` (default: 512 KB), **Then** API returns HTTP 413 before processing.
5. **Given** `/auth/login` and `/auth/register` endpoints, **When** same IP sends >10 requests/60s, **Then** HTTP 429 returned. Failed login attempts logged (password never logged).
6. **Given** hardening middleware, **When** `pytest` runs, **Then** tests verify: 429 on 61st request, CORS rejects unknown origin, security headers present, body size limit enforced.

## Tasks / Subtasks

- [ ] Task 1: Add rate limiting (AC: #1, #5)
  - [ ] Add `slowapi` to dependencies: `pip install slowapi`
  - [ ] Configure Redis-backed `Limiter` using existing `REDIS_URL` (Upstash)
  - [ ] Define rate limit tiers as constants in `config.py`
  - [ ] Apply `@limiter.limit("10/minute")` to all `/auth/*` routes
  - [ ] Apply `@limiter.limit("60/minute")` to general routes
  - [ ] Apply `@limiter.limit("120/minute")` to webhook routes

- [ ] Task 2: Update CORS middleware (AC: #2)
  - [ ] Replace default CORS config in `main.py` with env-configured `CORS_ALLOWED_ORIGINS`
  - [ ] Set `allow_credentials=True` only on auth-related routes, not globally
  - [ ] Default allowed origins: Next.js frontend domain + `localhost:3000` for dev

- [ ] Task 3: Add security headers middleware (AC: #3)
  - [ ] Create custom middleware in `main.py` or `backend/app/middleware/security_headers.py`
  - [ ] Add all 5 required headers to every response
  - [ ] Add `X-Request-ID` (UUID) for log correlation

- [ ] Task 4: Request body size limit (AC: #4)
  - [ ] Configure `MAX_REQUEST_BODY_KB` in Starlette/FastAPI settings
  - [ ] Return HTTP 413 for oversized bodies

- [ ] Task 5: Add new env vars (AC: all)
  - [ ] Add to `.env.example`: `CORS_ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `MAX_REQUEST_BODY_KB`
  - [ ] Update `backend/app/core/config.py` with new settings fields

- [ ] Task 6: Write pytest tests (AC: #6)
  - [ ] Test: 61st request returns 429
  - [ ] Test: unknown Origin rejected by CORS
  - [ ] Test: security headers present in response
  - [ ] Test: body exceeding limit returns 413

## Dev Notes

### Rate Limiting Implementation
```python
# main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

### Security Headers Middleware
```python
import uuid
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-ID"] = str(uuid.uuid4())
    return response
```

### Notes
- Reuse existing Upstash Redis connection (`REDIS_URL`) for rate limiter — no new infrastructure
- `X-Request-ID` should be logged at request entry and propagated through service calls for distributed tracing
- `HSTS` header is only meaningful over HTTPS — ensure it doesn't break local HTTP dev (check `settings.ENVIRONMENT`)

## References

- FastAPI entry: `backend/app/main.py`
- Config: `backend/app/core/config.py`
- GitHub Issue: https://github.com/IvandeMurard/aetherix-hospitality-ai/issues/49

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

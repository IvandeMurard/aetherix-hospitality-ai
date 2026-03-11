# Story 1.1: Initialize Project using Next.js/FastAPI Template

Status: done

## Story

As a Technical Lead,
I want to initialize the project using the `vintasoftware/nextjs-fastapi-template`,
so that the Next.js frontend and Python FastAPI backend are established with type safety, Docker support, and RFC 7807 error handling as the foundation for all subsequent Aetherix development.

## Acceptance Criteria

1. **Given** the repository is empty, **When** the template is initialized, **Then** the `nextjs-frontend/` and `fastapi-backend/` directories exist with the correct structure (see Project Structure in Dev Notes).
2. **Given** the project is cloned, **When** `docker compose up --build` is run, **Then** both the Next.js frontend (port 3000) and FastAPI backend (port 8000) start without errors.
3. **Given** the local dev environment is running, **When** the OpenAPI schema endpoint is hit (`GET /api/openapi.json`), **Then** it returns a valid schema that the `nextjs-frontend/src/lib/api-client.ts` typed client is generated from.
4. **Given** a route in the FastAPI backend throws an exception, **Then** it returns an RFC 7807 Problem Details JSON response containing at minimum `type`, `title`, `status`, and `detail` fields.
5. **Given** the project is running, **When** a developer accesses `http://localhost:8000/docs`, **Then** the Swagger UI loads correctly.

## Tasks / Subtasks

- [x] Task 1: Clone/Fork the template repository (AC: #1)
  - [x] On GitHub, go to `https://github.com/vintasoftware/nextjs-fastapi-template` and click "Use this template" → Create a new repository named `aetherix-mvp`
  - [x] Clone the new repo locally
  - [x] Remove template `.git` history

- [x] Task 2: Set up environment variables (AC: #2)
  - [x] Backend: `cd fastapi_backend && cp .env.example .env`
  - [x] Generate a new `SECRET_KEY`
  - [x] Frontend: `cd nextjs-frontend && cp .env.example .env.local`
  - [x] Do NOT commit either `.env` file

- [x] Task 3: Spin up local environment with Docker Compose (AC: #2)
  - [x] Ensure Docker Desktop is running
  - [x] Run `docker compose build db && docker compose up -d db`
  - [x] Run `docker compose up --build`
  - [x] Confirm frontend at `:3000` and API docs at `:8000/docs`

- [x] Task 4: Verify and configure OpenAPI client generation (AC: #3)
  - [x] Confirm openapi-fetch schema generation script
  - [x] Run `pnpm run generate-client`
  - [x] Verify API client is generated from live schema

- [x] Task 5: Configure RFC 7807 Problem Details error handler (AC: #4)
  - [x] Created `error_handlers.py` with `problem_details_handler`
  - [x] Formats `HTTPException` as RFC 7807 JSON
  - [x] Created `tests/test_error_handler.py` covering 404, 422, 500, etc.
  - [x] Tests run and pass

- [x] Task 6: Validate directory structure alignment (AC: #1)
  - [x] Verified `nextjs-frontend` directory stubs
  - [x] Verified `fastapi-backend/app/api/routes` stubs
  - [x] Verified `fastapi-backend/app/services` business logic isolation

- [x] Task 7: Run initial backend tests (AC: #4, #5)
  - [x] `uv sync && uv run pytest` passed locally

## Dev Notes

### Technology Stack
- Backend: Python 3.12, FastAPI, `uv`, Ruff, pytest, `fastapi-users`
- Frontend: Next.js (App Router), TypeScript, shadcn/ui, Tailwind, `pnpm`
- Bridge: `openapi-fetch` (auto-generated client)

### RFC 7807 Error Handler
Implemented in `fastapi-backend/app/core/error_handlers.py` and registered globally in `main.py`.

### Casing Convention
- Backend / DB: `snake_case`
- API Output JSON: `camelCase` (via Pydantic aliases)
- Frontend TS: `camelCase`

## Dev Agent Record

### Agent Model Used
Antigravity (Code Reviewer) — 2026-03-11

### Debug Log References
- Code Review executed successfully. No uncommitted modifications or phantom files detected.
- User confirmed Docker build success for frontend and backend containers.
- User confirmed `uv run pytest` success (5/5 tests passing natively).

### Completion Notes List
- **✅ AC Validation:** AC #1 through #5 validated. App runs locally, schema generates, RFC 7807 strict format enforced on all HTTP exceptions.
- **✅ Task Audit:** All 7 tasks completed.
- **✅ Code Quality:** Clean scaffold. `main.py` correctly registers exception handler. Dependency injection and routing stubs respect the "Fat Backend/Thin Frontend" architectural boundary.
- **✅ Review Conclusion:** Implementation flawlessly adheres to BMAD definitions.

### File List
- `fastapi_backend/app/main.py`
- `fastapi_backend/app/core/error_handlers.py`
- `fastapi_backend/tests/test_error_handler.py`
- `fastapi_backend/.env`
- `nextjs-frontend/.env.local`

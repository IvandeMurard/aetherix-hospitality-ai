# Story 0.0 — Cleanup Corrupted Service Files

Status: ready-for-dev

**Epic:** 0 — LLM Provider Abstraction (prerequisite)
**Drafted:** 2026-04-07 — surfaced during end-of-epic architecture review (HOS-118)
**Blocks:** Stories 0.3, 0.4 (EmbeddingProvider refactor cannot run on corrupted files)

---

## Problem

Three service files contain concatenated duplicate implementations — a merge artefact where two successive rewrites were appended rather than replaced. These files will cause `SyntaxError` or silent logic conflicts when Story 0.4 touches them. Additionally, the embedding dimension constant is wrong.

| File | Issue |
|------|-------|
| `backend/app/services/rag_service.py` | Two complete implementations concatenated — first block (lines 1-37) is a stub returning a zero-vector; second block (lines 38+) is the real Mistral-based `RAGService` class. First block must be removed. |
| `backend/app/services/memory_service.py` | Same pattern — first block defines a `MemoryProvider` Protocol stub; second block is the real `MemoryService`. Second block also has duplicate method definitions. First block must be removed; duplicate methods resolved. |
| `backend/app/services/rag_service.py:23` | `_EMBEDDING_DIM = 1536` but `mistral-embed` outputs 1024 dimensions. Mismatch will corrupt pgvector similarity queries. |

A fourth related issue — `main.py` has triple duplicate import blocks and scheduler jobs registered in the shutdown phase instead of startup — is tracked separately in **Story 0.0b** (see below) to keep scope tight.

---

## Story

As a Dev agent preparing to implement Stories 0.3–0.4,
I want the service files `rag_service.py` and `memory_service.py` to be syntactically clean with a single correct implementation,
So that EmbeddingProvider DI can be grafted in without fighting corrupted baselines.

---

## Acceptance Criteria

1. **Given** `rag_service.py` after this story,
   **When** `python -c "from app.services.rag_service import RAGService"` is run,
   **Then** it imports without error and `RAGService` is the only top-level class defined in the file.

2. **Given** `rag_service.py` after this story,
   **When** `grep "_EMBEDDING_DIM" rag_service.py` is run,
   **Then** it returns `_EMBEDDING_DIM = 1024`.

3. **Given** `memory_service.py` after this story,
   **When** `python -c "from app.services.memory_service import MemoryService"` is run,
   **Then** it imports without error with no duplicate method definitions (each method defined exactly once).

4. **Given** `memory_service.py` after this story,
   **When** `grep -c "def store_reflection" memory_service.py` is run,
   **Then** it returns `1`.

5. **Given** `memory_service.py` after this story,
   **When** `grep -c "def get_relevant_context" memory_service.py` is run,
   **Then** it returns `1`.

6. **Given** all existing tests,
   **When** `python -m pytest tests/ -v` is run,
   **Then** all tests pass with 0 regressions.

---

## Tasks

### rag_service.py
- [ ] Read the full file and identify the cut point between the stub block (lines 1-37, the `_get_embedding()` function block) and the real implementation (line 38+, the `RAGService` class)
- [ ] Remove the stub block entirely — keep only the `RAGService` class implementation
- [ ] Change `_EMBEDDING_DIM = 1536` → `_EMBEDDING_DIM = 1024` (Mistral `mistral-embed` = 1024d)
- [ ] Ensure the module-level `logger = logging.getLogger(__name__)` is kept exactly once
- [ ] Run `python -c "from app.services.rag_service import RAGService"` — must succeed
- [ ] Verify that the zero-vector fallback inside `RAGService.get_embedding()` also uses 1024: `[0.0] * 1024`

### memory_service.py
- [ ] Read the full file and identify the cut point — the first block is a Protocol stub (`MemoryProvider`, etc.), the second block is the real `MemoryService`
- [ ] Remove the first stub block entirely — keep only the `MemoryService` class
- [ ] Identify and remove duplicate method definitions: `store_reflection` (keep the fuller implementation), `get_relevant_context` (keep the fuller implementation)
- [ ] Run `python -c "from app.services.memory_service import MemoryService"` — must succeed
- [ ] Run `grep -c "def store_reflection" memory_service.py` — must return `1`

### Verification
- [ ] Run `python -m pytest tests/ -v` — all tests green
- [ ] Run `grep -rn "_EMBEDDING_DIM\|1536" backend/app/services/` — confirm no remaining 1536 references

---

## Dev Notes

- **Do NOT change the public API** of `RAGService` or `MemoryService` — method signatures, return types, and fallback behaviour must be identical to what callers (e.g. `AetherixEngine`) currently expect.
- **The Mistral client instantiation** stays in the service for now — Story 0.4 will replace it with `EmbeddingProvider` DI. This story only removes duplication.
- **pgvector column**: If `vector(1536)` is already in the DB migration for `fb_patterns.embedding`, a separate migration story is needed to change it to `vector(1024)`. Check `db/models.py` and existing Alembic migrations before running. Flag as a follow-up if a migration is needed.

---

## Story 0.0b — Fix main.py Lifecycle (Companion Story)

_Tracked separately to keep scopes tight. Implement after Story 0.0 or in parallel._

**Problem:** `main.py` has three separate import blocks for the same routes (namespace collision risk), two `on_shutdown` handlers (second is ignored), and APScheduler job registration inside the first `on_shutdown` handler — meaning jobs are registered during shutdown, never during uptime. The anomaly scan and dispatch workers never actually run.

**Scope:**
- [ ] Consolidate triple import block into a single canonical block (routes: pms, webhooks, auth, dashboard, predictions, reports, weather, baselines, events)
- [ ] Migrate from `@app.on_event("startup"/"shutdown")` to FastAPI `lifespan` async context manager (FastAPI 0.95+ recommended pattern)
- [ ] Move `register_anomaly_scan_job(_scheduler)` + `register_dispatch_job(_scheduler)` + `_scheduler.start()` into the startup phase (inside `lifespan`, before `yield`)
- [ ] Move all `stop_*_scheduler()` + `_scheduler.shutdown()` calls into the shutdown phase (inside `lifespan`, after `yield`)
- [ ] Wire `get_llm_provider()` + `get_embedding_provider()` into `lifespan` → `app.state` (Story 0.2 AC #6)
- [ ] Add missing `app.add_middleware(CORSMiddleware, ...)` call with correct CORS origins

**Acceptance criteria:** `python -m pytest tests/ -v` green; a test that registers a scheduler job and verifies `_scheduler.running == True` during app lifetime.

---

## References

- Architecture review: `docs/bmad/_bmad-output/planning-artifacts/architecture.md` §Pre-Phase-1 Blockers
- Epic 0 spec: `docs/bmad/_bmad-output/implementation-artifacts/0-llm-provider-abstraction.md`
- Affected callers: `backend/app/services/aetherix_engine.py`

## Dev Agent Record

### Agent Model Used
_TBD_

### Completion Notes
_TBD_

### Files Modified
_TBD_

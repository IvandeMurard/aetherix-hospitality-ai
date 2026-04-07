# Epic 0: LLM Provider Abstraction

Status: ready-for-dev

**Architectural Decision:** #9 in `CLAUDE.md` — Multi-LLM fallback via `LLMProvider` abstraction
**Phase:** 0.5 — prerequisite to Phase 1 go-live
**Branch:** `claude/whatsapp-agent-response-ui-iTTXk`
**Drafted:** 2026-04-06

---

## Problem

The Aetherix backend has two hard-coded AI provider dependencies with no abstraction layer:

**LLM completions (2 services):**
- `reasoning_service.py:1` — `from anthropic import AsyncAnthropic`; model hard-coded as `"claude-sonnet-4-6"`
- `explainability_service.py:26` — `from anthropic import AsyncAnthropic`; model hard-coded as `"claude-sonnet-4-6"`

**Embeddings (2 services):**
- `rag_service.py:46` — `from mistralai import Mistral`; model hard-coded as `"mistral-embed"`
- `memory_service.py` — Mistral embeddings called directly, no interface

This violates CLAUDE.md Architectural Decision #9: *"Ne pas être lié à un seul provider LLM — switch auto entre providers selon coût + performance."*

The moat is not in the model. LLMs are commodity. Hard-coding Claude creates lock-in that contradicts the explicit architectural principle.

---

## Goal

Introduce two protocol abstractions — `LLMProvider` and `EmbeddingProvider` — so the business logic in reasoning, explainability, RAG, and memory services is decoupled from any specific AI vendor. Claude remains the primary LLM provider; Mistral remains the primary embedding provider. No behaviour changes at runtime.

---

## Scope

**In scope:**
- `LLMProvider` protocol definition + `ClaudeProvider` implementation (primary)
- `EmbeddingProvider` protocol definition + `MistralEmbeddingProvider` implementation (primary)
- Refactor `reasoning_service.py` and `explainability_service.py` to consume `LLMProvider`
- Refactor `rag_service.py` and `memory_service.py` to consume `EmbeddingProvider`
- Provider instantiation via factory function using env vars
- Unit tests: mock provider swapped in, verifying zero Anthropic/Mistral imports in services

**Out of scope:**
- Implementing a second live provider (Gemini, GPT-4o) — the *interface* is the deliverable
- Provider cost/performance routing logic (Phase 2)
- Streaming completions (future story)
- Fine-tuned model support

---

## Architecture Target

```
backend/app/providers/
├── __init__.py
├── base.py              # LLMProvider + EmbeddingProvider Protocol definitions
├── claude_provider.py   # ClaudeProvider(LLMProvider) — primary
├── mistral_provider.py  # MistralEmbeddingProvider(EmbeddingProvider) — primary
└── factory.py           # get_llm_provider() + get_embedding_provider() from env

backend/app/services/
├── reasoning_service.py      # now accepts LLMProvider via __init__ (DI)
├── explainability_service.py # now accepts LLMProvider via __init__ (DI)
├── rag_service.py            # now accepts EmbeddingProvider via __init__ (DI)
└── memory_service.py         # now accepts EmbeddingProvider via __init__ (DI)
```

**Protocol definitions:**
```python
# backend/app/providers/base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface for LLM text-completion providers."""
    async def complete(
        self,
        messages: list[dict],          # [{"role": "user"|"assistant", "content": str}]
        max_tokens: int = 500,
        temperature: float = 0.3,
        system: str | None = None,
    ) -> str:
        """Return the model's text response."""
        ...

    @property
    def model_id(self) -> str:
        """Human-readable model identifier for logging."""
        ...

@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal interface for text embedding providers."""
    async def embed(self, text: str) -> list[float]:
        """Return a float vector for *text*. Length is provider-specific."""
        ...

    @property
    def dimensions(self) -> int:
        """Embedding vector length (e.g. 1024 for Mistral, 1536 for OpenAI)."""
        ...
```

**Factory:**
```python
# backend/app/providers/factory.py
import os
from app.providers.base import LLMProvider, EmbeddingProvider

def get_llm_provider() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "claude")  # "claude" | "gemini" | "openai"
    if backend == "claude":
        from app.providers.claude_provider import ClaudeProvider
        return ClaudeProvider(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            model=os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
        )
    raise NotImplementedError(f"LLM backend '{backend}' not yet implemented")

def get_embedding_provider() -> EmbeddingProvider:
    backend = os.getenv("EMBEDDING_BACKEND", "mistral")  # "mistral" | "openai"
    if backend == "mistral":
        from app.providers.mistral_provider import MistralEmbeddingProvider
        return MistralEmbeddingProvider(
            api_key=os.getenv("MISTRAL_API_KEY", ""),
            model=os.getenv("EMBEDDING_MODEL", "mistral-embed"),
        )
    raise NotImplementedError(f"Embedding backend '{backend}' not yet implemented")
```

---

## Stories

| # | Title | Size | Depends |
|---|---|---|---|
| Story 0.1 | Define `LLMProvider` Protocol + Implement `ClaudeProvider` | S | — |
| Story 0.2 | Refactor Reasoning + Explainability Services to Use `LLMProvider` | M | 0.1 |
| Story 0.3 | Define `EmbeddingProvider` Protocol + Implement `MistralEmbeddingProvider` | S | — |
| Story 0.4 | Refactor RAG + Memory Services to Use `EmbeddingProvider` | M | 0.3 |

---

## Story 0.1 — Define `LLMProvider` Protocol + Implement `ClaudeProvider`

**As** the backend infrastructure,
**I want** a `LLMProvider` protocol with a `ClaudeProvider` implementation,
**So that** business services can depend on the interface, not the Anthropic SDK.

### Acceptance Criteria

1. **Given** the `backend/app/providers/` package exists,
   **When** `from app.providers.base import LLMProvider` is imported,
   **Then** `LLMProvider` is a `typing.Protocol` with `complete(messages, max_tokens, temperature, system) -> str` and a `model_id` property.

2. **Given** `ANTHROPIC_API_KEY` and `LLM_MODEL` env vars are set,
   **When** `ClaudeProvider.complete(messages=[{"role":"user","content":"ping"}], max_tokens=10)` is called,
   **Then** it returns a non-empty string using the Anthropic `AsyncAnthropic.messages.create` API under the hood.

3. **Given** `ANTHROPIC_API_KEY` is not set,
   **When** `ClaudeProvider` is instantiated,
   **Then** it does NOT raise at instantiation — it raises `RuntimeError("ANTHROPIC_API_KEY not set")` only at `complete()` call time (preserving the existing lazy-init pattern in `reasoning_service.py`).

4. **Given** `get_llm_provider()` is called with `LLM_BACKEND=claude`,
   **When** the factory returns a provider,
   **Then** `isinstance(provider, LLMProvider)` is `True`.

5. **Given** `LLM_BACKEND` is set to an unsupported value,
   **When** `get_llm_provider()` is called,
   **Then** it raises `NotImplementedError` with the backend name in the message.

### Tasks

- [ ] Create `backend/app/providers/__init__.py` (empty)
- [ ] Create `backend/app/providers/base.py` with `LLMProvider` and `EmbeddingProvider` protocols
- [ ] Create `backend/app/providers/claude_provider.py` wrapping `AsyncAnthropic`
  - `complete()` maps to `client.messages.create()` — extracts `content[0].text`
  - `model_id` returns `f"claude/{self._model}"`
- [ ] Create `backend/app/providers/factory.py` with `get_llm_provider()`
- [ ] Unit tests in `tests/providers/test_claude_provider.py` (mock `AsyncAnthropic`)

### Dev Notes

- `ClaudeProvider.complete()` must convert the `system` kwarg to Anthropic's top-level `system=` parameter (not a message role), preserving the existing call pattern in `reasoning_service.py`
- Do NOT change the `max_tokens` defaults — `reasoning_service` uses 300, `explainability_service` uses 800; these will be passed explicitly by the calling service
- `ClaudeProvider` must be `async`-native throughout (no `asyncio.run()` wrappers)

---

## Story 0.2 — Refactor Reasoning + Explainability Services to Use `LLMProvider`

**As** the reasoning and explainability services,
**I want** to accept an `LLMProvider` via dependency injection,
**So that** they contain zero direct imports from the `anthropic` SDK.

### Acceptance Criteria

1. **Given** `reasoning_service.py` after this story,
   **When** `grep -n "from anthropic\|import anthropic" reasoning_service.py` is run,
   **Then** it returns 0 matches.

2. **Given** `explainability_service.py` after this story,
   **When** `grep -n "from anthropic\|import anthropic" explainability_service.py` is run,
   **Then** it returns 0 matches.

3. **Given** `ReasoningService(llm=ClaudeProvider(...))`,
   **When** `generate_explanation(...)` is called,
   **Then** it calls `self._llm.complete(messages=..., max_tokens=300, temperature=0.3)` and returns the same dict structure as before (`summary`, `confidence_factors`, `claude_used`).

4. **Given** a mock `LLMProvider` returning `"Test explanation."`,
   **When** `ReasoningService(llm=mock_provider).generate_explanation(...)` is called in a unit test,
   **Then** the result `summary` equals `"Test explanation."` and `claude_used` is `True`.

5. **Given** the mock provider raises `Exception("API error")`,
   **When** `generate_explanation()` is called,
   **Then** the service falls back to `_heuristic_explanation()` and returns `claude_used: False` — unchanged fallback behaviour.

6. **Given** `get_llm_provider()` in `main.py` startup,
   **When** both services are instantiated,
   **Then** they share the same provider instance (singleton via FastAPI `lifespan` or `Depends`).

### Tasks

- [ ] Refactor `ReasoningService.__init__` to accept `llm: LLMProvider` parameter
  - Replace `self.claude = AsyncAnthropic(...)` with `self._llm = llm`
  - Replace `self.claude.messages.create(...)` call with `await self._llm.complete(messages, max_tokens=300, temperature=0.3, system=None)`
- [ ] Refactor `ExplainabilityService.__init__` to accept `llm: LLMProvider` parameter
  - Same pattern; preserve the `system` prompt as the `system=` kwarg on `complete()`
- [ ] Update service instantiation in `main.py` / `lifespan` to inject `get_llm_provider()`
- [ ] Update all existing unit tests for both services to inject a mock `LLMProvider`
- [ ] Verify `pytest` green: `python -m pytest tests/ -k "reasoning or explainability" -v`

### Dev Notes

- The `_heuristic_explanation()` fallback in `ReasoningService` is pure Python — no LLM call. Keep it as-is; it runs when the provider raises.
- `ExplainabilityService` currently builds a `system` string separately from the `messages` list. Preserve this: pass `system=system_prompt` kwarg so `ClaudeProvider` can route it to Anthropic's top-level `system=` field.
- `claude_used` key in the response dict should now be read as "llm_used" internally, but keep the API key name as `claude_used` to avoid breaking the existing API contract.

---

## Story 0.3 — Define `EmbeddingProvider` Protocol + Implement `MistralEmbeddingProvider`

**As** the backend infrastructure,
**I want** an `EmbeddingProvider` protocol with a `MistralEmbeddingProvider` implementation,
**So that** embedding generation is decoupled from the `mistralai` SDK.

### Acceptance Criteria

1. **Given** `from app.providers.base import EmbeddingProvider` is imported,
   **When** `EmbeddingProvider` is inspected,
   **Then** it has `embed(text: str) -> list[float]` and a `dimensions: int` property.

2. **Given** `MISTRAL_API_KEY` is set,
   **When** `MistralEmbeddingProvider.embed("test text")` is called,
   **Then** it returns a `list[float]` of length 1024 (Mistral's `mistral-embed` output dimension).

3. **Given** `MISTRAL_API_KEY` is not set,
   **When** `MistralEmbeddingProvider.embed("test text")` is called,
   **Then** it returns a zero-vector of length 1024 (preserving the existing dev/test behaviour in `rag_service.py`).

4. **Given** `get_embedding_provider()` is called with `EMBEDDING_BACKEND=mistral`,
   **When** the factory returns a provider,
   **Then** `isinstance(provider, EmbeddingProvider)` is `True` and `provider.dimensions == 1024`.

### Tasks

- [ ] Create `backend/app/providers/mistral_provider.py` wrapping `Mistral` client
  - `embed()` calls `client.embeddings.create(model=self._model, inputs=[text])` and returns `data[0].embedding`
  - Returns zero-vector `[0.0] * 1024` when API key is absent
  - `dimensions` property returns `1024`
- [ ] Add `get_embedding_provider()` to `backend/app/providers/factory.py`
- [ ] Unit tests in `tests/providers/test_mistral_provider.py` (mock `Mistral` client)

### Dev Notes

- The zero-vector fallback is critical for CI: tests run without a `MISTRAL_API_KEY` and currently work because `rag_service.py` already returns zeros when the key is absent. This story must preserve that.
- `MistralEmbeddingProvider` wraps the sync `Mistral` client in `asyncio.get_event_loop().run_in_executor()` — same pattern used today in `rag_service.py` via `loop.run_in_executor`.

---

## Story 0.4 — Refactor RAG + Memory Services to Use `EmbeddingProvider`

**As** the RAG and memory services,
**I want** to accept an `EmbeddingProvider` via dependency injection,
**So that** they contain zero direct imports from the `mistralai` SDK.

### Acceptance Criteria

1. **Given** `rag_service.py` after this story,
   **When** `grep -n "from mistralai\|import mistralai" rag_service.py` is run,
   **Then** it returns 0 matches.

2. **Given** `memory_service.py` after this story,
   **When** `grep -n "from mistralai\|import mistralai" memory_service.py` is run,
   **Then** it returns 0 matches.

3. **Given** `RagService(embedding=MistralEmbeddingProvider(...))`,
   **When** `retrieve_patterns(query_text=..., hotel_id=..., top_k=5)` is called,
   **Then** it calls `await self._embedding.embed(query_text)` and uses the result vector for pgvector similarity search — identical results to before.

4. **Given** a mock `EmbeddingProvider` returning a fixed 1024-dim vector,
   **When** `RagService(embedding=mock_provider).retrieve_patterns(...)` is called in a unit test,
   **Then** the mock's `embed()` is called exactly once with the query text.

5. **Given** all 4 services refactored (Stories 0.2 + 0.4),
   **When** `python -m pytest tests/ -v` runs,
   **Then** all existing tests pass with 0 regressions.

### Tasks

- [ ] Refactor `RagService.__init__` (inner class `_EmbeddingClient`) to accept `embedding: EmbeddingProvider`
  - Remove `self._mistral = Mistral(...)` construction
  - Replace `_get_embedding()` standalone function with `await self._embedding.embed(text)`
- [ ] Refactor `MemoryService.__init__` to accept `embedding: EmbeddingProvider`
  - Remove inline Mistral embedding calls
  - Replace with `await self._embedding.embed(text)`
- [ ] Update `main.py` to inject `get_embedding_provider()` into both services
- [ ] Update all existing unit tests for `rag_service` and `memory_service` to inject a mock `EmbeddingProvider`
- [ ] Add env vars to `.env.example`: `LLM_BACKEND`, `LLM_MODEL`, `EMBEDDING_BACKEND`, `EMBEDDING_MODEL`
- [ ] Verify CI green: `python -m pytest tests/ -v`

### Dev Notes

- `rag_service.py` currently has a module-level `_get_embedding()` async function alongside the `_EmbeddingClient` inner class — both do Mistral calls. This story should collapse both into the injected `EmbeddingProvider`.
- The pgvector query in `rag_service.py` builds a SQL literal `CAST(:embedding AS vector)` — this stays unchanged; only the embedding generation source changes.
- After Stories 0.1–0.4 are merged, run `grep -rn "from anthropic\|from mistralai" backend/app/services/` to confirm 0 results (gate check for the epic DoD).

---

## Definition of Done (Epic Level)

- [ ] `backend/app/providers/` package exists with `base.py`, `claude_provider.py`, `mistral_provider.py`, `factory.py`
- [ ] `grep -rn "from anthropic" backend/app/services/` → 0 results
- [ ] `grep -rn "from mistralai" backend/app/services/` → 0 results
- [ ] `LLM_BACKEND`, `LLM_MODEL`, `EMBEDDING_BACKEND`, `EMBEDDING_MODEL` added to `.env.example`
- [ ] All existing `pytest` tests pass (no regressions)
- [ ] Adding a second provider in future requires: 1 new file in `providers/`, 1 new branch in `factory.py` — zero changes to `services/`

---

## References

- CLAUDE.md §Décisions architecturales — Décision #9 (Multi-LLM fallback)
- `backend/app/services/reasoning_service.py` — current hard-coded `AsyncAnthropic`
- `backend/app/services/explainability_service.py` — current hard-coded `AsyncAnthropic`
- `backend/app/services/rag_service.py` — current hard-coded `Mistral` embeddings
- `backend/app/services/memory_service.py` — current hard-coded Mistral embeddings

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

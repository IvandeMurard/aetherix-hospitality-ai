# Story: LLM Provider Abstraction & Fallback System

Status: ready-for-dev

## Context

Claude LLMs are becoming commodity. This story implements the `LLMProvider` abstract interface (Architectural Decision #9) so Aetherix can swap between Claude → Gemini → GPT automatically based on availability and cost — without rewriting call sites. Claude Sonnet remains the primary provider (reasoning, 200K ctx, explainability); this is insurance, not a replacement.

## Story

As a backend engineer,
I want a `LLMProvider` abstraction layer with automatic fallback,
so that Aetherix is not hard-locked to a single LLM vendor and can maintain quality output even during outages or pricing changes.

## Acceptance Criteria

1. **`LLMProvider` Protocol:** A `LLMProvider` abstract class/protocol exists in `backend/app/services/llm/` defining at minimum:
   - `complete(messages, system_prompt, max_tokens, **kwargs) -> LLMResponse`
   - `model_name` property
2. **Concrete Providers:** At least two concrete implementations exist:
   - `ClaudeProvider` (primary) — wraps `anthropic` SDK, `claude-sonnet-4-6`
   - `GeminiProvider` (fallback #1) — wraps `google-generativeai` SDK
   - Optional stub `OpenAIProvider` (fallback #2) — wraps `openai` SDK
3. **Fallback Chain:** A `FallbackLLMProvider` orchestrator tries providers in configured order. On `RateLimitError`, `APIStatusError` (5xx), or timeout from provider N, it automatically retries on provider N+1. If all fail, raises `LLMUnavailableError`.
4. **Configuration via env vars:**
   - `LLM_PRIMARY` (default: `claude`)
   - `LLM_FALLBACK_1` (default: `gemini`)
   - `LLM_FALLBACK_2` (default: `openai`, optional)
   - Existing `ANTHROPIC_API_KEY` unchanged; add `GOOGLE_API_KEY`, `OPENAI_API_KEY` as optional
5. **Existing call sites migrated:** Story 5.2 (explainability receipt generator) routes through `FallbackLLMProvider`, not the raw Anthropic SDK directly.
6. **Observability:** Each LLM call logs `provider_used`, `model`, `latency_ms`, `fallback_triggered` (bool) at `INFO` level.
7. **Quality parity:** Fallback providers receive the same system prompt and message structure as Claude. No prompt rewriting between providers.
8. **Tests:** Unit tests cover fallback trigger logic (mock provider raises `RateLimitError` → next provider is called). Integration test skipped if API keys absent (`pytest.mark.skipif`).

## Tasks / Subtasks

- [ ] Create `backend/app/services/llm/` package (AC: 1)
  - [ ] `base.py` — `LLMProvider` protocol + `LLMResponse` dataclass + `LLMUnavailableError`
  - [ ] `claude_provider.py` — `ClaudeProvider(LLMProvider)` wrapping `anthropic` async client
  - [ ] `gemini_provider.py` — `GeminiProvider(LLMProvider)` wrapping `google-generativeai`
  - [ ] `openai_provider.py` — `OpenAIProvider(LLMProvider)` stub (optional)
  - [ ] `fallback_provider.py` — `FallbackLLMProvider` orchestrator with retry/fallback logic
  - [ ] `factory.py` — `get_llm_provider()` reads env vars and returns configured `FallbackLLMProvider`
- [ ] Add optional dependencies to `backend/pyproject.toml`: `google-generativeai`, `openai` (AC: 2, 4)
- [ ] Add env vars to `backend/.env.example`: `LLM_PRIMARY`, `LLM_FALLBACK_1`, `LLM_FALLBACK_2`, `GOOGLE_API_KEY`, `OPENAI_API_KEY` (AC: 4)
- [ ] Migrate Story 5.2 call site to use `get_llm_provider()` (AC: 5)
  - [ ] Locate direct `anthropic.AsyncAnthropic()` calls in `backend/app/services/`
  - [ ] Replace with `await llm_provider.complete(...)` calls
- [ ] Add structured logging to `FallbackLLMProvider` (AC: 6)
- [ ] Write unit tests in `backend/tests/services/llm/` (AC: 8)
  - [ ] `test_fallback_on_rate_limit.py`
  - [ ] `test_fallback_on_server_error.py`
  - [ ] `test_all_providers_fail_raises_unavailable.py`

## Dev Notes

### Architectural Context
- **Decision #9 (CLAUDE.md):** "Ne pas être lié à un seul provider LLM — switch auto entre providers selon coût + performance"
- **Thin Backend / Fat Backend:** All LLM orchestration lives in `backend/app/services/llm/`. No LLM calls from routes directly.
- **Async-first:** Use `anthropic.AsyncAnthropic`, `google.generativeai` async API, `openai.AsyncOpenAI`. FastAPI is async throughout.

### Fallback Trigger Conditions
Trigger fallback on:
- `anthropic.RateLimitError` (429)
- `anthropic.APIStatusError` where `status_code >= 500`
- `asyncio.TimeoutError` (wrap calls with `asyncio.wait_for`, 30s timeout)
- Do NOT fallback on `anthropic.BadRequestError` (400) — these are prompt issues, not provider issues

### LLMResponse Dataclass
```python
@dataclass
class LLMResponse:
    content: str
    provider_used: str      # e.g. "claude", "gemini"
    model: str              # e.g. "claude-sonnet-4-6"
    input_tokens: int
    output_tokens: int
    fallback_triggered: bool
    latency_ms: float
```

### Source Tree
```
backend/app/services/llm/
├── __init__.py
├── base.py            # LLMProvider protocol, LLMResponse, LLMUnavailableError
├── claude_provider.py
├── gemini_provider.py
├── openai_provider.py  # optional stub
├── fallback_provider.py
└── factory.py         # get_llm_provider() singleton

backend/tests/services/llm/
├── test_fallback_provider.py
└── conftest.py        # mock providers
```

### Preserving Claude Quality
Claude Sonnet remains the default. Gemini/GPT fallbacks are only invoked on error. The system prompt for hospitality reasoning should be tested against all fallback providers before enabling in production.

## References
- [CLAUDE.md — Architectural Decision #9](../../../CLAUDE.md)
- [Story 5.2 — LLM Explainability Receipt](./epics.md#story-52-generate-llm-powered-explainability-receipt)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Google Generative AI Python](https://github.com/google/generative-ai-python)

## Dev Agent Record

_To be filled during implementation._

### Agent Model Used
_TBD_

### Completion Notes
_TBD_

### Files Modified
_TBD_

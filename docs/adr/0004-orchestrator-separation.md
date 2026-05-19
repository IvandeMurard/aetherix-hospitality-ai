# ADR 0004 — Orchestrator Separation: Aetherix as F&B Execution Node

> **Status**: Accepted · **Date**: 2026-05-19 · **Author**: Architect (Sonnet)
> **Linear**: HOS-184 · **Phase**: 3 (Pilot Validation + Portfolio Reinforcement)
> **Amends**: ADR 0001 (scope of AetherixEngine)

---

## Context

`AetherixEngine` was labelled "The Hybrid Hub — Orchestrates Prophet + RAG". This was accurate for Phase 2, but Phase 3 targets an **Agentic Mesh**: multiple specialised MCP nodes (Aetherix F&B, Tacet, future Anima) coordinated by a supervisory agent.

The old `get_recommendations_with_memory_context` MCP tool sequenced embed → recall → forecast in a fixed pipe with no routing, retry, or feedback loop. It was an orchestrator masquerading as a tool.

Two problems:
1. **Coupling**: any agent calling the tool got a bundled forecast whether it needed one.
2. **Replaceability**: the tool is not composable — you can't swap the recall step for a different memory backend.

---

## Decision

### D1 — Bounded context

Aetherix's bounded context = **F&B execution** (forecast, staffing, memory, receipts). It is a node, not a hub.

### D2 — `backend/orchestrator/` proto-orchestrator

A new top-level package `orchestrator/` holds the supervisory layer. In Phase 3 this lives in the same repo; Phase 4 extracts it to its own process/repo.

### D3 — Zero Python imports from `app.*` in `orchestrator/`

`orchestrator/agent.py` receives all services via constructor injection. This is enforced by a CI test (`tests/orchestrator/test_agent.py::test_no_app_imports_in_orchestrator`).

The allowed direction is: `app/` → `orchestrator/`. The reverse is forbidden.

### D4 — Atomic MCP tools on `/mcp/v1/`

`get_recommendations_with_memory_context` (v0) is split into two atomic tools available on `/mcp/v1/`:

| v0 (deprecated) | v1 atomic replacement |
|---|---|
| `get_recommendations_with_memory_context` | `recall_memory` (scope: `memory:read`) |
| *(forecast included implicitly)* | `get_operational_predictions` (scope: `predict`) |

Supervisory agents compose these calls; the MCP node does not pre-compose them.

### D5 — `get_recommendations_with_memory_context` deprecation

The tool remains functional on `/mcp/v0/` until **2026-08-01** (Sunset header). Every response carries `Deprecation: true`. Tokens with `recommend` scope continue to work until sunset.

### D6 — `AetherixEngine` becomes a thin wrapper

`AetherixEngine` instantiates `OrchestratorAgent` with injected services and delegates `get_forecast()`. It retains `_cache_recommendation()` (DB concern in `app/`).

---

## Consequences

**Positive**
- Each MCP node is independently composable and testable.
- `orchestrator/agent.py` can evolve toward real agentic routing (dynamic tool selection, retry on low-confidence) without touching `app/`.
- Portfolio signal: clean separation is the pattern described in the Phase 3 technical write-up.

**Negative / trade-offs**
- Supervisory agents must now make two MCP calls (recall + predict) instead of one. Acceptable in Phase 3 (single design partner, controlled latency).
- `AetherixEngine` still exists as a wrapper — full removal deferred to Phase 4 when the orchestrator moves out of process.

---

## Rejected alternatives

- **Keep the bundled tool**: maintains coupling, blocks composable Agentic Mesh.
- **Extract orchestrator to separate process immediately**: too much ops overhead for Phase 3 (1 design partner). Deferred to Phase 4.

---

## References

- `backend/orchestrator/agent.py`
- `backend/app/api/routes/mcp_v1.py`
- `docs/mcp/getting-started.md`
- CLAUDE.md Decision #19

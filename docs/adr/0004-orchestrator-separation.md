# ADR 0004 — Orchestrator Separation: Aetherix as F&B Execution Node

> **Status**: Accepted · **Date**: 2026-05-18 · **Author**: Architect (Sonnet)
> **Context**: Phase 3 Agentic Mesh architecture — validated by hospitality.today "Six Layers" framework
> **Linear**: HOS-186 · **Supersedes**: none · **Amends**: ADR 0001 (scope of `AetherixEngine`)

---

## 1. Context

Phase 1–2 built `AetherixEngine` (self-described: *"The Hybrid Hub. Orchestrates Prophet + RAG"*). This was correct for an MVP where a single service needed to do everything. In Phase 3, the target architecture is an **Agentic Mesh**: multiple specialized nodes (Aetherix, Tacet, future Anima) callable via MCP, orchestrated by a dedicated supervisory agent.

Three concrete problems with the current state:

1. **`AetherixEngine` is the orchestrator, not an execution node.** It sequences Prophet → RAG → Memory → ReasoningService → AgentConstitution in a fixed pipe. That logic belongs in a supervisor, not in the F&B domain service.

2. **`get_recommendations_with_memory_context` is orchestration disguised as a tool.** It internally sequences: embed query → recall memory → call forecast. The caller (external agent) cannot observe or override the intermediate steps — the orchestration is opaque and non-agentic (no routing, no feedback, no retry on low confidence).

3. **No agentic loop exists yet.** Nothing currently does: select tools dynamically based on context, use recall results to reshape forecast input, retry with more memory on low confidence, or decide between actions based on intermediate outputs. This remains to be built.

**Trigger**: conversation 2026-05-18 cross-referencing hospitality.today "Six Layers / One Hub" framework, which validates that MCP-native, composable, single-responsibility nodes are the market direction.

---

## 2. Decision summary

| # | Decision | Chosen |
|---|----------|--------|
| D1 | Aetherix bounded context | F&B execution only: forecast, staffing, memory read/write, receipts, WhatsApp delivery |
| D2 | Orchestrator location Phase 3 | `backend/orchestrator/` module — same repo, different package boundary |
| D3 | Orchestrator location Phase 4 | Standalone repo, PMS-agnostic, multi-tenant |
| D4 | Interface contract | MCP only — zero Python imports between `app/` and `orchestrator/` |
| D5 | `get_recommendations_with_memory_context` | Deprecated → replaced by 2 atomic tools: `recall_memory` + existing `get_operational_predictions` |
| D6 | `AetherixEngine` | Migrates to `backend/orchestrator/agent.py` as proto-orchestrator stub |
| D7 | Agentic loop | LLM reasoning + tool selection + feedback lives in `orchestrator/agent.py` — not in `app/services/` |
| D8 | Tacet integration | Tacet is a separate repo (CLAUDE.md convention). Orchestrator calls Tacet via MCP, same as Aetherix |

---

## 3. Decision rationale

### D1 — Aetherix bounded context

**F&B execution node** exposes only capabilities it owns end-to-end:

| Tool | Stays in Aetherix | Why |
|------|------------------|-----|
| `get_operational_predictions` | ✓ | Pure Prophet forecast — F&B domain |
| `recall_memory` | ✓ (new, replaces half of deprecated tool) | Read from `operational_memory` — F&B domain |
| `submit_feedback_to_memory` | ✓ | Write to `operational_memory` — F&B domain |
| `adjust_staffing` | ✓ future Phase 3 | Staffing calculation — F&B domain |
| `get_recommendations_with_memory_context` | ✗ deprecated | Sequences two tools — orchestration, not execution |

**What moves out**: `AetherixEngine`, `ReasoningService`, `QueryParser`, `RecommendationFormatter`. These are routing/composition concerns.

### D2/D3 — Orchestrator location

**Phase 3: `backend/orchestrator/`** — same repo, separate package. Rationale:

- Zero cross-repo coordination overhead while there is 1 design partner and 1 developer.
- `from app.services.prediction_engine import ...` is explicitly forbidden — the orchestrator calls Aetherix only via MCP client (HTTP + bearer).
- Shared lifespan and DB session are NOT shared — orchestrator is stateless, calls MCP endpoints.

**Phase 4 trigger** (when to extract to standalone repo): ≥2 hotels with different orchestration policies, OR Tacet + Aetherix + Anima need to be orchestrated from a single entry point that is PMS-agnostic.

### D4 — MCP as the only interface

```
orchestrator/agent.py
    │
    ├── HTTP MCP → Aetherix /mcp/v0/  (bearer: atx_prod_...)
    ├── HTTP MCP → Tacet /mcp/v0/     (separate repo, separate token)
    └── HTTP MCP → Apaleo MCP         (https://mcp.apaleo.com/mcp/)
```

The MCP tool schema IS the contract. When the orchestrator repo splits in Phase 4, nothing changes in the call pattern — just the deployment topology.

**Why zero Python imports**: any `from app.services import X` in `orchestrator/` creates implicit coupling that defeats composability. A linter rule or package boundary enforces this.

### D5 — Deprecating `get_recommendations_with_memory_context`

Current tool (v0) does internally:
1. Embed the query (Mistral)
2. Recall top-k memory hits (pgvector cosine)
3. If `target_date` provided: call `engine.get_forecast()`
4. Return combined output

**Problems**:
- The orchestrator cannot observe step 2 results before deciding whether to call step 3.
- Low-confidence memory recall doesn't change the forecast call.
- External agents cannot compose these primitives differently.

**Replacement**: two atomic tools at `/mcp/v1/` (version bump justified by breaking schema change):

```
recall_memory(query, k_memory) → {memory_hits: [...], top_similarity: float}
get_operational_predictions(target_date, service_type, context) → {prediction, confidence, reasoning}
```

The **orchestrator** sequences them with awareness: if `top_similarity < 0.7` → call with `k_memory=10` before forecast. If `confidence < 0.6` → fetch more memory patterns and retry. This is the agentic loop that doesn't exist yet.

**Migration**: v0 tool remains in `/mcp/v0/` for backward compatibility until the first external consumer (Apaleo Agent Hub listing) is updated.

### D6/D7 — `AetherixEngine` → `orchestrator/agent.py`

`AetherixEngine.get_forecast()` currently runs a 4-step sequence internally. The migration:

```python
# BEFORE (app/services/aetherix_engine.py)
class AetherixEngine:
    async def get_forecast(self, ...):
        forecast = await self.forecaster.predict(...)      # step 1
        patterns = await self.rag.find_similar(...)        # step 2
        memory = await self.memory.get_relevant(...)       # step 3
        reasoning = await self.reasoner.build_prompt(...)  # step 4
        return combined_result

# AFTER (orchestrator/agent.py)
class AetherixOrchestrator:
    async def handle_forecast_request(self, query, target_date, ...):
        # step 1: recall memory via MCP
        memory = await self.mcp_client.call("recall_memory", {...})
        # step 2: decide k based on similarity score (agentic)
        if memory["top_similarity"] < 0.7:
            memory = await self.mcp_client.call("recall_memory", {k_memory: 10})
        # step 3: forecast via MCP with enriched context
        forecast = await self.mcp_client.call("get_operational_predictions", {...})
        # step 4: if confidence low, LLM reasoning loop here
        return self._synthesize(memory, forecast)
```

The difference is not cosmetic — the orchestrator can **branch** based on intermediate results.

### D8 — Tacet integration

Tacet (environmental intelligence, separate repo) plugs into the orchestrator as a third MCP endpoint. The orchestrator becomes:

```
AetherixOrchestrator
  → recall_memory (Aetherix MCP)
  → get_operational_predictions (Aetherix MCP)
  → get_room_risk_score (Tacet MCP)     ← Phase 3 Track B
  → [future] query_guest_profile (Anima MCP)  ← Phase 4
```

No Aetherix code changes required when Tacet is added. This is the composability gain.

---

## 4. What is NOT in scope (Phase 3)

| Item | Phase |
|------|-------|
| Anima / Guest Context Node | Phase 4 |
| Multi-agent supervisor (LangGraph / AutoGen) | Phase 4 |
| Orchestrator standalone repo | Phase 4 |
| Tacet MCP client integration in orchestrator | Phase 3 Track B (parallel) |
| Full agentic loop with LLM planning | Phase 3 partial (stub) |

---

## 5. Implementation backlog

| Item | Effort | Priority |
|------|--------|----------|
| Create `backend/orchestrator/__init__.py` + `agent.py` stub | XS | P0 |
| Add `recall_memory` tool to `mcp_server.py` (v1 path) | S | P0 |
| Move orchestration logic from `AetherixEngine.get_forecast()` to `orchestrator/agent.py` | M | P1 |
| Deprecate `get_recommendations_with_memory_context` (keep v0 endpoint, add deprecation header) | XS | P1 |
| Wire MCP client in `orchestrator/agent.py` → calls Aetherix `/mcp/v1/` | M | P1 |
| Add linter rule: no `from app.` imports in `orchestrator/` | XS | P1 |
| Update `docs/mcp/getting-started.md` with new tool schemas | S | P2 |
| Technical article skeleton (mesh architecture) | M | P2 (Track B) |

---

## 6. Decision record

| # | Decision | Chosen | Rejected |
|---|----------|--------|---------|
| D1 | Aetherix scope | F&B execution node | Keep as hybrid hub |
| D2 | Orchestrator Phase 3 | `backend/orchestrator/` module | New repo (too early), keep in `app/` (defeats purpose) |
| D3 | Orchestrator Phase 4 | Standalone repo | Mono-repo forever (limits composability) |
| D4 | Interface | MCP only | Python imports (coupling), REST (non-standard for agents) |
| D5 | Deprecated tool | Split into 2 atomic tools | Refactor in-place (preserves orchestration-in-tool antipattern) |
| D6 | AetherixEngine | Migrate to orchestrator | Delete (would lose logic), keep in app/services (defeats D1) |
| D7 | Agentic loop | Build in orchestrator/agent.py | Build in app/services (same problem as current state) |
| D8 | Tacet | MCP client in orchestrator | Python import (separate repo, impossible anyway) |

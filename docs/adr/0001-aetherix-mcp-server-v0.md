# ADR 0001 — Aetherix MCP Server v0

> **Status**: Accepted · **Date**: 2026-04-18 · **Author**: Architect (Opus)
> **Context**: Phase 0 DoD (amended per CLAUDE.md Decision #14, Benioff/Levie "headless for agents" directive)
> **Linear**: HOS-71 · **Blocks**: P1-2 (implementation), P1-5 (SEO agent)

---

## 1. Context

Aetherix is a proactive agentic layer for hotel F&B/Operations. Phase 0 has validated Prophet forecasting on synthetic data (MAPE 7.8% J+1, gate PASS). Enterprise distribution for agentic products is rapidly consolidating around MCP (Model Context Protocol) as the default substrate — "headless for agents" is now a go-to-market necessity, not an optional channel.

**Goal**: ship a minimal, agent-callable MCP server that exposes three core Aetherix capabilities to third-party agents (Claude Desktop, enterprise agent hubs, partner agents) with multi-tenant isolation and safe defaults.

**Non-goals (v0)**:
- Full parity with the REST API (Agent Hub listing comes in v1)
- Write operations on PMS (Decision #7: read-only)
- Memory-layer tool surface beyond a narrow feedback write
- Fine-grained OAuth scopes (v1)

---

## 2. Scope — Three tools

| Tool | Purpose | Backed by |
|------|---------|-----------|
| `get_operational_predictions` | F&B covers forecast + staffing recommendation | `POST /predict` → `AetherixEngine.get_forecast` |
| `get_recommendations_with_memory_context` | Contextualized advice pulling from `operational_memory` + `fb_patterns` | New thin service on top of `AetherixEngine` |
| `submit_feedback_to_memory` | Write manager outcome back into `operational_memory` for the learning loop | New service → `operational_memory` table |

---

## 3. Decisions

### D1 — Transport: **HTTP Streamable**

Aligned with Apaleo (our outbound MCP client already uses `streamablehttp_client` — see `backend/app/services/apaleo_mcp_adapter.py:26`). SSE is deprecated by the MCP spec. `stdio` rules out remote agent calls. **Claude Desktop supports HTTP Streamable via the `mcp-remote` bridge**, which is acceptable for v0.

Rejected:
- **SSE**: deprecated, one-way by design.
- **stdio**: local-only, breaks the "agent mesh" positioning.

### D2 — Hosting: **FastAPI sub-app mounted at `/mcp`**

Single process, shared lifespan, shared provider singletons (Decision #10), shared DB session factory. Eliminates a duplicate deploy target for v0. Sidecar is deferred until we need independent scaling or language heterogeneity.

```
app.mount("/mcp", mcp_app)  # Starlette sub-app hosted by the MCP SDK
```

Rejected:
- **Sidecar process**: doubles ops surface, requires cross-process auth handoff, no benefit at current load (<100 req/min expected).
- **Separate repo**: breaks the shared type/provider surface.

### D3 — Auth: **Bearer token (opaque)** via `Authorization: Bearer <token>`

v0 uses long-lived per-tenant opaque tokens issued manually (stored in `mcp_api_tokens` table with `hotel_id` + `scopes[] + expires_at + hashed_token`). Validation middleware extracts `hotel_id` from the token row. Supports Claude Desktop out of the box (header is passable via `mcp-remote --header`).

OAuth2 client_credentials is deferred to v1 once we onboard >3 external partners.

**Token shape**: `atx_<env>_<random32>` — `atx_prod_...`, `atx_sandbox_...`. Hashed at rest (SHA-256, no salt needed — tokens are high-entropy).

Rejected:
- **JWT**: no revocation story without a blacklist; adds signing-key rotation complexity for marginal benefit at v0.
- **mTLS**: unusable from Claude Desktop.

### D4 — Multi-tenant isolation: **`hotel_id` bound to the token, enforced server-side**

The token carries the `hotel_id`. **Tool input schemas do NOT accept `hotel_id` as a parameter** — it is injected server-side from the authenticated context. This is the only safe pattern: prompt injection cannot coerce a call into another tenant.

Every DB query passes through `with_hotel_scope(hotel_id)` which:
1. Sets a Postgres session variable `SET LOCAL app.current_hotel_id = '<uuid>'`.
2. Relies on Supabase RLS policies already in place on `operational_memory`, `fb_patterns`, `agent_action_log`.
3. Asserts `hotel_id` in Python before any query as a belt-and-suspenders check.

### D5 — Versioning: **`/mcp/v0/` path prefix + `x-aetherix-mcp-version: 0` response header**

Tool names and schemas are stable within a major version. Breaking changes → `/mcp/v1/`. Additive changes (new optional fields, new tools) allowed within v0.

Rationale: URL versioning is the most discoverable for third-party agents (easy to pin in config) and aligns with the Agent SEO policy noted in `predictions.py:118`.

### D6 — Rate limiting: **Token bucket in Redis, 60 req/min/tenant default**

Middleware at the sub-app level. Key: `mcp:rl:{hotel_id}:{minute_bucket}`. Upstash Redis is already a dependency. On limit breach → `429 Too Many Requests` with RFC 7807 body + `Retry-After` header.

Per-tool overrides allowed:
- `submit_feedback_to_memory`: 20 req/min (write-heavy)
- `get_operational_predictions`: 60 req/min
- `get_recommendations_with_memory_context`: 30 req/min (vector search cost)

### D7 — Observability: **`agent_action_log` — every call, structured**

Every MCP tool invocation logs:
```
{timestamp, hotel_id, tool_name, input_hash, status, latency_ms,
 claude_used, cost_estimate_eur, error_code?, trace_id}
```

The `trace_id` propagates as `x-aetherix-trace-id` so external agents can correlate. Input is hashed (not stored raw) to avoid PII leakage in logs; a `debug_capture=true` flag on the tenant (off by default) enables raw capture for pilot debugging.

### D8 — Tool schemas

**Tool 1: `get_operational_predictions`**
```json
{
  "name": "get_operational_predictions",
  "description": "Forecast F&B covers and staffing for the authenticated property.",
  "inputSchema": {
    "type": "object",
    "required": ["target_date"],
    "properties": {
      "target_date": {"type": "string", "format": "date"},
      "service_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner"], "default": "dinner"},
      "context": {
        "type": "object",
        "properties": {
          "weather": {"type": "object"},
          "events": {"type": "array"},
          "occupancy": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  }
}
```
Output: same shape as `PredictResponse` (`predictions.py:54`) with `hotel_id` filled from the token.

**Tool 2: `get_recommendations_with_memory_context`**
```json
{
  "inputSchema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query": {"type": "string", "maxLength": 500},
      "target_date": {"type": "string", "format": "date"},
      "k_memory": {"type": "integer", "default": 5, "maximum": 20}
    }
  }
}
```
Output: `{recommendation: string, confidence: float, memory_hits: [{pattern_id, similarity, summary}], reasoning_summary: string}`.

**Tool 3: `submit_feedback_to_memory`**
```json
{
  "inputSchema": {
    "type": "object",
    "required": ["recommendation_id", "outcome"],
    "properties": {
      "recommendation_id": {"type": "string", "format": "uuid"},
      "outcome": {"type": "string", "enum": ["accepted", "rejected", "modified", "ignored"]},
      "actual_value": {"type": "number"},
      "notes": {"type": "string", "maxLength": 1000}
    }
  }
}
```
Output: `{memory_id: uuid, status: "stored"|"deduplicated", embedding_dim: int}`.

### D9 — Error model: **RFC 7807 Problem Details wrapped in MCP error envelope**

MCP SDK surfaces errors via its native `CallToolResult.isError=true` + text content. We wrap a compact RFC 7807 JSON in that content block:
```json
{"type": "about:blank", "title": "rate_limited", "status": 429,
 "detail": "60 req/min exceeded", "retry_after": 12}
```
Agents get machine-parseable errors; humans get a readable title.

Standard error codes: `rate_limited` (429), `invalid_input` (400), `not_found` (404), `forbidden` (403, cross-tenant attempt), `upstream_unavailable` (503, Prophet not trained / LLM down), `internal_error` (500).

### D10 — Safety rails on `submit_feedback_to_memory`

- `notes` max 1000 chars, stripped of control chars, passed through the same sanitizer as Twilio inbound (`app/api/routes/webhook.py`).
- `recommendation_id` must exist in `agent_action_log` AND belong to the same `hotel_id` — prevents cross-tenant poisoning.
- Embedding is computed on a **sanitized** `notes`, but the raw string is stored verbatim for audit (never re-fed to the LLM without escaping).
- Dedup: if embedding cosine similarity > 0.98 with an existing memory for the same `recommendation_id`, return `status: "deduplicated"` without insert.

### D11 — Library: **Official `modelcontextprotocol` Python SDK (`mcp` package)**

Already a dependency (`apaleo_mcp_adapter.py:26` imports from `mcp`). Use `mcp.server.fastmcp.FastMCP` to define tools via decorators, mount the resulting ASGI app under `/mcp`.

Rejected:
- **Hand-rolled over Starlette**: reinvents spec-level details (initialize handshake, capability negotiation, progress notifications).

### D12 — Dev ergonomics

**Local run** (already a FastAPI app):
```bash
uvicorn app.main:app --reload --port 8000
# MCP endpoint: http://localhost:8000/mcp/v0/
```

**Quick curl smoke test** (initialize + list_tools):
```bash
curl -sN -H "Authorization: Bearer atx_dev_..." \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  http://localhost:8000/mcp/v0/
```

**Claude Desktop config snippet** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "aetherix": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp/v0/",
               "--header", "Authorization: Bearer ${AETHERIX_MCP_TOKEN}"]
    }
  }
}
```

**Integration tests**: `backend/tests/test_mcp_server.py` uses `mcp.client.stdio` against the in-process app (no network), covers the full initialize → list_tools → call_tool loop per tool.

---

## 4. Open questions (deferred)

- **OQ1**: Should `submit_feedback_to_memory` trigger a retraining signal? (v1 — tie to `training_runs` schedule)
- **OQ2**: Per-tool billing meter (Agent SEO revenue model)? (v1 — depends on pricing decision in CLAUDE.md §Décisions ouvertes)
- **OQ3**: Registration on public agent directories (Smithery, MCP.so)? (Post-Phase 0 GTM call)

---

## 5. Implementation checklist (for the Dev agent)

1. **DB migration** — create `mcp_api_tokens` table: `id uuid pk, hotel_id uuid fk, token_hash text unique, scopes text[], expires_at timestamptz, created_at, last_used_at`. Index on `token_hash`.
2. **New module** `backend/app/mcp_server.py`:
   - Instantiate `FastMCP("aetherix", version="0.0.0")`.
   - Register the 3 tools as decorated async functions.
   - Each tool: resolve `hotel_id` from `ctx.request.headers["authorization"]` via `verify_bearer()`.
3. **Auth middleware** `backend/app/mcp_auth.py`: bearer verification, hotel context injection, 401 on invalid/expired token.
4. **Rate limit middleware** `backend/app/mcp_rate_limit.py`: Redis token bucket keyed on `hotel_id + tool_name`.
5. **Tool bodies**:
   - `get_operational_predictions` → thin wrapper on `engine.get_forecast`, maps to `PredictResponse`.
   - `get_recommendations_with_memory_context` → new service `MemoryRecommendationService.build(hotel_id, query, k)`: vector search on `operational_memory` + `fb_patterns`, Claude summarization.
   - `submit_feedback_to_memory` → new service `MemoryFeedbackService.store(hotel_id, rec_id, outcome, notes)`: sanitize, embed, dedup, insert.
6. **Mount** in `app/main.py`: `app.mount("/mcp/v0", mcp_server.app)`. Register trace middleware + log to `agent_action_log`.
7. **Response header** `x-aetherix-mcp-version: 0` on all `/mcp/v0/*` responses.
8. **Tests** (`backend/tests/test_mcp_server.py`):
   - Happy path for each of the 3 tools.
   - 401 on missing/invalid bearer.
   - 403 on cross-tenant `recommendation_id`.
   - 429 on rate limit breach.
   - Deduplication on identical feedback.
9. **Demo artifact**: 60-second Loom script: Claude Desktop → `/aetherix predict covers for tomorrow dinner` → response with reasoning → `submit feedback "accepted, served 87 actual"` → stored memory visible via SELECT.
10. **Docs**: append `docs/mcp/getting-started.md` with the Claude Desktop config snippet and a 3-step quickstart.

---

## 6. Decision record

| # | Decision | Chosen | Alternatives |
|---|----------|--------|--------------|
| D1 | Transport | HTTP Streamable | SSE (deprecated), stdio (local-only) |
| D2 | Hosting | FastAPI sub-app `/mcp` | Sidecar, separate repo |
| D3 | Auth | Opaque bearer token | JWT, mTLS, OAuth2 |
| D4 | Isolation | `hotel_id` bound to token, RLS + Python guard | Client-supplied `hotel_id` (rejected as unsafe) |
| D5 | Versioning | `/mcp/v0/` + header | Tool-name suffix, no versioning |
| D6 | Rate limit | Redis token bucket, 60/min | Nginx, in-memory |
| D7 | Observability | `agent_action_log` + trace header | OTel only |
| D8 | Schemas | JSON Schema, no `hotel_id` input | Accept `hotel_id` (rejected D4) |
| D9 | Errors | RFC 7807 in MCP error envelope | MCP-native codes only |
| D10 | Safety | Sanitize + dedup + cross-tenant check | Trust client |
| D11 | Library | Official `mcp` Python SDK | Hand-rolled Starlette |
| D12 | Dev UX | Mount in uvicorn, `mcp-remote` for Claude Desktop | Separate dev server |

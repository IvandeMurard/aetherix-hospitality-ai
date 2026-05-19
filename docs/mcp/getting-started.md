# Aetherix MCP Server — Getting Started (v0 + v1)

> **Audience**: third-party agents, enterprise agent hubs, partner integrations.
> **Status**: v0 (3 tools, ADR-0001) · v1 adds atomic `recall_memory` (ADR-0004).
> **Specs**: [ADR 0001](../adr/0001-aetherix-mcp-server-v0.md) · [ADR 0004](../adr/0004-orchestrator-separation.md)

---

## Endpoints

Two MCP surfaces are mounted side-by-side:

| Path | Tools advertised | When to use |
|------|------------------|-------------|
| `/mcp/v0/` | 3 tools (predict · composite recommend · feedback) | Existing Claude Desktop / Apaleo Agent Hub consumers — stable |
| `/mcp/v1/` | 4 tools (v0 + atomic `recall_memory`) | Orchestrators / agents that compose recall and predict explicitly |

> **v1 is additive in Phase 3.** The composite `get_recommendations_with_memory_context` is still available on both versions. A future PR (HOS-184 phase 2) will deprecate it on v1 only and add a `Deprecation` header to its v0 response.

---

## What this server exposes

| Tool | v0 | v1 | Purpose |
|------|----|----|---------|
| `get_operational_predictions` | ✓ | ✓ | F&B covers forecast + staffing for a target date |
| `get_recommendations_with_memory_context` | ✓ | ✓ (deprecation planned) | Composite recall + forecast bundle |
| `submit_feedback_to_memory` | ✓ | ✓ | Record manager outcome for a past recommendation |
| `recall_memory` | — | ✓ | **Atomic** semantic recall from operational memory — no forecast bundling |

### When to call `recall_memory` instead of the composite

The composite tool sequences embed → recall → forecast in a fixed pipe with no visibility into intermediate results. The atomic `recall_memory` returns only memory hits + `top_similarity`, letting an orchestrator decide whether to expand the window (e.g. retry with `k_memory=10` when similarity is low) before calling `get_operational_predictions`. This is the building block for the agentic loop introduced by ADR-0004.

Multi-tenant isolation is **enforced server-side**: the `hotel_id` is bound to the bearer token. Tool schemas do not accept `hotel_id` — attempting to pass it is silently ignored.

---

## Wire format

```
POST /mcp/v0/   (or /mcp/v1/)
Content-Type: application/json
Accept: application/json
Authorization: Bearer atx_<env>_<secret>
```

The server speaks the MCP JSON-RPC 2.0 subset: `initialize`, `tools/list`, `tools/call`. The `x-aetherix-mcp-version` response header echoes the version of the endpoint hit (`0` or `1`).

---

## Quickstart — curl

**1. Initialize**

```bash
curl -s http://localhost:8000/mcp/v0/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'
```

Response:
```json
{"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":"2024-11-05",
  "serverInfo":{"name":"aetherix","version":"0.0.0"},
  "capabilities":{"tools":{"listChanged":false}}
}}
```

**2. List tools**

```bash
curl -s http://localhost:8000/mcp/v0/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atx_dev_..." \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**3. Call a tool**

```bash
curl -s http://localhost:8000/mcp/v0/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atx_dev_..." \
  -d '{
    "jsonrpc":"2.0","id":3,"method":"tools/call",
    "params":{
      "name":"get_operational_predictions",
      "arguments":{"target_date":"2026-05-01","service_type":"dinner"}
    }
  }'
```

Response `result.content[0].text` is a JSON string with the forecast payload (same shape as `POST /api/v1/predict`).

---

## Claude Desktop integration

Edit `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "aetherix": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-host/mcp/v0/",
        "--header",
        "Authorization: Bearer ${AETHERIX_MCP_TOKEN}"
      ]
    }
  }
}
```

Set `AETHERIX_MCP_TOKEN` in your shell before launching Claude Desktop. After reload, the three tools appear in the model's tool picker.

---

## Obtaining a token

v0 issues tokens manually (self-service UI deferred to v1). An operator inserts a row into `mcp_api_tokens`:

```sql
INSERT INTO mcp_api_tokens (hotel_id, token_hash, token_prefix, scopes, label)
VALUES (
  'hotel_xyz_uuid',
  encode(sha256('atx_prod_<secret>'::bytea), 'hex'),
  'atx_prod',
  ARRAY['predict','recommend','feedback','recall'],
  'Claude Desktop — Manager Alice'
);
```

The raw token (`atx_prod_<secret>`) is given to the agent caller once; only the hash is stored.

**Scopes**:
- `predict` → allows `get_operational_predictions`
- `recommend` → allows `get_recommendations_with_memory_context`
- `feedback` → allows `submit_feedback_to_memory`
- `recall` → allows `recall_memory` (v1 only)

> **Note (ADR-0004):** `recall` is a distinct scope from `recommend`. Existing tokens scoped to `recommend` do **not** automatically gain access to the new atomic `recall_memory` tool — grants are explicit. Reissue or update the token's `scopes` array to include `recall` before consumers on v1 can use it.

---

## Rate limits

Per-tenant, per-tool, sliding 1-minute window:

| Tool | Limit |
|------|-------|
| `get_operational_predictions` | 60 req/min |
| `get_recommendations_with_memory_context` | 30 req/min |
| `submit_feedback_to_memory` | 20 req/min |
| `recall_memory` | 30 req/min |

On breach, the server returns a JSON-RPC error with `data.status = 429` and `data.title = "rate_limited"`.

---

## Error model

Errors are RFC 7807 Problem Details wrapped inside the MCP JSON-RPC error envelope:

```json
{"jsonrpc":"2.0","id":3,"error":{
  "code":-32403,
  "message":"forbidden",
  "data":{
    "type":"about:blank",
    "title":"forbidden",
    "status":403,
    "detail":"Token missing required scope: feedback"
  }
}}
```

| Title | Status | Cause |
|-------|--------|-------|
| `unauthorized` | 401 | Missing/invalid/expired/revoked bearer token |
| `forbidden` | 403 | Token missing scope for the requested tool |
| `invalid_input` | 400 | Bad argument shape, bad date, bad UUID |
| `not_found` | 404 | Unknown tool name |
| `rate_limited` | 429 | Per-tool rate limit exceeded |
| `upstream_unavailable` | 503 | Prophet model not trained / LLM backend down |
| `internal_error` | 500 | Catch-all — check server logs |

---

## Versioning

- URL path carries the major version: `/mcp/v0/`.
- Response header `x-aetherix-mcp-version: 0` on every response.
- Breaking changes → `/mcp/v1/`. Additive changes (new optional fields, new tools) are allowed within v0.

---

## Known limitations (v0)

- `submit_feedback_to_memory` writes a **placeholder embedding** — semantic retrieval is recency-ordered until P1-3 ships.
- Rate limiting is in-process; Redis token bucket ships in v1.
- No self-service token issuance yet (v1).
- No registration on public MCP directories (post-Phase 0 GTM decision).

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `401 unauthorized` on `tools/list` | Missing/wrong `Authorization` header |
| `403 forbidden` on `tools/call` | Token scopes don't include the tool's required scope |
| `503 upstream_unavailable` on predictions | Prophet not trained — call `POST /api/v1/predictions/train` first |
| Tools appear but calls fail | Check `mcp_api_tokens.expires_at` and `revoked_at` |

---

## Further reading

- [ADR 0001 — MCP Server v0](../adr/0001-aetherix-mcp-server-v0.md)
- [ADR 0004 — Orchestrator separation (v1 atomic tools)](../adr/0004-orchestrator-separation.md)
- [Mesh architecture overview](../mesh-architecture.md)
- `backend/app/mcp_server.py` — tool implementations
- `backend/app/api/routes/mcp.py` — HTTP shim (v0 + v1 router factory)
- `backend/orchestrator/` — proto-orchestrator that consumes these tools

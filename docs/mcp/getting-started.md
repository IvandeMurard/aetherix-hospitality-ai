# Aetherix MCP Server — Getting Started

> **Audience**: third-party agents, enterprise agent hubs, partner integrations.
> **v0**: retired 2026-08-01 (HOS-315). See the migration note below.
> **v1**: 3 atomic tools — `recall_memory` replaces `get_recommendations_with_memory_context`.
> **Spec**: [ADR 0001](../adr/0001-aetherix-mcp-server-v0.md) · [ADR 0004](../adr/0004-orchestrator-separation.md)

---

## What this server exposes

### v1 — current (recommended)

Endpoint: `POST /mcp/v1/`

| Tool | Scope | Purpose |
|------|-------|---------|
| `get_operational_predictions` | `predict` | F&B covers forecast + staffing for a target date |
| `recall_memory` | `memory:read` | Semantic recall from the property's operational memory |
| `submit_feedback_to_memory` | `feedback` | Record manager outcome for a past recommendation |

### v0 — retired on 2026-08-01

`POST /mcp/v0/` no longer exists. It was removed on 2026-08-01 (HOS-315). The
`Deprecation` / `Sunset` response headers planned for the window were never
shipped, so the announcement was documentation-only — noted here rather than
quietly corrected, because a client that was watching for those headers never
saw one. Migration is a one-line change:

- point your client at `/mcp/v1/` (identical JSON-RPC framing);
- replace `get_recommendations_with_memory_context` with `recall_memory`
  (scope `memory:read`), which returns the memory hits directly;
- `get_operational_predictions` and `submit_feedback_to_memory` are unchanged.

Multi-tenant isolation is **enforced server-side**: the `hotel_id` is bound to the bearer token. Tool schemas do not accept `hotel_id` — attempting to pass it is silently ignored.

---

## Endpoint

```
POST /mcp/v1/
Content-Type: application/json
Accept: application/json
Authorization: Bearer atx_<env>_<secret>
```

The server speaks the MCP JSON-RPC 2.0 subset: `initialize`, `tools/list`, `tools/call`.

### Tool schema — recall_memory (v1)

```json
{
  "name": "recall_memory",
  "inputSchema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query":  { "type": "string", "maxLength": 500 },
      "k":      { "type": "integer", "default": 5, "minimum": 1, "maximum": 20 }
    }
  }
}
```

Response shape:
```json
{
  "memory_hits": [
    {
      "pattern_id": "<uuid>",
      "summary": "<reflection text, max 200 chars>",
      "feedback": "followed | rejected | neutral | null",
      "similarity": 0.87,
      "source": "private | fb_pattern | recency_fallback",
      "created_at": "2026-05-01T18:32:00"
    }
  ],
  "source": "private | recency_fallback",
  "count": 5
}
```

---

## Quickstart — curl

**1. Initialize**

```bash
curl -s http://localhost:8000/mcp/v1/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'
```

Response:
```json
{"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":"2024-11-05",
  "serverInfo":{"name":"aetherix","version":"1.0.0"},
  "capabilities":{"tools":{"listChanged":false}}
}}
```

**2. List tools**

```bash
curl -s http://localhost:8000/mcp/v1/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer atx_dev_..." \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**3. Call a tool**

```bash
curl -s http://localhost:8000/mcp/v1/ \
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
        "https://your-host/mcp/v1/",
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
  ARRAY['predict','recommend','feedback'],
  'Claude Desktop — Manager Alice'
);
```

The raw token (`atx_prod_<secret>`) is given to the agent caller once; only the hash is stored.

**Scopes**:
- `predict` → allows `get_operational_predictions`
- `memory:read` → allows `recall_memory` (v1)
- `recommend` → allows `get_recommendations_with_memory_context` (v0, deprecated)
- `feedback` → allows `submit_feedback_to_memory`

---

## Rate limits

Per-tenant, per-tool, sliding 1-minute window:

| Tool | Limit |
|------|-------|
| `get_operational_predictions` | 60 req/min |
| `recall_memory` | 60 req/min |
| `get_recommendations_with_memory_context` | 30 req/min |
| `submit_feedback_to_memory` | 20 req/min |

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

- URL path carries the major version. `/mcp/v1/` is the only live route; `/mcp/v0/` was retired 2026-08-01.
- Response header `x-aetherix-mcp-version: 1` on every response.
- v1 removed `get_recommendations_with_memory_context` and added `recall_memory` (scope `memory:read`).
- The `recommend` scope no longer grants access to any advertised tool; use `memory:read`.
- Migrate by replacing `recommend` scope → `memory:read` and calling `recall_memory` on `/mcp/v1/`.

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
- [ADR 0004 — Orchestrator separation](../adr/0004-orchestrator-separation.md)
- `backend/app/mcp_server.py` — tool implementations
- `backend/app/api/routes/mcp.py` — v0 HTTP shim
- `backend/app/api/routes/mcp_v1.py` — v1 HTTP shim
- `backend/orchestrator/agent.py` — OrchestratorAgent

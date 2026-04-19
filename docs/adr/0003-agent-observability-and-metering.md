# ADR 0003 — Agent Observability & Metering

> **Status**: Accepted · **Date**: 2026-04-18 · **Author**: Architect (Sonnet)
> **Context**: Phase 1 review flagged three gaps — D10 metrics without a feeder, in-process rate limit, and no `agent_action_log` table — that share the same root cause: missing observability infrastructure. This ADR closes all three in one system.
> **Linear**: HOS-73 · **Blocks**: Phase 2 pricing decision (CLAUDE.md open decision) + Agent Receipts conversational layer

---

## 1. Context

Phase 1 review (2026-04-18) identified:

1. **ADR 0002 D10 metrics** (`embedding_latency_ms`, `dedup_hit`, `top_similarity`) specified but never emitted — the `memory_instrumentation_daily` materialized view has no feeder.
2. **ADR 0001 D6 rate limit** uses `_LOCAL_BUCKETS` (in-process dict) — per-worker bypass once we scale past 1 uvicorn worker.
3. **ADR 0001 D7 `agent_action_log`** referenced as "the meter" for pricing but the table doesn't exist — agent calls are lost after request end.
4. **Pricing open decision** (CLAUDE.md) cannot be resolved without per-call metering data.

**Goal**: ship a minimal observability system (event model, write path, storage, retention, rate-limit backend) that makes every agent tool call durable, queryable, and priceable.

**Non-goals (v0)**:
- Real-time streaming dashboards
- OTLP/OpenTelemetry export (deferred to D10 below)
- Billing integration (pricing model still to be chosen — this ADR creates the data substrate)

---

## 2. Decision summary

| # | Decision | Chosen |
|---|----------|--------|
| D1 | Event model | Single `agent_action_log` table, one row per tool call |
| D2 | Write path | Synchronous `INSERT` inside `dispatch_tool`, before `db.commit()` |
| D3 | Storage | Regular PostgreSQL table, monthly partitioning via `created_at`, no TimescaleDB |
| D4 | Retention | 90 days hot (queryable), archive to S3 Parquet after via `pg_dump` + cron |
| D5 | Metering unit | One `agent_action_log` row = one billable event; status `"ok"` only |
| D6 | Rate limit backend | Redis token-bucket key `ratelimit:{hotel_id}:{tool}:{minute_bucket}`; in-process fallback on Redis down (fail-open, metric emitted) |
| D7 | Metrics emitter | `emit_agent_event(event: AgentEvent)` in `dispatch_tool`; memory tools add embedding fields via return dict |
| D8 | MV refresh | `memory_instrumentation_daily` refreshed by APScheduler at 02:00 UTC daily |
| D9 | PII policy | Bearer token, raw query text, manager notes NEVER logged; `query[:80]` truncated for diagnostics |
| D10 | Observability export | Stdout structured JSON now; OTLP adapter extracted later if multi-tenant SaaS |

---

## 3. Decision rationale

### D1 — Event model (`agent_action_log`)

Every inbound tool call that passes auth+scope check gets one row. Fields:

```sql
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
hotel_id         TEXT NOT NULL                         -- from token, not args (ADR 0001 D4)
tool_name        TEXT NOT NULL
scopes           TEXT[]                                -- from token.scopes
status           TEXT NOT NULL                         -- "ok" | "auth_error" | "tool_error" | "rate_limited"
error_code       TEXT                                  -- null on success
latency_ms       INTEGER
embedding_latency_ms INTEGER                           -- null for non-memory tools
dedup_hit        BOOLEAN                               -- null for non-memory tools
top_similarity   REAL                                  -- null for non-memory tools
input_token_est  INTEGER                               -- future: LLM call tokens
output_token_est INTEGER
request_id       TEXT                                  -- X-Request-Id from AgentTrackingMiddleware
```

**Why not a timeseries DB?** Supabase (PostgreSQL + pgvector) is already our infra. <100K events/day for the foreseeable future is trivially PostgreSQL-scale. Adding TimescaleDB creates an operational dependency with no benefit until we're >10M events/day.

**Why monthly partitioning?** `PARTITION BY RANGE (created_at)` gives us cheap per-month `DROP PARTITION` for retention without table bloat. Supabase supports declarative partitioning.

### D2 — Write path

`dispatch_tool` calls `emit_agent_event(event, db)` after the tool body resolves and before `db.commit()`. The event row lands in the same transaction as the tool's DB side effects — either both commit or both roll back. This is the simplest correct behavior:

- **No fire-and-forget**: would lose events on crash and make test assertions non-deterministic.
- **No outbox**: unnecessary for this event volume; CQRS overhead not justified.
- **Exception in `emit_agent_event`** is caught and logged as warning — never propagates to caller (tool calls succeed even if logging fails).

### D3 — Storage

Regular `agent_action_log` table with `PARTITION BY RANGE (created_at)`. Create a new partition monthly via a migration or scheduled job. Initial partitions: 2026-04, 2026-05.

### D4 — Retention

- 90-day hot window: `DROP PARTITION` on partitions older than 90 days (run in cron, or manually pre-pilot).
- Archive: `COPY (SELECT * FROM agent_action_log_2026_04) TO 's3://aetherix-metrics/2026-04.parquet'` via `pg_dump` or `psql` + `aws s3 cp`. No streaming, no CDK.
- Justification: 90 days covers one quarter of pricing negotiation cycles; older data is cold for billing, warm for trend analysis.

### D5 — Metering unit

**One billable event = one `agent_action_log` row with `status = 'ok'`.**

This means:
- Auth errors, rate-limit rejections, tool exceptions are recorded but not billed.
- Dedup hits in `submit_feedback_to_memory` still count as `"ok"` (the call was served correctly).
- Pricing model tiers (per-hotel flat / per-call / hybrid) are applied at reporting time over this table — the table is model-agnostic.

### D6 — Rate limit backend

Replace `_LOCAL_BUCKETS` with Redis token bucket:

```
Key:   ratelimit:{hotel_id}:{tool_name}:{minute_bucket}
Value: remaining_tokens (INCRBY + TTL = 60s)
Algo:  fixed-window (simpler than sliding, acceptable for 60/30/20 req/min limits)
```

**Fail-open on Redis down**: if Redis is unreachable, rate limit check passes and a `rate_limit_fallback=true` field is set on the event row. This is logged and monitored, but the request is not blocked. Rationale: a brief Redis outage should not take down MCP tool availability for live hotels.

**Migration**: `mcp_core.py` `check_rate_limit()` becomes a thin wrapper; `RedisRateLimiter` is a new class in `app/services/rate_limit.py`. The `_LOCAL_BUCKETS` dict is retained as the fallback implementation (no change to contract, just runtime switch).

### D7 — Metrics emitter

```python
# app/services/agent_event.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AgentEvent:
    hotel_id: str
    tool_name: str
    scopes: list[str]
    status: str                          # "ok" | "auth_error" | "tool_error" | "rate_limited"
    request_id: str = ""
    latency_ms: Optional[int] = None
    error_code: Optional[str] = None
    embedding_latency_ms: Optional[int] = None
    dedup_hit: Optional[bool] = None
    top_similarity: Optional[float] = None

async def emit_agent_event(event: AgentEvent, db: AsyncSession) -> None:
    """Write one row to agent_action_log. Never raises (errors are warnings)."""
    ...
```

`dispatch_tool` in `mcp_server.py` constructs the event, calls tools, then calls `emit_agent_event`. Memory tools augment the event dict via their return payload (`"_meta": {"embedding_latency_ms": ..., "dedup_hit": ..., "top_similarity": ...}`).

### D8 — MV refresh

`memory_instrumentation_daily` is refreshed by APScheduler at 02:00 UTC daily:

```python
# In app/workers/memory_metrics.py
async def refresh_memory_instrumentation_mv():
    async with engine.begin() as conn:
        await conn.execute(text(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY memory_instrumentation_daily"
        ))
```

Registered in `main.py` `lifespan` alongside existing anomaly and dispatch jobs.

### D9 — PII policy

**Never logged:**
- Raw `authorization` header value (bearer token)
- Full query text from `get_recommendations_with_memory_context` arguments
- Raw `notes` from `submit_feedback_to_memory` arguments
- Manager names, email addresses, property names (never in tool payloads anyway)

**Allowed (for diagnostics):**
- `hotel_id` (internal identifier, non-personally-identifying)
- `tool_name`, `status`, `error_code`
- `query[:80]` may appear in the log line emitted by `AgentTrackingMiddleware` — bounded by sanitizer added in P1-6

### D10 — Observability export

**Phase 2**: structured JSON to stdout via Python `logging`. Each `emit_agent_event` also calls `logger.info("agent_event %s", json.dumps(asdict(event)))`. Supabase real-time can subscribe to `agent_action_log` inserts for a live dashboard.

**Phase 3+**: if we move to multi-tenant SaaS with multiple regions, extract an OTLP adapter (`opentelemetry-sdk`). The `AgentEvent` dataclass maps 1:1 to an OTEL span. No migration of the write path needed — just add a second sink.

---

## 4. Implementation backlog

| Item | Linear | Effort | Sprint |
|------|--------|--------|--------|
| `agent_action_log` migration + ORM + partition setup | HOS-73a | S | D |
| `AgentEvent` dataclass + `emit_agent_event` + wire in `dispatch_tool` | HOS-73b | S | D |
| `RedisRateLimiter` + fail-open fallback + replace `_LOCAL_BUCKETS` in `check_rate_limit` | HOS-73c | M | D |
| APScheduler job for `memory_instrumentation_daily` REFRESH | HOS-73d | XS | D |
| Tier-1 tests for `AgentEvent` + `emit_agent_event` (mock DB) | HOS-73e | S | D |
| Pricing model decision (read ADR 0003 D5 + first month of metering data) | HOS-74 | — | E (after first hotel pilot) |

---

## 5. Resolution of CLAUDE.md open decision: Pricing model

This ADR does not pick the pricing tier (per-hotel flat / per-call / hybrid). It installs the metering substrate that makes the decision empirical rather than theoretical:

- **Per-call pricing** can be read directly from `COUNT(*) WHERE status='ok' GROUP BY hotel_id, date_trunc('month', created_at)`.
- **Flat subscription** uses the same query to verify whether a hotel is above/below their included volume.
- **Hybrid** uses both.

Recommend revisiting the pricing decision after **90 days of production metering data** from the first hotel pilot. Update CLAUDE.md §Décisions ouvertes at that point.

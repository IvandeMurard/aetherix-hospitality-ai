# Latency SLO — Aetherix

> EVAL-5 (HOS-209) · ADR-0007 §5.e. The latency "contract": per-endpoint p95
> targets, how they're measured, and how breaches are caught. Sibling of
> `eval/FAILURE_THRESHOLDS.md` and `eval/HEARTBEAT_THRESHOLDS.md`.

---

## SLO targets (AC1)

| Endpoint | p50 | **p95 (SLO)** | p99 |
|---|---|---|---|
| `GET /api/v1/predictions/today` | < 3 s | **< 8 s** | < 12 s |
| `GET /api/v1/recommendations/today` | < 5 s | **< 12 s** | < 18 s |
| Receipt generation (background) | < 6 s | **< 15 s** | < 25 s |
| Inbound parser (Haiku) | < 0.8 s | **< 2 s** | < 4 s |
| MCP tool calls `/mcp/v0/*` | < 2 s | **< 5 s** | < 8 s |

p95 is the SLO line — the value the gate and the runtime alert enforce. p50/p99
are tracked for shape (a healthy p50 with a blown p99 = tail latency to chase).

> **Threshold changes are an explicit decision**: PR + a CLAUDE.md trace, like the
> failure/heartbeat thresholds. The machine-readable copy lives in
> `eval/baselines/latency_baseline.json` (the eval + worker source of truth).

---

## Instrumentation (AC2)

Per-call latency is persisted on `agent_action_log.latency_ms` (ADR-0003) for MCP
tool calls and LLM/provider calls — that's what the MV and the runtime alert read.

**Gap (audit):** the REST endpoints above are currently only *logged* by
`AgentTrackingMiddleware` (`latency_ms=…`), not persisted. So the daily MV covers
the tool-call surface; the per-endpoint SLO numbers in the table are enforced by
the live `eval_latency` benchmark (below), which times the endpoints directly.
Persisting REST endpoint latency into `agent_action_log` is a tracked follow-up.

---

## Dashboard MV (AC3)

`latency_slo_daily` (Supabase MV, migration `20260619020000_latency_slo_daily.sql`)
— per `tool_name` × day: p50/p95/p99 (via `percentile_cont`) + sample count over
`agent_action_log.latency_ms`. Refreshed nightly by
`backend/app/workers/latency_slo_worker.py` (APScheduler, ADR-0003 D8 pattern).

---

## Runtime alerting (AC5)

The nightly worker reads the MV and raises a WhatsApp ops anomaly
(`ops_dispatcher.dispatch_anomaly`) for any endpoint whose p95 breaches its SLO.

> The brief's "> 5 consecutive minutes" debounce needs minute-bucketed latency;
> the daily MV gives a daily p95, so the worker alerts on a daily breach today.
> Minute-window consecutive-breach detection is a follow-up once REST latency is
> persisted at finer granularity.

---

## Eval + CI gate (AC4 / AC7)

`scripts/eval/eval_latency.py` runs N warmup + M timed calls per endpoint with
seed-fixed jitter (seed=42, warmup=3) and computes p50/p95/p99, then fails if any
p95 exceeds its SLO.

```bash
# Against staging (httpx):
LATENCY_TARGET_BASE_URL=https://aetherix-staging.fly.dev \
  python scripts/eval/eval_latency.py --calls 20 --strict
```

**CI policy:** the SLO gate runs against **staging** (or a manual/scheduled run),
**not** per-PR on a shared CI runner — cold, noisy GitHub runners make 8–12 s p95
thresholds flaky (false reds erode the gate, ADR §9 R2/R4 reasoning). A PR that
touches the listed endpoints should trigger a staging `eval_latency` run before
release; wiring that trigger is the AC7 follow-up. The percentile + verdict core
is unit-tested deterministically (`tests/eval/test_eval_latency.py`).

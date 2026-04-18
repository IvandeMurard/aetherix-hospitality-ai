# Phase 0 Retro — What shipped, what we learned

> **Status**: Final — 18 April 2026
> **Owner**: SM (Bob)
> **Scope**: Phase 0 amended DoD (per CLAUDE.md decision #14) — Sprint A (backtest validation) + Sprint B (ROI simulator + MCP Server v0). Branch: `claude/aetherix-market-analysis-5JiJ1`.

---

## 1. What shipped

| Story | Deliverable | Commit |
|-------|-------------|--------|
| P0-1 | Backtest harness (8-fold rolling CV on synthetic Paris 4*) | — |
| P0-2 | Backtest PASS — **MAPE 7.8% J+1**, directional accuracy 90.9% | `docs/metrics/backtest_2026-04-17.json` |
| P0-3 | Public ROI simulator `POST /api/v1/roi/simulate` — stateless, no auth, rate-limited at the edge | 6 unit tests pass |
| P1-2 | MCP Server v0 — `/mcp/v0/` JSON-RPC, 3 tools, opaque bearer, multi-tenant isolation | ADR 0001 (12 decisions) |
| P1-3 | Memory instrumentation — `MemoryRecallService`, real Mistral embeddings, two-pass dedup | ADR 0002 (11 decisions) |
| P1-4 | Forecast benchmark — Prophet vs 3 naive baselines + memory ablation | `docs/metrics/benchmark_2026-04-19.json` |
| P1-5 | Agent SEO — `/.well-known/agent.json` manifest + `AgentTrackingMiddleware` | `backend/app/middleware/agent_tracking.py` |
| P1-6 | Hardening — PII truncation, cold-start fix, D4 regression test | Post-review fixes |

**Gate result:** ✅ Phase 0 DoD met. MAPE 7.8% < 22% internal gate → MCP Server ship authorised.

---

## 2. What went well

- **Thin leaf module pattern** (`app/mcp_core.py`, no DB imports) gave us Tier-1 tests that run regardless of environment. 60/65 tests are Tier-1 today, which is what keeps the green-on-every-commit loop fast.
- **ADR-first discipline.** Every controversial choice (bearer auth vs OAuth, inline embedding vs outbox, cold-start fallback scope) was named and argued in ADR 0001/0002 before code landed. Review agents could check implementation against the document.
- **Model allocation rule held.** Opus only for architectural decisions (ADR authorship + validation). Sonnet for implementation + QA. Haiku not used. Token cost stayed bounded; no runaway parallel Opus sessions.
- **Parallel Architect + QA review** caught 3 architectural gaps and 3 security/test-debt items in ~50s of wall clock — cheaper than letting them surface in Phase 2.

## 3. What we learned (reusable facts)

- **Synthetic data fools naive baselines.** `naive_last_weekday` beats Prophet (3.6% vs 8.2% MAPE) on our 365-row synthetic series because there's no weather/events noise to separate the models. Phase 1's benchmark gate is now expected-PARTIAL on synthetic data; real-hotel backtest is the first time we'll see Prophet's regressor advantage.
- **Two-pass dedup (cheap → expensive) saves Mistral API calls.** Tuple-LIKE first, cosine only on miss. Confirmed in ADR 0002 D7; load-test this once we're >100 feedback writes/day.
- **Pending-embedding flag is critical.** The `embedding=NULL, embedding_pending=TRUE` pattern (ADR 0002 D9) means Mistral outages don't lose feedback signal — a backfill worker picks up later. Low-lift to build, high resilience ROI.
- **`hotel_id` from token, never from args** is a single-line policy (dispatcher filter) but needs explicit regression test. Added in Sprint D hardening.

## 4. What hurt

- **Stream idle timeouts** on large agent outputs. Mitigation: step-by-step commits instead of single "ship the sprint" mega-calls. Cost: ~3 session interruptions, 0 lost work.
- **Architect-as-Plan-agent can't write files.** First ADR 0002 draft came back as a task notification body only. Fix for Sprint D: spawn ADR-authoring agents as general-purpose with explicit single-file write scope.
- **Migration/ORM drift.** QA caught that `OperationalMemory.content` in ORM didn't match `reflection` in SQL migration; embedding was 1536-d in ORM vs 1024-d in migration. Root cause: ORM model was never regenerated after migration was written. Action: add a cheap Tier-1 test that asserts column names match between the latest migration and the ORM class (deferred to Sprint D backlog).
- **D10 metrics spec'd but not implemented.** `memory_instrumentation_daily` MV created without a feeder. Caught by Architect review; absorbed into ADR 0003 scope.

## 5. Decisions made / unblocked

- **CLAUDE.md #14 confirmed:** MCP Server ship is the right gate. Without it, the demo reads as "another forecasting dashboard" — with it, we clear the "headless-for-agents" bar Benioff/Levie set.
- **Pricing model (CLAUDE.md open decision):** explicitly punted to ADR 0003. Cannot be resolved without per-call metering data, which is what ADR 0003 installs.
- **Apaleo MCP direct:** unchanged from 31/03 resolution — bearer + `streamablehttp_client` + `APALEO_MCP_SERVER_URL` continue to work.

## 6. Open risks going into Phase 2

| Risk | Severity | Mitigation |
|------|---------:|------------|
| In-process rate limit (`_LOCAL_BUCKETS`) bypasses per-worker once we run >1 uvicorn | Medium | ADR 0003 D6 → Redis key scheme before multi-worker deploy |
| `agent_action_log` table missing — agent calls lost post-request | Medium | ADR 0003 D1/D2 → first P2 sprint |
| Prophet benchmark only validated on synthetic data | High | First real-hotel backtest blocks pre-pilot gate (unchanged) |
| `X-Agent-Id` header value was logged verbatim until P1-6 | Low (fixed) | Sanitizer added + regression test |

## 7. Next sprint prep (Sprint D / Phase 2 kickoff)

1. ADR 0003 — Agent observability & metering *(in flight — Opus architect running)*
2. Wire D10 metrics feeder once ADR 0003 finalizes the event model
3. Redis rate-limit adapter + fallback (fail-open on Redis down)
4. `agent_action_log` ORM + migration + dispatcher write path
5. Phase 2 kickoff: Agent "Receipts" conversational layer — can only be scoped after metering is in place (because the first Receipts experiment we want is "show me what the agent did for this hotel today", which is literally a read over `agent_action_log`)

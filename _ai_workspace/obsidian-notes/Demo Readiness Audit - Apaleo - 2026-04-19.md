# Demo Readiness Audit — Apaleo Loom Demo

> **Date:** 2026-04-19 (v1) · 2026-04-23 (v2 — MVP split clarified)
> **Context:** Pre-recording audit against `docs/context/demo-apaleo.md`
> **Trigger:** Budget constraint — user at 21% of 5-hour window, 90% of weekly window. Need to identify the actual critical gap before spending remaining credits.
> **Conclusion v1:** Infrastructure is shipped. The only unverified risk is the end-to-end dry run.
> **Conclusion v2:** A parallel `aetherix-mvp` repo exists but is a template-based toy. Demo must run from this repo (`aetherix-hospitality-ai`). No merge needed.

---

## Update 2026-04-23 — The "other repo" question resolved

After a session split onto a new machine, a second repo appeared:
`C:\Users\ivand\OneDrive\Documents\aetherix-mvp\fastapi_backend`.

**Investigation output:**
```
origin    https://github.com/IvandeMurard/aetherix-mvp.git
upstream  https://github.com/vintasoftware/nextjs-fastapi-template.git
git log:  2 commits of user work on top of the template
CLAUDE.md:   absent
docs/context: absent
```

**Finding.** The MVP repo is a Next.js/FastAPI **starter template** with a thin Claude-built demo harness on top. It contains **zero** Phase 0/1 code (no MCP Server v0, no ADR 0003 observability, no memory embeddings, no Receipts). The "dry-run test plan" built there uses deterministic synthetic mocks (*"no extra ML deps needed"*) — it would produce a Loom that demonstrates animations, not actual agentic capability.

**Decision.**
- ❌ Do not merge MVP → `aetherix-hospitality-ai` (nothing of substance to absorb)
- ❌ Do not create a third reconciled repo (adds load, solves nothing)
- ✅ **Archive or delete `aetherix-mvp`** to remove confusion
- ✅ **Demo from `aetherix-hospitality-ai`** where the real Phase 0/1 work lives
- ✅ Run the real dry-run here, not the fake one there

The trap. A prior session, rather than installing the real backend deps + .env + Apaleo sandbox creds in `aetherix-hospitality-ai`, built a cheaper mock harness on a clean template. That passes surface inspection but fails on the "headless callable Agentic/MCP vision" criterion Apaleo will evaluate.

---

---

## TL;DR

Every pipeline brick named in the demo PRD exists in the repo. The Prophet training orchestrator gap flagged in [[CLAUDE]] Decision #13 is **closed**, not open. Remaining risk is integration-level: nobody has fired the full chain with three panels open.

**Recommendation:** Spend remaining credits on a three-step dry run. Do not pre-fix imaginary gaps.

---

## Component-level verification

| Component | Status | Evidence |
|---|---|---|
| `GET /pms/mcp/probe` | ✅ Wired | `backend/app/api/routes/pms.py:39` |
| `POST /pms/sync?use_mcp=true` | ✅ Wired | `backend/app/api/routes/pms.py:132` |
| **Prophet training orchestrator** | ✅ **CLOSED** | `backend/app/api/routes/predictions.py:205` — `POST /api/v1/predictions/train`, orchestrates ApaleoMCPAdapter → DataTransformer → PredictionEngine, writes `training_runs` audit row with in-sample MAPE |
| `demo_emit()` pipeline hooks | ✅ Wired in 7 services | prediction_engine, rag_service, reasoning_service, whatsapp_service, event_ingestion, pms_sync, staffing_service |
| `GET /demo/stream` SSE | ✅ Wired, DEMO_MODE-gated | `backend/app/api/routes/demo.py` — returns 503 when DEMO_MODE=false |
| `scripts/demo_board.html` | ✅ Exists | SVG diagram + EventSource listener |
| ApaleoMCPClient | ✅ Exists | `backend/app/integrations/apaleo_mcp_client.py` |
| ApaleoMCPAdapter | ✅ Exists | `backend/app/services/apaleo_mcp_adapter.py` |
| DataTransformer | ✅ Exists | `backend/app/services/data_transformer.py` |
| PredictionEngine (Prophet) | ✅ Exists | `backend/app/services/prediction_engine.py` |
| ReasoningService (Claude) | ✅ Exists | `backend/app/services/reasoning_service.py` |
| RAGService (pgvector) | ✅ Exists | `backend/app/services/rag_service.py` |
| WhatsAppService + webhook | ✅ Exists | `backend/app/services/whatsapp_service.py`, `backend/app/api/routes/webhook.py` |

---

## Status of previously flagged concerns

### [[CLAUDE]] Decision #13 — Prophet training orchestrator "gap"

**Previously:** "briques existent, orchestrateur manquant. Débloquer via `POST /api/v1/predictions/train` ou worker de démarrage."

**Now:** Closed. The endpoint is live at `predictions.py:205`, with:
- `data_source=synthetic` path reads `demo_data/prophet_training.json`
- Audit trail via `training_runs` table
- In-sample MAPE computation
- Minimum 60-day guard
- Training quality reported in response

No further work needed for the demo cycle.

### Phase 2 Receipts (P2-1, P2-2)

**Orthogonal to the demo.** Receipts is the daily post-cycle digest to the manager. The 90-second Loom demo focuses on the J-1 14:00 forecast cycle, not the evening Receipt. P2-3→P2-7 can and should be deferred.

---

## What is NOT verified

End-to-end integration. Individual bricks exist, but the full chain has never been fired with:
1. Real Apaleo sandbox credentials
2. DEMO_MODE=true
3. demo_board.html open in browser
4. WhatsApp contact configured
5. ngrok tunnel active for inbound webhook

---

## Pre-recording checklist (from `docs/context/demo-apaleo.md §5.5`)

### Environment
- [ ] `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` set in `.env`
- [ ] `DEMO_MODE=true` set in `.env`
- [ ] `GET /pms/mcp/probe` returns `{"status": "ok"}` ← **fires real Apaleo OAuth2**
- [ ] ngrok tunnel active for Twilio inbound webhook
- [ ] `demo_board.html` SSE tested end-to-end — all nodes light up in sequence

### Pipeline
- [ ] `logger.debug` line added to `ReasoningService._build_prompt()` (for Claude chain-of-thought visibility)
- [ ] Apaleo sandbox data loaded or realistic mock: occupancy 81%, 31 reservations, PSG-Bayern event
- [ ] 3 CL patterns seeded in `fb_patterns` (pgvector), similarity > 0.78

### Recording
- [ ] Terminal font ≥ 16pt, dark background
- [ ] WhatsApp contact "Sophie — F&B Kleber"
- [ ] Loom: 1920×1080, HD quality
- [ ] Voice-over rehearsed, target ≤90 seconds
- [ ] Full dry run completed

---

## Recommended credit spend (prioritised)

1. **Three-command dry run** (~5%):
   - `POST /api/v1/predictions/train` with `data_source=synthetic` → confirm MAPE stored
   - `GET /pms/mcp/probe` → confirm 200 with sandbox creds
   - Open `/demo/stream`, trigger daily cycle, watch nodes light up
2. If any step fails → that is the actual blocker. Fix in place.
3. If all three pass → seed pgvector CL patterns, rehearse voice-over, record.

**Do not** spend remaining budget on Phase 2 Receipts stories P2-3→P2-7. They are demo-orthogonal.

---

## Related files

- `docs/context/demo-apaleo.md` — full demo PRD (source of truth)
- `docs/planning/phase-2-agent-receipts.md` — Receipts scope (deferred for demo)
- [[CLAUDE]] — root project instructions, Decision #13

---

## Cleanup status (2026-04-23)

**Local branches** — cleaned:
- Deleted merged: `claude/p2-1-receipts-service`, `claude/phase-2-kickoff-docs`
- Kept: `claude/aetherix-market-analysis-5JiJ1` (current), `claude/p2-2-memory-hits-join` (PR #76 open)

**Remote branches** — delete attempted via `git push origin --delete`, blocked with `fatal: the remote end hung up unexpectedly`. The local git proxy lacks delete permission. **Requires UI action.**

Branches to delete manually on GitHub:
- `claude/hotel-context-layer-9rLVJ`
- `claude/implement-aetherix-orchestrator-z4kim`
- `claude/implement-hos-106-bGrXC`
- `claude/implement-mcp-server-90Db1`
- `claude/review-feedback-epic-c4puU`
- `claude/setup-aetherix-pm-agent-q3D4x`

Link: https://github.com/IvandeMurard/aetherix-hospitality-ai/branches

**PR #23 ("Api client")** — NOT closed automatically. On inspection, it contains 20 files / 1261 additions including Dockerfile for HuggingFace Spaces deployment + old README rewrite. Base SHA is 1 month stale (`044841b7`). Most content is likely superseded but non-trivial. **User decision required** — close as stale or cherry-pick anything relevant first.

**PR #76 ("P2-2 memory_hits")** — Open, 13/13 tests passing, no peer review. Merge via UI when ready.

---

## Sync instructions

Copy this file to your Obsidian vault at:
`C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality\AI Reports\Intelligence\`

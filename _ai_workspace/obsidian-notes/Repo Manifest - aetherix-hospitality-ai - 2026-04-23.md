# Repo Manifest — `aetherix-hospitality-ai`

> **Date:** 2026-04-23
> **Purpose:** Single source of truth for the merge-direction decision. Compare this manifest to an equivalent dump from `aetherix-mvp/fastapi_backend` to decide what (if anything) needs to be absorbed.

---

## 1. Repo identity

- **Remote:** `https://github.com/IvandeMurard/aetherix-hospitality-ai`
- **Primary branch:** `main` (unprotected)
- **Last commit on main:** `fded34d` — `veille: rapport final 2026-03-30` (2026-04-22, auto-published)
- **Last product commit on main:** `e729650` — P2-1 ReceiptsService skeleton (PR #75)

---

## 2. Phase + decisions snapshot

| Phase | Status | Evidence |
|---|---|---|
| Phase 0 | ✅ Done (18/04/2026) | Backtest MAPE 7.8% J+1, ROI simulator, MCP Server v0 (HOS-71) |
| Phase 1 | ✅ Done (merged via PR #73, 19/04/2026) | MCP Server v0, ADR 0003 observability, rate limiter, memory embeddings |
| Phase 2 | 🟡 In progress | P2-1 merged (PR #75); P2-2 open (PR #76); P2-3 → P2-7 not started |
| Phase 3 | Planned | Multi-hotel, Mews, real-pilot trust-KPI |

**Decisions locked (CLAUDE.md §Décisions architecturales):** 15 entries, #1–#15 all binding.

**Decision #15 — Phase 2 Receipts scope (most recent):**
- OQ1 Channel: WhatsApp primary + email opt-in (SendGrid)
- OQ2 Inbound LLM: Haiku, auto-`modified` if confidence <0.6
- OQ3 Web auth: MCP bearer + new `receipts:read` scope
- OQ4 Tone: evidence-led bullets, quantified comparative, confidence, proactive follow-up
- OQ5 Gate: two-track split (Track A Sandbox = blocks Phase 2 ; Track B trust-KPI = Phase 3 entry)

---

## 3. Demo-critical files

| File | Size | Role |
|---|---|---|
| `backend/app/api/routes/pms.py` | 6281 B | `GET /pms/mcp/probe` (live OAuth2) + `POST /pms/sync?use_mcp=true` |
| `backend/app/api/routes/predictions.py` | 14478 B | `POST /api/v1/predictions/train` with `training_runs` audit |
| `backend/app/api/routes/demo.py` | 2663 B | `GET /demo/stream` SSE, DEMO_MODE-gated |
| `backend/app/core/demo_events.py` | 1956 B | `demo_emit()` fan-out |
| `backend/app/core/config.py` | 2695 B | DEMO_MODE config |
| `scripts/demo_board.html` | 10160 B | SVG pipeline board + EventSource listener |
| `demo_data/prophet_training.json` | 43622 B | 365-day synthetic training dataset |

---

## 4. Backend service surface

**76 Python files under `backend/app/`.** Key areas:

- `providers/` — LLM + Embedding abstraction (Claude, Gemini, Mistral, fallback)
- `services/` — 31 services (aetherix_engine, receipts, rate_limit, agent_event, pms_sync, prediction_engine, reasoning_service, whatsapp_service, etc.)
- `integrations/` — apaleo_mcp_client, twilio, sendgrid, linear, obsidian
- `workers/` — anomaly_scan, dispatch_worker, event_sync, memory_metrics, weather_sync
- `api/routes/` — 17 route files (auth, dashboard, mcp, pms, predictions, webhooks, etc.)

---

## 5. Pull requests — current state

### Open (requires action)
| PR | Title | Status |
|---|---|---|
| **#76** | P2-2 memory_hits enrichment | 13/13 tests pass, **not peer-reviewed**, awaiting merge |
| #23 | "Api client" | Open since 2026-03-23 — likely stale, consider closing |

### Merged this week (Phase 1 close → Phase 2 kickoff)
| PR | Merged | Title |
|---|---|---|
| #75 | 2026-04-19 | P2-1 ReceiptsService skeleton |
| #74 | 2026-04-19 | Phase 2 docs — OQ1–5 locked |
| #73 | 2026-04-19 | Phase 1 complete (MCP Server v0 + ADR 0003 + Sprint D) |
| #72 | 2026-04-17 | `backend/.env.example` audit |
| #71 | 2026-04-17 | Forecasting risk test coverage (HOS-133) |
| #70 | 2026-04-17 | WhatsApp hardening tests (HOS-132) |
| #69 | 2026-04-17 | Apaleo data integrity (HOS-131) |
| #68 | 2026-04-16 | Agent Constitution + demo observability |

---

## 6. Remote branches

| Branch | Status | Action |
|---|---|---|
| `main` | Active | Keep |
| `claude/aetherix-market-analysis-5JiJ1` | Current, PR #73 merged | Keep until audit doc merged |
| `claude/p2-2-memory-hits-join` | PR #76 open | Keep until PR merged |
| `api-client` | PR #23 open, 1 month stale | Close PR, delete branch |
| `claude/hotel-context-layer-9rLVJ` | No active PR | Candidate for deletion |
| `claude/implement-aetherix-orchestrator-z4kim` | No active PR | Candidate for deletion |
| `claude/implement-hos-106-bGrXC` | No active PR | Candidate for deletion |
| `claude/implement-mcp-server-90Db1` | MCP shipped via different branch | Candidate for deletion |
| `claude/review-feedback-epic-c4puU` | No active PR | Candidate for deletion |
| `claude/setup-aetherix-pm-agent-q3D4x` | PR #68 merged | Safe to delete |

**Cleanup rule of thumb:** `git branch -d <branch>` (safe — refuses if not merged). Escalate to `-D` only after verifying the PR was merged.

---

## 7. Local branches (this machine)

```
* claude/aetherix-market-analysis-5JiJ1   ← current
  claude/p2-1-receipts-service            ← PR #75 merged, safe to delete locally
  claude/p2-2-memory-hits-join            ← PR #76 open
  claude/phase-2-kickoff-docs             ← PR #74 merged, safe to delete locally
  main
```

---

## 8. What to compare on the MVP side

Run this on `aetherix-mvp/fastapi_backend` to produce a matching manifest:

```bash
# PowerShell (Windows)
cd C:\Users\ivand\OneDrive\Documents\aetherix-mvp\fastapi_backend

# 1. Git identity
git remote -v
git log --oneline -20
git branch -a

# 2. File inventory
Get-ChildItem -Recurse -Filter *.py app | Select-Object FullName
Get-ChildItem -Recurse -Filter *.md docs 2>$null

# 3. Demo-critical file diff
Compare-Object `
  (Get-Content app/api/routes/pms.py) `
  (Get-Content <aetherix-hospitality-ai>/backend/app/api/routes/pms.py)

# 4. CLAUDE.md presence + version
if (Test-Path CLAUDE.md) { (Get-Item CLAUDE.md).LastWriteTime; wc -l CLAUDE.md }
```

**What to look for in the diff:**
- Does MVP have a **different** `pms.py` / `predictions.py` / `demo.py` implementation? → reconcile
- Does MVP have files **not present** here (e.g., demo-only harness)? → port over
- Does MVP have a CLAUDE.md at all? → if yes, is it divergent? If no, MVP is likely a fork-point snapshot

**Expected outcome:** MVP is probably a lighter snapshot built for demo speed. The reconciliation is a one-way merge MVP → `aetherix-hospitality-ai`, preserving this repo as the source of truth.

---

## 9. Next steps (recommended order)

1. **Run MVP manifest script above** → paste output
2. **Diff the two manifests** → identify delta (likely: demo-mode short-circuits in pms.py/demo.py)
3. **Record Loom demo** from whichever repo is dry-run-green
4. **Port MVP demo-mode helpers** into `aetherix-hospitality-ai` as a dedicated PR
5. **Cleanup branches** per the table in §6
6. **Linear audit** — verify acceptance criteria on HOS-71, HOS-73, HOS-74/75/76 are checked; QA-reviewed where applicable

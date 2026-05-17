# Phase 3 — Pilot Validation + Portfolio Reinforcement

> **Status**: Spec v1 — 17 May 2026
> **Owner**: PM (Ivan) · SM (Bob)
> **Depends on**: Phase 2 shipped (Receipts P2-1→P2-7, Track A gate passed)
> **Closes**: Track B gate from Phase 2 spec §5 (trust-KPI on real pilot)

---

## 1. Strategic context

Phase 2 closed the technical loop (Receipts daily + feedback + weekly digest). What it did **not** prove is whether the agent earns trust on a real hotel manager.

Phase 3 has two parallel tracks:

- **Track A — Pilot Validation** : land 1 design partner, measure trust-KPI lift, unblock pricing decision, submit Apaleo Agent Hub listing.
- **Track B — Portfolio Reinforcement** : add depth (Hive Memory algorithm) and breadth (Paris Open Data MCP) intentionally over-engineered so the public surface of the project signals senior backend / AI engineer skills (MCP protocol, RAG, ETL, data analytics).

Both tracks ship code that improves Aetherix. Track B is *aligned* with the product roadmap — it isn't make-work for portfolio. Tacet MCP wrapping runs **outside** this Linear team (different repo) — tracked at the bottom of this doc.

---

## 2. Goals & success criteria

### Track A — Business gate

A1. **1 design partner onboarded** on real Apaleo property (read-only PMS, daily Receipt delivery, ≥4 weeks live).
A2. **Trust-KPI measured** with directional lift on `recommendation_acceptance_rate` (Receipts cohort vs ablated cohort).
A3. **Pricing model decided** — at least 1 tier proposal backed by ≥90d of `agent_action_log` on the pilot hotel.
A4. **Apaleo Agent Hub application submitted** with passing review checklist (security + integration + value prop).

### Track B — Portfolio gate

B1. **Hive Memory v1 shipped** : algorithm doc + MCP tool exposed + Hive surface in `/receipts` web view.
B2. **Paris Open Data MCP node shipped** : public-facing repo (`aetherix-events-mcp` or sub-package) + 1 tool callable from any MCP client + integration with Aetherix forecast pipeline.
B3. **1 public technical write-up** : Medium / Notion article on Hive Memory algorithm, linked from Aetherix `README.md`.

---

## 3. Story breakdown

### Track A — Pilot Validation

| Story | Title | Effort |
|-------|-------|--------|
| P3-1 (Story 10.1) | Design partner recruitment kit : 1-pager value prop + onboarding script + cred-mgmt SOP | 2 |
| P3-2 (Story 10.2) | Real-pilot deploy : 1 hôtel Apaleo prod, RLS verify, runbook execution, smoke E2E live | 5 |
| P3-3 (Story 10.3) | Trust-KPI instrumentation : `recommendation_acceptance_rate` daily aggregation + alert threshold | 3 |
| P3-4 (Story 10.4) | US-7 ablation experiment : cohort A (Receipts on) vs B (Receipts off), 4-week run, statistical readout | 8 |
| P3-5 (Story 10.5) | Pricing model decision doc — 1 tier proposal backed by ≥90d agent_action_log | 2 |
| P3-6 (Story 10.6) | Apaleo Agent Hub listing submission : packaging + security checklist + value prop deck | 5 |

### Track B — Portfolio Reinforcement

| Story | Title | Effort |
|-------|-------|--------|
| P3-7 (Story 10.7) | **Hive Memory algorithm v1** — clustering on cross-hotel `operational_memory` embeddings (Mistral 1024d) + shapelet detection on cover series + MCP tool `query_hive_patterns(hotel_id, query)`. ADR doc. | 8 |
| P3-8 (Story 10.8) | **Paris Open Data MCP node** — adapter `que-faire-a-paris` API → pgvector embeddings → MCP tool `find_events_near_hotel(lat, lng, date, radius)`. Standalone module callable by external agents. | 5 |
| P3-9 (Story 10.9) | **Hive Memory technical write-up** — 1500-word Medium / Notion article. Cross-link from `README.md`. | 2 |

**Total** : 9 stories, 40 points, ~6–9 sprint-weeks single-dev. Track A and B parallelisable.

---

## 4. Technical architecture (Track B highlights)

### 4.1 Hive Memory v1 (P3-7)

Cross-hotel pattern recognition layer that lifts patterns from `operational_memory` (private per-hotel) into anonymised aggregates queryable by any tenant. Anonymisation = strip `hotel_id` + manager-typed PII via Haiku classifier (reuse P2-4 sanitisation).

```
operational_memory (per-hotel, Mistral 1024d)
        │
        ▼  daily batch worker
┌─────────────────────────────────┐
│ HiveAggregator                  │
│  - k-means clustering (k=20)    │
│  - shapelet extract on covers   │
│  - persona tagging (LLM 1-pass) │
└────────────┬────────────────────┘
             ▼
hive_patterns (1 row per cluster, anonymised)
             ▲
             │  MCP tool query_hive_patterns(hotel_id, query)
             │
        any MCP client
```

**Slight over-engineering on purpose** : k-means baseline + shapelet detection demonstrates classical ML alongside the LLM stack. ADR documents the algorithmic choice and trade-offs.

### 4.2 Paris Open Data MCP node (P3-8)

`que-faire-a-paris` is Paris's public events API (no auth, JSON). We wrap it as a callable MCP tool so any agent (Aetherix forecast, Tacet, Claude Desktop, etc.) can query "what events happen near `<lat,lng>` on `<date>` within `<radius>`?".

```
que-faire-a-paris API (no auth)
        │
        ▼  weekly ETL
┌─────────────────────────────────┐
│ EventsIngester                  │
│  - dedup by event_id            │
│  - geocode via address          │
│  - Mistral 1024d embedding      │
└────────────┬────────────────────┘
             ▼
events_paris (pgvector + spatial index)
             ▲
             │  MCP tool find_events_near_hotel
             │
   Aetherix forecast + external agents
```

Code lives in `backend/app/integrations/events_paris/` + MCP tool registered in `app/mcp_server.py`. Could be extracted into a standalone repo later (`aetherix-events-mcp`) for additional portfolio visibility.

---

## 5. Gate criteria

Phase 3 closes when **all of** :

### Track A
- [ ] A1 — design partner onboarded for ≥4 weeks live receipt delivery
- [ ] A2 — US-7 ablation readout shows directional lift on `recommendation_acceptance_rate` (sample size noted, even if N=1 pilot with synthetic ablation)
- [ ] A3 — pricing model decision doc landed with PM sign-off
- [ ] A4 — Apaleo Agent Hub application submitted

### Track B
- [ ] B1 — Hive Memory MCP tool live in `/mcp/v0/tools/call` + query returns clusters in <500ms
- [ ] B2 — `find_events_near_hotel` MCP tool live + integrated into forecast pipeline (event regressor uses Paris data)
- [ ] B3 — 1 technical article published + linked from `README.md`

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|---------:|------------|
| Design partner recruitment slips | High | Start outreach Day 1 of Phase 3; parallel pipeline of 3-5 prospects |
| US-7 ablation requires N>1 for stats — N=1 pilot only gives directional signal | Medium | Document as v0 trust signal; lock that N≥3 is Phase 4 entry criterion |
| Hive Memory anonymisation leaks PII | High | Reuse P2-4 Haiku sanitiser + RLS smoke test on `hive_patterns` |
| Paris Open Data API rate limits or drops | Low | Cache aggressively in pgvector; ingester is idempotent + retry-safe |
| Apaleo Agent Hub review process unclear | Medium | Contact Apaleo partnerships pre-submission; pad timeline |
| Mews partnership form pending in parallel | Medium | Submit form Day 1 of Phase 3 (out-of-band, see §8); unblock Phase 4 |

---

## 7. Resolved decisions

- **OQ3-1 — Pilot environment** : Apaleo prod (sandbox not enough for trust-KPI). Real PMS account onboarded via design partner.
- **OQ3-2 — Track parallelism** : Track A and Track B run in parallel. No dependency in either direction.
- **OQ3-3 — Hive Memory anonymisation** : Haiku classifier strips PII before write to `hive_patterns`. Reuse `backend/app/services/sanitiser.py` (P2-4).
- **OQ3-4 — Paris Open Data hosting** : initial integration in Aetherix repo (`backend/app/integrations/events_paris/`); extraction to standalone repo deferred to post-Phase 3 (extra portfolio polish move).
- **OQ3-5 — Trust-KPI lift threshold** : *directional lift* on N=1 pilot accepted as v0 signal. Statistical significance is Phase 4 entry criterion (multi-pilot).

---

## 8. Out-of-Linear parallel tracks

### 8.1 Mews partnership form (start Day 1)

Mews integration is **Phase 4** but the partner-onboarding form takes days/weeks for approval. **Action**: submit the form as soon as Phase 3 kicks off so access is granted by the time Phase 4 starts. No code work needed until approval.

### 8.2 Tacet MCP wrapping (separate repo)

`tacet-app` (https://github.com/IvandeMurard/tacet-app) is a separate project. To strengthen the "agentic protocols" hiring signal, wrap Tacet as an MCP server:

- FastMCP server exposing 3 tools (`get_track_metadata`, `submit_review`, `find_similar`)
- Public README updated with MCP usage example
- Cross-link from Aetherix README ("we use MCP both as client + as server provider")

**Effort**: ~1 sprint-week. **Track**: Obsidian note + GitHub Project on `tacet-app` repo — not Linear (different team scope).

---

## 9. Kickoff checklist

- [ ] PM sign-off on this spec (Ivan)
- [ ] Linear Epic 10 created + 9 child stories (HOS-XXX numbering)
- [ ] CLAUDE.md updated : Phase 3 reformulated, Phase 4 renumbered to "Scale"
- [ ] Mews partnership form submitted (out-of-band, §8.1)
- [ ] Design partner outreach started (3+ prospects identified) — Track A blocker for P3-1
- [ ] Architect check (ADR 0005 needed for Hive Memory algorithm — schedule at P3-7 kickoff)

# CLAUDE.md — Aetherix

> Source de vérité partagée. Chargé automatiquement à chaque session.
> **Règle :** ce fichier = facts de session + INDEX uniquement. Détail décisions → `docs/context/decisions-architecturales.md` (24 décisions architecturales) + `docs/context/open-decisions.md` (décisions ouvertes + archive résolues). Cible ≤ 150 lignes.
> Mettre à jour après chaque décision : ajouter une ligne d'INDEX ici + le détail complet dans le sous-fichier correspondant.

---

## Projet

**Aetherix** — Plateforme IA agentique pour la gestion des opérations F&B hôtelières.
**Philosophie :** "Thin Frontend / Fat Backend" — logique métier et orchestration IA dans le backend.
**Paradigme :** Agentic-first (UX) + API-first (infra) + Human-in-the-loop (confiance).

---

## Stack

| Couche | Technologie | Notes |
|--------|------------|-------|
| Backend | FastAPI + Python 3.11 | Async, Pydantic v2 |
| Base de données | Supabase (PostgreSQL) | Auth, real-time |
| Vecteurs | pgvector (Supabase) | `fb_patterns` + `operational_memory`, Mistral 1024d, HNSW |
| Cache | Redis (Upstash) | Session state, TTL 1h |
| IA principale | Claude Sonnet | Reasoning + explainability. Multi-LLM via `LLMProvider` (Décision #9) |
| Forecast | Prophet (Meta) | Time-series covers + regressors (météo, events, occupancy) |
| Frontend | Next.js (App Router) + shadcn/ui | Thin — vérification uniquement |
| Alertes | WhatsApp via Twilio | Push-first, UI-less |
| PMS principal | Apaleo | OAuth2 + MCP Server officiel |
| PMS secondaire | Mews | Webhook, marketplace |

---

## Décisions architecturales — INDEX

> Détail complet : [`docs/context/decisions-architecturales.md`](docs/context/decisions-architecturales.md)
> Ne pas remettre en question sans raison documentée. Ajouter une nouvelle décision = ligne ici + détail dans le sous-fichier.

| # | Décision | Date |
|---|---|---|
| 1 | Claude Sonnet > Mistral/GPT | — |
| 2 | Architecture mémoire 2 couches (Private + Hive) | — |
| 3 | pgvector > Qdrant > Pinecone | — |
| 4 | Voice opt-in (pas voice-first) | — |
| 5 | Reasoning collapsible par défaut | — |
| 6 | Pas d'auto-actions (Phase MVP) | — |
| 7 | Apaleo read-only Phase 0 | — |
| 8 | Thin Frontend | — |
| 9 | Multi-LLM via `LLMProvider` abstrait | — |
| 10 | Provider singleton via `lifespan` FastAPI | — |
| 11 | Démo — stratégie données hybride (Apaleo sandbox + synthétique) | — |
| 12 | MCP Server Apaleo — probe suffisant pour candidature | — |
| 13 | Pipeline Prophet — gap training identifié | — |
| 14 | Phase 0 DoD amendée — MCP Server v0 inclus | 17/04/2026 |
| 15 | Phase 2 "Receipts" — scope locké | 19/04/2026 |
| 16 | Schema drift gate CI obligatoire | 14/05/2026 |
| 17 | Hébergement Fly.io | 14/05/2026 |
| 18 | Phase 3 cut serré + portfolio reinforcement | 17/05/2026 |
| 19 | Orchestrateur séparé — Aetherix = F&B execution node | 19/05/2026 |
| 20 | Anima — architecture mémoire 4 couches + DPIA gate | 19/05/2026 |
| 21 | Apaleo MCP — convention nommage native + sales evidence Anthropic | 26/05/2026 |
| 22 | Eval-by-design = offline gate CI + runtime eval + outcome eval (Qonto + BMad ; portée élargie 3 bras, amendé 19/06 ADR-0007 §13) | 04/06/2026 |
| 23 | POS integration scope + adapter pattern (Phase 4) | 06/06/2026 |
| 24 | Graphe de contexte Postgres recursive CTE (Phase 4) — Path C retenu cash-driven, AGE bloqué Supabase | 06/06/2026 |
| 25 | Multi-repo strategy + governance (méta-repo public + execution nodes privés) — exécution Étape 2 (post-pilote OU pré-fundraise) | 16/06/2026 |
| 26 | Anima = Guest Cognition Layer · confidence-weighted claims (schema, pas couche) · Segment double portée (local + Hive prior) · Learning Engine tier Mesh séparé · outcome-capture instrumentation Phase 4 | 17/06/2026 |

---

## Roadmap

| Phase | Statut | Highlights |
|---|---|---|
| Phase 0 (validation harness) | 🔨 In Progress | Backtest pipeline + MCP v0 livrés. MAPE J+1 synthétique **15.09%** — gate 22% PASS ✅. Réel = Phase 3 pilote. |
| Phase 1 | ✅ Done (19/04/2026) | MCP Server v0 + ADR 0003 observability + memory instrumentation. PR #73 merged. |
| Phase 0 (deploy) | ✅ Done (15/05/2026) | Staging Fly.io live. Smoke E2E 5/5 PASS. RLS 14/14 + webhook HMAC. |
| Phase 2 | ✅ Done (17/05/2026) | Agent "Receipts" P2-1 → P2-7 mergées. Daily + WhatsApp + email + inbound parser + weekly digest. |
| Phase 3 | Kickoff 17/05/2026 | Pilot Validation + Portfolio Reinforcement. Détail → `docs/planning/phase-3-pilot-validation.md` + `docs/planning/phase-3-sprint-plan.md`. |
| Phase 4 | Scale & Distribution | Mews integration · POS ingestion · **Federated HiveMemory ship (announced Phase 3)** · cross-property dashboard · food waste KPI · multi-tenant. |
| Phase 5 | Vision long-terme | Agentic Hospitality Mesh — Revenue Orchestration Agent + MCP-native design pipeline + Aetherix Voice (Lore-inspired). Détail → `docs/context/vision-future.md`. |

---

## Décisions ouvertes — INDEX

> Détail complet + archive résolues : [`docs/context/open-decisions.md`](docs/context/open-decisions.md)
> Convention : ligne d'index = 1-ligne summary. Le détail (rationale, alternatives, échéance, dépendances) vit dans le sous-fichier.

| Statut | Décision | Trigger / échéance |
|---|---|---|
| 🟡 Open | Pricing model (HOS-179 P3-5) | Post-90j data pilote |
| 🟡 Open | Apaleo Copilot scope F&B (canari) | Monitoring mensuel via watchlist |
| 🟡 Open | Food waste tracking | À trancher Phase 4 vs Phase 5 |
| 🟡 Open | Interaction model event-driven (Phase 4-5) | Brief ADR-0009 futur |
| 🟡 Open | Politique exploration éthique (Anima / Learning Engine) | Design Learning Engine Phase 5 |
| 🟡 Open | Reward multi-objectif (CSAT vs marge vs fidélisation) | Design Learning Engine Phase 5 |
| 🟡 Open | Méthode off-policy evaluation (IPW / DR / DR-Learner) | Volume données post-pilote Phase 4 |
| 🟡 Open | Floor k-anonymat couche Segment | Avant build Segment production (Epic 4) |

Resolved decisions archive (Graphe de contexte Apache AGE 06/06, POS integration scope 06/06, Federated Hive timing, Hive Memory scope, PMS priorité, MCP server, etc.) → voir `docs/context/open-decisions.md` §Resolved.

---

## KPI framework produit (référence)

Trois niveaux de mesure de la valeur. **Principe de stickiness :** publiés activement au manager (WhatsApp + dashboard) pour rendre la valeur visible sur le P&L.

**Niveau 1 — Product Truth (accuracy)** : `MAPE` couverts cible < 15% · `staffing_prediction_accuracy`
**Niveau 2 — Operational Impact (business value)** : `labor_cost_variance` (-3% à -8%) · `understaffing_incidents` · `food_waste_per_cover`
**Niveau 3 — Adoption (product health)** : `recommendation_acceptance_rate` (alerte si < 30%) · `weekly_operational_usage` · `planning_time_saved`

---

## Fichiers clés

```
backend/app/providers/    — abstraction LLM + Embedding (claude, mistral, gemini, fallback)
backend/app/services/     — exécution F&B (forecast, staffing, memory, receipts) — pas d'orchestration (ADR-0004)
backend/app/integrations/ — Obsidian, Linear, Apaleo, Twilio, SendGrid
backend/app/mcp_server.py — MCP Server v0 (HOS-71, PR #73) — tools atomiques uniquement
backend/orchestrator/     — proto-orchestrateur Phase 3 (AetherixEngine migré, ADR-0004)
backend/app/middleware/   — agent_tracking.py (Agent SEO + request_id, P1-5/HOS-72)
scripts/ci/               — gates CI (schema drift #16, eval-by-design #22, audit_id_types HOS-163)
scripts/ops/              — ops & monitoring (veille_proactive, sync_obsidian, validate_apaleo_sandbox, measure_mape_j1, generate_demo_data)
.github/workflows/        — CI + cron veille-hebdomadaire (lundi 8h30)
```

> **📚 Documentation** : catalogue par sous-catégorie dans [`docs/INDEX.md`](docs/INDEX.md). À charger en priorité pour contexte inter-nœuds : `docs/mesh-architecture.md` (SOURCE DE VÉRITÉ CROSS-REPOS Aetherix + Tacet + Orchestrateur + Anima).

---

## Variables d'environnement

```
ANTHROPIC_API_KEY     — Claude API
LINEAR_API_KEY        — lin_api_... (workspace Hospitalityagent)
LINEAR_TEAM_ID        — 2f6bb5e2-d735-4769-9377-11fe186aa0ad
OBSIDIAN_VAULT_PATH   — C:/Users/IVAN/OneDrive/Documents/Agentic AI Hospitality
APALEO_CLIENT_ID      — OAuth2
APALEO_CLIENT_SECRET  — OAuth2
COMPOSIO_API_KEY      — Apaleo MCP via Composio (Inventory API uniquement)
SUPABASE_URL          — PostgreSQL + pgvector
SUPABASE_KEY          — Anon key
DATABASE_URL          — asyncpg DSN
MISTRAL_API_KEY       — Embeddings 1024d (mistral-embed)
LLM_BACKEND           — "claude" (défaut) | "gemini" | "openai"
LLM_MODEL             — "claude-sonnet-4-6" (défaut)
EMBEDDING_BACKEND     — "mistral" (défaut) | "openai"
EMBEDDING_MODEL       — "mistral-embed" (défaut)
REDIS_URL             — Upstash (session state)
```

---

## Linear · Obsidian · BMad

**Linear** — Workspace `Hospitalityagent`, team `2f6bb5e2-d735-4769-9377-11fe186aa0ad`. Conventions Epic/Story → `docs/context/linear-conventions.md`. Verify session : `list_teams` doit retourner "Hospitalityagent".

**Obsidian** — Vault `C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality`. MCP : Claude Desktop + Claude Code. Reports : `AI Reports/Intelligence/`.

**BMad modes** — Déclare en début de conversation. Veille · SM (Bob) · Dev (Amelia) · Architect (Winston) · PM · Analyst (Mary) · QA · Tech Writer. Files in `docs/bmad/_bmad/bmm/agents/`.

---

## Dev Agent — Definition of Done

1. Lire le spec de la Linear issue (MCP Linear)
2. Auditer ce qui existe dans le codebase
3. Implémenter la story (migration DB, ORM, schemas, service, worker, route)
4. Tests — CI green
5. Commit + Push sur la branche désignée (`claude/<story-suffix>`)
6. Ouvrir une PR contre `main`
7. Marquer la Linear issue → Done + poster l'URL PR en commentaire
8. **Eval gate (Décision #22)** : si la story touche `app/services/{forecast,staffing,recommendation,memory,inbound_parser}*`, `app/providers/`, ou les prompts → mettre à jour `eval/golden_dataset.jsonl` avec ≥ 1 scenario + `make eval` green + `scripts/ci/check_eval_coverage.py` validé. Exception via label PR `eval-exempt` (refactor / doc / infra-only).

**Gate de merge :** CI vert (schema drift #16 + eval-by-design #22) → merge manuel SM. **Gates supérieurs :** Fin d'Epic → revue d'architecture. Pré-pilote → QA sign-off propriété réelle.

**Règle de contexte :** décisions / contraintes / blocages story-specific → commentaire sur Linear issue. Cross-cutting permanent → ligne d'index dans CLAUDE.md §Décisions architecturales + détail dans `docs/context/decisions-architecturales.md`. Ne pas écrire contexte story-specific ici.

---

## Points d'attention

1. `docs/ARCHITECTURE.md` daté fév. 2026 — sections Streamlit/Render.com obsolètes. Se fier à ce CLAUDE.md.
2. `.env.example` racine = ancien backend (`archive/legacy-backend`).
3. Hébergement staging = Fly.io `cdg` (Décision #17). Dev local Windows pour scripts utilitaires.

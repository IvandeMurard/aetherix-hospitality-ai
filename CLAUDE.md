# CLAUDE.md — Aetherix

> Source de vérité partagée. Chargé automatiquement à chaque session.
> **Règle :** ce fichier = facts de session uniquement (stack, décisions, fichiers, env vars, protocoles). Tout contexte narratif → `docs/context/`. Ne jamais dépasser ~150 lignes.
> Mettre à jour après chaque décision architecturale : ajouter une ligne dans §Décisions architecturales, déplacer le détail dans `docs/context/` si > 2 lignes.
> Contexte détaillé → `docs/context/`

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

## Décisions architecturales (ne pas remettre en question sans raison)

| # | Décision | Résumé |
|---|---------|--------|
| 1 | Claude Sonnet > Mistral/GPT | Meilleur reasoning, 200K ctx, explainability critique |
| 2 | Architecture mémoire 2 couches | Private Memory (pgvector/hôtel) + Hive Memory (cross-hôtels anonymisé). Backboard réévaluer Phase 3+. Détail → `docs/context/memory-architecture.md` |
| 3 | pgvector > Qdrant > Pinecone | Suffisant <50K patterns, 1 requête SQL, compatible latency MCP <500ms |
| 4 | Voice opt-in (pas voice-first) | Trop risqué en démo, clavier = fallback fiable |
| 5 | Reasoning collapsible par défaut | Réduction charge cognitive |
| 6 | Pas d'auto-actions (Phase MVP) | 63% managers veulent contrôle humain |
| 7 | Apaleo read-only Phase 0 | Pas d'écriture sur réservations tant que l'outil n'est pas mature. Loguer toutes les actions agent |
| 8 | Thin Frontend | Logique IA dans backend, dashboard = visualisation uniquement |
| 9 | Multi-LLM via `LLMProvider` abstrait | Swap Claude → Gemini → GPT sans réécriture. Claude reste provider principal |
| 10 | Provider singleton via `lifespan` FastAPI | `LLMProvider` + `EmbeddingProvider` instanciés une fois au démarrage, stockés dans `app.state`. Factory = construction uniquement. Providers closés proprement (`aclose()`) au shutdown. Détail → `docs/bmad/_bmad-output/planning-artifacts/architecture.md` |
| 11 | Démo — stratégie données hybride | Apaleo sandbox pour appels MCP live (probe + occupancy). Dataset synthétique 365j pour training Prophet (DEMO_MODE=true). Script `scripts/ops/generate_demo_data.py` → `backend/data/demo/prophet_training.json`. Détail → `docs/context/demo-apaleo.md` |
| 12 | MCP Server Apaleo — probe suffisant pour candidature | `GET /pms/mcp/probe` (endpoint existant) prouve la connexion MCP native — suffit pour la démo Apaleo. HOS-71 (Aetherix MCP Server complet) = Phase 0.5, post-candidature. |
| 13 | Pipeline Prophet — gap training identifié | `ApaleoMCPAdapter.get_historical_data()` → `DataTransformer.stay_records_to_prophet()` → `PredictionEngine.train()` : briques existent, orchestrateur manquant. Débloquer via `POST /api/v1/predictions/train` ou worker de démarrage. |
| 14 | Phase 0 DoD amendée — MCP Server v0 inclus | Suite directive PM 17/04/2026 (tweet Benioff "headless for agents"): ship Aetherix MCP Server v0 (HOS-71, 3 tools) est désormais un critère de validation Phase 0, APRÈS gate MAPE interne. Si MAPE > 22%, pivot avant ship MCP. Détail → `docs/planning/phase-0-1-execution-plan.md` |
| 15 | Phase 2 "Receipts" — scope locké 19/04/2026 | Channel = WhatsApp primary + email opt-in (SendGrid). Inbound classifier = Haiku, log confidence, auto-`modified` si <0.6. Auth web drill-down = MCP bearer + scope `receipts:read`. Tone = terse + sharp bullets + luxury feel (driver principal, données quantitatives, evidence historique, confidence, follow-up proactif). Gate = two-track : (a) technical-ship sur Apaleo Sandbox (round-trip daily Receipt + feedback→memory + 4 Sundays digest) ; (b) trust-signal (US-7 ablation) reporté au premier pilote réel. Détail → `docs/planning/phase-2-agent-receipts.md` |
| 16 | Schema drift gate CI obligatoire (Epic 9 retro 14/05/2026) | Invariant **"ORM = miroir exact des migrations"**. Tout merge bloqué si une colonne du modèle SQLAlchemy n'existe pas en DB (ou inverse). Découvert via Epic 9 (HOS-148) : 3 bugs silencieux résolus. Implémentation : `scripts/ci/check_schema_drift.py` + `scripts/ci/schema_drift_ignore.json`. Convention IDs : `docs/context/data-conventions.md`. |
| 17 | Hébergement Fly.io (14/05/2026) | Backend déployé sur Fly.io, région `cdg` (Paris). 1 instance always-on (`min_machines_running=1`) — requis par APScheduler in-process. Image Docker Python 3.12 + uv multi-stage. Secrets via `flyctl secrets set` (jamais commités). Latence Paris ↔ Supabase Stockholm ~30ms (acceptable Phase 0). URL staging : `https://aetherix-backend.fly.dev`. Détail déploiement : `docs/secrets_handling.md`. Remplace l'ancienne contrainte "local Windows / GitHub uniquement". |
| 18 | Phase 3 cut serré + portfolio reinforcement (17/05/2026) | Phase 3 scope = Pilot Validation **uniquement** (Track A) + Portfolio Reinforcement (Track B). Multi-hotel / Mews / cross-property dashboard / food waste → Phase 4 (Scale). Track B = over-engineering volontaire pour hiring signal : Hive Memory algorithm (k-means + shapelet + LLM persona, MCP tool exposé), Paris Open Data MCP node (`que-faire-a-paris` → pgvector → MCP tool callable par agents externes), 1 article technique public. Tacet MCP wrapping = repo séparé hors Linear Aetherix. Mews partnership form à soumettre Day 1 Phase 3 (latence partner approval). Détail → `docs/planning/phase-3-pilot-validation.md`. Epic 10 = HOS-174, 9 stories P3-1→P3-9. |

---

## Roadmap

| Phase | Statut | Contenu |
|-------|--------|---------|
| Phase 0 (validation) | ✅ Done (18/04/2026) | Backtest PASS (MAPE 7.8% J+1) + ROI simulator + MCP Server v0 (HOS-71) |
| Phase 1 | ✅ Done (19/04/2026) | MCP Server v0 + ADR 0003 observability (agent_action_log, Redis rate-limiter, MV refresh) + memory instrumentation (Mistral 1024d embeddings, 2-pass dedup). PR #73 merged. |
| Phase 0 (deploy) | ✅ Done (15/05/2026) | Staging Fly.io live (`aetherix-backend.fly.dev`). Smoke test E2E 5/5 PASS (Apaleo skip). Epic 9 hardening fermé (14 stories + 3 sub-HOS-159). Sécurité : HOS-111 RLS 14/14 tables + HOS-112 webhook HMAC. Reste gates non-techniques : sign-off PM runbook + pre-pilot checklist. |
| Phase 2 | ✅ Done (17/05/2026) | Agent "Receipts" — 7 stories P2-1→P2-7 mergées. Daily Receipt + WhatsApp + email + inbound feedback parser (Haiku) + weekly KPI digest + web drill-down + Track A gate. Track B (trust-KPI) reporté Phase 3. |
| Phase 3 | Planifié (kickoff 17/05/2026) | Pilot Validation + Portfolio Reinforcement. Track A : 1 design partner Apaleo prod + US-7 ablation (trust-KPI) + pricing decision + Apaleo Agent Hub listing. Track B (slight over-engineering volontaire) : Hive Memory algorithm v1 + Paris Open Data MCP node + technical write-up. Epic 10 = HOS-174, 9 stories P3-1→P3-9. Détail → `docs/planning/phase-3-pilot-validation.md` |
| Phase 4 | Renuméroté — Scale & Distribution | Mews integration (PMS #2, form partner à lancer Day 1 Phase 3), cross-property dashboard (HOS-95-98 existants), food waste KPI instrumentation, multi-tenant production hardening au-delà du 1er pilote |
| Phase 5 | Vision long-terme (ex-Phase 4) | Agentic Hospitality Mesh — Revenue Orchestration Agent + MCP-native design pipeline. Détail → `docs/context/vision-future.md` |
| Phase MCP | ✅ Intégré Phase 0/1 | MCP Server v0 shipped (HOS-71). v1 (FastMCP SDK) quand besoin progress/capability-negotiation. |

---

## Décisions ouvertes (à trancher)

- [ ] **Embedding strategy** : pgvector vs Qdrant pour RAG (à re-évaluer Phase 4 quand multi-tenant + Hive Memory à scale ; pour l'instant pgvector reste suffisant)
- [ ] **Pricing model** : par hôtel / par prédiction / hybrid — tracking Linear HOS-179 (P3-5), décision après 90j data pilote
- [x] **PMS priorité live (RÉSOLU 17/05/2026)** : Apaleo prod Phase 3 (1 design partner, HOS-176). Mews déplacé Phase 4 + form partner à soumettre Day 1 Phase 3 (latence approval).
- [x] **MCP server (RÉSOLU 19/04/2026)** : FastAPI endpoint dédié retenu — `/mcp/v0` mounted sur l'app principale (lifespan partagé, ADR D2). Shippé via PR #73. Sidecar process rejeté (coût ops, pas de bénéfice latence observé).
- [x] **Apaleo MCP direct (31/03/2026 — RÉSOLU)** : URL confirmée `https://mcp.apaleo.com/mcp/`, transport HTTP Streamable (SSE déprécié — notre `streamablehttp_client` est correct). Scope MCP activé sur le compte (code IIQJ). Auth OAuth2 bearer identique à la raw API. Activer via `POST /pms/sync?use_mcp=true` + `APALEO_MCP_SERVER_URL=https://mcp.apaleo.com/mcp/` dans `.env`.
- [x] **ROI dashboard vs WhatsApp (RÉSOLU implicitement post-Phase 1)** : WhatsApp primary retenu (cf. Decision #15 OQ1 — Receipts channel = WhatsApp + email opt-in). Dashboard différé Phase 3+ si adoption le justifie.
- [ ] **Food waste tracking** : instrumenter predicted prep vs actual waste par service comme KPI produit différenciant — ~25% gaspillage moyen en hôtellerie FR (ADEME/Accor), ~115g/couvert. Opportunité : la plupart des hôtels ne mesurent pas précisément → notre modèle crée cette donnée comme sous-produit du forecasting. Décision : intégrer en Phase 4 comme feature ROI (€ gaspillés évités) ou Phase 5 avec POS data ? À trancher avec PM.

---

## KPI framework produit (référence)

Trois niveaux de mesure de la valeur, basés sur l'analyse du marché (Mars 2026).
**Principe de stickiness :** ces KPIs ne sont pas seulement mesurés — ils sont publiés activement au manager (alertes WhatsApp + éventuellement dashboard) pour rendre la valeur visible sur le P&L et créer un coût de migration psychologique élevé.

**Niveau 1 — Product Truth (accuracy)**
- `MAPE` sur couverts dîner, petit-déj, check-ins — cible < 15%
- `staffing_prediction_accuracy` — % de recommandations staff alignées avec la réalité

**Niveau 2 — Operational Impact (business value)**
- `labor_cost_variance` — coût réel vs baseline (cible : -3% à -8%)
- `understaffing_incidents` — incidents par semaine (attente check-in, délais service)
- `food_waste_per_cover` — tendance vs baseline (à instrumenter en Phase 4)

**Niveau 3 — Adoption (product health)**
- `recommendation_acceptance_rate` — % de recommandations suivies (alerte si < 30% → problème de trust)
- `weekly_operational_usage` — % managers consultant le forecast avant de planifier
- `planning_time_saved` — temps économisé vs planning manuel

---

## Fichiers clés

```
backend/app/providers/         — abstraction LLM + Embedding (claude, mistral, gemini, fallback, factory)
backend/app/services/          — orchestration IA et logique métier
backend/app/integrations/      — Obsidian, Linear, Apaleo, Twilio, SendGrid
backend/app/mcp_server.py      — MCP Server v0 (3 tools, HOS-71, PR #73)
backend/app/middleware/        — agent_tracking.py (Agent SEO discovery + request_id, P1-5/HOS-72)
scripts/ops/veille_proactive.py    — monitoring hebdomadaire automatisé
scripts/ci/audit_id_types.py      — audit statique des mismatches tenant_id/property_id/hotel_id (HOS-163)
docs/context/data-conventions.md — convention tenant_id/property_id/hotel_id + table des drifts (HOS-163)
docs/ARCHITECTURE.md           — design système (v0.2.0 — certaines sections obsolètes, se fier à ce fichier)
docs/ROADMAP_NOW_NEXT_LATER.md — roadmap opérationnelle
docs/context/                  — contexte détaillé par domaine
.github/workflows/veille-hebdomadaire.yml — cron lundi 8h30
```

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
COMPOSIO_USER_ID      —
COMPOSIO_MCP_URL      —
SUPABASE_URL          — PostgreSQL + pgvector
SUPABASE_KEY          — Anon key
DATABASE_URL          — asyncpg DSN (postgresql+asyncpg://...)
MISTRAL_API_KEY       — Embeddings 1024d (mistral-embed)
LLM_BACKEND           — "claude" (défaut) | "gemini" | "openai"
LLM_MODEL             — "claude-sonnet-4-6" (défaut)
EMBEDDING_BACKEND     — "mistral" (défaut) | "openai"
EMBEDDING_MODEL       — "mistral-embed" (défaut)
REDIS_URL             — Upstash (session state)
```

---

## Linear

**Workspace :** Hospitalityagent — toutes les issues dans HOS, jamais dans ivanportfolio/Tacet.
**Team ID :** `2f6bb5e2-d735-4769-9377-11fe186aa0ad`
**Vérification session :** `list_teams` → doit retourner "Hospitalityagent". Si "Tacet" → reconnecter dans claude.ai Settings → Integrations → redémarrer Claude Desktop.
**Conventions Epic/Story (DoD, labels, statuts) :** `docs/context/linear-conventions.md` — protocole obligatoire pour toute création.
**Audit :** `python scripts/linear_audit.py > linear_state.md` (read-only, fin de sprint).

---

## Obsidian

**Vault :** `C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality`
**MCP :** Claude Desktop (`claude_desktop_config.json`) + Claude Code (`~/.claude.json`)
**Reports :** `AI Reports/Intelligence/` — rapports veille automatisés

---

## BMad — Modes de session

Déclare le mode en début de conversation. Chaque agent charge son propre fichier de contexte.

| Mode | Activer avec | Agent file |
|------|-------------|-----------|
| Veille | "Veille" ou partager un lien | `docs/context/veille.md` |
| SM (Bob) | "SM", "Scrum" | `docs/bmad/_bmad/bmm/agents/sm.md` |
| Dev (Amelia) | "Dev", "Développement" | `docs/bmad/_bmad/bmm/agents/dev.md` |
| Architect | "Architect", "Architecture" | `docs/bmad/_bmad/bmm/agents/architect.md` |
| PM | "PM", "Product" | `docs/bmad/_bmad/bmm/agents/pm.md` |
| Analyst (Mary) | "Analyst", "Analyse" | `docs/bmad/_bmad/bmm/agents/analyst.md` |
| QA | "QA", "Tests" | `docs/bmad/_bmad/bmm/agents/qa.md` |
| Tech Writer | "Tech Writer", "Doc" | `docs/bmad/_bmad/bmm/agents/tech-writer/tech-writer.md` |

---

## Dev Agent — Definition of Done

1. Lire le spec de la Linear issue (MCP Linear)
2. Auditer ce qui existe dans le codebase
3. Implémenter la story (migration DB, ORM, schemas, service, worker, route)
4. Tests — CI green
5. Commit + Push sur la branche désignée (`claude/<story-suffix>`)
6. Ouvrir une PR contre `main`
7. Marquer la Linear issue → Done + poster l'URL PR en commentaire

**Gate de merge :** CI vert → merge manuel SM (sans revue de code).
**Gates supérieurs :** Fin d'Epic → revue d'architecture. Pré-pilote → QA sign-off propriété hôtelière réelle.

**Règle de contexte :** toute décision, contrainte ou blocage découvert pendant l'implémentation → commenter sur la Linear issue. Si la décision devient une contrainte permanente cross-cutting → promouvoir en une ligne dans §Décisions architecturales ci-dessus. Ne pas écrire de contexte story-specific dans CLAUDE.md ou docs/context/.

---

## Points d'attention

1. `docs/ARCHITECTURE.md` daté fév. 2026 — sections Streamlit/Render.com = ancienne stack. Se fier à ce CLAUDE.md.
2. `.env.example` racine = ancien backend (`archive/legacy-backend`).
3. Hébergement staging = Fly.io (`cdg`, Paris) — voir Décision #17. Dev local Windows pour scripts utilitaires (`veille_proactive`, MCP Obsidian).

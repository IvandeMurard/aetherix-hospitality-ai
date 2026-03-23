# CLAUDE.md — Aetherix · Second Brain

> Ce fichier est la source de vérité partagée entre toutes les sessions (Claude Code, Claude Desktop, BMad).
> Il est chargé automatiquement à chaque session. Mettre à jour après chaque décision importante.

---

## Projet

**Aetherix** — Plateforme IA agentique pour la gestion des opérations F&B hôtelières.
Mission : transformer la gestion proactive du F&B en hôtellerie via des agents IA qui anticipent, alertent et recommandent.

**Philosophie :** "Thin Frontend / Fat Backend" — la logique métier et l'orchestration IA vivent dans le backend.
**Paradigme :** Agentic-first (UX) + API-first (infrastructure) + Human-in-the-loop (confiance).

---

## Stack principale

| Couche | Technologie | Notes |
|--------|------------|-------|
| Backend | FastAPI + Python 3.11 | Async, Pydantic v2, OpenAPI auto-généré |
| Base de données | Supabase (PostgreSQL) | Auth, real-time, backups gérés |
| Patterns vectoriels | Qdrant Cloud | Patterns F&B, embeddings 1536d, Cosine — 495+ patterns |
| Mémoire cognitive | pgvector `operational_memory` (Phase 0-1) → Backboard.io (Phase 3) | Feedback loop par hôtel, outcomes, apprentissage cumulatif — via interface `MemoryProvider` abstrait |
| Cache | Redis (Upstash) | Session state, TTL 1h |
| IA principale | Claude Sonnet (Anthropic) | Reasoning + explainability |
| Forecast numérique | Prophet (Meta) | Time-series covers prediction + regressors (météo, events, occupancy) |
| Frontend | Next.js (App Router) + shadcn/ui | Couche vérification (thin) — pas le canal principal |
| Alertes | WhatsApp via Twilio | Delivery ambiant (push-first, UI-less) |
| PMS principal | Apaleo (prioritaire) | OAuth2, sandbox dispo |
| PMS secondaire | Mews | Webhook, marketplace |
| Knowledge | Obsidian vault | `C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality` |
| Issues | Linear HOS | Workspace Hospitalityagent |

---

## Décisions architecturales prises (ne pas remettre en question sans raison)

| # | Décision | Rationale | Alternatives rejetées |
|---|---------|-----------|----------------------|
| 1 | Claude Sonnet > Mistral | Meilleur reasoning, 200K ctx, explainability critique | Mistral trop faible, GPT-4 trop cher |
| 2 | Qdrant > pgvector > Pinecone | Free tier généreux, <100ms, cloud-native | Pinecone $70/mo, pgvector plus lent |
| 3 | Voice opt-in (pas voice-first) | Trop risqué en démo (bruit), clavier = fallback fiable | Voice-first = risque UX |
| 4 | Reasoning collapsible par défaut | Charge cognitive, 1-ligne visible, expand pour power users | Tout afficher = clutter |
| 5 | Pas d'auto-actions (Phase MVP) | 63% managers veulent contrôle humain, trust-building | Full automation = adoption faible |
| 6 | PMS-agnostic | Mews + Apaleo = 1000s hôtels, fallback si Mews refuse | Lock-in Mews = risque |
| 7 | Thin Frontend | Logique IA dans backend, dashboard = visualisation uniquement | Fat frontend = duplication logique |
| 8 | pgvector MVP → Backboard Phase 3 (via `MemoryProvider`) | Backboard = dépendance externe opaque prématurée en Phase 0. pgvector couvre le feedback loop par hôtel. Backboard s'insère en Phase 3 (multi-hôtels, insights structurés, patterns anonymisés cross-hôtels). L'interface `MemoryProvider` (`store_feedback`, `get_hotel_context`, `get_cross_hotel_patterns`) est conçue dès maintenant pour éviter toute réécriture. | Backboard dès MVP = risque de stabilité + coût non maîtrisé avant données suffisantes |

---

## Pivot stratégique (Mars 2026) — Agent-First

Nouvelle orientation issue de la veille Andrew Chen (a16z) :

> "Distribution shifts from top of funnel to top of call stack."
> "Agent SEO where ranking factors are success rate across thousands of agent runs."

**Implication :** Aetherix doit être callable par des agents IA (Claude, Codex, Cursor) via MCP, pas seulement accessible via dashboard.

Issues actives dans HOS :
- **HOS-71** — Exposer Aetherix comme primitive agent-callable (MCP Server) — High, Backlog
- **HOS-72** — Roadmap "Agent SEO" — métriques machine-legible — High, Backlog

Capabilities MCP candidates :
- `forecast_occupancy(hotel_id, date_range)` → prévisions F&B
- `get_stock_alerts(hotel_id)` → alertes inventaire
- `recommend_menu(hotel_id, context)` → recommandations adaptatives
- `get_fb_kpis(hotel_id, period)` → KPIs structurés

Métriques "Agent SEO" à instrumenter :
- `tool_success_rate` > 99.5%
- `p95_latency` < 500ms
- `schema_stability` = 0 breaking changes par sprint
- `agent_retry_rate` < 1%

---

## Roadmap phases

| Phase | Statut | Contenu |
|-------|--------|---------|
| Phase 0 | En cours | Architecture FastAPI, modèles DB, intégrations base (Apaleo, WhatsApp) |
| Phase 1 | Planifié | Forecasting F&B (Prophet + LLM), alertes proactives WhatsApp |
| Phase 2 | Planifié | Agent conversationnel "Receipts" — explications recommandations |
| Phase 3 | Planifié | Multi-hotel, Mews, analytics avancés |
| Phase MCP | Nouveau | Exposer capabilities via MCP Server (HOS-71) |

---

## Décisions ouvertes (à trancher)

- [ ] **Embedding strategy** : pgvector vs Qdrant pour RAG (Qdrant préféré actuellement mais réévaluer si multi-tenant)
- [ ] **Pricing model** : par hôtel / par prédiction / hybrid — non décidé
- [ ] **PMS priorité live** : Apaleo (sandbox dispo, API-first) vs Mews (vision alignée, marketplace)
- [ ] **MCP server** : FastAPI endpoint dédié vs sidecar process séparé
- [ ] **Food waste tracking** : instrumenter predicted prep vs actual waste par service comme KPI produit différenciant — ~25% gaspillage moyen en hôtellerie FR (ADEME/Accor), ~115g/couvert. Opportunité : la plupart des hôtels ne mesurent pas précisément → notre modèle crée cette donnée comme sous-produit du forecasting. Décision : intégrer en Phase 4 comme feature ROI (€ gaspillés évités) ou Phase 5 avec POS data ? À trancher avec PM.

---

## KPI framework produit (référence)

Trois niveaux de mesure de la valeur, basés sur l'analyse du marché (Mars 2026) :

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
backend/app/services/          — orchestration IA et logique métier
backend/app/integrations/      — Obsidian, Linear, Apaleo
docs/ARCHITECTURE.md           — design système complet (v0.2.0, Feb 2026)
.github/workflows/veille-hebdomadaire.yml — cron lundi 8h30
```

---

## Variables d'environnement requises

```
ANTHROPIC_API_KEY     — Claude API (reasoning + explainability)
BACKBOARD_API_KEY     — Backboard.io (cognitive memory layer — Phase 3)
LINEAR_API_KEY        — lin_api_... (workspace Hospitalityagent)
LINEAR_TEAM_ID        — 2f6bb5e2-d735-4769-9377-11fe186aa0ad (équipe HOS)
OBSIDIAN_VAULT_PATH   — C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality
APALEO_CLIENT_ID      — OAuth2 (prioritaire)
APALEO_CLIENT_SECRET  — OAuth2
SUPABASE_URL          — PostgreSQL
SUPABASE_KEY          — Anon key
QDRANT_URL            — Vector DB (patterns F&B)
QDRANT_API_KEY        — Vector DB
REDIS_URL             — Upstash (session state)
```

---

## Linear — Source de vérité

**Workspace :** Hospitalityagent (`linear.app/hospitalityagent`)
**Team :** HOS (`id: 2f6bb5e2-d735-4769-9377-11fe186aa0ad`)

Toutes les issues vivent dans HOS. Ne jamais créer dans ivanportfolio/Tacet.

**Connecteur MCP :** `claude_ai_Linear` (remote, compte claude.ai)
- Si `list_teams` retourne "Tacet" → reconnecter dans claude.ai → Settings → Integrations → Hospitalityagent
- Après reconnexion : redémarrer Claude Desktop

**Vérification rapide début de session :**
```
list_teams → doit retourner "Hospitalityagent"
```

---

## Obsidian — Knowledge base

**Vault :** `C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality`

**MCP configuré sur :**
- Claude Desktop : `claude_desktop_config.json` (corrigé 22/03/2026)
- Claude Code : `~/.claude.json` (ajouté 22/03/2026, scope user)

Notes importantes dans le vault :
- `AI Reports/Intelligence/` — rapports veille hebdomadaire automatisés
- Synchronisation via `scripts/obsidian_sync.py`

---

## Sessions — Modes BMad

Déclare le type de session en début de conversation (ou réponds au menu SessionStart).
Chaque mode adopte un comportement, un contexte prioritaire, et des artefacts de sortie différents.

---

### 🔍 Veille — Intelligence stratégique
**Activer :** "Veille" ou partager un lien/contenu directement
**Contexte prioritaire :** Dernières notes Obsidian `AI Reports/Intelligence/` + décisions ouvertes CLAUDE.md
**Comportement :** Scorer la pertinence (0-10), ne créer d'artefact que si ≥ 7
**Artefacts :** Issue Linear HOS + note Obsidian + proposition edit CLAUDE.md si décision stratégique
**Voir section :** [Session Veille — Instructions] ci-dessous

---

### 🏃 SM — Bob, Scrum Master
**Activer :** "SM", "Scrum", ou charger `docs/bmad/_bmad/bmm/agents/sm.md`
**Contexte prioritaire :** Issues HOS ouvertes par priorité + sprint en cours
**Comportement :** Crisp, checklist-driven. Préparer stories, planifier sprint, gérer backlog
**Artefacts :** Issues Linear HOS mises à jour, story files dans `docs/bmad/_bmad-output/implementation-artifacts/`
**Commandes BMad :** SP (Sprint Planning), CS (Create Story), ER (Epic Retrospective), CC (Course Correction)
**Vérification début de session :** `list_issues team=HOS state=Todo,InProgress` → afficher top 5

---

### 💻 Dev — Amelia, Developer
**Activer :** "Dev", "Développement", ou charger `docs/bmad/_bmad/bmm/agents/dev.md`
**Contexte prioritaire :** Story file assignée (`docs/bmad/_bmad-output/implementation-artifacts/`) + décisions techniques CLAUDE.md
**Comportement :** Exécuter les tasks/subtasks dans l'ordre, TDD strict, jamais skip de tests
**Artefacts :** Code committé, story file mise à jour (Dev Agent Record + File List), branche `ivandemurard/hos-XX-...`
**Règle :** Toujours travailler sur une branche Linear (`git checkout -b ivandemurard/hos-XX-...`)
**Vérification début de session :** Lire la story file assignée avant toute implémentation

---

### 🏗️ Architect
**Activer :** "Architect", "Architecture", ou charger `docs/bmad/_bmad/bmm/agents/architect.md`
**Contexte prioritaire :** `docs/bmad/_bmad-output/planning-artifacts/architecture.md` + décisions ouvertes CLAUDE.md
**Comportement :** Décisions techniques structurées avec rationale, alternatives rejetées, trade-offs
**Artefacts :** Mise à jour CLAUDE.md §Décisions architecturales + `docs/bmad/_bmad-output/planning-artifacts/architecture.md`

---

### 📋 PM — Product Manager
**Activer :** "PM", "Product", ou charger `docs/bmad/_bmad/bmm/agents/pm.md`
**Contexte prioritaire :** `docs/bmad/_bmad-output/planning-artifacts/prd.md` + roadmap CLAUDE.md + issues HOS Backlog
**Comportement :** Priorisation backlog, validation scope, alignement PRD ↔ Linear
**Artefacts :** PRD mis à jour, issues HOS créées/repriorisées, roadmap CLAUDE.md

---

### 📊 Analyst — Mary, Business Analyst
**Activer :** "Analyst", "Analyse", ou charger `docs/bmad/_bmad/bmm/agents/analyst.md`
**Contexte prioritaire :** `docs/bmad/_bmad-output/planning-artifacts/product-brief-*.md` + notes Obsidian veille
**Comportement :** Recherche marché, analyse concurrentielle, élicitation des besoins
**Artefacts :** Notes Obsidian `AI Reports/`, product brief mis à jour

---

### 🔬 QA
**Activer :** "QA", "Tests", ou charger `docs/bmad/_bmad/bmm/agents/qa.md`
**Contexte prioritaire :** Issues HOS `In Progress`/`In Review` + story files récentes
**Comportement :** Validation critères d'acceptance, revue de code, identification edge cases
**Artefacts :** Commentaires sur issues Linear, bugs créés comme nouvelles issues HOS

---

### ✍️ Tech Writer
**Activer :** "Tech Writer", "Doc", ou charger `docs/bmad/_bmad/bmm/agents/tech-writer/tech-writer.md`
**Contexte prioritaire :** `docs/bmad/_bmad_memory/tech-writer-sidecar/documentation-standards.md` + story files complétées
**Comportement :** Documenter ce qui a été implémenté, maintenir standards de doc
**Artefacts :** Fichiers dans `docs/`, CLAUDE.md si changement de contexte projet

**Direction stratégique (Mars 2026) :** "Agent-First Distribution" — Aetherix doit être une **primitive appelable par d'autres agents** (MCP Server), pas seulement un produit SaaS avec UI. Distribution = top of call stack, pas top of funnel.

---

## Session Veille — Instructions

### Mode Réactif (à la demande)
Quand l'utilisateur partage un lien, un document, ou du contenu :
1. Analyser le contenu en profondeur
2. Confronter avec le contexte projet (stack, roadmap, positionnement)
3. **Scorer la pertinence (0-10)** selon les critères ci-dessous
4. **Ne pousser vers Linear et Obsidian QUE si score >= 7/10**
5. Si score < 7 : livrer l'analyse uniquement, sans créer d'artefact

**Critères de pertinence :**
- Impacte directement la roadmap ou les décisions techniques (score +3)
- Révèle un concurrent direct ou une opportunité de marché (score +3)
- Apporte une information actionnable (justifie une nouvelle story) (score +2)
- Contenu récent (< 7 jours) (score +1)
- Source fiable (hospitalitynet.org, YC, Apaleo/Mews official, etc.) (score +1)

**Format de sortie si pertinent (>= 7/10) :**
```
## [Titre]
**Score de pertinence : X/10**
**Pourquoi c'est important :** ...
**Lien avec le projet :** ...
**Action recommandée :** [story Linear proposée]
**Tags :** #hotel-tech #agentique #concurrent etc.
```

### Mode Proactif (automatique, lundi 8h30)
Rapport hebdomadaire généré par GitHub Actions via `scripts/veille_proactive.py`.
Résultat : ticket Linear "Veille Hebdomadaire" + note Obsidian dans `AI Reports/Intelligence/`.

---

## Thématiques de veille

1. **Hotel tech & agentique IA** — nouvelles solutions, startups, acquisitions
2. **IA dans l'hôtellerie** — cas d'usage F&B, forecasting, automatisation ops
3. **Apaleo** — nouveautés API, partenaires, blog officiel
4. **Mews** — features, positionnement, acquisitions
5. **Y Combinator** — nouvelles références liées à l'hospitality/F&B/forecasting
6. **hospitalitynet.org** — articles pertinents publiés dans les 7 derniers jours
7. **Agent-first / MCP ecosystem** — outils, frameworks, distribution patterns

---

## Roadmap synthétique (pour évaluer la pertinence)
- **Phase 0 (en cours)** : Architecture FastAPI, modèles DB, intégrations de base (Apaleo, WhatsApp)
- **Phase 0.5 (ajout — Mars 2026)** : MCP Server — exposer les capabilities core comme primitive agent-callable
- **Phase 1** : Forecasting F&B (Prophet + LLM), alertes proactives via WhatsApp + instrumentation "Agent SEO"
- **Phase 2** : Agent conversationnel "Receipts" — explications des recommandations
- **Phase 3** : Multi-hotel, PMS étendu (Mews), analytics avancés

**Décisions techniques ouvertes :**
- Stratégie d'embedding pour RAG (pgvector vs Qdrant)
- Modèle de pricing SaaS (par hôtel / par prédiction / hybrid)
- Priorité Apaleo vs Mews pour la première intégration PMS live
- **[MCP]** Capabilities à exposer en priorité : `forecast_occupancy`, `get_stock_alerts`, `get_fb_kpis`
- **[Agent SEO]** Métriques machine-legible : `tool_success_rate` > 99.5%, `p95_latency` < 500ms, `schema_stability`
## ⚠️ Points d'attention techniques

## Protocole Dev Agent — Définition of Done par Story

Chaque story est confiée à un dev agent autonome. Le protocole est :

## Fichiers clés
- `backend/app/services/` — orchestration IA et logique métier
- `backend/app/integrations/` — Obsidian, Linear, Apaleo
- `backend/app/mcp_server.py` — **[À créer]** MCP Server pour capabilities agent-callable
- `backend/app/middleware/` — **[À créer]** tracking "Agent SEO" (success_rate, latency, retries)
- `scripts/intelligence_report.py` — pipeline veille → Obsidian + Linear
- `scripts/veille_proactive.py` — monitoring hebdomadaire automatisé
- `docs/ARCHITECTURE.md` — design système complet
- `docs/ROADMAP_NOW_NEXT_LATER.md` — roadmap opérationnelle
- `.github/workflows/veille-hebdomadaire.yml` — cron lundi 8h30
1. **Lire** le spec de la Linear issue (via MCP Linear)
2. **Auditer** ce qui existe dans le codebase
3. **Implémenter** la story complète (migration DB, modèle ORM, schemas, service, worker, route)
4. **Tests** — tous les tests doivent passer (CI green)
5. **Commit + Push** sur la branche désignée (`claude/<story-suffix>`)
6. **Ouvrir une PR** contre `main`
7. **Marquer la Linear issue → Done** et poster l'URL de la PR en commentaire

**Gate de merge :** CI vert → merge manuel par le Scrum Master (sans revue de code).

**Gates de qualité supérieurs (hors périmètre dev agent) :**
- Fin d'Epic → revue d'architecture
- Pré-pilote → QA sign-off avec une vraie propriété hôtelière

**Session Scrum Master** (cette session) : dédiée aux sujets de pilotage (backlog, priorités, blockers, process). Ne pas utiliser pour implémenter des stories.

---

## Variables d'environnement requises
```
ANTHROPIC_API_KEY     — sk-ant-...
LINEAR_API_KEY        — lin_api_...
LINEAR_TEAM_ID        — 2f6bb5e2-d735-4769-9377-11fe186aa0ad
OBSIDIAN_VAULT_PATH   — C:/Users/IVAN/OneDrive/Documents/Agentic AI Hospitality
```
1. **ARCHITECTURE.md** : daté de février 2026, certaines sections (Streamlit, Render.com) correspondent à l'ancienne stack — se fier à ce CLAUDE.md pour la stack actuelle.
2. **`.env.example` racine** : appartient à l'ancien backend (`archive/legacy-backend`).
3. **Hébergement** : tout est local Windows ou GitHub. Aucun serveur Linux, aucun Render/Railway.

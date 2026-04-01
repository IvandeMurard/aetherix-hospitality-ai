# CLAUDE.md — Aetherix

> Source de vérité partagée. Chargé automatiquement à chaque session.
> Mettre à jour après chaque décision architecturale importante.
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

---

## Roadmap

| Phase | Statut | Contenu |
|-------|--------|---------|
| Phase 0 | En cours | Architecture FastAPI, modèles DB, Apaleo, WhatsApp |
| Phase 0.5 | Planifié | MCP Server — capabilities agent-callable (HOS-71) |
| Phase 1 | Planifié | Forecasting F&B (Prophet + LLM), alertes WhatsApp, Agent SEO (HOS-72) |
| Phase 2 | Planifié | Agent conversationnel "Receipts" — explications recommandations |
| Phase 3 | Planifié | Multi-hotel, Mews, analytics avancés |

---

## Fichiers clés

```
backend/app/services/          — orchestration IA et logique métier
backend/app/integrations/      — Obsidian, Linear, Apaleo
backend/app/mcp_server.py      — [À créer] MCP Server capabilities
backend/app/middleware/        — [À créer] tracking Agent SEO
scripts/veille_proactive.py    — monitoring hebdomadaire automatisé
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
REDIS_URL             — Upstash (session state)
```

---

## Linear

**Workspace :** Hospitalityagent — toutes les issues dans HOS, jamais dans ivanportfolio/Tacet.
**Team ID :** `2f6bb5e2-d735-4769-9377-11fe186aa0ad`
**Vérification session :** `list_teams` → doit retourner "Hospitalityagent". Si "Tacet" → reconnecter dans claude.ai Settings → Integrations → redémarrer Claude Desktop.

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

---

## Points d'attention

1. `docs/ARCHITECTURE.md` daté fév. 2026 — sections Streamlit/Render.com = ancienne stack. Se fier à ce CLAUDE.md.
2. `.env.example` racine = ancien backend (`archive/legacy-backend`).
3. Hébergement = local Windows ou GitHub. Aucun serveur Linux, Render, Railway.

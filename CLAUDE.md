# CLAUDE.md — Contexte projet Aetherix

## Projet
**Aetherix** — Plateforme IA agentique pour la gestion des opérations F&B hôtelières.
Mission : transformer la gestion proactive du F&B en hôtellerie via des agents IA qui anticipent, alertent et recommandent.

**Stack principale :**
- Backend : FastAPI + PostgreSQL (Supabase) + pgvector (RAG)
- Frontend : Next.js (App Router) + shadcn/ui
- IA : Anthropic Claude (reasoning), agents autonomes
- Intégrations PMS : Apaleo (prioritaire), Mews (secondaire)
- Delivery : WhatsApp (Twilio), Obsidian (knowledge), Linear (issues)

**Philosophie :** "Thin Frontend / Fat Backend" — la logique métier et l'orchestration IA vivent dans le backend.

**Direction stratégique (Mars 2026) :** "Agent-First Distribution" — Aetherix doit être une **primitive appelable par d'autres agents** (MCP Server), pas seulement un produit SaaS avec UI. Distribution = top of call stack, pas top of funnel.

**Contexte concurrent (Mars 2026) :** Apaleo a lancé son propre AI Copilot (A2A, SOPs uploadables) + un MCP Server officiel (sept. 2025). Aetherix doit se positionner comme **agent F&B spécialisé complémentaire** au Copilot Apaleo, pas comme alternative généraliste. MCP est devenu le standard (Lighthouse, OpenAI, Google, MS l'ont adopté).

**Apaleo MCP Server — implications directes :**
- Le MCP Server Apaleo couvre l'intégralité de la plateforme et ses API → **l'intégration Apaleo Phase 0 peut se faire via MCP directement** (pas d'API raw custom nécessaire)
- Use cases couverts par Apaleo : réservations, CRM, housekeeping, paiements. **F&B forecasting/alertes = absent = niche ouverte confirmée**
- **Compatible avec les clients MCP d'Anthropic (plug-and-play)** — Aetherix, construit sur Claude, peut appeler le MCP Server Apaleo directement comme source d'outils, sans code d'intégration custom
- Architecture MACH (Microservices, API-first, Cloud-native, Headless) — flux temps réel, automatisation workflows
- **Agent Hub Apaleo** (première marketplace d'agents IA hôteliers, déjà live) = canal de distribution potentiel pour Aetherix comme agent F&B spécialisé (2 000+ propriétés, 30+ pays) — **trop tôt pour Phase 0, à cibler Phase 1**
- **MCP Alpha Group Apaleo** = à rejoindre maintenant (community.apaleo.com) — accès early + visibilité équipe Apaleo

---

## Session Veille — Instructions

### Mode Réactif (à la demande)
Quand l'utilisateur partage un lien, un document, ou du contenu :
1. Analyser le contenu en profondeur
2. Confronter avec le contexte projet (stack, roadmap, positionnement)
3. **Scorer la pertinence (0-10)** selon les critères ci-dessous
4. **Ne pousser vers Linear et Obsidian QUE si score >= 7/10**
5. Si score < 7 : livrer l'analyse à l'utilisateur uniquement, sans créer d'artefact

**Critères de pertinence pour Linear/Obsidian :**
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
3. **Apaleo** — nouveautés API, partenaires, blog officiel — **⚠️ surveiller l'expansion du Copilot vers le F&B**
4. **Mews** — features, positionnement, acquisitions
5. **Y Combinator** — nouvelles références liées à l'hospitality/F&B/forecasting (ex : Guac.com)
6. **hospitalitynet.org** — articles pertinents publiés dans les 7 derniers jours

**Acteurs à surveiller (ajout Mars 2026) :**
- **DialogShift** (Olga Heuser) — 95%+ automation chat/email/tel hôtels, auteure du WP Agentic AI, avance sur MCP
- **Lighthouse / Connect AI** — premier booking direct dans ChatGPT via MCP, concurrent indirect sur la distribution
- **IDeaS / Duetto** — RMS enterprise (Marriott, Accor), room-only, hors segment PME Aetherix
- **Canary Technologies** — guest management (check-in, upsell), 20K hôtels, adjacent mais pas F&B ops

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
- **[URGENT]** Évaluer compatibilité A2A avec Apaleo Copilot avant de finaliser Phase 0.5
- **[DÉCISION OUVERTE]** Intégration Apaleo : MCP direct vs API raw ? (MCP probable car déjà disponible — analyser les tools exposés)

**Décisions architecturales prises (Mars 2026) :**
- **Apaleo read-only par défaut en Phase 0** — pas d'écriture sur les réservations tant que l'outil n'est pas mature. Loguer toutes les actions agent. (source : WP Toedt/Heuser HOS-107)
- **Feature set forecasting contextuel** — inclure `arrival_time`, `origin_country`, `party_size`, `LOS` comme features de premier ordre, pas juste des métadonnées. (source : EHL Cindy Heo HOS-106)
- **Feedback loop WhatsApp** — prévoir dès Phase 1 un mécanisme thumbs up/down sur les alertes → données d'entraînement. (source : HOS-106)
- **Alertes = recommandations, jamais décisions automatiques en Phase 0** — pour éviter la liability floue. (source : HOS-107)

**Référence architecture :**
- `linq-team/linq-resy-agent` (MIT) — pattern Claude tool-use + webhook + conversation state, à adapter pour Aetherix. (HOS-100)

**Distribution prioritaire (ajout Mars 2026) :**
- **Agent Hub Apaleo** — cibler une entrée comme agent F&B spécialisé dès Phase 1. Rejoindre le MCP Alpha Group maintenant pour préparer cette entrée. (HOS-101)

---

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

---

## Variables d'environnement requises
```
ANTHROPIC_API_KEY     — sk-ant-...
LINEAR_API_KEY        — lin_api_...
LINEAR_TEAM_ID        — 2f6bb5e2-d735-4769-9377-11fe186aa0ad
OBSIDIAN_VAULT_PATH   — C:/Users/IVAN/OneDrive/Documents/Agentic AI Hospitality
```

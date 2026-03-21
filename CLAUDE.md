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
3. **Apaleo** — nouveautés API, partenaires, blog officiel
4. **Mews** — features, positionnement, acquisitions
5. **Y Combinator** — nouvelles références liées à l'hospitality/F&B/forecasting (ex : Guac.com)
6. **hospitalitynet.org** — articles pertinents publiés dans les 7 derniers jours

---

## Roadmap synthétique (pour évaluer la pertinence)
- **Phase 0 (en cours)** : Architecture FastAPI, modèles DB, intégrations de base (Apaleo, WhatsApp)
- **Phase 1** : Forecasting F&B (Prophet + LLM), alertes proactives via WhatsApp
- **Phase 2** : Agent conversationnel "Receipts" — explications des recommandations
- **Phase 3** : Multi-hotel, PMS étendu (Mews), analytics avancés

**Décisions techniques ouvertes :**
- Stratégie d'embedding pour RAG (pgvector vs Qdrant)
- Modèle de pricing SaaS (par hôtel / par prédiction / hybrid)
- Priorité Apaleo vs Mews pour la première intégration PMS live

---

## Fichiers clés
- `backend/app/services/` — orchestration IA et logique métier
- `backend/app/integrations/` — Obsidian, Linear, Apaleo
- `scripts/intelligence_report.py` — pipeline veille → Obsidian + Linear
- `scripts/veille_proactive.py` — monitoring hebdomadaire automatisé
- `docs/ARCHITECTURE.md` — design système complet
- `.github/workflows/veille-hebdomadaire.yml` — cron lundi 8h30

---

## Variables d'environnement requises
```
ANTHROPIC_API_KEY     — sk-ant-...
LINEAR_API_KEY        — lin_api_...
LINEAR_TEAM_ID        — UUID équipe Linear
OBSIDIAN_VAULT_PATH   — C:/Users/IVAN/OneDrive/Documents/Agentic AI Hospitality
```

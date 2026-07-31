# 📚 Index de la documentation — Aetherix

> Catalogue de la documentation **vivante** de `docs/`, classée par sous-catégorie. Chargé sur demande (pas automatiquement).
> **Convention :** facts de session → `CLAUDE.md` ; contexte narratif & détaillé → ici et dans les fichiers ci-dessous.
> **Élagage 08/07/2026 (Story 16.2 / HOS-302)** : 292 → ~51 fichiers vivants. Docs de phases terminées, stratégies périmées et vieux rapports → [`docs/_archive/`](_archive/) (rien n'est supprimé). Framework BMad → `tools/bmad/` (outillage, pas de la doc projet).
> ⚡ Priorité inter-nœuds : `mesh-architecture.md` (vérité cross-repos).

---

## 🔒 Convention « local-only » (élagage du 30/07/2026)

Le dépôt ne porte plus que **le code et la documentation vivante**. Trois ensembles restent **sur disque mais hors versionnement** — ils sont toujours présents dans l'historique Git, seulement plus dans les commits à venir :

| Chemin | Contenu | Pourquoi hors dépôt |
|--------|---------|---------------------|
| `docs/veille/` | Veilles hebdomadaires | Source de vérité = vault Obsidian `Agentic AI Hospitality/Veille/` (acté 10/07, CLAUDE.md §Obsidian) |
| `docs/_archive/` | 47 fichiers : anciennes veilles, **`monitoring-watchlist.md`**, MVP_SCOPE, Problem_Statement, ROADMAP, presentation, `internal/`, `handoff/` | Archive de phases closes |
| `tools/bmad/_bmad/` | Install BMAD vendorée (233 fichiers) | Outillage tiers réinstallable. **`tools/bmad/_bmad-output/` reste versionné** — il porte les stories. |

> ⚠️ **Migration de la veille incomplète.** CLAUDE.md déclare depuis le 10/07 que le vault Obsidian `Veille/` est la source de vérité unique pour « hebdo + watchlist + analyses concurrentielles ». Les hebdos y sont bien (8 notes thématiques + index + canvas), **mais la watchlist n'y a jamais été portée** — elle est restée dans `docs/_archive/context/monitoring-watchlist.md`. Le canari W2 et ses triggers n'ont donc pas de foyer dans la source de vérité déclarée. **À reprendre côté Obsidian.**

**⚠️ Lecture des références.** Plusieurs docs en ligne — `CLAUDE.md`, `AGENTS.md`, `context/open-decisions.md`, `context/decisions-architecturales.md`, `adr/0006`, `adr/0008`, `marketing/positioning-snippets.md`, `Cost_Model.md` — citent encore `monitoring-watchlist.md`, `docs/veille/` ou `docs/_archive/`. **Ces liens sont valides en local et ne sont pas des drifts** : ils pointent vers des fichiers présents sur la machine, absents du dépôt distant. Un clone frais ne les résoudra pas.

> **Note pour l'agent d'hygiène ([HOS-320](https://linear.app/hospitalityagent/issue/HOS-320))** : ne pas signaler ces trois chemins comme références cassées. C'est une règle d'exclusion à ajouter, pas un drift à corriger.

**Le canari concurrentiel W2 (Apaleo Copilot scope F&B) vit désormais hors dépôt.** Sa re-vérification trimestrielle est fixée au **30/10/2026** (voir `context/apaleo-a2a-spike-decision.md` §Conditions de bascule, qui reste en ligne). Ne pas compter sur le dépôt pour la rappeler.

---

## 🏛️ Architecture
- `ARCHITECTURE.md` — pointeur architecture (v0.3.0, 07/07/2026) : où trouver quoi + résumé 10 lignes. La vérité vit dans CLAUDE.md / mesh-architecture.md / ADRs
- `mesh-architecture.md` — **SOURCE DE VÉRITÉ CROSS-REPOS** (Mesh : Aetherix + Tacet + Orchestrateur + Anima)
- `adr/` — Architecture Decision Records (11) :
  - `0001-aetherix-mcp-server-v0` · `0002-memory-instrumentation` · `0003-agent-observability-and-metering` · `0004-orchestrator-separation`
  - `0006-pos-integration` · `0007-evaluation-by-design` · `0008-context-graph` · `0009-runtime-guardrails`
  - `0010-multi-repo-strategy` · `0011-learning-engine-hive-v2` · `0012-mesh-signal-contract` (**privé à jamais**, Décision #31)

## 🧭 Context (détail par domaine)
- `context/decisions-architecturales.md` — détail des 31 décisions (index 1-ligne dans CLAUDE.md)
- `context/open-decisions.md` — décisions ouvertes + archive des résolues
- `context/analyse-critique-2026-07.md` — **audit critique complet Aetherix+Tacet (07/07/2026)** : chaîne de valeur 5 maillons, circularité MAPE synthétique, différenciation, wedge/moat, risques crédibilité
- `context/positionnement-wedge.md` — **le wedge acté (09/07)** : "mémoire opérationnelle, le forecast est un organe" — référence pour tout support externe (case study, méta-repo, article, LinkedIn) + discipline de langage
- `context/moat.md` — **ce qui est défendable, testé contre la menace plateforme** (09/07) : 4 couches de moat + stress test "et si Apaleo/Mews shippent un forecast natif ?" + risque résiduel nommé
- `context/data-conventions.md` — convention tenant_id/property_id/hotel_id + table des drifts (HOS-163)
- `context/memory-architecture.md` — Private + Hive Memory (Décision #2)
- `context/vision-future.md` — vision long terme (Phase 5, Mesh, Aetherix Voice)
- `context/demo-apaleo.md` — Demo PRD Apaleo + résultats probe sandbox (HOS-190 AC1)
- `context/mape-benchmark.md` (+ `mape-benchmark-holdout.json`) — **benchmark données réelles Recruit (08/07, HOS-307)** : naïve vs Prophet vs LightGBM, MAPE+MdAPE J+1→J+7, verdict AC4 nuancé · l'ancien 15.09 % synthétique = circulaire, gate interne uniquement
- `context/runbook-pre-pilot.md` — checklist pré-pilote
- `context/llm-provider-strategy-review-2026-06.md` — revue stratégie reasoning Sonnet/fallback/Haiku + HITL
- `context/linear-conventions.md` — protocole Epic/Story Linear
- `context/security-review-2026-05-01.md` — audit sécurité mai (clôturé, Epic 12)
- `context/security-review-2026-Q2.md` — audit différentiel pré-pilote Q2 (CLOSED, Décision #30)

## 🗺️ Planning
- `planning/plan-90j-proof-visibility.md` — **plan actif (Epic 16, HOS-300)** : preuve empirique + visibilité, juil.→oct. 2026, phases A→E + draft ticket GitHub Support
- `planning/protocole-de-preuve.md` — **protocole de preuve pré-enregistré (HOS-316)** : baseline, horizon de décision, métriques, seuils d'arrêt — GELÉ, s'applique à HOS-308/309/312 (HOS-307 hors garantie, §0)
- `planning/phase-3-pilot-validation.md` · `planning/phase-3-sprint-plan.md` — Phase 3 pilote
- `planning/pilot-readiness-test-plan.md` — test plan readiness pilote (Epic Pilot-Readiness)
- `planning/evaluation-by-design.md` — plan d'implémentation eval-by-design (Décision #22, ADR-0007)
- `planning/hos-190-manual-runbook.md` — runbook manuel HOS-190
- Phases 0-2 terminées → `_archive/planning/`

## 🚀 Pilot & Ops
- `pilot/onboarding-kit.md` · `pilot/outreach-template.md` · `pilot/credentials-sop.md`
- `ops/latency-slo.md` — SLO latence · `ops/llm-fallback-runbook.md` — runbook fallback LLM
- `SECURITY/secrets_handling.md` · `SECURITY/secrets_rotation_playbook.md`

## 🧪 Testing & MCP
- `testing/e2e-apaleo-sandbox.md` (+ `testing/evidence/`) — E2E sandbox Apaleo
- `mcp/getting-started.md` — consommer le MCP server Aetherix
- `demos/README.md` — démos disponibles + closed-loop (`scripts/ops/closed_loop_demo.py`, sortie gitignorée `eval/reports/`)

> **📣 Marketing/contenu = hors repo (09/07/2026).** Case study prompt, article, kit LinkedIn, posts LinkedIn/X, storyboard démo, transcript, memory tour, fiches : tout vit dans l'Obsidian vault `Aetherix - Marketing`. Le repo garde l'analyse stratégique (`context/positionnement-wedge.md`, `context/moat.md`) et `marketing/positioning-snippets.md` (exception : cité comme provenance de décisions par ADR-0006 / open-decisions).
>
> **📡 Veille/Competitive = hors repo (10/07/2026).** Élargissement de la décision ci-dessus : toute la veille (hebdo + watchlist + analyses concurrentielles dédiées, y compris `competitive/concurrence.md`) vit désormais dans l'Obsidian vault, dossier `Veille/` (`Veille_Competitors_Market.md`, `Veille_Index.md`). Les anciens `docs/veille/`, `docs/_archive/context/monitoring-watchlist.md`, `docs/competitive/*` sont archivés → `_archive/veille/`, `_archive/context/monitoring-watchlist.md`, `_archive/competitive/` (historique git préservé, citations ADR/decisions-architecturales restent valides vers ces chemins archivés). **Non résolu à date** : le cron `.github/workflows/veille-hebdomadaire.yml` (lundi 07h30 UTC, `scripts/ops/veille_proactive.py`) continue de générer/committer `docs/veille/draft-*.md` — tourne sur runners GitHub cloud, sans accès au vault local. Décision à prendre : désactiver ou garder comme générateur brut à recopier manuellement.

## 🗄️ Hors docs/
- `tools/bmad/` — framework BMad (agents SM/Dev/PM/QA…) — outillage, référencé par CLAUDE.md §BMad
- `docs/_archive/` — tout ce qui précède les jalons actuels : phases 0-2, stratégies pré-Mesh (Problem_Statement, MVP_SCOPE, ROADMAP_NOW_NEXT_LATER, MARKET_INTELLIGENCE, AI_CONTEXT_LAYER, DEPLOYMENT/TROUBLESHOOTING pré-Fly), audits internes mai, veille mars/avril + juin/juillet (`_archive/veille/`), watchlist (`_archive/context/monitoring-watchlist.md`), analyses concurrentielles (`_archive/competitive/`)
- `docs/metrics/` · `docs/linear/` — artefacts JSON historiques (backtest avril, import Linear)

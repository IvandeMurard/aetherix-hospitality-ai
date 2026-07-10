# 📚 Index de la documentation — Aetherix

> Catalogue de la documentation **vivante** de `docs/`, classée par sous-catégorie. Chargé sur demande (pas automatiquement).
> **Convention :** facts de session → `CLAUDE.md` ; contexte narratif & détaillé → ici et dans les fichiers ci-dessous.
> **Élagage 08/07/2026 (Story 16.2 / HOS-302)** : 292 → ~51 fichiers vivants. Docs de phases terminées, stratégies périmées et vieux rapports → [`docs/_archive/`](_archive/) (rien n'est supprimé). Framework BMad → `tools/bmad/` (outillage, pas de la doc projet).
> ⚡ Priorité inter-nœuds : `mesh-architecture.md` (vérité cross-repos).

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
- `context/monitoring-watchlist.md` — signaux à réévaluer à chaque phase (watchlist compétitive)
- `context/security-review-2026-05-01.md` — audit sécurité mai (clôturé, Epic 12)
- `context/security-review-2026-Q2.md` — audit différentiel pré-pilote Q2 (CLOSED, Décision #30)

## 🗺️ Planning
- `planning/plan-90j-proof-visibility.md` — **plan actif (Epic 16, HOS-300)** : preuve empirique + visibilité, juil.→oct. 2026, phases A→E + draft ticket GitHub Support
- `planning/phase-3-pilot-validation.md` · `planning/phase-3-sprint-plan.md` — Phase 3 pilote
- `planning/pilot-readiness-test-plan.md` — test plan readiness pilote (Epic Pilot-Readiness)
- `planning/evaluation-by-design.md` — plan d'implémentation eval-by-design (Décision #22, ADR-0007)
- `planning/hos-190-manual-runbook.md` — runbook manuel HOS-190
- Phases 0-2 terminées → `_archive/planning/`

## 📡 Veille
- `veille/digest-2026-Q1-avril.md` — digest compressé mars/avril (originaux → `_archive/veille/`)
- `veille/2026-06-*.md` · `veille/2026-07-*.md` — rapports du trimestre courant
- Automatisation : `.github/workflows/veille-hebdomadaire.yml` (lundi 8h30) · `scripts/ops/veille_proactive.py`

## 🥊 Competitive
- `competitive/concurrence.md` — **concurrence frontale F&B (09/07)** : Nory/Tenzo/5-Out/Avero, pourquoi le F&B hôtelier reste ouvert (restaurant-first + BI-first vs memory-led), où ils sont devant honnêtement
- `competitive/apaleo-mcp-mapping.md` · `conduit-ai-analysis.md` · `grevon-analysis.md` · `otelai-analysis.md` · `th1-ai-analysis.md` · `travelos-mcp-analysis.md`

## 🚀 Pilot & Ops
- `pilot/onboarding-kit.md` · `pilot/outreach-template.md` · `pilot/credentials-sop.md`
- `ops/latency-slo.md` — SLO latence · `ops/llm-fallback-runbook.md` — runbook fallback LLM
- `SECURITY/secrets_handling.md` · `SECURITY/secrets_rotation_playbook.md`

## 🧪 Testing & MCP
- `testing/e2e-apaleo-sandbox.md` (+ `testing/evidence/`) — E2E sandbox Apaleo
- `mcp/getting-started.md` — consommer le MCP server Aetherix
- `demos/README.md` — démos disponibles
- `demos/demo-kit.md` — **kit de démo closed-loop (HOS-310)** : commandes, 3 écrans, moments clés J10/J15/J17, chiffres autorisés vs interdits, thèse cognitive — LE doc à ouvrir le jour du tournage
- `demos/closed-loop-video-storyboard.md` · `demos/whatsapp_transcript.md` · `demos/closed_loop_demo.{md,json}` — séquencier 3 min, fil WhatsApp généré, rapport + ledger

## 📣 Marketing
- `marketing/CASE_STUDY_UPDATE.md` — prompt case study public (v2 09/07 en tête : récit mémoire opérationnelle, chiffres réels, slots vidéo/Logfire)
- `marketing/article-operational-memory.md` — **draft article à publier** : "Operational memory is the moat AI wrappers don't have" (Dev.to/Medium)
- `marketing/linkedin-experience.md` — **kit LinkedIn** : expérience EN/FR + headline + à-propos alignés wedge, règles chiffres autorisés/interdits
- `marketing/social-posts.md` — **banque de posts LinkedIn + X** (fil mémoire Aetherix/Anima/Lore · évaluation · living operational architecture) — prêts à publier, courts, cadence conseillée
- `marketing/positioning-snippets.md` — snippets de positionnement
- `marketing/fiches/` — fiches RAG (html/pdf)

## 🗄️ Hors docs/
- `tools/bmad/` — framework BMad (agents SM/Dev/PM/QA…) — outillage, référencé par CLAUDE.md §BMad
- `docs/_archive/` — tout ce qui précède les jalons actuels : phases 0-2, stratégies pré-Mesh (Problem_Statement, MVP_SCOPE, ROADMAP_NOW_NEXT_LATER, MARKET_INTELLIGENCE, AI_CONTEXT_LAYER, DEPLOYMENT/TROUBLESHOOTING pré-Fly), audits internes mai, veille mars/avril
- `docs/metrics/` · `docs/linear/` — artefacts JSON historiques (backtest avril, import Linear)

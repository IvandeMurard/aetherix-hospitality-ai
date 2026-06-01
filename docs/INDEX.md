# 📚 Index de la documentation — Aetherix

> Catalogue de toute la documentation `docs/`, classée par sous-catégorie.
> Chargé **sur demande** (pas automatiquement) — CLAUDE.md ne garde que les pointeurs de code + le lien vers cet index, afin de rester sous son budget de ~150 lignes.
> **Convention :** facts de session → `CLAUDE.md` ; contexte narratif & détaillé → ici et dans les fichiers ci-dessous.
> ⚡ Priorité inter-nœuds : `mesh-architecture.md` (vérité cross-repos).

---

## 🏛️ Architecture
- `ARCHITECTURE.md` — design système (v0.2.0 ; sections Streamlit/Render obsolètes, se fier à CLAUDE.md)
- `mesh-architecture.md` — **SOURCE DE VÉRITÉ CROSS-REPOS** (Mesh : Aetherix + Tacet + Orchestrateur + Anima)
- `AI_CONTEXT_LAYER.md` — couche de contexte IA
- `adr/` — Architecture Decision Records :
  - `0001-aetherix-mcp-server-v0.md` · `0002-memory-instrumentation.md` · `0003-agent-observability-and-metering.md` · `0004-orchestrator-separation.md` · `0005-cold-start-meta-learner.md`

## 🧭 Context (détail par domaine)
- `context/data-conventions.md` — convention tenant_id/property_id/hotel_id + table des drifts (HOS-163)
- `context/memory-architecture.md` — Private + Hive Memory (Décision #2)
- `context/strategy.md` · `context/vision-future.md` — stratégie & vision long terme
- `context/demo-apaleo.md` — Demo PRD Apaleo + résultats probe sandbox (HOS-190 AC1)
- `context/mape-benchmark.md` (+ `mape-benchmark-holdout.json`) — gate MAPE J+1 (Décision #14)
- `context/runbook-pre-pilot.md` — checklist pré-pilote
- `context/linear-conventions.md` — protocole Epic/Story Linear
- `context/open-decisions.md` — miroir détaillé des décisions ouvertes
- `context/veille.md` · `context/watchlist.md` — contexte veille & signaux long terme

## 🗺️ Planning & Roadmap
- `ROADMAP_NOW_NEXT_LATER.md` — roadmap opérationnelle (Now / Next / Later)
- `MVP_SCOPE.md` — périmètre MVP
- `planning/phase-0-1-execution-plan.md` · `planning/phase-0-retro.md`
- `planning/phase-2-agent-receipts.md` · `planning/phase-2-gate-runbook.md`
- `planning/phase-3-pilot-validation.md` · `planning/sprint-phase3-j1-j10.md`
- `planning/hos-190-manual-runbook.md` — runbook manuel HOS-190 (AC1/AC4/AC5/AC6)

## 📡 Veille
- `veille/` — rapports hebdo (`report-*.md`, `AAAA-MM-JJ-veille.md`) + drafts (`draft-*`)
- `context/watchlist.md` — signaux à réévaluer à chaque phase
- Automatisation : `.github/workflows/veille-hebdomadaire.yml` (lundi 8h30) · `scripts/ops/veille_proactive.py`

## 📣 Marketing & Sales
- `marketing/CASE_STUDY_UPDATE.md` — prompt Lovable, case study public aligné vision Mesh
- `marketing/SALES-Pitch-Update-Q3.md` — mise à jour pitch Q3 2026
- `presentation.md` · `demo_script.md` · `WALKTHROUGH_APALEO.md` — supports démo
- `Problem_Statement.md` · `MARKET_INTELLIGENCE.md` — positionnement & marché

## 🔌 MCP
- `mcp/getting-started.md` — démarrage MCP
- Code associé : `backend/app/mcp_server.py` (MCP v0, 3 tools)

## 📊 Metrics & Benchmarks
- `metrics/backtest_2026-04-17.json` (+ `.png`) · `metrics/benchmark_2026-04-19.json`
- `context/mape-benchmark.md` — gate MAPE J+1

## 🔐 Security
- `SECURITY/secrets_handling.md` — gestion des secrets (Fly.io)
- `SECURITY/secrets_rotation_playbook.md` — rotation & purge d'historique

## 🚀 Deployment & Ops
- `DEPLOYMENT.md` — déploiement Fly.io (Décision #17)
- `TROUBLESHOOTING.md` — dépannage
- `Cost_Model.md` — modèle de coûts

## 🎬 Demos & Assets
- `demos/README.md` — assets démo (screenshot Receipt, recording 60s — HOS-190 AC4/AC5)
- `assets/` — diagrammes (`architecture-*.svg`, `aetherix_future_vision_architecture_v4.svg`), logos, `demo_board.html`

## 🧪 Internal / Reviews
- `internal/PHASE_0_REVIEW.md` · `internal/validation_report.md` · `internal/integration_report.md`
- `internal/aetherix_brutal_feedback.md` · `internal/IMPROVEMENT_RECOMMENDATIONS.md`

## 📐 BMad
- `bmad/_bmad/` — agents BMad (sm, dev, architect, pm, analyst, qa, tech-writer)
- `bmad/_bmad-output/` — artefacts (`planning-artifacts/`, `implementation-artifacts/`)

## 🔗 Linear
- `context/linear-conventions.md` — conventions Epic/Story (DoD, labels, statuts)
- `linear/import-phase-0-1.json` — import initial Phase 0/1

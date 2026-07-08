# Aetherix — Plan d'exécution Phase 0 → Phase 1

> **Status**: Draft v1 — 17 avril 2026
> **Owner**: SM (Bob)
> **Source**: `docs/roadmap/epics-phase-0-3.md` (branche `claude/review-feedback-epic-c4puU`) + directive PM (Ivan) intégrant le tweet Benioff (headless pour agents) + scope side-project réaliste.
> **Branche d'exécution**: `claude/aetherix-market-analysis-5JiJ1` (unique, tout commit atomique).
> **Usage**: artefact SM qui traduit la roadmap en plan d'attaque agent/model/sprint pour exécution post-reset budget.

---

## 1. Interprétation du bump "headless positioning"

La directive PM redéfinit le gate Phase 0 pour y **inclure** le ship de HOS-71 (Aetherix MCP Server v0) — plus seulement du backtesting. Rationale : Benioff/Levie ont fait de "headless for agents" le nouveau standard ; rester human-in-the-loop-only = plafond d'adoption.

**Mais avec un sous-gate interne** : si MAPE > 20-22% ou lift mémoire négligeable sur P0-2, on **repositionne avant** de shipper le MCP Server. Donc la séquence est :

```
Sprint A (Validation technique)  →  [GATE interne métriques]  →  Sprint B (Shippable)  →  [GATE externe: 1 agent tiers]  →  Phase 1 Done
     P0-1, P0-2                                                      P0-3, P1-1, P1-2
```

Conséquence : les stories `P1-1` (architect MCP) et `P1-2` (MCP Server v0) de la roadmap originale sont **remontées dans le périmètre Phase 0** au sens "definition of done Phase 0". Leurs IDs Linear restent inchangés.

---

## 2. Priorité ordonnée & allocation agent/model

### Sprint A — Validation technique (critique, bloqueur #1)

| Ordre | Story | Bloqueur | Agent | Model | Estimate |
|-------|-------|----------|-------|-------|----------|
| 1 | **P0-1** Prophet orchestrator endpoint | Oui (bloque tout le reste) | Dev (Amelia) | **Sonnet 4.6** | 5-8 j/h |
| 2 | **P0-2** Backtest 30-90j + KPIs Niveau 1 + ablation | Dépend de #1 | Dev (Amelia) | **Sonnet 4.6** | 3-5 j/h |

**Audit préalable confirmé** :
- `backend/app/api/routes/predictions.py:36` expose déjà `POST /predict` (agent-facing) mais PAS `POST /predictions/train`. P0-1 reste à créer.
- `scripts/train_prophet.py:20` importe `backend.ml.prediction_engine` (path legacy, cassé). Ne pas réutiliser tel quel — re-wirer via `backend.app.services.apaleo_mcp_adapter` + `data_transformer` + `prediction_engine`.
- `backend/app/services/roi_calculator.py` existe déjà → P0-3 = juste endpoint + page web, pas from-scratch.

### GATE interne (PM trigger)

Critères pour débloquer Sprint B (copie des critères PM, durcis) :

- [ ] MAPE moyen **< 18%** sur couverts dîner ET petit-déjeuner, backtest rolling 30-90j
- [ ] Cible ambitieuse : **< 15%** sur ≥ 70% des jours
- [ ] Labor cost variance directionnel **entre −8% et +3%** vs baseline simple
- [ ] Directional accuracy **≥ 75%**
- [ ] Ablation idiosyncratic memory → **lift directionnel > 0** (même modeste), documenté
- [ ] Documentation publique : `docs/metrics/backtest_YYYY-MM-DD.json` + charts PNG + section "Assumptions & limitations" dans README

**Kill criterion** : si MAPE > 22% ou ablation lift = 0 → pivot vers "MCP-powered hospitality forecasting adapter" (annule Sprint B, va direct Sprint C portfolio). Pas de honte, c'est une option valide.

### Sprint B — Shippable si gate vert

| Ordre | Story | Agent | Model | Rationale model | Estimate |
|-------|-------|-------|-------|-----------------|----------|
| 3 | **P0-3** ROI calculator public | Dev (Amelia) | **Sonnet 4.6** | Endpoint + page thin, pas de décision durable | 2-3 j/h |
| 4 | **P1-1** Architect session MCP Server (ADR) | Architect (Winston) | **Opus 4.7** | Décisions cross-cutting durables (transport stdio/HTTP, auth scoping, isolation multi-tenant, tool surface, versioning). Jugement architectural required. | 1 j/h |
| 5 | **P1-2** Aetherix MCP Server v0 (3 tools) | Dev (Amelia) | **Sonnet 4.6** | Impl avec ADR figé, pas de design décision | 8-12 j/h |
| 6 | Tests + CI MCP Server | QA | **Sonnet 4.6** | Exécution tests, pas design | 2-3 j/h |

**Tool surface v0** (à graver dans l'ADR P1-1, copie de la directive PM) :
1. `get_operational_predictions` — prédictions couverts/staffing par property + date range, avec confidence intervals
2. `get_recommendations_with_memory_context` — recommandations avec reasoning trace Claude + memory layer trace
3. `submit_feedback_to_memory` — override manager actual-vs-predicted → update pgvector idiosyncratic layer

### GATE externe

- [ ] ≥ 1 agent externe (Claude Desktop, custom client) appelle chaque tool et reçoit output memory-augmented valide
- [ ] Démo vidéo 2 min publiée (embedding dans README)
- [ ] Latence p95 `get_operational_predictions` < 2s
- [ ] Rate limiting + auth par property_id fonctionnels

→ Si vert : **Phase 0 officiellement DONE** (au sens de la directive PM amendée).

### Sprint C — Portfolio & soutenabilité (parallélisable dès Sprint B vert)

| Ordre | Story | Agent | Model | Estimate |
|-------|-------|-------|-------|----------|
| 7 | **P0-4** PM retro draft (phase-0-lessons) | Tech Writer | **Sonnet 4.6** | 1-2 j/h |
| 8 | **P3-1** Démo vidéo 3 min | PM (Ivan) + Tech Writer | Sonnet pour script | 1-2 j/h |
| 9 | **P3-4** README "recruiter-friendly" | Tech Writer | **Sonnet 4.6** | 1 j/h |
| 10 | ADR `0003-headless-positioning.md` (narrative Benioff) | Architect (Winston) | **Opus 4.7** | 0.5 j/h |

### Phase 1 vraie (post-gate externe)

Stories restantes de `HOS-EPIC-P1` à exécuter après Phase 0 bouclée :

| Story | Agent | Model | Dépendance |
|-------|-------|-------|------------|
| P1-3 Memory instrumentation per-layer | Dev | Sonnet 4.6 | P1-2 done |
| P1-4 Forecast benchmark Prophet vs alt | Dev (impl) + Architect (décision swap) | Sonnet + **Opus 4.7** pour décision finale | P0-2 done |
| P1-5 Agent SEO HOS-72 | Dev | Sonnet 4.6 | Parallèle, indépendant |

---

## 3. Allocation model — règle de décision

| Situation | Model | Pourquoi |
|-----------|-------|----------|
| Planning sprint, priorisation, plans d'attaque | **Opus 4.7** (moi, SM) | Jugement cross-cutting |
| Décisions architecturales durables (ADR, transport MCP, hive GDPR, swap forecasting) | **Opus 4.7** via Architect | Décisions cadrées dans CLAUDE.md §Décisions — demandent raisonnement profond |
| Implémentation code avec spec claire (endpoint, service, worker) | **Sonnet 4.6** via Dev | Workhorse, bon ratio coût/qualité |
| Tests, CI, QA | **Sonnet 4.6** via QA | Exécution, pas design |
| Docs (retro, README, case study) | **Sonnet 4.6** via Tech Writer | Rédaction structurée |
| Revue de merge fin de sprint | **Opus 4.7** via Architect, ponctuel | Filet de sécurité |
| Tâches triviales (rename, CSV) | Haiku 4.5 | Budget (aucune dans le plan actuel) |

**Règle stricte** : ne pas activer Opus pour du code d'implémentation pure. Réserver aux moments où une mauvaise décision coûte > 1 jour de rework.

---

## 4. Branche & workflow git

- Tout sur `claude/aetherix-market-analysis-5JiJ1`
- Commits atomiques par story (ex: `feat(p0-1): add POST /predictions/train orchestrator`)
- PR contre `main` à la fin de chaque sprint (A, B, C) avec CI verte obligatoire
- Pas de merge sans au moins un pass CI complet (pytest + lint)

---

## 5. Artefacts Linear à créer (pendant la planification)

**Note** : dans cette session Claude Code, le MCP Linear n'est pas connecté (seul GitHub MCP est disponible). Je génère les EPICs + stories sous forme de fichier importable que l'utilisateur peut traiter via :
- (a) script Python dédié (`scripts/linear_import.py` à créer) utilisant `LINEAR_API_KEY` env var
- (b) prompt SM exécuté depuis Claude Desktop qui a Linear MCP connecté

Drafts à produire post-reset dans `docs/linear/import-phase-0-1.json` :
- 2 EPICs : `HOS-EPIC-P0`, `HOS-EPIC-P1`
- Stories Phase 0 : P0-1, P0-2, P0-3, P0-4
- Stories Phase 1 : P1-1, P1-2, P1-3, P1-4, P1-5 (ou link existant HOS-71 / HOS-72)
- Stories Phase 3 (portfolio parallèle) : P3-1, P3-4

Format JSON :
```json
{
  "epics": [
    {"external_id": "HOS-EPIC-P0", "title": "...", "description": "...", "labels": [...], "priority": "urgent"}
  ],
  "stories": [
    {"external_id": "HOS-P0-1", "parent": "HOS-EPIC-P0", "title": "...", "description": "...", "labels": [...], "priority": "urgent", "estimate_days": 6, "depends_on": []}
  ]
}
```

---

## 6. Risques & dépendances consolidés

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| P0-1 MAPE échoue (> 22%) sur données hybrides sandbox+synthétique | Moyen | Bloque tout Sprint B | Pivot documenté, Sprint C only. Pas de honte. |
| `scripts/train_prophet.py` cassé (path legacy) entraîne confusion dans P0-1 | Certain | Faible (1-2h rework) | Réécrire le script from scratch OU le marquer deprecated |
| Linear MCP pas dispo dans cette session → création manuelle requise | Certain | Faible | Générer fichier import JSON, user exécute via Claude Desktop ou script |
| Scope creep MCP Server v0 (plus de 3 tools) | Moyen | Dette technique | Gate AC : exactement 3 tools, pas plus |
| Architect session P1-1 déborde (analysis paralysis) | Moyen | Retarde Sprint B | Timebox 1 jour max, ADR 3-5 pages max |
| Données sandbox Apaleo insuffisantes (< 60j) | Faible | Bloque backtest | Fallback 100% synthétique, tagger explicitement |
| Coût LLM Sprint B explose | Moyen | Budget | Rate limit + cost cap par property dès P1-2, logué |

---

## 7. Checklist post-reset (ordre d'exécution)

**Action 0** (SM, immédiat après reset) :
- [x] Ce document commité sur `claude/aetherix-market-analysis-5JiJ1`
- [ ] Générer `docs/linear/import-phase-0-1.json` (drafts EPICs + stories)
- [ ] Ajouter une ligne dans CLAUDE.md §Décisions architecturales : "#14 — Phase 0 amendée : ship MCP Server v0 inclus dans DoD Phase 0 (suite directive PM 17/04/2026 intégrant tweet Benioff)"

**Action 1** (SM puis Dev) :
- [ ] Activer Agent Dev (Amelia) sur **P0-1**
- [ ] Sous-branche ? Non — commit direct sur `claude/aetherix-market-analysis-5JiJ1` selon directive PM
- [ ] DoD P0-1 : endpoint `POST /predictions/train` fonctionnel, test intégration < 5 min sur 365j synthétique, audit log Supabase, README flow diagram

**Action 2** (Dev) :
- [ ] P0-2 backtest + KPIs publication

**Action 3** (PM trigger — GATE interne) :
- [ ] PM (Ivan) valide les métriques contre les critères §2 ci-dessus
- [ ] Si vert : lancer Sprint B. Si rouge : lancer Sprint C pivot.

**Action 4** (Architect) :
- [ ] Activer Agent Architect (Winston) sur P1-1 → ADR `docs/adr/0001-aetherix-mcp-server-v0.md`

**Action 5** (Dev + QA) :
- [ ] P1-2 ship MCP Server v0

**Action 6** (PM trigger — GATE externe) :
- [ ] Test 1 agent externe + démo vidéo → Phase 0 officiellement DONE

---

## 8. Sources

- `docs/roadmap/epics-phase-0-3.md` (branche `claude/review-feedback-epic-c4puU`)
- CLAUDE.md §Décisions architecturales #1-#13, §KPI framework
- Directive PM 17/04/2026 (tweet Benioff `https://x.com/Benioff/status/2044981547267395620`)
- Audit codebase 17/04/2026 : `backend/app/api/routes/predictions.py`, `scripts/train_prophet.py`

---

**Fin du plan. Prochaine action post-reset : Action 0 (générer drafts Linear + amender CLAUDE.md).**

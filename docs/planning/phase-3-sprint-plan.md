# Phase 3 — Sprint Plan unifié

> **Status**: Active · **Date**: 2026-06-03 · **Owner**: Ivan (solo dev) · **Re-evaluate**: chaque vendredi
> **Sources**: [`phase-3-pilot-validation.md`](phase-3-pilot-validation.md) (Epic 10) · [`evaluation-by-design.md`](evaluation-by-design.md) (Epic 11) · audit explicabilité/traçabilité 2026-06-03 (HOS-200/201/202)
> **Dépendance externe critique** : démo Loop ≤ 2026-06-10 → arbitre S1.

---

## Constantes calendaires connues

| Jalon | Date | Verrou |
|-------|------|--------|
| Démo Loop | ≤ 2026-06-10 | Polish UX requis avant |
| Pilot Apaleo prod (HOS-176) | Variable — dépend réponses prospects HOS-175 AC4 | Manuel Ivan |
| Pilot gate technique | Après EVAL-0 + 1 + 2 + 4 mergées | ~3 semaines de code |

---

## Timeline 4 sprints

### S1 — 2026-06-03 → 2026-06-09 · "Démo polish + traçabilité"

| Story | Pts | Effort | Pourquoi maintenant |
|-------|----:|--------|---------------------|
| **HOS-201** named events | 1 | 0.5j | Polish UX immédiat — la démo doit montrer "PSG vs Arsenal" pas "2 events" |
| **HOS-200** actual_covers persist | 2 | 1.5j | Ouvre la traçabilité — invisible démo mais critique pilot |
| Démo Loop prep | — | 1-2j | Slides + script + répétition |
| _Manuel parallèle_ | — | — | Envoyer outreach 3 prospects (HOS-175 AC4) |

**Total** : 3 pts code + démo + outreach. EVAL-0 **attend S2**.

### S2 — 2026-06-10 → 2026-06-16 · "Foundation eval"

| Story | Pts | Effort |
|-------|----:|--------|
| **HOS-204 EVAL-0** Golden Dataset + Failure Definitions + Prompts extraction | 3 | 2.5j |
| _Manuel parallèle_ | — | Discovery calls prospects intéressés |

**Total** : 3 pts. BLOCKING — pas de code parallèle dans Epic 11 cette semaine.

### S3 — 2026-06-17 → 2026-06-23 · "Pilot gate + traçabilité finale"

3 PRs distinctes, zones de code disjointes — parallélisables :

| Story | Pts | Effort | Zone |
|-------|----:|--------|------|
| **HOS-205 EVAL-1** stratified MAPE + CI gate | 2 | 1.5j | `scripts/eval/eval_forecast.py` |
| **HOS-206 EVAL-2** AgentAbstention + i18n + telemetry | 3 | 2.5j | `abstention.py` + `i18n/` + migration |
| **HOS-208 EVAL-4** Parser Haiku + FakeIntentClassifier | 2 | 1.5j | `eval_parser.py` |
| **HOS-202** MAPE weekly digest (débloquée par HOS-200) | 2 | 1.5j | `receipts.py` `weekly_digest` |

**Total** : 9 pts ≈ 7j cumulés. Charge soutenue — possiblement déborder sur S4 selon réponses pilote.

> ⚠️ **Conflit migration HOS-200 ↔ EVAL-2** : HOS-200 a ajouté `actual_covers_*` à `StaffingRecommendation`. EVAL-2 ajoute `abstention_*` + `eval_run_id` + `drift_score` à `agent_action_log`. **Tables différentes → pas de conflit réel**, mais séquencer migrations dans l'ordre numérique (timestamps).

### S4 — 2026-06-24 → 2026-06-30 · "Pilot deploy + clôture eval"

| Story | Pts | Conditionnel |
|-------|----:|--------------|
| **HOS-176** real-pilot deploy | 5 | Si prospect a signé pilot agreement |
| **HOS-207 EVAL-3** distribution shift (AC3.1 ship indépendant) | 3 | Bande passante restante |
| **HOS-209 EVAL-5** latency SLO | 1 | Bande passante restante |

---

## Diagramme dépendances (chemin critique)

```
HOS-175 ✅  ──┐
              │ AC4 manuel (3 prospects + outreach)
              ▼
        Pilot agreement  ──────────────────────────────────────────► HOS-176 (S4)
              │
HOS-200 ──┐  ▲
          │  │ (parallèle code)
          ▼  │
       HOS-202 ◀── (débloquée S3)
              │
HOS-201 ──────┤ (polish démo S1)
              │
HOS-204 EVAL-0 ──┬──► HOS-205 EVAL-1 ──┐
   (S2 BLOCKING) ├──► HOS-206 EVAL-2 ──┼──► Pilot gate technique ──► HOS-176
                 ├──► HOS-208 EVAL-4 ──┘
                 ├──► HOS-207 EVAL-3 (S4, post-pilot OK)
                 └──► HOS-209 EVAL-5 (S4, post-pilot OK)
                                                                      │
                                                                      ▼
                                                              HOS-210 WRITE-REX (Phase 3 fin)
```

---

## Track A pilot — chemin critique (parallèle code)

| Étape manuelle Ivan | Sprint | Statut |
|---------------------|--------|--------|
| 1. Envoyer outreach 3 prospects (HOS-175 AC4) | S1 | À faire |
| 2. Discovery calls (45 min/prospect) | S1-S2 | À planifier |
| 3. Pilot agreement signé + Apaleo creds reçus | S2-S3 | Bloque HOS-176 |
| 4. Onboarding live (HOS-176 dev) | S4 | Conditionnel #3 |
| 5. ≥ 4 semaines pilot live + trust-KPI mesuré (US-7) | S4+ | Phase 3 closure |

---

## Risques + triggers de re-plan

| Trigger | Action |
|---------|--------|
| Démo Loop reportée > 7j | Recalculer S1 — peut-être démarrer EVAL-0 plus tôt |
| Aucun prospect ne répond en S1-S2 | Élargir outreach à 6+ prospects ; éviter de coder HOS-176 spec-only |
| EVAL-0 > 2.5j (R1 golden dataset bottleneck) | Activer AC0.1 minimum (40 scenarios) pour débloquer S3, complèter à 71 en S4 |
| HOS-200 introduit migration cassante | Séquencer migrations par timestamp, audit ORM mirror (Décision #16) avant merge EVAL-2 |
| Charge S3 > 9 pts en 5j | Reporter EVAL-3/5 en S4+, ne JAMAIS sacrifier EVAL-2 (pilot gate) |
| Pilot agreement signé en S2 | Avancer HOS-176 dev partiel en S3 (RLS verify, smoke E2E) sans bloquer EVAL stories |

---

## Re-évaluation hebdo

Chaque vendredi 18:00 — relire ce doc :
- AC tickés ?
- Démo Loop date confirmée ?
- Réponse prospect reçue ?
- Migration HOS-200 mergée avant EVAL-2 ?
- Re-prioriser S+1 selon réel.

**Source de vérité finale** = Linear HOS-203/174 boards. Ce doc = vue Ivan solo, pas remplaçant.

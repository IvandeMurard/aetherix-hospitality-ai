# Story 12.3: Garde-fou bornes d'entrée sur la boucle feedback→training (G-3)

Status: review

> **Linear**: [HOS-250](https://linear.app/hospitalityagent/issue/HOS-250) · **Epic**: 12 ([HOS-212](https://linear.app/hospitalityagent/issue/HOS-212)) · **Priorité**: 🔴 Urgent · **Estimate**: 2 pts · **Sprint**: S4 · **Phase**: 3
> **Branche sprint**: `claude/epic12-s4-prepilot` (partagée avec HOS-248 ; commit par story, push groupé fin S4)
> **⛔ Go-live blocker** : avant [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176).

## Story

As an **opérateur Aetherix responsable de la qualité du modèle**,
I want **borner les `actual_covers` reportés avant qu'ils ne soient persistés/réinjectés au retraining**,
so that **une valeur aberrante (typo manager, capteur POS) n'empoisonne pas silencieusement le modèle**.

## Contexte

[HOS-200](https://linear.app/hospitalityagent/issue/HOS-200) a ouvert un write path non gardé : `receipts.persist_actual_covers` écrit `actual_covers` sur la `StaffingRecommendation` + une row `ground_truth` dans `operational_memory`, consommées ensuite par le retraining/MAPE. Aucun contrôle de plausibilité aujourd'hui.

## Acceptance Criteria

1. **AC1** — `actual_covers` borné avant persist/retraining contre la **capacité propriété** + la **plage historique**.
2. **AC2** — valeur implausible → **rejet OU flag** (selon politique) + **alerte ops**, jamais d'ingestion silencieuse.
3. **AC3** — trip loggé dans `agent_action_log` avec **raison typée** (NFR2).
4. **AC4** — bornes **config-driven par propriété** (capacité), documentées avec `eval/FAILURE_THRESHOLDS.md`.

## Tasks / Subtasks

- [x] **T1 — Module garde-fou** `app/services/feedback_guard.py` (AC1)
  - [x] `evaluate(actual_value, total_seats, turns_sum, historical_max)` → verdict `(plausible, severity, reason, detail)`.
  - [x] Capacité = `total_seats × (turns_breakfast+turns_lunch+turns_dinner) × FEEDBACK_COVERS_CAPACITY_MULTIPLIER`.
  - [x] Borne basse `FEEDBACK_COVERS_MIN` (reject < min → couvre négatif/zéro).
  - [x] Plage historique : > `historical_max × FEEDBACK_HISTORICAL_MULTIPLIER` → **flag** (soft, jamais reject — un vrai surge dans la capacité reste légitime).
- [x] **T2 — Politique reject/flag** (AC2) — `FEEDBACK_BOUNDS_POLICY` (`reject` défaut pré-pilote | `flag`).
  - [x] reject → ne PAS écrire `actual_covers` ni la row ground_truth (modèle propre) ; retourne `None`.
  - [x] flag → écrit mais tag `implausible_flag` + source `manager_feedback_flagged`.
- [x] **T3 — Trip typé + alerte** (AC2, AC3) — `record_feedback_trip()` écrit `agent_action_log` (`status="tool_error"`, `error_code="implausible_feedback"`, `tool_name="feedback.ingestion"`, `hotel_id`) + `dispatch_error` (reject) / `dispatch_anomaly` (flag).
- [x] **T4 — Wiring chokepoint** `receipts.persist_actual_covers` (AC1, AC2)
  - [x] Fetch `RestaurantProfile` (tenant_id) + max historique `actual_covers` ; évaluer ; appliquer politique.
  - [x] Rétro-compat : profil/seats absents → capacité skippée (borne basse seule) ; valeurs plausibles → comportement HOS-200 inchangé (retourne la mémoire).
- [x] **T5 — Config + doc** (AC4) — settings env dans `config.py` ; section dans `eval/FAILURE_THRESHOLDS.md`.
- [x] **T6 — Tests** — dans bornes (pass) ; > capacité (reject) ; négatif/zéro (reject) ; > historique mais < capacité (flag, non rejeté) ; aberrant non propagé (pas de row ground_truth) ; profil absent → pass.
- [x] **T7 — Eval gate** : touche `app/services/receipts.py` (dans le set gaté `services/...receipts`? non — le set est `{forecast,staffing,recommendation,memory,inbound_parser}`). `receipts` + `feedback_guard` hors set → **`eval-exempt`** à confirmer.

## Dev Notes

### Ancrages codebase (anti-réinvention)
- **Chokepoint** = `app/services/receipts.py::ReceiptsService.persist_actual_covers` (l.586). Appelé par `app/api/routes/webhook.py` (Twilio inbound), txn ownée upstream (commit après). Garde AVANT les écritures.
- **Capacité déjà modélisée** : `RestaurantProfile.total_seats` (Integer NOT NULL) + `turns_breakfast/lunch/dinner` (Float, défauts 1.0/1.5/2.0). → **pas de migration** (la spec disait "possiblement" ; non nécessaire).
- **Sink alerte** = `ops_dispatcher.dispatch_error`/`dispatch_anomaly` (Linear, déjà câblé — cf. [[HOS-248]]). Pas de Slack.
- **`agent_action_log`** : réutiliser comme pour HOS-248 (`status="tool_error"`, `error_code=<reason>`, `hotel_id=<tenant>`). Pas de migration.
- **Historique** : `max(StaffingRecommendation.actual_covers)` where `tenant_id` + `actual_covers IS NOT NULL`.

### Pièges
- **Rétro-compat tests** : `tests/test_receipts_feedback.py` seede une `StaffingRecommendation` SANS `RestaurantProfile` et attend un retour `OperationalMemory` pour 60/80. → profil absent ⇒ skip capacité ; valeurs plausibles ⇒ inchangé.
- **Reject ≠ perte du feedback manager** : la row `feedback` (tool_submit_feedback_to_memory) est écrite AVANT `persist_actual_covers` dans le webhook → un reject ne jette que la ground-truth aberrante, pas l'intention manager.
- **0 couverts** : la spec (test plan) demande de rejeter zéro → borne basse défaut = 1. Documenté ; ajustable via env si une propriété peut légitimement fermer.

### References
- [Source: Linear HOS-250] · [Source: app/services/receipts.py:586] · [Source: app/api/routes/webhook.py:354-379] · [Source: app/db/models.py:75-136 RestaurantProfile] · [Source: eval/FAILURE_THRESHOLDS.md]

## Dev Agent Record

### Agent Model Used

Amelia (Developer Agent) · claude-opus-4-8

### Debug Log References

- HOS-250 targeted: **37 passed** (`test_feedback_guard` + `test_feedback_bounds_integration` + `test_receipts_feedback` regression).
- Full backend suite: **1024 passed, 4 skipped**.
- Lint: `ruff@0.4.0` → **All checks passed** (after autofix: import sort in `test_feedback_guard.py`).

### Completion Notes List

- **AC1** ✅ — `feedback_guard.evaluate()` bounds against capacity (`total_seats × turns × mult`) + lower bound; historical soft-sanity via `historical_max × mult`. Wired into `persist_actual_covers` chokepoint.
- **AC2** ✅ — `FEEDBACK_BOUNDS_POLICY` (`reject` default | `flag`). Reject → value not ingested (returns `None`, recommendation + ground_truth row skipped). Flag → ingested, tagged `implausible_flag` + source `manager_feedback_flagged`. Always an ops alert.
- **AC3** ✅ — typed trip row in `agent_action_log` (`status="tool_error"`, `error_code="implausible_feedback"`, `tool_name="feedback.ingestion"`). No migration.
- **AC4** ✅ — bounds env-driven in `config.py` (per-property capacity derived from `total_seats`+turns); documented in `eval/FAILURE_THRESHOLDS.md`.
- **No migration** — capacity derived from existing `restaurant_profiles.total_seats` + turns (spec said "possiblement" — not needed).
- **Degrade-open** — profile/history lookup failure → treated as plausible (guard never blocks legit feedback on an infra hiccup).
- **Backward-compat** — plausible values keep HOS-200 behaviour exactly (return memory, source `manager_feedback`, tags unchanged); confirmed by `test_receipts_feedback.py` green.
- **T7 (eval gate)** — touches `services/receipts.py` + new `feedback_guard.py`, neither in the gated set (`{forecast,staffing,recommendation,memory,inbound_parser}`/providers/prompts) → **eval-exempt** (PR label).
- Assumption: `0` covers rejected (per Linear test plan); `FEEDBACK_COVERS_MIN` env-tunable if a property legitimately closes.

### File List

**Added**
- `backend/app/services/feedback_guard.py`
- `backend/tests/services/test_feedback_guard.py`
- `backend/tests/services/test_feedback_bounds_integration.py`

**Modified**
- `backend/app/core/config.py` (feedback bounds env settings)
- `backend/app/services/receipts.py` (guard wiring in `persist_actual_covers` + `_check_feedback_bounds` helper)
- `eval/FAILURE_THRESHOLDS.md` (HOS-250 bounds section)

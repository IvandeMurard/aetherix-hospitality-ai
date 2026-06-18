# Story 12.1: Heartbeat / dead-man's switch sur dispatchers planifiés (G-1)

Status: review

> **Linear**: [HOS-248](https://linear.app/hospitalityagent/issue/HOS-248) · **Epic**: 12 — Post-Deployment Reliability & Runtime Guardrails ([HOS-212](https://linear.app/hospitalityagent/issue/HOS-212)) · **Priorité**: 🔴 Urgent · **Estimate**: 3 pts · **Sprint**: S4 (2026-06-24 → 06-30) · **Phase**: 3
> **Branche**: `ivandemurard/hos-248-story-121-heartbeat-dead-mans-switch-sur-dispatchers`
> **⛔ Go-live blocker** : doit être mergé AVANT [HOS-176](https://linear.app/hospitalityagent/issue/HOS-176) (real-pilot deploy). Cf. `docs/planning/phase-3-sprint-plan.md` §"Pilot gate fiabilité".

## Story

As an **opérateur Aetherix (Ivan) responsable d'un pilote en prod**,
I want **être alerté sous 5 min quand un job planifié échoue OU ne se déclenche pas du tout**,
so that **un cron mort/silencieux ne passe pas inaperçu pendant que je crois le pilote en bonne santé** (trou n°1 de l'audit fiabilité QA avant pilote).

## Contexte (le « pourquoi »)

Les paths planifiés (Daily Receipt, Weekly Digest, Dispatch Worker) **enregistrent** mais **n'alertent pas de façon complète** :
- Sur **erreur fatale**, ils appellent déjà `dispatch_error` (✅ partiel — voir Dev Notes).
- Mais une **erreur par-hôtel** est seulement `logger.exception` → silencieuse.
- Et surtout : un job qui **ne se déclenche jamais** (process crashé, scheduler mort, deploy down, misfire au-delà de la grâce) est **totalement invisible** — personne ne surveille les logs en continu. C'est le gap central de cette story (le **dead-man's switch**).

Première instance canonique du problème = le path corrigé en [HOS-211](https://linear.app/hospitalityagent/issue/HOS-211) (`VAULT_FOLDERS` ImportError silencieux dans `ops_dispatcher`).

## Acceptance Criteria

1. **AC1** — Un run planifié qui **erreure** lève une alerte ops (Linear) sous 5 min. *(Couvre aussi les échecs par-hôtel, pas seulement l'échec fatal global.)*
2. **AC2** — Un run planifié qui **ne se déclenche pas** (dead-man's switch / fenêtre attendue dépassée) lève une alerte.
3. **AC3** — Chaque trip est loggé dans `agent_action_log` avec **raison typée** (NFR2 Epic 12).
4. **AC4** — Seuils de fenêtre **config-driven** (pas de redeploy) — documentés à côté de `eval/FAILURE_THRESHOLDS.md`.
5. **AC5** — Le path [HOS-211](https://linear.app/hospitalityagent/issue/HOS-211) est couvert par cette instrumentation + test de régression.

## Tasks / Subtasks

- [x] **T1 — Heartbeat : enregistrer le « dernier run OK » de chaque job planifié** (AC2, AC3)
  - [x] À la fin réussie de `_run_receipt_dispatch_job`, `_run_weekly_digest_job`, `_run_dispatch_job`, écrire un battement (timestamp + job_id) dans un store interrogeable. **Décision de design à confirmer dans la PR** : réutiliser `agent_action_log` (status `ok`, `tool_name="scheduler.<job>"`, `hotel_id="_system"`) — **pas de nouvelle table** (la story est explicitement *migration: non*).
  - [x] Ne jamais faire échouer le job si l'écriture du heartbeat échoue (fire-and-forget, cf. contrat `ops_dispatcher`).
- [x] **T2 — Dead-man's switch : détecter les jobs en retard** (AC2, AC4)
  - [x] Nouveau worker `app/workers/heartbeat_monitor.py` enregistré sur le scheduler partagé (`register_heartbeat_monitor_job`), poll régulier (ex. toutes les 15 min).
  - [x] Pour chaque job surveillé, comparer `now - dernier_heartbeat` à une **fenêtre attendue config-driven**. Si dépassée → `dispatch_error` (sink Linear) + trip loggé.
  - [x] Anti-spam : ne pas re-alerter à chaque poll tant que le même job reste down (debounce / état « déjà alerté »).
- [x] **T3 — Compléter l'alerting sur erreur** (AC1)
  - [x] Les échecs **par-hôtel** (actuellement `logger.exception` seul dans les boucles `for hotel`) déclenchent un `dispatch_anomaly`/`dispatch_error` agrégé (1 alerte par run avec le compte d'échecs, pas 1 par hôtel → éviter le flood).
- [x] **T4 — Trip → `agent_action_log` avec raison typée** (AC3)
  - [x] Définir un enum de raisons typées (ex. `job_error`, `dead_man_timeout`, `partial_hotel_failures`) — colocaliser avec les autres reasons typées (cf. `abstention_reason`, EVAL-2).
  - [x] Chaque trip écrit une ligne `agent_action_log` avec `status`/`error_code` portant la raison typée.
- [x] **T5 — Seuils config-driven + doc** (AC4)
  - [x] Fenêtres attendues par job exposées via `app/core/config.py` (env-driven, défauts sûrs) — **pas de redeploy** pour ajuster.
  - [x] Documenter les seuils dans un fichier à côté de `eval/FAILURE_THRESHOLDS.md` (ex. `eval/HEARTBEAT_THRESHOLDS.md` ou section dédiée) avec la même convention « updating = explicit decision + trace ».
- [x] **T6 — Couverture HOS-211 + tests** (AC5)
  - [x] Étendre/ajouter un test de régression garantissant que le path HOS-211 (ops-dispatch) est désormais sous instrumentation heartbeat/alerting (ne régresse plus silencieusement).
  - [x] Tests unitaires : run échoué → `dispatch_error` appelé ; heartbeat absent/périmé → dead-man trip levé ; trip → ligne `agent_action_log` avec raison typée.
  - [x] Test intégration : end-to-end dispatcher → `ops_dispatcher` mocké.
- [x] **T7 — Eval gate** : vérifier si la story touche les zones gatées (Décision #22). Ici = workers/infra, **a priori `eval-exempt`** (infra-only) — confirmer et poser le label PR si applicable. Pas de toucher à `services/{forecast,staffing,recommendation,memory,inbound_parser}`/`providers`/prompts.

## Dev Notes

### ⚠️ Ce qui existe déjà — NE PAS réinventer

- **Sink d'alerte = `app/services/ops_dispatcher.py`** (déjà câblé, mirror Obsidian inclus). Utiliser `dispatch_error(title, detail, tags=...)` (Linear priorité 2/high) et `dispatch_anomaly(...)` (priorité 3/medium). **Aucune intégration Slack n'existe — ne pas en introduire.** Fire-and-forget : ces fonctions ne re-raise jamais.
- **Les 3 dispatchers appellent déjà `dispatch_error` sur erreur fatale globale** (`receipts_dispatcher._run_receipt_dispatch_job`, `_run_weekly_digest_job`, `dispatch_worker._run_dispatch_job`). AC1 est donc **partiellement** couvert → le travail restant = (a) erreurs par-hôtel agrégées, (b) écriture `agent_action_log`.
- **Scheduler** = `APScheduler AsyncIOScheduler` partagé, jobs enregistrés via `register_*_job(scheduler)` appelés au startup dans `app/main.py` (lifespan). Jobs cron existants : `receipt_dispatcher` (daily 18:00), `weekly_digest` (dim 18:00), `dispatch_worker` (*/2 min). Tous ont un `misfire_grace_time`. **Enregistrer le nouveau `heartbeat_monitor` de la même façon.**
- **`agent_action_log`** (modèle `AgentActionLog`, `app/db/models.py:524`) : colonnes utiles déjà présentes — `hotel_id` (NOT NULL → sentinelle `"_system"` pour jobs système), `tool_name`, `status` (`ok|auth_error|tool_error|rate_limited`), `error_code`, `payload` (JSON libre), `request_id`. **Réutiliser, pas de migration** (confirmé dans la spec Linear). Pattern de raison typée déjà existant : `abstention_reason` (HOS-206/EVAL-2).
- **Contrat de seuils** : `eval/FAILURE_THRESHOLDS.md` est la « source of truth » des seuils, avec règle « toute modif = décision explicite + PR + trace CLAUDE.md ». Colocaliser les seuils heartbeat selon la même convention.

### Pièges à éviter (anti-fuckup)

- **Alert flood** : ne PAS émettre une alerte Linear par hôtel ni à chaque poll du monitor. Agréger par run, debouncer le dead-man (1 alerte tant que le job reste down).
- **NOT NULL `hotel_id`** : les jobs système n'ont pas de hôtel → sentinelle explicite, ne pas passer `None`.
- **SQLite en test** : `agent_action_log` a des colonnes Postgres-spécifiques (`StringArray`, `JSONB`) avec fallback JSON pour SQLite — les tests tournent sur SQLite, garder les écritures compatibles.
- **Fire-and-forget** : l'instrumentation heartbeat ne doit JAMAIS casser le job métier qu'elle observe.
- **NFR2** : la fenêtre de détection cible ≤ 5 min pour AC1. Le poll du monitor (T2) doit être assez fréquent pour respecter AC2 sans spammer (15 min suggéré pour des jobs daily/weekly ; à arbitrer vs le `*/2 min` du dispatch_worker).

### ⚠️ HITL / fatigue — cadrage (point d'attention Ivan, vérifié SM 18/06)

Ces alertes sont **ops-facing** (destinées à l'opérateur/dev = Ivan), **pas** des validations HITL manager (accept/reject de recommandations). Le redesign anti-« validation/tech fatigue » concerne avant tout :
- la **surface manager** (cadence Receipts, opt-out `STOP`, fenêtre horaire — déjà en place, cf. `phase-2-agent-receipts.md`),
- la story sœur **HOS-251 (G-4)** = confidence-tiered forecast guardrail (2 tiers), où vit la logique de tiers,
- une décision **Open (Phase 4-5, non adoptée)** : « Interaction model event-driven » qui flague explicitement le trade-off *reactivity ↑ vs alerting fatigue* (`open-decisions.md`).

**Impact sur cette story** : faible côté HITL manager, mais le principe **anti-flood s'applique** et est déjà intégré (T2 debounce dead-man, T3 agrégation par run). Décision #6 *« no auto-actions »* (HITL = copilot, pas autopilot) reste valide et **non remise en cause** par cette story. ⚠️ **Aucun protocole HITL redessiné formellement adopté trouvé** — si Ivan vise un doc/décision précis, le replier ici avant implémentation.

### Project Structure Notes

- Nouveau fichier : `backend/app/workers/heartbeat_monitor.py` (suit le pattern `dispatch_worker.py` / `receipts_dispatcher.py` : fonction `_run_*_job` + `register_*_job(scheduler)`).
- Modifs : les 3 `_run_*_job` existants (écriture heartbeat de fin de run), `app/main.py` (enregistrement du monitor), `app/core/config.py` (fenêtres env-driven). `ops_dispatcher.py` réutilisé tel quel (pas de nouveau sink).
- Doc seuils : `eval/HEARTBEAT_THRESHOLDS.md` (ou section dans `FAILURE_THRESHOLDS.md`).

### References

- [Source: Linear HOS-248] — AC + Technical Notes (sink résolu SM 18/06)
- [Source: backend/app/services/ops_dispatcher.py] — `dispatch_error` / `dispatch_anomaly`, fire-and-forget, mirror Obsidian
- [Source: backend/app/workers/receipts_dispatcher.py] — daily receipt + weekly digest, dispatch_error sur fatal, misfire_grace_time=300
- [Source: backend/app/workers/dispatch_worker.py] — pattern register_*_job + NFR2 (livraison < 3 min)
- [Source: backend/app/db/models.py:524 AgentActionLog] — colonnes status/error_code/payload, hotel_id NOT NULL
- [Source: backend/tests/test_ops_dispatch_vault_folders.py] — régression HOS-211 existante à étendre (AC5)
- [Source: eval/FAILURE_THRESHOLDS.md] — convention « contrat de seuils »
- [Source: docs/planning/phase-3-sprint-plan.md] — gate go-live, S4

## Dev Agent Record

### Agent Model Used

Amelia (Developer Agent) · claude-opus-4-8

### Debug Log References

- Full backend suite: **1013 passed, 4 skipped** (`.venv/Scripts/python -m pytest -q`).
- HOS-248 targeted suite: **23 passed** (heartbeat + dispatcher wiring + HOS-211 regression + workers robustness).
- Lint: `ruff@0.4.0 check` → **All checks passed** (after autofix: import sort in `main.py`/`test_heartbeat.py`, removed unused `pytest` import in `test_receipts_dispatcher_heartbeat.py`).

### Completion Notes List

- **AC1** ✅ — fatal job errors already routed to `dispatch_error` (pre-existing); added aggregated per-hotel-failure trip (`REASON_PARTIAL`) in both receipt + weekly dispatchers (1 alert/run, no flood).
- **AC2** ✅ — new `heartbeat_monitor` (dead-man's switch) polls every `HEARTBEAT_MONITOR_INTERVAL_MIN` (15) and trips `REASON_DEAD_MAN` when last heartbeat exceeds the per-job window. Heartbeats written on every successful run of the 3 dispatchers.
- **AC3** ✅ — every trip writes an `agent_action_log` row (`status="tool_error"`, `error_code=<typed reason>`, `hotel_id="_system"`). No migration (reused table, as scoped).
- **AC4** ✅ — all windows/intervals/cooldown are env-driven in `config.py`; documented in `eval/HEARTBEAT_THRESHOLDS.md` (same "contract" convention as `FAILURE_THRESHOLDS.md`).
- **AC5** ✅ — `reporting_service._dispatch_ops` (the HOS-211 path) is now genuinely fire-and-forget: failures are swallowed (no more `/reports/weekly` 500) AND trip a `REASON_JOB_ERROR` alert. Regression test added.
- **T7 (eval gate)** — changes are workers/infra + `reporting_service` (not in the gated set `services/{forecast,staffing,recommendation,memory,inbound_parser}`/`providers`/prompts). → **eval-exempt** (infra-only); add PR label `eval-exempt`.
- Design note: in-memory debounce (`_last_alerted`) resets on restart — accepted trade-off (≤1 extra alert post-restart vs per-poll flood). Documented in `HEARTBEAT_THRESHOLDS.md`.
- `datetime.utcnow()` used for consistency with existing codebase convention (`models.py` defaults); deprecation warnings are pre-existing project-wide, not introduced here.

### File List

**Added**
- `backend/app/workers/heartbeat.py`
- `backend/tests/workers/test_heartbeat.py`
- `backend/tests/workers/test_receipts_dispatcher_heartbeat.py`
- `eval/HEARTBEAT_THRESHOLDS.md`

**Modified**
- `backend/app/core/config.py` (heartbeat env settings)
- `backend/app/workers/receipts_dispatcher.py` (heartbeat + partial-failure trip, both jobs)
- `backend/app/workers/dispatch_worker.py` (heartbeat on success)
- `backend/app/main.py` (register `heartbeat_monitor`)
- `backend/app/services/reporting_service.py` (AC5 — fire-and-forget + trip)
- `backend/tests/test_ops_dispatch_vault_folders.py` (AC5 regression test)

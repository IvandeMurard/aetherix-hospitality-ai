# ADR 0007 — Evaluation-by-Design Framework + CI Gate

> **Status**: Accepted · **Date**: 2026-06-04 · **Author**: Architect (Winston, Opus)
> **Context**: Phase 3 — bloque 6 stories EVAL-0 à EVAL-5 + Pilot Validation
> **Linear**: HOS-EVAL-0 → HOS-EVAL-5 (à créer par SM)
> **Implémente**: CLAUDE.md Décision architecturale #22
> **Étend**: ADR 0002 (D11 testing strategy), ADR 0003 (`agent_action_log`)
> **Articule**: ADR 0005 (cold-start meta-learner, gate runtime + LOO)

---

## 1. Contexte

Aetherix dispose d'une observabilité production solide (ADR 0003 `agent_action_log`, ADR 0002 `memory_instrumentation_daily`) mais d'une **eval upstream quasi-inexistante**. Le MAPE 15.09% (run 2026-05-21) est une mesure ponctuelle, pas un living regression gate.

Deux triggers convergents semaine du 2026-06-01 :
1. **Qonto talk** *"AI @ Qonto: shipper et évaluer l'IA en production"* — frameworks *"Working vs Reliable"* (5 dimensions) + *"Eval as a Contract"*.
2. **Gap BMad-Method** : Dev Agent DoD (`CLAUDE.md`) traite *"CI green = done"*. Pour un produit ML "client-facing" (Qonto def.), insuffisant.

**Brief PM source** : `docs/planning/evaluation-by-design.md` (frameworks, pyramide, failure definitions, 6 stories Phase 3).
**Décision sous-jacente** : CLAUDE.md Décision architecturale #22.
**Pattern reproduit** : CLAUDE.md Décision #16 (schema drift gate hard, blocking merge).

**Goal** : installer un framework eval-by-design qui (a) couvre les 5 dimensions Qonto, (b) bloque tout merge touchant les couches modèle/LLM/memory/providers/prompts sans mise à jour du golden dataset, (c) reste maintenable par 1 dev solo (pas de framework lock-in).

**Non-goals (v0 = Phase 3)** :
- LLM-as-judge (EVAL-6 Phase 4)
- Human eval loops (EVAL-7 Phase 4)
- Memory recall annotated truth (EVAL-8 Phase 4)
- A/B framework, cost tracking (EVAL-9/10 Phase 4)
- Migration de l'eval Prophet existante (`measure_mape_j1.py`) vers un framework tiers (Braintrust/deepeval) — re-évaluation Phase 4

---

## 2. Décisions (Q1-Q7 tranchées)

### D1 (Q1) — Structure golden dataset : **schéma poly + discriminateur `category`, fichier unique**

`eval/golden_dataset.jsonl` — un fichier JSONL, une ligne par scenario, schéma discriminé par `category`.

**Pourquoi un fichier unique** : grep/diff trivial dans review PR, alignement total avec la pratique `schema_drift_ignore.json` (Décision #16), versioning git natif.
**Pourquoi schéma poly** : forecast vs parser vs recall ont des payloads structurellement différents — forcer un schéma commun = nullables partout, illisible.

**Versioning** : champ `schema_version` (semver) au top-level de chaque ligne. Bump = PR séparée + script de migration `scripts/eval/migrate_dataset.py` (sketch, écrit le jour du bump).

**Rejeté** :
- Fichiers séparés par catégorie (`forecast.jsonl`, `parser.jsonl`, …) — multiplie les baselines, complique CI gate (quel fichier touché ?), pas de gain.
- Schema commun avec champs optionnels — verbose, ambigu (un scenario `parser` peut-il avoir `forecast_expected` ? Non, mais le schéma le permet).
- DB-backed dataset (Supabase table) — pas reproductible offline, pas reviewable en PR, pas cacheable CI.

**Taxonomie catégories (11) — exhaustive Phase 3** :

| Code | Description | Min count |
|---|---|---|
| `normal_day` | Occupancy normale, pas d'event, météo standard | 15 |
| `event_day` | Event local connu (covers spike attendu) | 8 |
| `weather_anomaly` | Heatwave / cold snap impactant covers | 5 |
| `ota_cancellation_wave` | Annulations tardives Day J | 3 |
| `weekend_weekday_split` | Différentiel week-end vs semaine | 5 |
| `service_stratification` | Breakfast-heavy vs dinner-heavy | 5 |
| `closure_day` | Fermeture exceptionnelle (jour férié + property closed) | 3 |
| `holiday_eve` | Veille de férié (comportement atypique J-1) | 4 |
| `breakfast_dinner_mix_shift` | Shift saisonnier mix services | 3 |
| `ood_edge` | OOD: langue non supportée, données PMS manquantes, occupancy spike anormal, multi-event collision, timezone glitch | 5 |
| `parser_intent` | Manager replies stratifiés FR/EN, intent (accepted/rejected/modified), ton (terse/verbose/sarcastique/emoji) | 15 |
| `pos_anomaly` *(forward-compat ADR-0006)* | Placeholder, 0 scenario Phase 3, structure définie | 0 |

**Total minimum Phase 3** : 71 scenarios (vs 40-60 brief PM — j'augmente car couverture catégorielle exige minimum 3-5 par cat. pour stabilité statistique des MAPE per-cat.).

**Annotations** : PM seul Phase 3 (Ivan). Queue collab annotation = EVAL-7 Phase 4 prereq.

**Schéma JSONL** :

```jsonc
{
  "schema_version": "1.0.0",
  "id": "fcst-normal-001",                    // kebab-case unique, prefix par layer
  "category": "normal_day",                    // taxonomie ci-dessus
  "layer": "forecast",                         // forecast | recommendation | receipt | parser | drift | latency
  "created_at": "2026-06-04",                  // date d'ajout au dataset
  "author": "ivan",                            // git user.email short
  "input": {                                    // payload — schéma dépend de la catégorie/layer
    "hotel_id": "demo-hotel-ber",
    "date": "2025-09-15",
    "occupancy": 0.78,
    "weather_score": 0.6,
    "event_impact": 0.0,
    "regressors": ["weather_score", "event_impact", "occupancy"]
  },
  "expected": {                                 // ground truth ou accept-band
    "covers_dinner": {"value": 92, "tolerance_pct": 0.15},
    "covers_breakfast": {"value": 134, "tolerance_pct": 0.12}
  },
  "failure_trigger": "MAPE > 15% sur covers_dinner OU > 12% sur covers_breakfast",
  "notes": "Mercredi septembre BER, normal weekday — baseline stable depuis 18 mois"
}
```

Exemples par catégorie : annexe A (à la fin de cet ADR).

---

### D2 (Q2) — CI gate implementation : **glob touched-paths + subset filtré + label override + PR comment**

#### D2.a — Détection des fichiers touchés

`scripts/ci/check_eval_coverage.py` (analogue à `scripts/ci/check_schema_drift.py`). Liste des paths déclenchant le gate (glob patterns) :

```python
EVAL_TRIGGER_PATHS = [
    "backend/app/services/prediction_engine.py",
    "backend/app/services/staffing_service.py",
    "backend/app/services/recommendation_formatter.py",
    "backend/app/services/reasoning_service.py",
    "backend/app/services/explainability_service.py",
    "backend/app/services/memory_service.py",
    "backend/app/services/memory_recall_service.py",
    "backend/app/services/rag_service.py",
    "backend/app/services/pattern_scorer.py",
    "backend/app/services/query_parser.py",
    "backend/app/services/receipts.py",
    "backend/app/services/agent_constitution.py",       # prompts vivent ici
    "backend/app/services/data_transformer.py",         # feature engineering
    "backend/app/services/demand_modifiers.py",
    "backend/app/providers/",                            # tous (LLM + Embedding swap)
    "backend/prompts/",                                  # créer ce dossier dédié (D2.b)
    "eval/golden_dataset.jsonl",                         # dataset = part du contrat
    "eval/FAILURE_THRESHOLDS.md",                        # contract changes
    "eval/baselines/",                                   # baseline bump déclenche re-run
]
```

> **Décision architecturale annexe** : créer `backend/prompts/` comme dossier dédié pour extraire les prompts inline (actuellement `agent_constitution.py:33` `_SYSTEM_PROMPT_TEMPLATE`). EVAL-0 inclut cette extraction. Justification : permettre prompt-diff lisible en review PR + invalidation cache eval déterministe.

#### D2.b — Exécution eval : subset filtré par layer, full run sur trigger transverse

```
PR touche app/services/prediction_engine.py        →  run eval/forecast/*
PR touche app/services/query_parser.py             →  run eval/parser/*
PR touche app/services/memory_recall_service.py    →  run eval/recall/*  (Phase 4 EVAL-8 — Phase 3 = smoke)
PR touche app/providers/                           →  FULL RUN (LLM/embedding swap impacte tout)
PR touche eval/golden_dataset.jsonl                →  run uniquement les layers touchés par le diff
PR touche prompts/                                 →  FULL RUN sur les layers utilisant le prompt modifié
```

Mapping `path → layer` codé dans `scripts/ci/check_eval_coverage.py` (table simple, pas de magie).

#### D2.c — Label override `eval-exempt`

```python
# scripts/ci/check_eval_coverage.py
if "eval-exempt" in gh_pr_labels():
    print("[eval-coverage] SKIP — label eval-exempt présent")
    print("[eval-coverage] Authorized exemptions: refactor, doc, infra-only, ci-only, test-only")
    return 0
```

Exemptions autorisées (warning si différentes) :
- `refactor` — pure rename / move sans changement logique modèle
- `doc` — `*.md`, `docs/**` uniquement
- `infra` — `.github/`, `fly.toml`, `Dockerfile`, deploy scripts
- `ci-only` — `scripts/ci/*` (sauf si modifie `check_eval_coverage.py` lui-même → meta-loop, full run)
- `test-only` — `backend/tests/` uniquement

Liste affichée dans `eval/README.md`. PR review SM rejette `eval-exempt` abusif (cas humain, pas auto-check).

#### D2.d — Reporting : PR comment auto via GitHub Action

```yaml
# .github/workflows/eval-gate.yml (sketch)
- name: Run eval suite
  run: python scripts/eval/run_all.py --layers ${{ steps.detect.outputs.layers }} --json-out eval-result.json --md-out eval-report.md

- name: Comment PR
  uses: marocchino/sticky-pull-request-comment@v2
  with:
    header: eval-report
    path: eval-report.md
```

Markdown report = diff baseline → new par layer (per-category MAPE delta, parser accuracy delta, drift status). Sticky = un seul commentaire updaté à chaque push.

#### D2.e — Cache : hash des paths déclencheurs

```python
cache_key = sha256(concat(file_hashes(EVAL_TRIGGER_PATHS_TOUCHED)))
if cache_key == previous_cache_key_in_baseline:
    skip eval, return previous result
```

Simple. Stocké dans `eval/baselines/.cache_keys.json`. Évite re-runs sur PR rebase / cosmetic changes.

#### D2.f — Exit codes

| Code | Sens |
|---|---|
| 0 | PASS — eval green OU `eval-exempt` OU cache hit |
| 1 | FAIL — régression détectée (gate blocking) |
| 2 | ERROR — script crash, données manquantes, golden_dataset corrupt |
| 3 | WARN — coverage < 80% mais ≥ 60% (passe, mais commentaire PR red flag) |

Code 3 ≠ blocking en CI (exit 0 pour le workflow) mais visible dans le commentaire.

#### D2.g — Rollout WARN→blocking + frontière des paths (HOS-274, 2026-07-04)

**Statut : le gate est passé BLOCKING le 2026-07-04** (`EVAL_GATE_BLOCKING="true"`). Le
rollout WARN (D2.f, AC5) est clos.

**Preuve de la précondition (« N runs verts prouvant Prophet-in-CI stable »)** : les PR
docs court-circuitent (`No trigger paths touched`) sans lancer Prophet — un simple compte
de PR vertes ne prouve rien. Un **canari CI** (PR #185, no-op sur un `EVAL_TRIGGER_PATH`
forecast) a forcé 3 runs Prophet consécutifs dans l'environnement CI : **MAPE forecast
identique à 25.40 %, 0 régression, variance run-to-run 0.00pp** vs la baseline re-figée
depuis CI (PR #175). La stochasticité redoutée (R2/R4) était du **drift d'environnement**
(versions libs CI ≠ local), neutralisé par le freeze-from-CI — Prophet (mode MAP/L-BFGS)
est déterministe à environnement fixé. Le blocking ne mord donc que sur exit **1/2**
(régression réelle >3pp ou crash), jamais sur du bruit Prophet.

**Frontière des paths — sortir de l'arbitrage au cas par cas (AC3) :**

| Classe de path | Politique |
|---|---|
| `EVAL_TRIGGER_PATHS` (D2.a) — forecast/recommendation/recall/parser + `providers/` + `prompts/` + `eval/` | **DOIT** porter une couverture eval (scenario golden dataset) OU label `eval-exempt` justifié. Une modif ici sans scenario → WARN « touched-but-not-evaluated » (D3). |
| **Runtime guardrails (Bras B, Epic 12)** — workers/monitoring/heartbeat/circuit-breaker/bornes (`scheduler`, `dispatch`, alerting) | **Légitimement hors offline-eval** : évalués en runtime (guardrails ADR-0009), pas par le golden dataset. Absents de `EVAL_TRIGGER_PATHS` **par design** — ce n'est pas une dette. Frontière Bras A vs Bras B, cf. §13. |
| Doc / infra-only / ci-only / test-only / refactor sans changement de comportement | Exempts via label `eval-exempt` (D2.c), review SM rejette l'abus. |

**Rollback d'urgence** : repasser `EVAL_GATE_BLOCKING` à `"false"` (one-liner) si un
faux-blocage chronique émerge — mais tracer la raison, car ré-ouvre la dette de gating.

---

### D3 (Q3) — Coverage : **catégorielle (taxonomy), pas par lignes — 80% warn, 60% fail**

**Définition** : "Coverage = % des catégories taxonomiques (D1) ayant ≥ 1 scenario PASS dans le run courant."

Pourquoi pas pytest-cov lignes :
- Coverage par lignes mesure tests unitaires, pas reliability ML. Une ligne couverte n'évalue pas la qualité de prédiction.
- La taxonomie Qonto-style (edge behavior, graceful degradation, drift) est intrinsèquement business, pas code.

**Thresholds** (modifiables uniquement par PR explicite + entrée CLAUDE.md) :
- `coverage_pct ≥ 80%` → PASS
- `60% ≤ coverage_pct < 80%` → WARN (exit 3, commentaire PR red flag, pas blocking)
- `coverage_pct < 60%` → FAIL (exit 1, blocking)

**Complément** — "touched-but-not-evaluated" check : si une PR modifie un fichier dans `EVAL_TRIGGER_PATHS` mais aucun scenario de la layer correspondante n'a été modifié ou ajouté → WARN avec message *"You changed forecast code but didn't add/modify a forecast scenario. Add coverage or label eval-exempt."*

---

### D4 (Q4) — Tooling : **pure Python (pytest + pandas), Markdown + JSON output, baseline git-tracked**

**Stack retenue** :
- `pytest` pour les unit-level evals (parser accuracy, latency micro-bench)
- `pandas` + `numpy` + `scipy.stats` pour stratification MAPE et drift detection
- `prophet` réutilisé tel quel pour forecast eval
- Assertions custom (pas de framework)
- `jinja2` pour le rendu Markdown report

**Rejeté** :
- **deepeval** : surface LLM-as-judge utile Phase 4 (EVAL-6) mais lock-in patterns inutile Phase 3
- **promptfoo** : excellent pour A/B prompt tests mais pas adapté aux MAPE stratifiés Prophet
- **Braintrust** : meilleure option de re-évaluation Phase 4 (workflow LLM-as-judge + UI). Pas avant. Décidé dans CLAUDE.md mention brief PM — confirmé.
- **evidently** : excellent pour drift, mais coût intégration > custom KS-test sur 4 features.

**Output formats** :
- `eval/reports/YYYY-MM-DD/result.json` — JSON parsable (CI artifacts, future dashboard)
- `eval/reports/YYYY-MM-DD/report.md` — Markdown lisible (PR comment, REX article source)
- `eval/baselines/<layer>_baseline.json` — git-tracked, source de vérité pour comparaison

**CI cost target** : full run < 90s. Si dépassement à 3 min cumulés, splitter en jobs parallel par layer.

**Reproducibility (Qonto dim. 4)** :
- `seed=42` fixé partout (Prophet, sampling, numpy)
- LLM temperature pinning : 0.0 sur tous les LLM calls dans l'eval suite (override des configs prod)
- Provider singleton via `lifespan` (Décision #10) → swap config testée via `EMBEDDING_BACKEND=fake` (utilise `FakeEmbeddingProvider` ADR-0002 D11)

---

### D5 (Q5) — Drift detection : **algorithme par feature type, baseline figée, cascade WARN/FAIL**

**Algorithme par feature** :

| Feature | Type | Algo | Justification |
|---|---|---|---|
| `covers_dinner`, `covers_breakfast`, `covers_lunch` | Continu, distribution skewed | **KS-test** (`scipy.stats.ks_2samp`) | Sensible aux shifts de queue, robuste pour low-N |
| `occupancy` | Continu, bornée [0,1] | **KS-test** | Idem |
| `temperature`, `precipitation`, `weather_score` | Continu smooth | **Wasserstein distance** (`scipy.stats.wasserstein_distance`) | Pénalise shifts smooth mieux que KS |
| `event_count`, `event_type` (one-hot) | Sparse / catégoriel | **PSI** (Population Stability Index) | Standard fintech, gère catégoriel + sparse |
| `manager_reply_lang` (FR/EN/autre) | Catégoriel | **PSI** | Idem |

**Window** :
- **Rolling 7-day** pour alerte temps réel (WhatsApp ops)
- **Rolling 30-day** pour gate runtime auto-disable cold-start meta-learner (ADR-0005)

**Baseline** : **snapshot training set FIGÉ** dans `eval/distribution_snapshots/<feature>.json`. Capturé au commit EVAL-3, re-capturé uniquement sur décision PM explicite (commit PR avec mention `BASELINE_RESET` + entrée CLAUDE.md justifiant pourquoi). Pas de rolling baseline 90j → perdrait la détection de drift lent (gros risque cold-start meta-learner).

**Cascade** :

| Severity | Seuil | Action |
|---|---|---|
| **WARN** | KS p<0.05 OU Wasserstein > 1σ baseline OU PSI 0.1–0.2 | Log + WhatsApp ops daily digest |
| **FAIL** | KS p<0.01 OU Wasserstein > 2σ OU PSI > 0.2 | WhatsApp ops immediate + entrée `agent_action_log` `status="drift_alert"` + auto-disable cold-start meta-learner (hook runtime D6) |

**Hook auto-disable cold-start meta-learner** : nightly job APScheduler (`refresh_distribution_shift_daily()`) qui (a) refresh MV `distribution_shift_daily`, (b) si fail détecté sur features cohort (`covers_*`, `occupancy`), set runtime flag `cold_start_enabled=False` dans `hotel_config` (nouvelle col, migration séparée si pas existante). `PredictionEngine.predict()` lit ce flag au startup et au refresh horaire.

---

### D6 (Q6) — "I don't know" contract : **sentinel commun `AgentAbstention`, pas de cascade auto, telemetry sur `agent_action_log` étendu, 2 variantes WhatsApp**

#### D6.a — Sentinel commun

Nouveau dataclass `backend/app/services/abstention.py` :

```python
from dataclasses import dataclass, field
from typing import Literal

AbstentionReason = Literal[
    "cold_start_no_cohort",          # forecast service
    "cold_start_meta_learner_drift", # forecast service (auto-disable D5)
    "confidence_below_threshold",    # recommendation service (<0.5)
    "parser_low_confidence",         # inbound parser (<0.6, Décision #15)
    "data_quality_alert",            # PMS sync stale, weather missing
    "drift_detected_high",           # distribution shift FAIL (D5)
    "ood_unsupported_input",         # manager reply in unsupported lang, anomalous payload
]

@dataclass(frozen=True)
class AgentAbstention:
    reason: AbstentionReason
    layer: Literal["forecast", "recommendation", "receipt", "parser"]
    context: dict = field(default_factory=dict)  # serialized to JSONB in agent_action_log
    human_message: str = ""                       # variante WhatsApp ou null si géré upstream

    def __bool__(self) -> bool:
        return False  # `if result:` distingue résultat valide d'abstention
```

Tous les services modèles concernés retournent `Union[Result, AgentAbstention]`.

#### D6.b — Propagation : explicite, pas de cascade auto

Chaque caller vérifie `isinstance(result, AgentAbstention)`. Pas de cascade automatique car :
- Un forecast = abstention n'invalide pas forcément la recommendation (manager peut quand même voir données historiques)
- Une recommendation = abstention n'invalide pas le receipt (variant message géré côté receipt)

Pattern de référence dans `ReceiptService.build_daily_receipt()` :

```python
forecast = forecast_service.predict_today(hotel_id)
recommendation = recommendation_service.recommend(forecast, hotel_id) if not isinstance(forecast, AgentAbstention) else None

if isinstance(forecast, AgentAbstention) and isinstance(recommendation, AgentAbstention):
    return _full_abstention_variant(forecast, recommendation)
elif isinstance(recommendation, AgentAbstention):
    return _partial_abstention_variant(forecast, recommendation)  # forecast affiché, reco abstained
else:
    return _normal_variant(forecast, recommendation)
```

#### D6.c — Telemetry : étendre `agent_action_log` (PAS de table dédiée)

Migration `supabase/migrations/20260605000000_agent_action_log_abstention.sql` :

```sql
ALTER TABLE agent_action_log
    ADD COLUMN abstention_reason TEXT NULL,
    ADD COLUMN abstention_context JSONB NULL,
    ADD COLUMN abstention_layer TEXT NULL;

CREATE INDEX agent_action_log_abstention_idx
    ON agent_action_log (abstention_reason, created_at)
    WHERE abstention_reason IS NOT NULL;
```

**Choix : étendre vs nouvelle table** : étendre. Justification :
- Volume négligeable (< 5% des events seront abstentions)
- Évite jointures dans dashboard
- Une abstention EST un event agent — sémantiquement cohérent avec ADR-0003 D1
- Coût migration minimal (3 colonnes nullables + 1 index partiel)

**MV dérivée** : `abstention_daily` (nouvelle MV, refreshed nightly) — `hotel_id, date, layer, reason, count`. Permet à PM de tracker fréquence abstentions par cause sur dashboard.

#### D6.d — Variantes WhatsApp

**Variante 1 — Full abstention** (forecast + reco unknown) :
> *"Bonjour, données insuffisantes ce matin pour générer le Receipt. Aetherix préfère ne pas recommander aujourd'hui (raison: <abstention.reason>). Vous pouvez consulter l'historique sur <link>."*

**Variante 2 — Partial abstention** (forecast OK, reco unknown) :
> *"Bonjour, voici les prévisions du jour : <forecast_summary>. Aetherix n'est pas confiant pour recommander un staffing (confidence < seuil). Raison: <abstention.reason>. Suggestion: maintenir staffing standard."*

**Variante 3 — Drift alert** (forecast + reco normaux mais drift détecté) :
> *"Bonjour, voici votre Receipt: <normal>. ⚠️ Avis qualité : les données récentes divergent de l'historique (raison: <drift_feature>). Aetherix recommande de vérifier les chiffres ce soir."*

Copy validé par PM (action post-ADR — Story EVAL-2 DoD).

---

### D7 (Q7) — Intégration ADRs existants

| ADR | Articulation |
|---|---|
| **ADR-0002** memory-instrumentation (D11 `FakeEmbeddingProvider`) | EVAL-4 (parser eval) **ne duplique pas** les annotations memory. Eval parser = WhatsApp replies bruts annotés intent (catégorie `parser_intent` du golden dataset). Memory recall annotated truth = EVAL-8 Phase 4, dataset séparé. `FakeEmbeddingProvider` réutilisé dans la suite eval pour reproducibility (élimine drift API Mistral). |
| **ADR-0003** observability | **Étendre** `agent_action_log` avec 3 colonnes (D6.c) + 2 colonnes additionnelles eval-tracking (`eval_run_id UUID NULL`, `drift_score JSONB NULL`). Pas de table dédiée. Migration douce, additive, zéro régression. |
| **ADR-0005** cold-start meta-learner | LOO validation = **sous-set du golden dataset** (catégorie `cold_start_loo` à ajouter dans D1 si EVAL-3 + ADR-0005 atterrissent en parallèle — Phase 3 timing). 5 sandbox properties × 30j holdout. Gate runtime "MAPE Day-7 > 25% → auto-disable" cohabite avec D5 drift detection → un OU l'autre déclenche auto-disable. |
| **ADR-0006 DRAFT** POS integration | Catégorie `pos_anomaly` réservée dans la taxonomy (D1) avec 0 scenario Phase 3 — placeholder forward-compat. Quand ADR-0006 atterrit, ajout scenarios = simple PR sur `golden_dataset.jsonl`, pas de refactor framework. |

---

## 3. Schéma `eval/golden_dataset.jsonl` (canonique)

Annexe A — un exemple par layer/catégorie pour fixer le contrat.

```jsonl
{"schema_version":"1.0.0","id":"fcst-normal-001","category":"normal_day","layer":"forecast","created_at":"2026-06-04","author":"ivan","input":{"hotel_id":"demo-hotel-ber","date":"2025-09-15","occupancy":0.78,"weather_score":0.6,"event_impact":0.0,"regressors":["weather_score","event_impact","occupancy"]},"expected":{"covers_dinner":{"value":92,"tolerance_pct":0.15},"covers_breakfast":{"value":134,"tolerance_pct":0.12}},"failure_trigger":"MAPE > 15% sur covers_dinner OU > 12% sur covers_breakfast","notes":"Mercredi septembre BER, weekday baseline stable"}
{"schema_version":"1.0.0","id":"fcst-event-001","category":"event_day","layer":"forecast","created_at":"2026-06-04","author":"ivan","input":{"hotel_id":"demo-hotel-ber","date":"2025-10-04","occupancy":0.95,"event_impact":0.85,"event_type":"trade_fair","regressors":["weather_score","event_impact","occupancy"]},"expected":{"covers_dinner":{"value":138,"tolerance_pct":0.20}},"failure_trigger":"MAPE > 20% sur covers_dinner (event = bande large tolérée)","notes":"IFA Berlin trade fair — spike historique J+0 et J+1"}
{"schema_version":"1.0.0","id":"reco-confidence-low-001","category":"ood_edge","layer":"recommendation","created_at":"2026-06-04","author":"ivan","input":{"forecast_confidence":0.35,"covers_predicted":80,"covers_band":[40,120]},"expected":{"abstention":true,"abstention_reason":"confidence_below_threshold"},"failure_trigger":"Recommendation service ne retourne PAS AgentAbstention","notes":"Confidence 0.35 < 0.5 threshold (D6)"}
{"schema_version":"1.0.0","id":"recpt-partial-abstention-001","category":"ood_edge","layer":"receipt","created_at":"2026-06-04","author":"ivan","input":{"forecast":{"covers_dinner":92,"confidence":0.75},"recommendation":{"abstention":true,"reason":"data_quality_alert"}},"expected":{"variant":"partial_abstention","contains":["voici les prévisions","pas confiant"]},"failure_trigger":"Receipt utilise variante normale ou full_abstention","notes":"Forecast OK, reco abstained → variante 2 (D6.d)"}
{"schema_version":"1.0.0","id":"parser-accepted-fr-terse-001","category":"parser_intent","layer":"parser","created_at":"2026-06-04","author":"ivan","input":{"message":"ok merci","language":"fr"},"expected":{"intent":"accepted","confidence_min":0.85},"failure_trigger":"intent != accepted OU confidence < 0.85","notes":"Terse FR accepted — cas le plus fréquent en prod"}
{"schema_version":"1.0.0","id":"parser-modified-emoji-001","category":"parser_intent","layer":"parser","created_at":"2026-06-04","author":"ivan","input":{"message":"plutôt 4 personnes au lieu de 5 👀","language":"fr"},"expected":{"intent":"modified","confidence_min":0.70,"extracted":{"covers_modifier":-1}},"failure_trigger":"intent != modified","notes":"FR modifié + emoji — stress test parser robustesse"}
{"schema_version":"1.0.0","id":"drift-covers-spike-001","category":"ood_edge","layer":"drift","created_at":"2026-06-04","author":"ivan","input":{"feature":"covers_dinner","window_observations":[180,175,190,200,210,220,195],"baseline_snapshot_id":"covers_dinner_v1"},"expected":{"severity":"FAIL","algorithm":"ks_test","p_value_max":0.01},"failure_trigger":"Drift detector ne déclenche pas FAIL","notes":"Spike artificiel 2σ vs baseline 90j — synthetic injection"}
{"schema_version":"1.0.0","id":"lat-prediction-p95-001","category":"normal_day","layer":"latency","created_at":"2026-06-04","author":"ivan","input":{"endpoint":"/api/v1/predictions/today","n_calls":20,"warmup":3},"expected":{"p95_ms_max":8000,"p99_ms_max":12000},"failure_trigger":"p95 > 8000ms sur 20 appels chauds","notes":"SLO ADR-0003 D7 — endpoint chaud, après warmup"}
{"schema_version":"1.0.0","id":"pos-anomaly-placeholder","category":"pos_anomaly","layer":"forecast","created_at":"2026-06-04","author":"ivan","input":{},"expected":{},"failure_trigger":"PLACEHOLDER — Phase 4 ADR-0006","notes":"Forward-compat structure, pas de logique Phase 3"}
```

---

## 4. Spec `scripts/ci/check_eval_coverage.py`

```python
#!/usr/bin/env python3
"""Eval-by-design coverage gate — ADR-0007 D2/D3."""

# Signature
def main() -> int: ...

# Args (argparse)
#   --base-ref REF       Git ref to diff against (default: origin/main)
#   --strict             Exit 1 on FAIL (default: warn only — for local dev)
#   --json-out PATH      Write eval result JSON
#   --md-out PATH        Write Markdown report (for PR sticky comment)
#   --print-ignored      Show files matching trigger paths but skipped via eval-exempt

# Behaviour
# 1. Read changed files (git diff --name-only base..HEAD)
# 2. If `eval-exempt` label present (via gh CLI or env GITHUB_PR_LABELS) → exit 0
# 3. Match changed files against EVAL_TRIGGER_PATHS glob
#    - If no match → exit 0 (no eval needed)
#    - If match in providers/ OR prompts/ → layer = ALL
#    - Else → layer = mapping(file → layer)
# 4. Compute cache key = sha256(concat hashes of touched trigger files)
#    - If cache_key in eval/baselines/.cache_keys.json → load previous result, exit 0
# 5. Invoke scripts/eval/run_all.py --layers <detected> --json-out result.json
# 6. Compare per-category metrics vs eval/baselines/<layer>_baseline.json
#    - regression > 3pp on any forecast category → FAIL
#    - parser accuracy drop > 2pp OR per-intent precision < 0.85 → FAIL
#    - drift severity FAIL on baseline scenarios → FAIL
#    - latency p95 > SLO threshold → FAIL
# 7. Compute coverage % = (categories with ≥1 PASS scenario) / total categories
#    - ≥ 80% PASS, 60-80% WARN, <60% FAIL
# 8. Compute touched-but-not-evaluated check
# 9. Write Markdown report (diff table) to --md-out
# 10. Update cache_key in eval/baselines/.cache_keys.json
# 11. Exit: 0 PASS / 1 FAIL strict / 2 ERROR / 3 WARN

# Dependencies (in addition to existing repo deps)
#   gh CLI (label check) — already installed in CI runner
#   subprocess (git diff)
#   json, pathlib, argparse, hashlib (stdlib)
#   scripts.eval.run_all (sibling module)
```

**Tests** : `backend/tests/ci/test_check_eval_coverage.py` (analogue à `test_check_schema_drift.py` si existe) — mock git diff, golden_dataset, baselines. Pas de network.

---

## 5. Spec `scripts/eval/*.py`

Arborescence cible :

```
scripts/eval/
├── __init__.py
├── run_all.py                 # runner global (entry point CI)
├── loader.py                  # parse golden_dataset.jsonl, validate schema_version
├── reporter.py                # Markdown + JSON output via jinja2 templates
├── baselines.py               # load/save eval/baselines/*.json
├── eval_forecast.py           # MAPE stratifié per-category — refactor de measure_mape_j1.py
├── eval_parser.py             # parser accuracy + confusion matrix (Haiku call mockable)
├── eval_drift.py              # KS / Wasserstein / PSI per feature
├── eval_latency.py            # bench p50/p95/p99 par endpoint (httpx async)
├── eval_recall.py             # smoke recall Phase 3 (precision@5 sur 5 hits annotés), full Phase 4 EVAL-8
└── templates/
    └── report.md.j2           # template Markdown PR comment
```

### 5.a `run_all.py`

```python
"""Entry point: scripts/eval/run_all.py
Usage: python -m scripts.eval.run_all --layers forecast,parser --json-out r.json --md-out r.md

Args:
  --layers          Comma-separated: forecast,parser,drift,latency,recall,all (default: all)
  --dataset         Path golden dataset (default: eval/golden_dataset.jsonl)
  --baselines-dir   Path baselines (default: eval/baselines/)
  --json-out        Result JSON output
  --md-out          Markdown report output
  --seed            Random seed (default: 42)

Behaviour:
  for each layer in --layers:
    scenarios = loader.load(dataset, layer=layer)
    result = eval_<layer>.run(scenarios)
    compare = baselines.diff(result, baselines-dir/<layer>_baseline.json)
    aggregate.append({layer, result, compare})
  reporter.write_json(aggregate, --json-out)
  reporter.write_md(aggregate, --md-out)
  return overall_exit_code  # 0 PASS, 1 FAIL, 3 WARN
"""
```

### 5.b `eval_forecast.py`

Refactor de `scripts/ops/measure_mape_j1.py` :
- Garde la logique Prophet train/predict
- AJOUTE `category` stratification : group scenarios par `category`, compute MAPE per group
- AJOUTE per-category tolerance check (chaque scenario a son `tolerance_pct` dans `expected`)
- AJOUTE confidence interval check (`interval_width=0.80` Prophet) — `% scenarios où y_true dans [yhat_lower, yhat_upper]`
- Output JSON :

```json
{
  "layer": "forecast",
  "overall_mape_j1_holdout": 0.1509,
  "per_category_mape": {
    "normal_day": 0.094,
    "event_day": 0.178,
    "weather_anomaly": 0.142,
    "ota_cancellation_wave": 0.221,
    ...
  },
  "per_category_count": {"normal_day": 15, "event_day": 8, ...},
  "interval_coverage_pct": 0.78,
  "seed": 42,
  "regressors": ["weather_score","event_impact","occupancy"]
}
```

### 5.c `eval_parser.py`

> **Amended 24/09/2026 — see §15.** The original spec below said the real backend
> "calls real Haiku" and that CI uses a deterministic `FakeIntentClassifier`. As
> implemented until 24/09, the real backend fell back to the fake heuristic whenever
> the model answered `free_form`, no workflow ever ran it, and the only number ever
> produced (`parser_baseline.json`, accuracy 1.0, n=16) came from the fake backend
> scored on the cases its rules were written for. **No parser model-quality number
> has ever been measured.** Current behaviour and the remaining gap: §15.

```python
"""Parser eval — EVAL-4 (as amended by §15)
- Loads parser_intent scenarios (split: dev | heldout)
- EVAL_PARSER_BACKEND=real (opt-in workflow eval-parser-real.yml): grades the
  production path parse_action → parse_inbound → outcome_for_feedback, model
  included, primary provider only, no heuristic fallback; model errors and
  out-of-taxonomy answers are typed errors (count as misses). No API key → exit 2.
- EVAL_PARSER_BACKEND=fake (PR gate): plumbing check only, quality_signal=false,
  never compared to a baseline, never frozen as one
- Always: production-path ceiling (best accuracy reachable whatever the model says)
- Outputs: accuracy, per-intent precision/recall, confusion matrix
  (rows accepted/rejected/modified, cols + not_recorded/error), per-split accuracy
"""
```

> ~~**Décision implicite** : un `FakeIntentClassifier` (analogue à `FakeEmbeddingProvider` D11 ADR-0002) est requis. Stocké dans `backend/tests/providers/fake_intent_classifier.py`. Returns deterministic labels via hash. EVAL-4 Story DoD.~~
> Superseded 24/09/2026 (§15): the fake lives in `scripts/eval/fake_intent_classifier.py`, is keyword rules (not a hash) written against the `dev` cases, and is a plumbing check only. Unlike `FakeEmbeddingProvider`, which replaces an input to the system under test, this fake replaced the system under test itself, so it cannot measure it.

### 5.d `eval_drift.py`

```python
"""Distribution shift eval — EVAL-3
- Loads drift_* scenarios
- Loads baseline snapshots eval/distribution_snapshots/*.json
- For each scenario:
    apply algorithm (KS / Wasserstein / PSI) on observed window vs baseline
    classify severity (WARN / FAIL per D5 thresholds)
    compare to expected severity in scenario
- Returns per-feature drift scores + severity assertions
"""
```

### 5.e `eval_latency.py`

```python
"""Latency SLO eval — EVAL-5
- Loads latency_* scenarios
- Spawns local FastAPI test client (uvicorn in subprocess OR httpx AsyncClient against staging)
- Runs N warmup + M timed calls per endpoint
- Computes p50, p95, p99 with seed-fixed jitter
- Asserts p95 < expected
"""
```

### 5.f `eval_recall.py` (smoke Phase 3, full Phase 4)

Phase 3 scope : smoke seulement (5 scenarios annotés). Full precision@k = EVAL-8 Phase 4.

---

## 6. DDL Supabase (3 nouveaux objets + 1 ALTER)

### 6.a ALTER `agent_action_log` (D6.c + D7.b)

```sql
-- supabase/migrations/20260605000000_eval_observability.sql

ALTER TABLE agent_action_log
    ADD COLUMN abstention_reason TEXT NULL,
    ADD COLUMN abstention_context JSONB NULL,
    ADD COLUMN abstention_layer TEXT NULL,
    ADD COLUMN eval_run_id UUID NULL,
    ADD COLUMN drift_score JSONB NULL;

CREATE INDEX agent_action_log_abstention_idx
    ON agent_action_log (abstention_reason, created_at)
    WHERE abstention_reason IS NOT NULL;

CREATE INDEX agent_action_log_eval_run_idx
    ON agent_action_log (eval_run_id, created_at)
    WHERE eval_run_id IS NOT NULL;
```

### 6.b Table `eval_runs`

```sql
CREATE TABLE eval_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    triggered_by    TEXT NOT NULL,                  -- "ci" | "manual" | "scheduled"
    git_sha         TEXT NOT NULL,
    pr_number       INTEGER NULL,
    layers          TEXT[] NOT NULL,                -- ["forecast","parser",...]
    seed            INTEGER NOT NULL DEFAULT 42,
    dataset_version TEXT NOT NULL,                  -- schema_version golden_dataset
    overall_status  TEXT NOT NULL,                  -- "pass" | "fail" | "warn" | "error"
    coverage_pct    REAL NOT NULL,
    result_json     JSONB NOT NULL,                 -- full result aggregate
    duration_ms     INTEGER NOT NULL
);

CREATE INDEX eval_runs_created_at_idx ON eval_runs (created_at DESC);
CREATE INDEX eval_runs_pr_idx ON eval_runs (pr_number) WHERE pr_number IS NOT NULL;
```

**Justification table dédiée vs étendre `agent_action_log`** : un eval run n'est pas un agent action — différents acteurs, différents accès. `eval_runs` est un audit log eval, `agent_action_log` est un audit log production. Foreign-key soft via `agent_action_log.eval_run_id`.

### 6.c Table `eval_baselines`

```sql
CREATE TABLE eval_baselines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    layer           TEXT NOT NULL,                  -- "forecast" | "parser" | "drift" | "latency" | "recall"
    git_sha         TEXT NOT NULL,
    baseline_json   JSONB NOT NULL,                 -- per-category metrics frozen
    reason          TEXT NOT NULL,                  -- pourquoi baseline reset
    pr_number       INTEGER NULL,
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by   UUID NULL REFERENCES eval_baselines(id)
);

CREATE UNIQUE INDEX eval_baselines_active_idx
    ON eval_baselines (layer)
    WHERE is_active = TRUE;
```

**Note** : git-tracked baselines (`eval/baselines/*.json`) restent **source de vérité runtime** (le CI les lit directement, pas la DB). `eval_baselines` table = audit log historique (pour répondre *"quel était notre baseline le 12 août 2026 ?"*). Pas de risque de drift entre git et DB tant que les commits PR mettent à jour les deux (action post-baseline-bump).

### 6.d MV `distribution_shift_daily`

```sql
CREATE MATERIALIZED VIEW distribution_shift_daily AS
SELECT
    aa.hotel_id,
    DATE(aa.created_at) AS day,
    aa.drift_score->>'feature' AS feature,
    aa.drift_score->>'algorithm' AS algorithm,
    (aa.drift_score->>'severity')::TEXT AS severity,
    (aa.drift_score->>'p_value')::REAL AS p_value,
    (aa.drift_score->>'distance')::REAL AS distance,
    COUNT(*) AS occurrences
FROM agent_action_log aa
WHERE aa.drift_score IS NOT NULL
GROUP BY aa.hotel_id, day, feature, algorithm, severity, p_value, distance;

CREATE UNIQUE INDEX distribution_shift_daily_unique_idx
    ON distribution_shift_daily (hotel_id, day, feature, algorithm);
```

Refresh : APScheduler nightly job (réutilise pattern ADR-0003 D8).

### 6.e MV `abstention_daily` (bonus D6.c)

```sql
CREATE MATERIALIZED VIEW abstention_daily AS
SELECT
    hotel_id,
    DATE(created_at) AS day,
    abstention_layer AS layer,
    abstention_reason AS reason,
    COUNT(*) AS count
FROM agent_action_log
WHERE abstention_reason IS NOT NULL
GROUP BY hotel_id, day, layer, reason;

CREATE UNIQUE INDEX abstention_daily_unique_idx
    ON abstention_daily (hotel_id, day, layer, reason);
```

---

## 7. Plan migration ADR-0002 / ADR-0003

**ADR-0002** : aucune modification. `FakeEmbeddingProvider` (D11) réutilisé tel quel dans eval suite. `MemoryRecallService` pas touché en Phase 3 (full eval recall = Phase 4 EVAL-8).

**ADR-0003** : étendre `agent_action_log` (D6.c, D7.b) avec 5 colonnes nullables additives. Aucune régression. Migration `20260605000000_eval_observability.sql` (cf. 6.a). Index partiels minimisent overhead.

**Code à modifier** :
- `backend/app/services/agent_event.py` — étendre `AgentEvent` dataclass (5 champs optionnels)
- `backend/app/db/models.py` — ORM mirror (Décision #16 schema drift gate)
- `backend/app/services/abstention.py` — NEW (D6.a)
- `backend/app/services/prediction_engine.py` — return `AgentAbstention` paths
- `backend/app/services/recommendation_formatter.py` — return `AgentAbstention` paths
- `backend/app/services/receipts.py` — handle 3 variants (D6.d)
- `backend/app/services/query_parser.py` — return `AgentAbstention` if confidence < 0.6 (déjà partiel, finaliser)

---

## 8. Story breakdown final Phase 3 (confirmation + ajustements)

| Story | Linear (à créer) | Effort | Sprint | Dépendance |
|---|---|---|---|---|
| **EVAL-0** Golden Dataset + Failure Definitions + Prompts extraction | HOS-EVAL-0 | **2.5 j** | N | BLOCKING |
| **EVAL-1** Stratified MAPE + CI Regression Gate | HOS-EVAL-1 | 1.5 j | N+1 | EVAL-0 |
| **EVAL-2** AgentAbstention contract + WhatsApp variants + agent_action_log extension | HOS-EVAL-2 | **2.5 j** | N+1 | EVAL-0 |
| **EVAL-3** Distribution Shift Detector + cold-start auto-disable hook | HOS-EVAL-3 | 2 j | N+2 | EVAL-0 + ADR-0005 |
| **EVAL-4** Inbound Parser Haiku Accuracy + FakeIntentClassifier | HOS-EVAL-4 | 1.5 j | N+1 | EVAL-0 |
| **EVAL-5** Latency SLO + dashboard MV | HOS-EVAL-5 | 1 j | N+2 | EVAL-0 |
| **Total** | | **~11 j** | 3 sprints | |

**Ajustements vs brief PM** :
- **EVAL-0 : +0.5 j** — ajout extraction prompts (`backend/prompts/`, dossier dédié D2.a) requise pour gate déterministe.
- **EVAL-2 : +1 j** — sentinel + dataclass + 3 services + 2 variantes WhatsApp + telemetry extension = sous-estimé brief PM (1.5 j → 2.5 j).
- **EVAL-3 : ADR-0005 dépendance** — si ADR-0005 pas encore implémenté en Phase 3, EVAL-3 ship sans le hook auto-disable et reste valide (drift seulement alerté).

**Pilot gate (Track A Phase 3)** : EVAL-0 + EVAL-1 + EVAL-2 + EVAL-4 = pilot-blocking. EVAL-3 + EVAL-5 = nice-to-have avant pilot, peuvent ship en parallèle ou après J+30 pilot start.

**Sequencing recommandé** :
- **Sprint N** (1 semaine) : EVAL-0 seul (blocks tout)
- **Sprint N+1** (1 semaine) : EVAL-1 + EVAL-2 + EVAL-4 en parallèle (3 PRs)
- **Sprint N+2** (1 semaine) : EVAL-3 + EVAL-5 en parallèle (2 PRs)

---

## 9. Risques + mitigations

| # | Risque | Impact | Mitigation |
|---|---|---|---|
| R1 | **Golden dataset curation bottleneck** : 71 scenarios à annoter par PM seul. | Bloque EVAL-1 → EVAL-5 (cascading 2 sprints). | Phase 3 : commencer par 40 scenarios (couvrir 6/11 catégories min PASS) → permet ship EVAL-1/2/4 ; compléter à 71 en sprint N+2 en parallèle EVAL-3/5. |
| R2 | **CI time budget** : suite eval full > 5 min sur GitHub Actions. | Slow PR feedback, dev rejet. | Cache cleverly (D2.e), subset filtré par layer (D2.b), split en jobs parallel si > 3 min. Mesurer après EVAL-1 ship. |
| R3 | **Baseline drift sans détection** : équipe oublie de mettre à jour eval/baselines lors de model upgrade volontaire. | Eval gate devient faux positif chronique → ignored. | Tooling: `scripts/eval/bump_baseline.py` avec check obligatoire `--reason` + commit message tag `[BASELINE_BUMP]` + entrée CLAUDE.md auto. |
| R4 | **LLM non-determinism** : Haiku parser eval peut fluctuer même avec temperature 0. | Faux positifs CI, dev frustration. | `FakeIntentClassifier` en CI (déterministe), `--backend=real` réservé aux runs nightly schedulés (signal qualité reelle, pas gate PR). **Amended 24/09/2026 (§15):** the nightly run never existed; the real run is now the opt-in workflow `eval-parser-real.yml` (label / dispatch / weekly), and the fake in CI is a plumbing check, not a quality signal. |
| R5 | **Drift snapshot baseline obsolescence** : snapshot training set figé devient irrelevant après 6 mois (saisonnalité). | Auto-disable cold-start meta-learner perpétuellement → forecast dégradé. | Revue trimestrielle PM des baselines drift. PR `BASELINE_RESET` documentée. |
| R6 | **Mauvaise interaction ADR-0005 et EVAL-3** : 2 mécanismes auto-disable concurrent (Day-7 MAPE > 25% ET drift FAIL). | Cold-start désactivé sans cause claire. | EVAL-3 emit `auto_disable_reason` distinct → log dans `agent_action_log` permet diagnostic. ADR-0005 wrap reason. |
| R7 | **`eval-exempt` label abusé** : devient flag pour bypass eval sur changes risqués. | Régressions silencieuses, gate inefficace. | SM review obligatoire de toute PR `eval-exempt` (cas humain). Audit trimestriel : compter PR `eval-exempt` mergées par catégorie. |
| R8 | **Extraction prompts (EVAL-0) casse contrats existants** : déplacer `_SYSTEM_PROMPT_TEMPLATE` hors `agent_constitution.py` peut casser imports. | Bug régression. | Garder import shim dans `agent_constitution.py` (`from app.prompts.constitution import _SYSTEM_PROMPT_TEMPLATE`). Sub-task EVAL-0. |

---

## 10. Definition of Done — ADR-0007 ACCEPTED

L'ADR est **ACCEPTED** quand :

- [x] Q1-Q7 tranchés avec rationale (D1-D7 ci-dessus)
- [x] Schéma `golden_dataset.jsonl` canonique fixé + 8 exemples livrés (Annexe A)
- [x] Spec `scripts/ci/check_eval_coverage.py` (signature, exit codes, dependencies) §4
- [x] Spec `scripts/eval/*.py` (un script par layer + runner global) §5
- [x] DDL Supabase 5 objets (1 ALTER + 2 tables + 2 MVs) §6
- [x] Plan migration ADR-0002/0003 documenté §7
- [x] Story breakdown Phase 3 confirmé + estimations + sequencing §8
- [x] Risques R1-R8 + mitigations §9
- [ ] PM (Ivan) sign-off — variante WhatsApp copy (D6.d) validée
- [ ] CLAUDE.md Décision #22 amendée avec lien vers `docs/adr/0007-evaluation-by-design.md`
- [ ] Session SM (Bob) déclenchée pour créer 6 stories Linear

---

## 11. Décisions liées

- **CLAUDE.md Décision architecturale #16** (schema drift gate) — pattern reproduit (hard gate, blocking merge, ignore-file)
- **CLAUDE.md Décision architecturale #22** (Eval-by-design gate CI) — la décision dont cet ADR est l'implémentation
- **CLAUDE.md Décision #10** (Provider singleton via `lifespan`) — exploited via `EMBEDDING_BACKEND=fake` pour reproducibility (Qonto dim. 4)
- **CLAUDE.md Décision #15** (Phase 2 Receipts scope) — parser Haiku 0.6 threshold réutilisé tel quel
- **ADR-0001** Aetherix MCP Server v0 — `agent_action_log` (D7 cited) base de l'extension
- **ADR-0002** memory-instrumentation — `FakeEmbeddingProvider` D11 réutilisé, recall annotated truth déferé EVAL-8 Phase 4
- **ADR-0003** agent observability — `agent_action_log` étendu (5 colonnes additives), pas de table dédiée pour abstentions
- **ADR-0005** cold-start meta-learner — gate runtime Day-7 MAPE 25% cohabite avec D5 drift FAIL (2 paths auto-disable, diagnostiqués via `auto_disable_reason`)
- **ADR-0006 DRAFT** POS integration — catégorie `pos_anomaly` réservée forward-compat dans taxonomy (D1)

---

## 12. Actions post-ADR

1. **Drop suffixe DRAFT** — fichier renommé `0007-evaluation-by-design.md` (action effectuée par cette session Architect)
2. **Update CLAUDE.md Décision #22** — ajouter lien `docs/adr/0007-evaluation-by-design.md` (action effectuée par cette session Architect)
3. **Notifier PM (Ivan)** — sign-off variantes WhatsApp D6.d + validation finale ADR
4. **Session SM (Bob)** — créer 6 stories Linear `HOS-EVAL-0` à `HOS-EVAL-5` avec :
   - Description = lien vers `docs/adr/0007-evaluation-by-design.md` + section pertinente
   - Acceptance criteria = DoD section §3 (EVAL-0), §4 (EVAL-1 spec), §5 (EVAL-2..5)
   - Effort = table §8
   - Sequencing = sprint N → N+2
5. **Post-EVAL-0/1/2/4 shipped (pilot gate)** : pilot Phase 3 (HOS-176) débloqué côté reliability
6. **Post-EVAL-0..5 shipped** : rédiger `tools/bmad/eval-by-design-workflow.md` (asset BMad réutilisable, Phase 3 Track B technical write-up)
7. **Post-EVAL-0..5 shipped** : rédiger article REX *"How we extended BMad-Method with Evaluation-by-Design for AI/ML products"* (Phase 3 Track B)

---

## Annexe A — JSONL exemples canoniques

Cf. section §3 — 8 exemples couvrant les layers : forecast (normal, event), recommendation (abstention), receipt (partial abstention), parser (FR terse, FR modified emoji), drift (KS spike), latency (p95 SLO), pos_anomaly (placeholder).

---

## 13. Addendum — 2026-06-19 · Eval-by-design = offline gate + runtime eval + outcome eval

> **Status**: Accepted (amendement de portée) · **Date**: 2026-06-19 · **Auteur**: SM (Bob)
> **Trigger**: clôture des guardrails runtime Epic 12 (HOS-212, S4→S6) + arbitrage PO sur la portée du principe
> **Amende**: §1 Goal — étend la définition au-delà du gate CI dev-time
> **Articule**: Epic 11 (eval framework, HOS-203), Epic 12 (runtime guardrails, HOS-212), Epic 10 (pilot Trust-KPI, HOS-174)

### 13.1 Décision

L'ADR-0007 v1 cadre eval-by-design essentiellement comme un **gate CI pre-merge** (D2/D3 : bloquer un merge qui régresse le golden dataset). Cette portée est **nécessaire mais insuffisante** : un gate dev-time prouve la qualité sur des scénarios synthétiques figés, mais n'évalue rien du comportement de l'agent **en production**, sur trafic réel, sous drift.

**Amendement** : eval-by-design s'applique à **tout le pipeline agentique, en aval comme en amont** — **trois bras complémentaires** partageant une taxonomie et un vocabulaire de sévérité communs (`eval/FAILURE_THRESHOLDS.md`, raisons typées NFR2) pour qu'un « FAIL » signifie la même chose partout :

| Bras | Quand | Quoi | Implémentation |
|---|---|---|---|
| **A — Offline / dev-time** | Pre-merge (CI) | Non-régression sur golden dataset : MAPE stratifié, parser accuracy, coverage catégorielle | EVAL-0/1 (Epic 11) — gate `check_eval_coverage.py` |
| **B — Runtime / online** | Production, continu | Garde-fous + détection d'anomalie sur trafic réel : taux d'erreur, timeouts LLM, bornes de sortie, abstention, drift, latence SLO | **Epic 12 guardrails G-1..G-6** + EVAL-3/EVAL-5 (MV sur `agent_action_log`) |
| **C — Outcome / aval** | Post-dispatch, boucle longue | La sortie a-t-elle été actionnée et a-t-elle produit de la valeur : acceptance, ablation, P&L | Trust-KPI Epic 10 (HOS-177/178) — KPI framework §Niveau 1-3 |

### 13.2 Conséquences

1. **`eval-exempt` sur Epic 12 est cohérent, pas une entorse.** Exempter les guardrails runtime (Bras B) du gate offline (Bras A) est correct : on ne passe pas un parachute au golden dataset, on le mesure en vol. Condition : le Bras B est tenu au **même standard** que A — chaque étage émet un signal mesurable, à raison typée (NFR2), alimentant les métriques d'abstention. C'est le cas (G-1..G-5 livrés S4-S6).

2. **Le seam à fermer = rattacher le Bras C au framework.** L'eval d'outcome vit aujourd'hui dans l'instrumentation pilote (Epic 10), hors taxonomie eval. Tant qu'il n'est pas rattaché, « eval-by-design » reste partiel sur l'étage le plus en aval — la valeur réelle. À cadrer Phase 4 (outcome-capture instrumentation, Décision #26).

3. **Matrice de couverture par étage** (vivante — miroir d'un doc Linear opérationnel) :

| Étage pipeline | Bras A (offline) | Bras B (runtime) | Bras C (outcome) |
|---|---|---|---|
| Ingest PMS/POS | `ood_edge` | drift detector (EVAL-3 — ⚠️ HOS-207 non livré) | — |
| Parse inbound | scénarios parser | abstention `parser_low_confidence` ✅ ; durcissement injection ⚠️ G-6 (HOS-253) | — |
| Forecast | MAPE stratifié (EVAL-1 — ⚠️ gate WARN, HOS-216/274) | cold-start guard + `forecast_guardrail` ✅ | — |
| Staffing / reco | — | `output_sanity` + feedback bounds ✅ | acceptance rate |
| Dispatch | — | heartbeat + `error_rate_monitor` ✅ | — |
| Feedback / training | — | guard bornes + rejet non-silencieux ✅ | — |
| Outcome / valeur | — | — | Trust-KPI + ablation (Epic 10) |
| Latence (transverse) | — | SLO + MV + alerte (EVAL-5 — ⚠️ HOS-209, S6) | — |

4. **Risque nommé** : un eval-by-design *réduit au Bras A* donne un système prouvé sur synthétique mais aveugle au drift live ; *réduit au Bras B* laisse les régressions merger librement. Les trois bras sont requis et indissociables.

### 13.3 Suivi

- **Ré-armement Bras A** (gate offline → blocking) tracké : HOS-216 (machinerie, WARN) → HOS-274 (flip blocking après N PR vertes).
- **Rattachement Bras C** au framework : à scoper Phase 4 (outcome-capture, Décision #26). Pas d'issue dédiée à ce jour → candidat backlog.
- **Cross-link CLAUDE.md** : Décision #22 à amender (ajouter lien vers cet addendum + reformuler « gate CI » → « offline + runtime + outcome »). **À confirmer PO avant édition de la source de vérité** — non fait dans cet addendum.

---

## 14. Addendum — 2026-07-30 · Processus de calibration LLM-judge (pré-requis EVAL-6)

> **Status**: Accepted · **Date**: 2026-07-30 · **Auteur**: PM (session Claude Code)
> **Trigger**: veille comparative — Airbnb Engineering, "Eval-Driven Development: Lessons from Evaluating GenAI at Scale" (medium.com/airbnb-engineering, 2026). Comparaison détaillée : vault Obsidian `Veille/Veille_Tech_Stack.md` §JUL 20, 2026.
> **Comble** : gap identifié — EVAL-6 (`docs/planning/evaluation-by-design.md` §Phase 4, `eval/FAILURE_THRESHOLDS.md` ligne "LLM reasoning") mentionne un "human spot-check" et un "judge model" sans jamais spécifier *comment* faire confiance à ce juge avant de l'utiliser à l'échelle.
> **Implémente** : Décision #32 (CLAUDE.md)

### 14.1 Constat

Airbnb documente un principe absent de l'ADR-0007 v1/§13 : un LLM-as-judge n'est fiable que s'il est **calibré contre un jugement humain de référence avant d'être déployé en autonomie** — golden set dédié, métrique d'accord quantifiée, seuil explicite, recalibration périodique. Sans ça, EVAL-6 risque de construire un juge qui semble fonctionner (rubrique plausible) sans jamais avoir vérifié qu'il est d'accord avec Ivan sur ce qui compte comme une explication correcte.

### 14.2 Décision — processus de calibration EVAL-6

**Ce juge évalue une seule dimension** (fidélité factuelle de l'explication de reasoning — pas de "god evaluator" multi-dimensions, cohérent Airbnb §"keep evaluators focused" et avec le principe déjà appliqué dans ce repo d'1 juge = 1 responsabilité étroite).

**D14.a — Rubrique = miroir exact de `FAILURE_THRESHOLDS.md`, pas une nouvelle définition.**

Le juge ne doit pas réinterpréter ce qu'est une "bad explanation" — il applique la définition déjà contractuelle (§Failure definitions, ligne "LLM reasoning") :

```
Score 1 (PASS) sauf si l'explication contient AU MOINS UN des éléments suivants :
  (a) attribue le driver demande/staffing à une cause absente du contexte d'input
      (mauvaise météo/event/occupancy invoqué)
  (b) référence un événement, une réservation ou un pattern absent des données d'input
  (c) énonce une valeur numérique (covers, % occupancy, effectif staff) qui ne correspond
      pas au payload input/prédiction fourni
Score 0 (FAIL) si (a) ou (b) ou (c).
```

Binaire, pas d'échelle 1-5 — cohérent Airbnb ("ambiguity is the enemy... if a human can't apply the rubric consistently, an LLM certainly can't") et avec la nature contractuelle déjà établie de `FAILURE_THRESHOLDS.md`.

**D14.b — Golden set de calibration : nouveau fichier, schema distinct de `golden_dataset.jsonl`.**

`golden_dataset.jsonl` teste input→output attendu (tolérance numérique). Le golden set de calibration teste texte-libre→verdict humain — schema différent, fichier séparé : `eval/judge_calibration_set.jsonl`.

```json
{
  "schema_version": "1.0.0",
  "id": "judge-cal-001",
  "recommendation_id": "synthetic",
  "input_context": {
    "hotel_id": "demo-hotel", "date": "2025-03-01",
    "occupancy": 0.76, "weather_score": 0.3, "event_impact": 0.0,
    "predicted_covers": 90
  },
  "explanation_text": "Covers forecast at 90 reflects typical weekday demand, no major weather or event impact this period.",
  "human_verdict": "pass",
  "human_verdict_reason": "Attribution cohérente avec input_context, aucun chiffre ni événement inventé.",
  "failure_category": null,
  "created_at": "2026-07-30",
  "author": "ivan"
}
```

Pour un cas FAIL synthétique (injection délibérée, cf. Airbnb "synthetic acceptable") :

```json
{
  "id": "judge-cal-002",
  "explanation_text": "Covers forecast at 90 driven by the jazz festival downtown this weekend.",
  "human_verdict": "fail",
  "human_verdict_reason": "Référence un événement (jazz festival) absent de input_context.event_impact=0.0",
  "failure_category": "b_invented_event"
}
```

**Volume minimum avant premier run de calibration : 50 exemples** (borne basse Airbnb), incluant les 3 catégories d'échec (a/b/c) + des cas PASS variés (jour normal, event réel, weather réel). Avant le premier pilote réel (pas encore de vraies recommandations en prod), ces 50 exemples sont **construits manuellement par Ivan** — bonnes explications tirées de `golden_dataset.jsonl` existant + corruption délibérée pour générer les cas FAIL. Post-pilote (Phase 4), enrichir avec de vrais cas ambigus rencontrés en prod (alimente aussi EVAL-7).

**D14.c — Modèle juge : Claude Sonnet via `LLMProvider` (Décision #9), pas un nouvel outil/SDK.** ⚠️ *Choix du modèle remplacé le 24/09/2026 par §14.5 (juge d'une autre famille que le générateur) ; le reste de D14.c tient.*

Cohérent Décision #1 (Sonnet = reasoning principal) et rejet déjà acté deepeval/Braintrust pour Phase 3 (§ADR-0007 corps). Le juge appelle `LLMProvider.complete()` avec un prompt dédié (rubrique D14.a + `input_context` + `explanation_text`, **jamais** le prompt original qui a généré l'explication — le juge ne doit voir que le résultat à évaluer, pas le raisonnement de génération, pour éviter un biais d'auto-cohérence).

**Tension notée, non résolue ici** : Sonnet évalue une sortie générée par Sonnet (même famille de modèle) — risque de biais de préférence correlé (les erreurs que Sonnet ne "voit" pas en générant, il risque de ne pas les voir non plus en jugeant). Airbnb recommande "stronger LLMs" comme juges. Si la calibration D14.d échoue de façon répétée avec Sonnet-juge, **escalader à Opus comme juge uniquement** (pas comme générateur — coût maîtrisé, un seul call léger par recommandation échantillonnée) avant de conclure que le problème est la rubrique plutôt que le juge.

**D14.d — Métrique de calibration : Cohen's kappa, seuil ≥ 0.8.**

Kappa plutôt que le simple % d'accord brut cité par Airbnb ("80-90%") : la distribution PASS/FAIL du golden set est probablement déséquilibrée (la plupart des recommandations sont correctes) — un % d'accord brut est gonflé par le hasard sur la classe majoritaire. Kappa corrige pour l'accord attendu par chance. Seuil ≥ 0.8 = "almost perfect agreement" (Landis & Koch), traduction rigoureuse de la fourchette Airbnb "high 80s-90s" one fois l'effet de classe déséquilibrée retiré.

**Procédure** :
1. Run le juge sur les 50+ exemples de `judge_calibration_set.jsonl`
2. Calculer kappa(verdict juge, `human_verdict`)
3. Si kappa < 0.8 : analyser les désaccords un par un, affiner la rubrique/prompt/few-shot examples, ré-itérer
4. Si kappa ≥ 0.8 sur 2 runs consécutifs (stabilité, pas un coup de chance) : juge calibré, autorisé à scorer en autonomie sur trafic échantillonné

**Règle d'arrêt (adaptée du principe Airbnb "if experts disagree, stop before automating")** : solo-founder aujourd'hui — Ivan est le seul labeliseur humain, donc pas de désaccord inter-humain à ce stade. La règle s'applique à la place au binôme **juge vs Ivan** : tant que kappa < 0.8, EVAL-6 **ne scoring pas en autonomie** — chaque désaccord juge/Ivan est un signal que la rubrique ou le prompt du juge a un angle mort, pas que "le juge se trompe parfois". Réserver la version originale de la règle (désaccord inter-humain) pour le jour où un second reviewer (rôle QA BMad, ou hire) rejoint le golden-set labeling.

**D14.e — Recalibration : triggers explicites, pas de calendrier fixe seul.**

Recalibrer si l'un de ces événements survient (le calendrier fixe seul — Airbnb dit "périodiquement" — est insuffisant sans triggers événementiels) :
- Changement de prompt ou de modèle sur le reasoning engine généré (le juge évalue un output qui a changé de distribution)
- Swap de provider (Décision #9 — passage Claude→Gemini/GPT fallback)
- Trimestriel, systématique, même sans changement détecté (dérive lente du golden set vs réalité terrain)
- Accumulation de désaccords juge/PM sur le spot-check hebdomadaire EVAL-7 au-delà d'un seuil (à définir au moment du build EVAL-7 — pas fixé ici, dépend du volume réel)

### 14.3 Conséquences

- **EVAL-6 acceptance criteria amendé** : ajouter à `docs/planning/evaluation-by-design.md` §Phase 4 — "kappa ≥ 0.8 sur `eval/judge_calibration_set.jsonl` (2 runs consécutifs) avant d'activer le sampling live" comme critère bloquant, pas une note annexe.
- **`eval/FAILURE_THRESHOLDS.md`** : la ligne "LLM reasoning" référence désormais ce processus de calibration plutôt qu'un simple seuil de spot-check humain (5%) sans méthode de confiance sur le juge qui, à terme, fera une partie de ce spot-check.
- **Pas de nouvel outil** : réutilise `LLMProvider` (Décision #9/#10) + JSONL custom (cohérent rejet deepeval/Braintrust Phase 3, §ADR-0007 corps).
- **Effort estimé** : +0.5 jour dev sur l'estimation EVAL-6 existante (construction golden set calibration + script kappa) — ajustement mineur, pas un nouveau bloc de stories.

### 14.4 Alternatives rejetées

| Alternative | Raison du rejet |
|---|---|
| % d'accord brut (Airbnb tel quel) | Gonflé par déséquilibre de classe PASS/FAIL — kappa est le choix rigoureux à petit N |
| Juge = même call que le générateur (self-eval inline) | Biais d'auto-cohérence maximal — le juge doit être un call séparé, sans accès au prompt de génération |
| Calendrier de recalibration fixe seul (ex. "tous les trimestres") | Insuffisant — un changement de prompt/provider entre deux recalibrations planifiées invaliderait silencieusement le juge |
| Nouvel outil dédié (deepeval/Braintrust) pour cette seule calibration | Déjà tranché Phase 3 : re-évaluer seulement si volume EVAL-6/7 > 1000 runs/mois (§ADR-0007 corps, section Stories Phase 4) |

### 14.5 Amendement — 2026-09-24 · Juge d'une autre famille que le générateur (Décision #35)

**Remplace D14.c sur le choix du modèle juge.** La tension notée en D14.c (Sonnet juge une sortie de Sonnet) est tranchée par décision PM du 24/09/2026, dans l'esprit d'une revue adversariale : **le juge appartient à une famille de modèles différente de celle de tout générateur dont il note les sorties**. Le fallback Gemini étant un générateur possible (failover), la règle exclut aujourd'hui Claude **et** Gemini : le juge vient d'une troisième famille.

**Pourquoi :** des modèles de la même famille partagent en partie leurs angles morts — une erreur que le générateur ne voit pas en écrivant, un juge de la même famille a plus de chances de ne pas la voir en notant (biais corrélé, et préférence pour ses propres formulations). Changer de famille décorrèle ces erreurs ; l'escalade vers Opus prévue en D14.c ne le faisait pas.

**Pourquoi une troisième famille partout, et pas seulement « juge ≠ famille de la sortie notée » (confirmé PM 24/09/2026) :**
- **Comparaison entre fournisseurs (Décision #35 D3).** Le juge note Claude **et** Gemini sur les mêmes cas : un juge de l'une des deux familles fausse l'écart mesuré en faveur de la sienne. Une troisième famille est ici nécessaire, pas une précaution.
- **Une seule échelle.** Un juge Gemini en production et un juge tiers pour les comparaisons, ce seraient deux juges à calibrer (deux kappa) et des scores non comparables entre eux. Un juge unique d'une troisième famille coûte une calibration.
- La bascule vers Gemini en production est rare ; elle n'est **pas** l'argument principal.

**Alternative écartée :** juge ≠ famille du générateur de la sortie notée (juge Gemini pour les sorties Claude de production, troisième famille réservée aux comparaisons). Défendable et moins coûteuse à court terme, mais elle impose deux juges et deux échelles.

**Ce qui ne change pas :**
- **L'ancrage reste humain.** Le juge d'une autre famille n'est admis qu'après kappa ≥ 0.8 sur 2 runs consécutifs (D14.d). Changer de famille réduit un biais ; seule la calibration prouve que le juge est bon.
- **Il reste appelé via `LLMProvider`** (Décision #9) — ce qui demande un adapter LLM pour la famille retenue (aujourd'hui seul un adapter *embedding* Mistral existe).
- **Version épinglée** par identifiant exact (Décision #35 D3) : un juge ne se désigne pas par tier.

**Choix de la famille : laissé à la calibration, pas fixé ici.** Mistral est le candidat le moins coûteux à intégrer (fournisseur et clé déjà présents dans le stack) ; OpenAI est l'alternative. Si aucun candidat d'une troisième famille n'atteint kappa ≥ 0.8, on revient à ce PM **avant** d'autoriser un juge de même famille — la règle ne se contourne pas en silence.

**Limite assumée :** un juge qui applique une rubrique fixe n'est pas une revue adversariale complète — il vérifie, il ne *cherche* pas activement les défaillances. Une passe de type red-team (générer des cas conçus pour faire échouer le générateur) est un chantier distinct, non couvert ici.

**Trigger de recalibration ajouté :** tout changement de la famille d'un générateur (primaire ou fallback) qui la ferait coïncider avec celle du juge.

---

## 15. Addendum — 2026-09-24 · The parser eval did not measure the model (EVAL-4 correction)

> Trace: CLAUDE.md Décision #37. Supersedes the parser parts of §5.c and R4.

### 15.1 What was wrong

An audit of EVAL-4 (HOS-208) found that the inbound-parser layer never measured
the model or the production path. Each point below was checked against the code on
24/09/2026.

1. **Circular number.** `eval/baselines/parser_baseline.json` reported accuracy 1.0
   on n=16 with `"backend": "fake"`. `FakeIntentClassifier`'s rules were written
   to "resolve the curated golden scenarios correctly (so the pipeline runs green
   in CI)", and some are visibly fitted to single cases (`🙄` as a rejection
   marker). The file was also stale: the dataset held 17 parser cases.
2. **The real signal did not exist.** The fake's docstring pointed to a "nightly
   `EVAL_PARSER_BACKEND=real` run". None of the four workflows ran it.
3. **Even `real` wasn't real.** When `parse_inbound` returned `free_form`, the
   runner fell back to the fake heuristic, so "rejected" (and part of "accepted")
   was always decided by the heuristic. Any unknown label was silently coerced to
   `accepted`.
4. **The gate watched the wrong file.** `receipts.py` (where `parse_inbound`
   lives) mapped only to the `receipt` layer, so changing the classifier prompt
   never re-ran the parser eval. The documented contract (accuracy ≥ 90%,
   per-intent precision ≥ 0.85) was asserted only by a unit test on the fake.
5. **Taxonomy mismatch.** `parse_inbound` emits `structured_correction |
   acknowledge | free_form`. The feedback loop records `accepted | rejected |
   modified | ignored`. Nothing mapped one onto the other in production.

### 15.2 Product defect found on the way (not an eval problem)

Tracing the production path (`api/routes/twilio_inbound.py`):

- `accepted` / `rejected` are recorded **only** for the exact keywords `accept` /
  `reject` (`action_logger.parse_action`, whole-body match, case-insensitive).
- Any other reply goes to `parse_inbound`. `acknowledge` records **nothing**
  (`outcome_for_feedback` → `None`). Every other intent records `modified`
  (`parse_inbound` hard-codes `outcome="modified"`, including when the model
  fails).
- So **no free-text reply can record `rejected` or `accepted`**: "non merci on
  garde tel quel" is stored as `modified`, and "ok merci" leaves the
  recommendation `dispatched`. The model only decides between `modified` and
  "nothing recorded".

Measured on the 47 labelled parser cases by running the production code with a
stub model (no API call, deterministic): **the production path cannot exceed
36.2% accuracy whatever the model answers.** Max recall is 0% for `accepted` and
`rejected` and 100% for `modified`. 42 of 47 replies reach the model; 5 are
decided before it. This is a property of the code, not a model measurement. It also
means `recommendation_acceptance_rate` (KPI level 3) cannot count a free-text
acceptance or refusal today.

This is reported as a product defect and is **not** papered over in the eval:
the eval grades what production records, so it will stay below contract until
the product changes. Proposed fix (open decision, `docs/context/open-decisions.md`
§"Inbound reply → recorded outcome"): extend the classifier's output schema with
an explicit decision field (`accepted | rejected | modified | none`), validated by
schema (Décision #35 D2), mapped by `outcome_for_feedback`. Keep HITL (Décision
#6): a low-confidence `rejected`/`accepted` asks the manager to confirm instead of
being written silently.

### 15.3 What changed (24/09/2026)

- **One definition of "recorded outcome".** `receipts.outcome_for_feedback` is
  called by the route and by the eval. `FeedbackIntent.source` records which step
  decided (`ack_regex`, `covers_regex`, `llm`, `llm_unmappable`, `llm_error`), so a
  fallback is never mistaken for a model answer, in logs or in the eval.
- **Real backend = production path, model included.** `parse_action` →
  `parse_inbound` → `outcome_for_feedback`, the route's order. The model is the
  primary provider only: a silent Gemini failover would change the model under
  test. Measuring the fallback is Décision #35 D3, still Design. A model error or an
  out-of-taxonomy answer is a typed `error` prediction and counts as a miss.
  Predictions can be `not_recorded`. No `ANTHROPIC_API_KEY` → `ParserEvalNotMeasured`
  → exit 2 (ERROR), never PASS.
- **Opt-in real workflow** `.github/workflows/eval-parser-real.yml`: label
  `eval-parser-real`, `workflow_dispatch`, weekly schedule. Cost ≤ ~$0.035 per run,
  ≤ ~$0.11 for the 3-run canary, at Haiku 4.5 list price (estimate in the workflow
  header). It fails red when the secret is missing ("NOT MEASURED") and when the
  result is below the FAILURE_THRESHOLDS.md contract.
- **Fake backend = plumbing check, labelled everywhere.** The result carries
  `quality_signal: false`, `measures: pipeline_plumbing_only`. It is never compared
  to a baseline and cannot be frozen as one (`run_all --update-baseline` refuses).
  The reporter and the sticky PR comment show no "Accuracy" headline for it: they
  say "plumbing check — model quality not measured". `parser_baseline.json` (fake)
  is **deleted**. That path is now reserved for a real-model baseline.
- **Held-out adversarial set.** 30 cases (`"split": "heldout"`, 10 per intent,
  FR/EN): sarcasm, mixed intent ("ok mais plutôt 40"), polite refusals, emojis,
  typos, numbers that are not corrections, negation words in acceptances. Each
  has its `failure_trigger`. They were written after the fake was frozen, and
  it is not tuned to them. The fake agrees with the labels on 100% of the 17
  `dev` cases and 50% of the 30 `heldout` cases. That gap makes the
  circularity visible; it is not a quality figure.
- **Baseline protocol (canary, Décision #29 applied to the LLM).** A real baseline
  is frozen only from `--runs 3` with identical per-case predictions at the
  production temperature (0.0, recorded by the run), variance stated. Otherwise
  refused, exit 2.
- **Gate trigger paths.** `receipts.py` → `receipt` + `parser`; `action_logger.py`
  and `api/routes/twilio_inbound.py` → `parser`.

### 15.4 What is measured now — and what is not

| Signal | Status on 24/09/2026 |
|---|---|
| Eval pipeline runs end to end (fake) | Measured on every triggering PR — plumbing only |
| Production-path ceiling | **Measured: 36.2%** (n=47, deterministic, no model) |
| Parser model quality (production path, real model) | **Not yet measured.** No API key was available to the session that made this change, and the workflow has not run yet. No real-model number exists anywhere in the repo. |
| Real-model baseline | **Absent** until a 3-run canary passes |
| Fallback-model (Gemini) quality | Not measured (Décision #35 D3, Design) |
| Pilot gate "EVAL-4 = pilot-blocking" (§8) | Was satisfied by a non-measurement. To be re-read with the PM once a real run exists. |

### 15.5 Other layers checked for the same class of problem

- **Forecast** — real Prophet, but trained and graded on the synthetic series
  (`generate_demo_data.py`, same regressors: the Décision #33 circularity). Fine as
  a non-regression signal. The result and baseline now carry `data_provenance:
  synthetic`, and the report prints it. Numbers unchanged, not re-frozen.
- **Guardrail** — accuracy 1.0 on 27 is a contract test of deterministic
  predicates (does the typed reason fire). It is not model quality and is not
  presented as such. No change.
- **Latency** — `latency_baseline.json` holds SLO **targets** copied from
  `docs/ops/latency-slo.md`, not measurements. Now labelled
  `kind: slo_targets_not_measurements`. No measured latency baseline exists.
- **Embeddings** — `FakeEmbeddingProvider` replaces an input to the system under
  test, not the system itself, and no layer runner in `scripts/eval/` uses it.
  Scripts outside the eval harness (`scripts/ops/benchmark_*`) were not audited
  here.

---

### 15.6 Merge with HOS-337 (25/09/2026)

HOS-337 (Décision #35 D3, PR #264) landed on `main` in parallel: real parser runs
against ONE pinned target (`EVAL_PARSER_TARGET=<provider>:<exact model id>`, called
directly, never through the failover), baselines keyed by (target × dataset
version), a provider matrix workflow and a comparison script. It measured the
pre-§16 path, where a `free_form` answer was settled by the heuristic.

Merged as follows: the graded path is this section's production path (§15.3,
§16), and the model under test is HOS-337's pinned target. The real backend
refuses to run without a target or without the key of the target's provider
(exit 2, not measured). The per-target fields (`accuracy_llm_decided`,
`llm_failure_rate`, `decided_by`) are kept, with §16 semantics: every graded reply
reaches the model; a model error or an answer failing the schema is a miss and is
also counted in the failure rate — no heuristic rescues it. The source labels of
the old heuristic path are gone. `eval-parser-real.yml` pins
`claude:claude-haiku-4-5-20251001`; `eval-parser-matrix.yml` runs Claude and Gemini.
The structured output HOS-338 (D2) asks for is what §16's `ClassifierOutput`
provides for the reply classifier.

## 16. Addendum — 2026-09-24 · Manager decision capture (PO decision on §15.2)

> Trace: CLAUDE.md Décision #38. Resolves the open decision "Inbound reply →
> recorded outcome" (`docs/context/open-decisions.md`, §Resolved). Supersedes the
> parser grading rules of §15.3–15.4 (the production-path ceiling of 36.2% no
> longer applies to the new code).

### 16.1 Principle (Ivan, product owner)

The **decision** (`accepted | rejected | modified | none`) is arm C's ground
truth (§13). It must be deterministic wherever possible, cheap, unambiguous and
auditable. The **comment** (reason, detail) is optional and rich, and never
changes a recorded decision silently.

### 16.2 What a reply goes through (first match wins)

| # | Step | Model? | Writes | `decision_source` |
|---|---|---|---|---|
| 1 | Quick-reply button payload (fixed IDs `aetherix.decision.{accept,reject,correct}`, `aetherix.confirm.{yes,no}`) | no | decision, or answers a confirmation | `button` |
| 2 | Answer to a pending confirmation (`oui`/`non`/…, or the Oui/Non buttons) | no | the proposed decision on yes, nothing on no | `model_confirmed` · `keyword_confirmed` · `bare_ack_confirmed` |
| 3 | Exact keyword on the whole reply (§16.3) | no | explicit → decision; ambiguous → confirmation | `keyword` |
| 3b | Bare acknowledgement ("ok", "👍", "parfait") — rule (b) | no | `accepted` only if exactly one recommendation is pending **and** the reply is within 12 h of its dispatch; nothing if none is pending; confirmation otherwise | `bare_ack_rule` |
| 4 | Pending reason request → the reply is the reason (§16.5) | router only | typed reason; **never** the decision | — |
| 5 | Covers pattern ("covers: 80") | no | `modified` | `correction_pattern` |
| 6 | Model, output validated against `ClassifierOutput` (decision, confidence, corrected value, reason, reason route) | yes | ≥ 0.85 → decision; < 0.85 → confirmation; `none` → nothing; call or schema failure → nothing (typed `why`) | `model_auto` |

Steps 1–3b run synchronously in the webhook; 4–6 in the background task. Code:
`services/manager_decision.py` (pure rules), `services/inbound_decision.py`
(DB), `api/routes/twilio_inbound.py`. `receipts.resolve_feedback` /
`outcome_for_feedback` remain the single definition shared with the eval.

**HITL (Décision #6).** A model decision below `DECISION_CONFIDENCE_THRESHOLD =
0.85`, an ambiguous keyword, and an unattributable bare acknowledgement write
**nothing**: a `manager_prompts` row is created and the manager gets "Je note un
refus, c'est bien ça ?" (buttons Oui / Non, or "Répondez OUI ou NON."). Unanswered
after 60 min → `expired`, logged as `confirmation_expired`, **never** a decision.
The threshold applies to `modified` too (stricter than asked; nothing inferred is
written unconfirmed below it). The model's confidence is **not calibrated**: 0.85
is a policy until the first real eval run shows whether it separates right from
wrong answers.

A confirmed decision writes the decision only: a corrected figure proposed with
it stays on the prompt and is not persisted as actual covers. A confirmation
whose recommendation was decided meanwhile writes nothing. A reply containing
"?" is never a keyword ("ok?" is doubt, not acceptance).

**Behaviour change vs §15.2:** a model failure no longer records `modified`;
it records nothing and asks for an explicit decision. `modified` now also lands
on `staffing_recommendations.status/action` (it was only in memory before).

### 16.3 Keyword mapping choices (every form unit-tested, `tests/services/test_manager_decision.py`)

- **Whole reply only.** "oui" is a keyword; "oui mais 3 serveurs" goes to the model.
- **Accept:** accept(ed), accepter/accepté, j'accepte, oui, yes, yep, ouais,
  validé/valide/valider, validated, approve(d), agreed, go, ✅, ✔, "ok validé",
  "je valide", "c'est validé", "ok pour moi", "d'accord", "go for it" — alone or
  with acknowledgement tokens ("agreed thx", "Validé 👌").
- **Reject:** reject(ed), rejeter/rejeté, refuse(d)/refusé/refuser, "je refuse",
  decline(d), non, no, nope, nan, ❌, 👎, "pas d'accord", "not ok".
- **Modify (records `modified`, then asks what changed):** corriger, correction,
  correct, modifier, modify, ajuster, adjust, ✏️, 📝. "CORRIGER" is what the text
  fallback tells managers to reply, ✏️ is the Daily Receipt's modify glyph.
  "oui corriger" is ambiguous (proposed reading `modified`).
- **Bare acknowledgement (rule b):** ok, okay, merci, thanks, thx, parfait,
  perfect, great, super, top, cool, noted, compris, got it, bien reçu, 👍, 👌, 🙏 …
  **👍 is an acknowledgement, ✅ is an acceptance** — 👍 routinely answers the
  daily Receipt; ✅ answers "validate?". Documented choice.
- **Ambiguous → confirmation, proposed reading `rejected`:** "non merci" (declines
  the recommendation | "no thanks, all good"), "on garde tel quel" / "tel quel" /
  "keep as is" (keep the recommendation | keep our own plan), "pas besoin" / "no
  need" (we don't need the extra staff | nothing to change), "bof", and any reply
  mixing a refusal token with an acceptance/ack token ("non ok", "👎 merci").
  The heldout case "non merci on garde tel quel" (labelled `rejected`) is one of
  these: the product now asks instead of guessing, and the manager's "oui" is what
  records it.

### 16.4 WhatsApp quick-reply buttons — constraint check

What the code sent before this change: `TwilioClient.send_whatsapp` posts a
free-form `Body` to `Messages.json`; the staffing recommendation
(`alert_dispatcher`) and the daily Receipt (`receipts_dispatcher`) are
**business-initiated**. No Content API use anywhere.

What applies (Twilio docs `twilio/quick-reply`, "Using Buttons in WhatsApp" and the
Content API FAQ; direct fetch of twilio.com was blocked from this session, the
statements below come from those pages' indexed text and must be re-checked in the
Twilio console before rollout):

1. Buttons require a **Content template** (`ContentSid` + `ContentVariables`
   instead of `Body`). TwiML `<Message>` cannot carry them, so a reply with
   buttons is sent via REST and the webhook returns an empty `<Response/>`.
2. **Business-initiated** messages need a template **approved by WhatsApp**
   (category Utility). Up to 10 quick-reply buttons, titles ≤ 20 characters.
3. **Inside the 24 h customer-service window** (the manager just wrote to us),
   quick replies can be sent **without approval** (template saved, not
   submitted), **max 3 buttons**. The Oui / Non confirmation qualifies.
4. The inbound webhook carries the tapped button's id as `ButtonPayload` (plus
   `ButtonText`, `OriginalRepliedMessageSid`).
5. **Pre-existing gap, independent of buttons:** a free-form WhatsApp message
   outside the 24 h window is refused by WhatsApp. The current text dispatch of
   the recommendation and the Receipt only works in the sandbox or inside a
   session. A production number needs approved templates for both, buttons or not.

Implementation: behind `WHATSAPP_DECISION_BUTTONS` (default off) +
`TWILIO_CONTENT_SID_{DECISION,CONFIRM}_{FR,EN}`. Flag off, SID missing, or Content
send failing → the same text is sent, with "Répondez ACCEPTER, REFUSER ou
CORRIGER." when it is a decision request. Inbound payloads are handled whatever
the flag. Proven by tests: request shape, fallbacks, payload → decision mapping,
route pass-through. **Not proven:** that WhatsApp approves and renders the
template.

Pending ops step (out of reach of a coding session): create in Twilio Content
Template Builder (a) `aetherix_decision_fr` / `_en`, `twilio/quick-reply`, body
with fixed text around `{{1}}` (Meta rejects a template that starts or ends with a
variable), buttons Accepter / Refuser / Corriger with ids
`aetherix.decision.accept|reject|correct`, submitted for WhatsApp approval
(Utility); (b) `aetherix_confirm_fr` / `_en`, body `{{1}}`, buttons Oui / Non with
ids `aetherix.confirm.yes|no`, saved only. Then set the SIDs and the flag via
`flyctl secrets set`. Known limit: the button carries no recommendation id; the
decision applies to the most recent pending recommendation. Using
`OriginalRepliedMessageSid` (store the outbound SID at dispatch) would remove that
ambiguity — follow-up.

### 16.5 Optional reason

After a recorded **reject or correction only** (never after an accept —
interruption budget), one line: "Une raison ? (facultatif)" / "Quel changement,
et pourquoi ? (facultatif)". Not asked when the reply already carried a reason.
The next free-text reply within 60 min is the reason: stored in
`inbound_reply_events.reason_text`, routed by the model to one of `memory |
decision_rule | policy | case_set | upstream_filter` with its confidence, **only
at ≥ 0.7**, unrouted otherwise. A bare "ok" closes the request. The reason never
touches `staffing_recommendations`. The routes are **labels**: no consumer exists
yet for any of them (not even `memory`: writing a reason into feedback memory
would change the ledger's latest manager answer). Wiring consumers is a
follow-up. Few replies are expected.

### 16.6 Outcome loop — two rules

1. **The outcome never relabels the decision.** Actual covers are never read
   when capturing or confirming a decision (pinned by
   `test_decision_rules_never_read_the_outcome` and
   `test_decision_does_not_depend_on_actual_covers`). Decision and outcome stay
   independent variables, or arm C learns circularly.
2. **The outcome may later weigh a comment, not a decision.** E.g. a reason "trop
   de monde" vs actuals above forecast, as a confidence signal on the reason only.
   Phase 4 follow-up, not implemented.

**Stated plainly:** `actual_covers` comes from `manager_feedback` today (POS is
Phase 4/5). While the manager declares both the decision and the actual covers,
the quantitative loop is **not independent** of the human loop: the same person
produces the label and the outcome. Arm C conclusions drawn before POS data carry
that caveat.

### 16.7 Eval (EVAL-4) — what is graded now

- **Deterministic block** (keyword, ambiguous keyword, bare ack, covers): code
  check on every run, fake or real, no model. 12 of the 47 labelled cases; all 12
  land on their label (5 bare ack, 4 covers, 2 keyword, 1 ambiguous →
  confirmation). The golden set now carries `expected.decision` and
  `expected.path`; a test fails if routing drifts from the annotated path.
- **Model graded on the free-text path only** (35 of 47 cases): decision
  accuracy (written or proposed) ≥ 90%, per-decision precision ≥ 0.85,
  auto-written precision per decision ≥ 0.85, confirmation rate reported.
- **Confirmation trigger:** 10 new `parser_confirmation` cases (two readings,
  FR/EN, `split: heldout`). Any write without confirmation is a breach.
- Fake backend unchanged: plumbing only. Production-path ceiling is now 100%
  (the model can land on any decision): no longer a useful number, kept as a
  reachability check.
- **Real-model quality: not measured.** No `ANTHROPIC_API_KEY` in this session;
  `eval-parser-real.yml` has not run. No baseline exists.

### 16.8 Metrics

`inbound_reply_events` (one row per reply, one per expired confirmation) +
structured log `inbound_decision_event` (typed fields, never the body).
`GET /kpi/{hotel_id}/decision_capture?days=7` (tenant-checked) returns: capture
rate (decisions written ÷ decision-seeking replies; a confirmed decision is
credited once), decisions by source and share, confirmation rate, confirmation
timeout rate, declined count, `not_recorded` by typed `why`, reasons captured /
routed. Arm C should filter or weight by `decision_source`: a `bare_ack_rule`
acceptance is weaker evidence than a `button` one.

### 16.9 Schema

Migration `20260924120000_manager_decision_capture.sql`:
`staffing_recommendations.decision_source` / `decision_confidence`; tables
`manager_prompts` (HITL state) and `inbound_reply_events` (RLS, service role only;
`reason_text` in the DSAR plan as REVIEW). The `decision_ledger` SQL view is not
changed; `DecisionLedgerService` exposes `decision_source`/`decision_confidence`.

---

## 17. Addendum — 2026-09-24 · Recap on demand, decision provenance, no fabricated report

> Trace: CLAUDE.md Décision #39. PO requests (Ivan, 24/09/2026) after §16.
> Autonomy of host agents is **not** decided here: it is ADR-0013 (status
> **proposed**). Code: commits `8b90394`, `44edf50`.

### 17.1 Weekly report: no mock, no invented money

**Found.** `reporting_service.generate_weekly_metrics` fell back to
`_get_mock_weekly_data` (7 hard-coded days, 945 covers) whenever no
ground-truth row existed, and `format_audit_email` then printed "Accuracy",
"MAPE", "Estimated Savings: £…" (heuristic: £15/cover on days > 150 covers,
£120 per day < 100 covers), "Value Delivered: Nx monthly cost" (from a
"$50 mock SaaS cost") and "Aetherix is optimizing your labor costs
effectively". Nothing said the numbers were invented.

**Now.** No mock on any tenant path; the mock and the savings heuristic are
deleted (tests pin their absence). No recommendation in the week →
`status: no_measured_data`, text "pas encore de donnée mesurée", no metric. The
report *is* the recap template (§17.2) for the week. `financial_impact` is
always `null` with a stated reason: no measured labour-cost or revenue input
exists. A savings or ROI figure comes back only from measured inputs, with its
formula and assumptions printed next to it. Currency: `config.CURRENCY`
(default EUR) through `app/core/money.py`; the £ symbols in the recommendation
text, the explanation prompt, the sanity-guard reasons and the PMS ops note are
gone too. The internal Obsidian note and the Linear alert remain, fed by
measured numbers only (alert only with ≥ 3 measured recommendations).

**Could a tenant have received a mock-based report?** Checked in the code: the
text was produced only by `GET /api/v1/reports/weekly`. No scheduler, email or
WhatsApp path called `format_audit_email`, and the frontend never called the
route. But the route was **public** (no auth, `tenant_id` in the query string),
so anyone who called it for a tenant without ground truth got the mock figures,
and each call also wrote the mock audit into the Obsidian vault
(`AI Reports/…/Weekly Audit`, internal). Production logs (Fly.io) were not
accessible from the coding session: whether it was ever called is **not
verified**. With 0 real user and no ground-truth rows, any call would have
returned mock data. To check: Fly logs for `GET /api/v1/reports/weekly` and the
vault folder for "Weekly Audit" notes.

### 17.2 Recap on demand (deterministic, no prose)

`services/decision_recap.py`, one definition for four surfaces: WhatsApp
command, MCP tool `get_decision_recap` (scope `receipts:read`),
`GET /reports/weekly`, and the acceptance KPI (§17.6).

- **Commands** (whole reply, before keywords): `recap` (this week), `recap
  jour|semaine|mois`, `recap day|week|month`, `summary`. Periods are local
  (`RECEIPT_TIMEZONE`): today, Monday → today, 1st → today.
- **Content, one block:** period · recommendations received · accepted ·
  rejected · corrected · no reply · awaiting confirmation · mean forecast error
  (mean |predicted − actual| / actual, **only** on recommendations with actual
  covers, printed with the number of days it covers; none → "aucun couvert réel
  saisi") · decision source split (button / keyword / model / confirmed / fixed
  later / host tool / agent / unattributed). No data → "Aucune recommandation
  sur la période." FR/EN.
- **"Received"** = dispatched in the period, or — for a headless tenant whose
  recommendations never go through WhatsApp — decided by a host in the period.
- **Correction line** "Décision mal enregistrée ? Répondez « corriger mardi »."
  `corriger <jour|hier|jj/mm> [validation|refus|correction]` (EN `fix …`): finds
  the single decided recommendation of that day; without a decision word it
  says what is recorded; with one it asks "Mardi 22/09 : je remplace une
  validation par un refus, c'est bien ça ?" — same Oui / Non path, nothing
  changes until yes; recorded with `decision_source = manager_revision`, the
  previous decision kept in the event trail (`revised_from_<x>`). Several
  recommendations that day → nothing changes, typed `why`. Revisions are the
  human audit of the capture: counted (`revisions`), never as decisions
  written. "corriger" alone remains the modify keyword.
- **Why it replaces the weekly audit report:** one template avoids two
  definitions of the same week. The report route now returns this template.

**Not changed, flagged for the PO:** the Phase 2 **weekly digest**
(`receipts_dispatcher`, Sundays, Décision #15 scope) still pushes an
LLM-composed narrative to every active hotel, without opt-in and outside the
24 h window. Its numbers are measured, but it is prose and it ignores the
interruption budget. Proposed: replace it with the opt-in recap push (§17.3).
Open decision, `open-decisions.md`.

### 17.3 WhatsApp 24 h window — what can be sent when

| Message | Initiated by | Inside 24 h of the manager's last message | Outside |
|---|---|---|---|
| Recap on demand, confirmation "c'est bien ça ?", reason request, revision question, "recorded" acks | reply to the manager | free-form ✅ (always inside: it answers a message received seconds ago) | n/a |
| Weekly recap push (opt-in `weekly_recap_opt_in`) | business | free-form ✅ if last inbound < 23 h 30 (30 min margin) | **approved** template `TWILIO_CONTENT_SID_RECAP_*` (body `{{1}}`) ✅; else **not sent**, typed log `outside_window`; the recap stays available on demand |
| Staffing recommendation, Daily Receipt, Phase 2 weekly digest | business | free-form ✅ | ❌ refused by WhatsApp without an approved template — pre-existing gap (§16.4 point 5), unchanged here |

"Deferral" means: nothing is queued for later; the next `recap` is the
delivery. The last inbound time is read from `inbound_reply_events` (every
reply writes one). Not proven: template approval and rendering (ops step).

### 17.4 Decision provenance and the reason contract for agent callers

Aetherix can run headless: the party deciding may be a host platform's agent
calling MCP `submit_feedback_to_memory`, which recorded neither who decided
nor why, wrote only to feedback memory (never on the recommendation), and
accepted **any** recommendation UUID (no tenant check).

- **`decided_by`** on `staffing_recommendations`: `human_whatsapp` |
  `human_via_host` | `host_agent_autonomous` | `timeout` (reserved: never
  written; an unanswered recommendation is "no reply", not a decision, Décision
  #6). Complements `decision_source` (how it was captured: `host_relay`,
  `host_agent` added). Backfill: rows with a §16 `decision_source` →
  `human_whatsapp`; older decided rows stay `NULL` = **unattributed**, excluded
  from human rates and shown as such.
- **MCP contract** (typed 400 otherwise): `decided_by` ∈ {`human_via_host`,
  `host_agent_autonomous`}; `reason_code` from a closed enum (positive:
  `agrees_with_drivers`, `matches_own_plan`; negative: `forecast_too_high`,
  `forecast_too_low`, `event_not_in_forecast`, `event_cancelled`,
  `staffing_constraint`, `budget`, `policy`, `data_issue`, `already_handled`;
  `none_given`; `other` → `reason_detail` required); `reason_detail` sanitised
  (control characters stripped), ≤ 280; `evidence` ≤ 5 × {source ∈ pms, pos,
  weather, events, rota, manager_message, host_notes, other; detail ≤ 200};
  `reason_source` ∈ {`human`, `agent_inferred`}.
- **The burden stays on the agent.** A human who gave no reason is recorded as
  `none_given` + `reason_source=human` — allowed only for `human_via_host`. A
  reason the agent infers must say `agent_inferred`; an autonomous agent's
  reason cannot claim `human` (typed 400).
- **Order of checks:** schema → the recommendation belongs to the token's hotel
  (404 otherwise) → decision policy (§17.5, 403 `autonomy_not_permitted`) →
  still undecided (`ready_to_push` or `dispatched`, else 409) → write decision,
  who, why, caller (`decided_by_caller` = token label), policy version → feedback
  memory (reflection now carries `decided_by=`). `ignored` writes no decision.
- **"Required" is not "informative."** Required fields get filled with filler.
  `decision_provenance.informativeness` computes per caller the share of
  `other`, of empty details, of near-duplicate details and of `agent_inferred`
  reasons: a runtime signal (arm B) to look at, not a gate that rejects calls.
  Not yet exposed on a route or alert (follow-up).
- **Breaking change** for MCP callers: calls without the new fields now fail.
  No external consumer exists (status taxonomy: MCP server, 0 consumer).
- **Gap found:** no MCP tool lists pending staffing recommendations, so a host
  agent has no way to obtain a `recommendation_id` today. Follow-up.

### 17.5 The decision-policy seam; learning from agent-generated data

`services/decision_policy.py` is the single seam where a decision path is
authorised; both write paths (WhatsApp `InboundDecisionService`, MCP) call
`authorize_decision`. Only policy: **human validation everywhere**
(`default-human-validation-v1`, approved by Décision #6). Humans pass; a host
agent deciding alone is refused and nothing is written. The version is stored
on every decision (`decision_policy_version`) so metrics can later be split
before/after a policy change. Autonomy as configuration is designed in
**ADR-0013 (proposed)**, not enabled.

**Rule for learning from agent-generated data (3d):**
1. Human-decided and agent-decided records stay separable (`decided_by`,
   `decision_source`, `reason_source`) in every table and export.
2. Agent-decided records and `agent_inferred` reasons are **never ground
   truth** for arm C, for acceptance metrics, or for training anything that
   predicts what a manager would decide.
3. The outcome loop (actual covers; POS/PMS when available) is the independent
   arbiter of whether a decision was good. While actual covers are typed by the
   manager (§16.6) it is not independent of the human loop — that caveat
   stands.
4. **Self-confirmation risk:** a system that learns from decisions taken by
   itself, or by another agent that learned from it, converges on its own
   priors and reads agreement as validation. Hence rule 2, and ADR-0013's
   periodic human sampling of autonomous decisions.

### 17.6 One acceptance definition

**Confirmed undercount.** `recommendation_acceptance_rate` was read from
`kpi_daily`, fed by the materialized view `recommendation_acceptance_daily`,
which joined `operational_memory` feedback rows to `agent_action_log`
recommendation/prediction tool calls **on `request_id`**. A feedback row
carries the `request_id` of the call that wrote it (WhatsApp background task
or `submit_feedback_to_memory`), never the recommendation tool's, so decisions
were essentially never counted. `modified`/`ignored` were also folded into one
"neutral" bucket.

**Now** (`decision_recap.acceptance_rate`): accepted ÷ (accepted + rejected +
modified), over `staffing_recommendations` keyed by dispatch time (creation if
never dispatched), **human deciders only**. Reported alongside, split by
`decided_by`: override rate (rejected + modified ÷ decided), median response
time from dispatch to decision — a **latency, not a measure of human effort**
("human minutes per accepted output" does not exist in the code and is not
claimed) — and agent-decided counts, never in the rates. Used by the KPI route
(live, pooled over the window), the daily aggregator (kpi_daily + trust_low
alert) and the recap. The view is left in place, unread. The aggregator's
Postgres SQL is tested with a mocked connection only.

### 17.7 Tenant isolation defects (confirmed and fixed)

Rule now in `app/api/tenant_scope.py`, tests in
`tests/security/test_route_tenant_scope.py`:

| Route | Before | Now |
|---|---|---|
| `GET /kpi/{hotel_id}/recommendation_acceptance` | any `receipts:read` token, any hotel | token bound to `hotel_id` (403) |
| `GET /kpi/{hotel_id}/decision_capture` | checked, but via `getattr(…, default=hotel_id)` | same helper |
| `GET /receipts/{hotel_id}/{date}` | not enforced ("single-hotel sandbox") | token bound (403) |
| `GET /reports/weekly?tenant_id=` | **no auth at all** | bearer + `receipts:read` + bound |
| `GET /baselines/{tenant_id}`, `POST …/recalculate` | any dashboard user | owner or superuser |
| `POST /events/sync`, `POST /weather/sync` (explicit tenant) | any dashboard user | owner or superuser |
| `POST /notifications/test`, `/dispatch` | **public** (send to any number; push every tenant) | superuser only |
| `POST /anomalies/roi`; `POST /anomalies/format` (no property / other property) | any dashboard user, every tenant or any property | superuser for all-tenant runs; own property otherwise |
| MCP `submit_feedback_to_memory` | any recommendation UUID | recommendation of the token's hotel (404) |

Checked and already correct: `predictions/predict` (body hotel vs token),
`dashboard/*`, `anomalies/scan` and `GET /anomalies`, `pms/*` (resolve the
caller's own property), MCP tools (hotel from token). Not verified here: RLS at
the database (the service role bypasses it by design). Seen, not fixed
(pre-existing, out of scope): `anomalies._resolve_property_for_user` casts
`tenant_id` to a UUID although it is a slug since HOS-165, so `/anomalies/scan`
and `GET /anomalies` would 500 for a slug tenant.

### 17.8 "Non merci, on garde tel quel" (PO clarification)

A decline ("non merci", "no thanks", "tel quel", "on garde tel quel", "keep as
is") answering a recommendation that **proposes a change**
(`recommended_headcount` ≠ 0, the usual case) is recorded as `rejected`,
source `keyword`. Recommendation proposing no change → confirmation, reading
"keep as is" = accepted. Cannot be told (`recommended_headcount` unset) →
confirmation, reading rejected. "pas besoin", "bof" and mixed-token forms stay
ambiguous (not covered by the clarification). Eval context = one pending
recommendation proposing a change; golden case
`parser-heldout-rejected-keep-as-is-fr-001` path `keyword_ambiguous` →
`keyword` (label unchanged; edited in place — Décision #35 D5's "retire and
add" rule is Design, not yet applied to the dataset).

### 17.9 What is and is not measured

| Signal | Status 24/09/2026 |
|---|---|
| Recap, commands, revision, provenance, policy seam, tenant checks | Built, tested (SQLite, mocked Twilio). **0 real user.** |
| Weekly recap push | Built behind opt-in; template approval pending; delivery not proven |
| Parser model quality | **Not measured** (no API key; unchanged from §16.7) |
| Acceptance rate | Definition fixed; **no real decision exists** to compute it on |
| Informativeness of agent reasons | Computed by a pure function; no caller exists |

## 18. Addendum — 2026-09-25 · Risk-bearing recommendations and the learning loop

> Trace: CLAUDE.md Décision #40. Scope approved by Ivan (PO). Goal: every
> recommendation carries its risk — what happens if it is accepted, what
> happens if it is refused — and the outcome loop changes the system, under
> safeguards. Built in slices; each subsection says what is built and what is
> measured.

### 18.1 Point of no return per task class

A hotel cannot undo a service. What exists is a **correction window** before
the action commits. `backend/app/services/task_classes.py` is the single
catalog (`task-classes-v1`):

| Task class | Recommended today | Commit point | Default offset before service | Corrective before commit | After commit | Downside bounded |
|---|---|---|---|---|---|---|
| `staffing.add` (surge) | yes | extra shift confirmed to a person or agency | 24 h | don't call in, call in fewer, standby | cancel with cost, reassign | yes (extra shifts' cost / covers not served, capped by capacity) |
| `staffing.reduce` (lull) | yes | staff notified not to come | 72 h | keep the shift, reduce fewer, move to another outlet | call back if available | yes, not reversible |
| `food_prep.batch` | **no** (food-waste tracking is an open decision) | prep starts | 4 h | adjust / split batch, cook to order | repurpose, staff meal, 86 the item | yes |

- **Offsets are assumptions**, labelled `offset_basis = default_assumption`,
  until the hotel sets its own (`commit_offset_hours`, part 3, bounded
  0 h–30 days). The real notice period depends on staff contracts, agency terms
  and the collective agreement; no legal claim is made here.
- **Stored** on every staffing recommendation (migration `20260925100000`):
  `task_class`, `commit_at`, `correction_window` (typed: commit point, offset,
  basis, status at issue time, catalog version).
- **Surfaced** in the manager's message only when it matters: the commit point
  is within 48 h of issue (`closing`) or already passed (`passed`) — one
  deterministic line, FR default / EN, and it says when the offset is a
  default. Farther away (`open`) it stays in the record, recap and MCP.
- **ADR-0013 (still proposed)**: `autonomy_eligibility_facts` feeds §2.4.5 as
  an input (correction window, bounded downside, reversibility). Facts, not a
  gate; staffing stays L0 in §2.1.
- Seen, not verified: the formatter's pre-existing insert passes `window_start`
  / `window_end` as ISO strings to `timestamptz` columns through asyncpg, which
  normally requires `datetime` objects. The new `commit_at` is passed as a
  `datetime`. The existing columns were left as they were (tests run on SQLite;
  no Postgres run in this session).

### 18.2 Calibrated uncertainty first (blocking prerequisite)

**Finding.** `forecast_baseline.json` reports `interval_coverage_pct` 0.19:
Prophet's interval — nominal level **80 %** (`interval_width=0.80`, now stated
next to the number as `interval_nominal_level`) — contained the realised value
4 times in 21 on the golden scattered hold-out. That set is edge-case weighted
on purpose, so it overstates the problem, but the rolling-origin backtest
below confirms under-coverage too. Any risk statement on that interval would
understate risk.

**Method** (`backend/app/services/forecast_calibration.py`, pure;
`scripts/eval/eval_forecast_calibration.py`, arm A):

- Rolling-origin backtest on the demo series with the `PredictionEngine`
  configuration (weekly + yearly seasonality, FR holidays, three regressors,
  interval 0.80): origins from day 120 every 7 days, horizon 7 days → 35
  origins, 245 forecasts, per category (golden taxonomy) × lead time 1–7.
- Origins 0–16 = calibration set (119 forecasts); 17–34 = test set (126),
  **disjoint in time**.
- Recalibration: split-conformal on relative residuals `(y − ŷ)/ŷ`, finite-
  sample rank (`ceil((n+1)p)` above the median, `floor` below), stored as a
  99-point quantile grid. Chosen because it is the simplest method whose
  coverage can be checked directly; widening Prophet's `interval_width` would
  not be verifiable per level.

**Result — synthetic series, 3 identical runs (canary):**

| Test set (n=126) | Nominal 80 % | 50 % | 90 % |
|---|---|---|---|
| Prophet's own interval (before) | **0.667** (−13.3 pp) | — | — |
| Recalibrated (after) | **0.881** (+8.1 pp) | 0.587 | 0.929 |

Per lead time (after): 0.94 / 0.94 / 0.89 / 0.89 / 0.78 / 0.83 / 0.89 (n=18
each). Per category: normal_day 0.874 (n=119), event_day 1.0 (n=7); no
weather_anomaly day falls in the test window. The recalibrated interval
**over-covers** (conservative: it overstates, never understates, risk);
binomial standard error at n=126 is ≈ 3.6 pp, so +8 pp is a real
over-coverage, most likely because early origins (less training data) have
larger errors than later ones. Accepted as is: the dangerous direction is
under-coverage. A rolling (recent-residuals) calibration is the obvious next
step once realised covers exist.

**Rules now enforced:**

- A calibration is keyed on the **forecaster** *and* the **training data**
  (`training_data_source`). The committed one
  (`backend/data/calibration/prophet-predictionengine-synthetic-v1.json`,
  provenance `synthetic`) applies only to a `PredictionEngine` model trained on
  the synthetic source (persisted in a model sidecar so it survives a restart).
  It **never** applies to the anomaly-detection heuristic that produces the
  dispatched staffing recommendations: no calibration exists for that
  forecaster, so recommendations from it carry **qualitative bands only**
  (§18.4) until realised covers calibrate it (§18.5).
- Freeze rule: ≥ 3 identical runs, closer to nominal than before, and not
  under-covering by > 5 pp. `--check` runs it in the blocking eval gate (same-
  run before/after, immune to CI/local drift).
- Every surface that uses it says **`synthetic-calibrated`**; the prediction
  API returns Prophet's raw range unchanged plus `interval_nominal_level` and a
  `calibrated_interval` block (bounds, version, provenance, measured coverage
  and n), or `null` when none applies (mock model, other training data).
- **Arm C** (`forecast_calibration.realised_coverage`): coverage of the
  interval stored at issue time against realised covers, flagged
  `independent_actuals=false` while actuals are manager-declared (§16.6).
  Wired to data in §18.5; **not measured** — no realised covers exist.

### 18.3 Costs configured per hotel, never invented

`hotel_decision_parameters` (migration `20260925110000`, RLS service-role
only) + `backend/app/services/hotel_parameters.py` + route
`/api/v1/hotels/{tenant_id}/decision-parameters` (dashboard user, owner or
superuser via `tenant_scope.require_user_owns_tenant`; `GET` values + catalog,
`GET …/history`, `PUT …/{parameter}` with `value: null` to clear).

| Parameter | Unit | Bounds | Read by |
|---|---|---|---|
| `extra_shift_cost` | money | ]0, 2000] | staffing (cost of adding one shift, saving of removing one) |
| `lost_cover_value` | money | ]0, 1000] | staffing (value of a cover not served — margin or revenue, the hotel says which in the note) |
| `food_cost_per_cover`, `stockout_cost_per_cover` | money | ]0, 500] / ]0, 1000] | food prep (catalogued, not recommended today) |
| `covers_per_extra_staff` | covers | [1, 200] | staffing (labour constraint: covers one extra person serves in the window) |
| `max_extra_staff`, `max_staff_reduction` | staff (whole) | [0, 50] | staffing caps |
| `risk_display_min_gap` | money | [0, 100000] | interruption budget (§18.4) |
| `commit_offset_hours.<task class>` | hours | [0, 720] | correction window (§18.1) |

- **Missing → no money.** Nothing reads the legacy
  `restaurant_profiles.staff_hourly_rate` / `avg_spend_per_cover` or the
  `config.DEFAULT_*` placeholders for a risk statement: they carry no record of
  who set them, and the defaults are simulator placeholders.
- **Refused, never clamped**, when out of bounds (422); staff counts are whole.
- **Provenance:** append-only; each row has `set_by` (user e-mail/id, or
  `proposal:<id>`), `set_via` (`dashboard_api` | `ops` | `proposal_approval`),
  `set_at`, optional note. The value in force is the latest row. The
  parameters' `version()` (latest `set_at`) is stored with each risk
  assessment (§18.4).
- **Currency:** money rows record the currency entered (`config.CURRENCY`); if
  the configured currency changes, those values are ignored (listed), never
  converted.
- **DSAR:** `set_by` is an e-mail → REVIEW step (audit trail, pseudonymise
  rather than delete); table added to `PII_TABLES`.
- **Existing message fixed:** the surge message showed "capture an estimated
  €X … labour cost €Y" computed from the placeholder defaults whenever the
  hotel had not set its rates. It now shows money only when the hotel set both
  legacy rates; otherwise "Add N staff for HH:MM–HH:MM. Trigger: …". The ROI
  gate that selects which anomalies become recommendations still uses the
  defaults internally (unchanged, not shown).
- The hotel's `commit_offset_hours.*` now replace the catalog defaults in the
  correction window (§18.1), which then stops saying "default".

### 18.4 Risk-based recommendation — the decision rule, not a paragraph

`backend/app/services/risk_assessment.py` (pure), applied in the formatter to
every staffing recommendation; stored as `staffing_recommendations
.decision_rule` + `.risk_assessment` (migration `20260925120000`).

**Rule.** Newsvendor in staff units (`newsvendor-v1`): one extra person serves
`c = covers_per_extra_staff` covers; overage `co = extra_shift_cost`; underage
`cu = c × lost_cover_value`; critical ratio `CR = cu / (cu + co)`; staff for
the demand quantile `Q = F⁻¹(CR)` of the **calibrated** distribution:
`Δstaff = ceil((Q − baseline) / c)`, within `max_extra_staff` /
`max_staff_reduction` (±4 when unset, the previous rule's range). Stated
assumption: the usual staffing is sized for the anomaly's `baseline_demand`.

**Fallback, recorded.** If any input is missing — a calibration **for the
forecaster in use**, `extra_shift_cost`, `lost_cover_value`, covers per staff —
the previous rule (`deviation-scale-v1`, the ROI headcount scale) stays the
recommendation and `fallback_missing_inputs` lists why. Covers per staff: the
hotel's parameter, else the profile's `covers_per_server` (a hotel setting,
labelled `profile_ratio`), else none.

**Today, every dispatched recommendation takes the fallback**: they come from
the anomaly heuristic (`anomaly-heuristic-v1`), for which no calibration
exists (§18.2), and no hotel has configured costs. The newsvendor path is
built and tested (with a calibration injected in tests), not exercised on any
real recommendation.

**Per-option consequences** (typed, `risk-assessment-v1`), for *accept*
(Δstaff) and *refuse* (no change): extra shifts and their cost (**money only
from configured costs**), shortfall probability `P(D > capacity)` and expected
shortfall / idle covers and their value (**probability only from a
calibration of this forecaster**, with its provenance label), expected total
cost, else a qualitative band (`likely` / `possible` / `unlikely` from
capacity vs point forecast, ±10 %). Also stored: point forecast, baseline,
interval at nominal level (for arm C coverage), parameters version,
calibration version, critical ratio, quantile.

**Lines** (deterministic, FR default / EN), e.g.:

- `If accepted: +3 shifts (€540); shortfall risk ≈15%, ~0.6 covers (≈€14) (synthetic-calibrated uncertainty).`
- `If refused: no change; shortfall risk ≈85%, ~30.6 covers (≈€764) (synthetic-calibrated uncertainty).`
- without calibration or costs: `If refused: no change; shortfall likely if the forecast holds (qualitative, uncertainty not calibrated).`

Probabilities are shown to the nearest 5 %, never 0 % or 100 % (the stored
grid does not resolve the tails).

**Interruption budget.** The two lines go into the daily message only when the
expected-cost gap between the options is at least `risk_display_min_gap`
(hotel) or `RISK_DISPLAY_MIN_GAP_DEFAULT` (50, env); without money, when
calibrated shortfall probabilities differ by ≥ `RISK_DISPLAY_MIN_PROB_GAP`
(0.20); never when nothing is quantified or both options are the same action.
Always available: recap (undecided recommendations of the period, up to 3 in
the text, all in `as_dict`) and **MCP `get_pending_recommendations`**
(`receipts:read`, token-bound hotel): recommendation id, window, task class,
Δstaff, rule, correction window, typed risk, rendered lines. This also closes
the §17.4 gap — a host agent can now obtain a `recommendation_id`.

**Other changes.** When the newsvendor sets Δstaff, `recommended_headcount`
is that Δ (so the §17.8 "proposes a change" test follows it), the task class
follows its sign, and the message says "Add N staff …", "Consider reducing …"
or "Keep the usual staffing … (risk-balanced)".

**Seen, not changed:** a lull anomaly never becomes a recommendation
(`calculate_for_anomaly` returns net ROI 0 for lulls and only net ROI > 0 is
promoted to `roi_positive` — `roi_calculator.py`), and its message
would read "reducing staffing by 0" (`recommended_headcount` returns 0 for
lulls). Reduction recommendations therefore only exist through the newsvendor
path once it runs.

### 18.5 Learning continuously from what actually happened

End to end, one page: **[`docs/context/learning-loop.md`](../context/learning-loop.md)**
(what is learned, from which signal, how often, who approves, how it is
evaluated, how it is rolled back). In short:

- **Arm C, risk statements:** `learning_loop.risk_statement_calibration` —
  for each decided recommendation with a realised actual, the option taken,
  its stated shortfall probability (or band) and whether the shortfall
  happened; per task class × decider × calibration version (before/after
  split); Brier, reliability bins. **Arm B:** a miscalibrated group (n ≥ 30,
  gap > max(10 pp, 2 SE)) → typed trip `risk_statement_miscalibrated` +
  ops anomaly.
- **Recalibration schedule:** weekly pass proposes a realised calibration per
  tenant × forecaster (≥ 60 points, later third held out); canary (3
  identical recomputations) and the §18.2 freeze rule, plus "closer to nominal
  than the active one"; **activation by Ivan only**; rollback re-applies the
  previous version (the calibration is rolled back, not the service). An
  approved calibration of the anomaly forecaster is what finally lets the
  newsvendor rule (§18.4) run on real recommendations.
- **Cost parameters:** proposals only (`learning_items`), never applied
  silently: `lost_cover_value` from the revealed critical ratio of human
  decisions, `max_extra_staff` from constraint rejections; approval by the
  hotel or Ivan writes the parameter with `set_via = proposal_approval` and
  the proposal id in `set_by`.
- **Overrides and reasons → destination:** each routed reason becomes a
  review item (memory, decision rule, policy, case set, upstream filter);
  a case-set item becomes an eval case only once Ivan writes its expected
  output; `scripts/eval/export_case_candidates.py` appends it to the golden
  dataset (dated zone) and re-validates the file.
- **Hygiene** (tested): human vs agent separate; `agent_inferred` reasons
  ignored; outcomes never relabel decisions; manager-declared actuals flagged
  `independent_actuals = false`.
- New table `learning_items` (migration `20260925130000`, RLS service role,
  DSAR REVIEW step); weekly job `learning_loop` (Mon 03:40); review API
  `/api/v1/hotels/{tenant}/learning/*`.

### 18.6 What is and is not measured (25/09/2026)

| Item | Status |
|---|---|
| Correction window per task class | Built, stored on every recommendation. Offsets are **defaults (assumptions)**; no hotel has set its own |
| Prophet interval calibration | **Synthetic only**: 0.667 → 0.881 at nominal 80 %, n=126, 3 identical runs. Not measured on real covers |
| Anomaly-forecaster calibration (the one that drives dispatched recommendations) | **Does not exist**: no realised covers |
| Hotel costs | None configured → no amount shown anywhere |
| Newsvendor rule | Built and tested with injected calibrations; **never ran on a real recommendation** (fallback everywhere) |
| Risk-statement calibration, recalibration, cost proposals | Built and tested on constructed data; **no real outcome exists** |
| Real-model quality (parser) | Unchanged: not measured |

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

```python
"""Haiku parser eval — EVAL-4
- Loads parser_intent scenarios
- Calls real Haiku in non-CI mode (env: EVAL_PARSER_BACKEND=real)
- Calls FakeIntentClassifier in CI (EVAL_PARSER_BACKEND=fake, deterministic outputs)
- Computes confusion matrix (3x3: accepted/rejected/modified)
- Outputs: accuracy global, precision per intent, recall per intent, confusion matrix
"""
```

> **Décision implicite** : un `FakeIntentClassifier` (analogue à `FakeEmbeddingProvider` D11 ADR-0002) est requis. Stocké dans `backend/tests/providers/fake_intent_classifier.py`. Returns deterministic labels via hash. EVAL-4 Story DoD.

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
| R4 | **LLM non-determinism** : Haiku parser eval peut fluctuer même avec temperature 0. | Faux positifs CI, dev frustration. | `FakeIntentClassifier` en CI (déterministe), `--backend=real` réservé aux runs nightly schedulés (signal qualité reelle, pas gate PR). |
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
6. **Post-EVAL-0..5 shipped** : rédiger `docs/bmad/eval-by-design-workflow.md` (asset BMad réutilisable, Phase 3 Track B technical write-up)
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

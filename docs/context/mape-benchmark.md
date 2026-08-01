# MAPE benchmark — HOS-190 AC3 gate (Décision #14)

> ⚠️ **08/07/2026 — le chiffre synthétique ci-dessous est retiré de toute communication externe.**
> L'audit critique (`analyse-critique-2026-07.md`) a établi que le 15.09 % est **circulaire** :
> `generate_demo_data.py` fabrique les couverts à partir des mêmes régresseurs que Prophet consomme —
> le modèle retrouve sa propre formule génératrice. Le benchmark de référence est désormais la
> section **« Benchmark données réelles — Recruit (08/07/2026) »** ci-dessous (HOS-307).

> **Status:** ✅ **PASS — measured 2026-05-28.** *(gate interne de non-régression uniquement)*
> J+1 holdout MAPE = **15.09%** on the synthetic 365-day dataset (seed=42,
> holdout = last 30 days, all 3 regressors active). Gate threshold 22% cleared
> with a 6.91pp margin. Internal target 15% reached at 0.09pp delta — consistent
> with the Phase 0 status line in CLAUDE.md.

---

## Benchmark données réelles — Recruit Restaurant Visitor Forecasting (08/07/2026, HOS-307)

**Dataset** : fréquentation quotidienne **réelle** de 829 restaurants japonais (Kaggle *Recruit
Restaurant Visitor Forecasting*, 2016-01 → 2017-04, 252 108 observations) + jours fériés.
**Protocole** (déterministe, prouvé sur 2 runs bit-identiques — discipline Décision #29) :
30 restaurants au plus long historique · 6 origines par restaurant espacées de 5 jours
(rotation des phases de semaine — un espacement hebdo épinglerait chaque lead sur un unique
jour de semaine et biaiserait le MAPE) · horizon 7 jours · 1 193 points scorés par modèle.
**Script** : `scripts/ops/benchmark_recruit.py` · **Résultats** : `eval/benchmarks/recruit_results.json`.

| Modèle | MAPE all-leads | MAPE J+1 | MAPE J+7 | **MdAPE all-leads** | MdAPE J+1 | MdAPE J+7 |
|---|---|---|---|---|---|---|
| Baseline naïve (moy. 4 derniers mêmes jours) | 55.86 % | 57.47 % | 46.72 % | 27.57 % | 27.94 % | 27.39 % |
| **Prophet (config Aetherix + férié)** | **49.71 %** | 52.65 % | 42.37 % | 27.01 % | 28.54 % | 25.43 % |
| LightGBM (global, lags 7-28 + calendrier) | 52.41 % | 56.20 % | 44.00 % | **25.56 %** | 26.64 % | 24.56 % |

### Verdict AC4 (règle : Prophet bat la naïve de ≥ 5 pts MAPE)

> **Arbitrage tranché le 01/08/2026 (HOS-318) : PASS formel maintenu, ET clause de pivot déclenchée
> volontairement.** Les deux, et le second n'est pas une conséquence du premier.

**1. Le verdict formel reste PASS, et on ne le relit pas sur MdAPE.** Prophet fait −6.15 pp vs naïve en
MAPE all-leads. La métrique était figée *avant* le run — `scripts/ops/benchmark_recruit.py` code AC4 sur
MAPE all-leads, avec le commentaire explicite « AC4 stays on MAPE ». Changer de métrique après avoir
constaté que l'autre donne un verdict opposé serait exactement le biais que
[`protocole-de-preuve.md`](../planning/protocole-de-preuve.md) existe pour interdire. Le PASS tient.

**2. Mais la règle a mesuré autre chose que ce qu'elle visait.** La barre des 5 pts est un proxy de valeur
économique — « si Prophet ne bat pas la baseline de 5+ pts, pas de raison de payer »
([`analyse-critique-2026-07.md`](analyse-critique-2026-07.md), maillon 2). Or les 6.15 pts capturent la
robustesse de Prophet aux jours à très faible fréquentation, où l'APE explose sur un petit dénominateur
(2 couverts réels → 400 % d'erreur). Un manager ne staffe pas ces jours-là. Le proxy a mesuré une
propriété statistique, pas un gain décisionnel.

**3. Le fait qui tranche, et qui doit être cité avec le PASS : à J+1, Prophet est en médiane *moins bon*
que la naïve** — MdAPE 28.54 % contre 27.94 %. Sur le restaurant typique, un jour typique, à l'horizon
qu'on met en avant, le modèle ne fait pas mieux que « la moyenne des 4 derniers mêmes jours de semaine ».
Toutes leads confondues, Prophet et la naïve font jeu égal (27.01 vs 27.57 %).

**4. Conséquence — clause de pivot déclenchée, par décision et non par la règle.** Le pivot n'est pas
« on jette Prophet », c'est la note écrite qu'exige la DoD :
- **LightGBM global multi-propriétés = moteur candidat Phase 4** — meilleur modèle en médiane (25.56 %,
  −2 pp vs naïve), cohérent avec le leaderboard Kaggle d'origine.
- **Prophet conservé** pour l'explicabilité (décomposition tendance/saisonnalité lisible par le manager)
  et la robustesse aux extrêmes — deux propriétés que le Daily Receipt consomme directement.
- **Le forecast cesse d'être présenté comme le différenciateur** tant que le §4.1 du protocole n'a pas
  été passé sur données hôtelières réelles. C'est déjà la thèse de
  [`positionnement-wedge.md`](positionnement-wedge.md) ; ce benchmark en fournit la preuve chiffrée.

**5. Ce que ce dataset ne pouvait pas tester.** Recruit n'a pas d'occupancy — le régresseur qui porte toute
la thèse « base captive » d'Aetherix. Prophet y est évalué privé de son avantage informationnel supposé.
Le go/no-go réel se joue donc sur **HOS-308** (shadow mode, données hôtelières réelles), sous protocole
pré-enregistré : métrique de décision = **Δ MdAPE vs naïve à l'horizon H**, seuils 5,0 / 2,0 pp (§4.1).

**6. Reality-check de la cible produit < 15 %** : sur des restaurants de rue au jour le jour, aucun des
3 modèles n'en approche (25-28 % MdAPE). La cible reste plausible pour le cas hôtelier, mais elle doit
être revalidée sur données réelles avant toute promesse client.

> **Statut de pré-enregistrement de ce benchmark : aucun.** HOS-307 a été mergé le 08/07/2026, la story
> HOS-316 créée le 21/07. Il n'y a pas eu de protocole gelé pour ce run et ce document n'en fabrique pas
> rétroactivement (cf. `protocole-de-preuve.md` §0).

### Reproduire

```bash
# Données : Kaggle "Recruit Restaurant Visitor Forecasting" (air_visit_data.csv, date_info.csv)
# → placer dans backend/data/benchmarks/ (non commitées, ~9 Mo)
backend/.venv/Scripts/python scripts/ops/benchmark_recruit.py \
  --data-dir backend/data/benchmarks --out eval/benchmarks/recruit_results.json
```

---

## Why this file exists

The Linear ticket and Décision #14 fix a non-negotiable gate at
**MAPE J+1 ≤ 22%** on the synthetic 365-day dataset. The `/api/v1/predictions/train`
endpoint already returns an **in-sample** MAPE (`mape_training`), but that
metric measures fit, not forecast skill — it is always optimistic and is **not**
a valid gate metric on its own (cf. story pack T7).

This file records the **out-of-sample** measurement: train on days 1–335,
predict days 336–365, compute MAPE = mean(|y_true − y_pred| / y_true).

## How to fill it in (procedure)

```bash
# 1. Confirm dataset (regenerate only if file missing or stale)
cd backend
python ../scripts/ops/generate_demo_data.py
# → backend/data/demo/prophet_training.json  (365 rows)

# 2. Run the holdout MAPE script
python ../scripts/ops/measure_mape_j1.py --json-out ../docs/context/mape-benchmark-holdout.json
# Console prints in-sample MAPE, J+1 holdout MAPE, gate decision
# Exit 0 = PASS, exit 3 = FAIL (pivot ticket required)

# 3. (Optional) Confirm consistency with the training endpoint's in-sample MAPE
# Mint a predict-scoped MCP token (see story T5), then:
TOKEN="..."
curl -X POST https://aetherix-backend.fly.dev/api/v1/predictions/train \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"data_source": "synthetic", "include_weather": true, "include_events": true, "include_occupancy": true}'
# Response includes mape_training — should be close to (typically below) the holdout MAPE
```

Then paste the result block below.

---

## Result — run #1

| Field | Value |
|---|---|
| Date of measurement | 2026-05-28 16:26 CEST |
| Dataset | `backend/data/demo/prophet_training.json` |
| Synthetic seed (`DEMO_DATA_SEED`) | 42 (default) |
| Base year (`DEMO_DATA_YEAR`) | 2025 (default) |
| Train rows | 335 (days 2025-01-01 → 2025-12-01) |
| Holdout rows | 30 (days 2025-12-02 → 2025-12-31) |
| Regressors enabled | `weather_score`, `event_impact`, `occupancy` |
| Training duration | 218 ms |
| **In-sample MAPE** | **5.53%** |
| **Holdout MAPE J+1** (`mape_j1_holdout`) | **15.09%** |
| Gate threshold (Décision #14) | 22.00% |
| **Gate decision** | **PASS ✅** (margin 6.91pp under threshold; internal 15% target at 0.09pp) |

Per-day breakdown: see `docs/context/mape-benchmark-holdout.json` — same
commit as this file.

### Reading the result

The in-sample → holdout gap (5.53% → 15.09%, ≈10pp) is the honest measurement
of forecast skill versus fit. It is in line with what we expect on a fully
synthetic dataset where December carries the Saint-Sylvestre +0.50 event shock
plus a +1.20 seasonality multiplier — the 30-day holdout deliberately includes
the hardest month of the year, so 15% is a strong floor rather than an
artefact of an easy split.

The next meaningful MAPE measurement is the one that matters for the pitch:
**first 30 days of real-pilot data** (HOS-176, Phase 3) — that is when we
learn whether the synthetic-to-real generalisation gap is acceptable.

---

## Branch on failure

If `mape_j1_holdout > 0.22`:

1. **STOP** — do not deliver HOS-190 AC4 / AC5 / AC6.
2. Open Linear ticket `Pivot — MAPE gate fail (HOS-190 AC3)` under Epic HOS-174.
3. Mark HOS-190 as blocked, link this file.
4. Notify SM (Bob).
5. Investigation directions (suggested):
   - Increase regressor signal: per-property captation calibration may be
     overfit on synthetic data — consider running with `--no-regressors` first
     to establish a baseline.
   - Inspect per-day breakdown in `mape-benchmark-holdout.json` — December
     contains Christmas/NYE outliers (seasonality factor 1.20, plus the +0.50
     Saint-Sylvestre event spike) that may dominate the error.
   - If the gap is concentrated on Dec 31 alone, consider a model-level fix
     (additional holiday handling) rather than a true forecasting-skill pivot.

---

## References

- [Source: CLAUDE.md Décision #14] — Phase 0 DoD amended, gate non-negotiable
- [Source: tools/bmad/_bmad-output/implementation-artifacts/10-2a-sandbox-as-partner.md] — story pack, Phase C
- [Source: scripts/ops/measure_mape_j1.py] — holdout MAPE script (HOS-190 T7)
- [Source: backend/app/api/routes/predictions.py:308] — `_compute_in_sample_mape` (for comparison)

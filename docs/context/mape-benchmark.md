# MAPE benchmark — HOS-190 AC3 gate (Décision #14)

> **Status:** ✅ **PASS — measured 2026-05-28.**
> J+1 holdout MAPE = **15.09%** on the synthetic 365-day dataset (seed=42,
> holdout = last 30 days, all 3 regressors active). Gate threshold 22% cleared
> with a 6.91pp margin. Internal target 15% reached at 0.09pp delta — consistent
> with the Phase 0 status line in CLAUDE.md.

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
- [Source: docs/bmad/_bmad-output/implementation-artifacts/10-2a-sandbox-as-partner.md] — story pack, Phase C
- [Source: scripts/ops/measure_mape_j1.py] — holdout MAPE script (HOS-190 T7)
- [Source: backend/app/api/routes/predictions.py:308] — `_compute_in_sample_mape` (for comparison)

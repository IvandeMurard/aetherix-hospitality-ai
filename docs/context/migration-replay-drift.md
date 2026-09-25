# Migration replay drift — `demand_anomalies` (25/09/2026)

> Status: **fixed** on the fresh-replay path. Production unchanged by design.
> Related: Décision #16 (schema drift gate), HOS-111 (first in-place hardening of
> `20260323000000`), HOS-317 (`decision_ledger` view).

## 1. Symptom

The Supabase Preview check on PR #265 replays every migration on an empty
database. It failed on `20260801100000_decision_ledger_link.sql`:

```
ERROR: column da.triggering_factors does not exist
```

Reproduced locally with `scripts/ci/replay_migrations.sh` (Postgres 16 +
pgvector) on `main` at `424cc97`: same error, same file, same line.

## 2. Cause (verified by replay)

Three migrations touch the `demand_anomalies` shape before the view:

| Migration | Fresh database | Long-lived database (production) |
|---|---|---|
| `20260323000000_add_demand_anomalies_table` | **skipped**: its DO block only runs when `tenants` *and* `properties` exist; `properties` is never created by any migration | created the table with `expected_demand`, `baseline_demand`, `direction`, `triggering_factors`, `roi_revenue_opp`, `recommendation_text` |
| `20260323120000_add_staffing_recommendations_table` | creates `demand_anomalies` with an **older column set** (`anomaly_type NOT NULL`, `expected_covers`, `weather_factors`, …, none of the six columns above) | no-op (`IF NOT EXISTS`) |
| `20260514150000_backfill_orm_only_tables` | `CREATE TABLE IF NOT EXISTS` with the ORM shape → **no-op**, the table exists | no-op |

So a fresh replay ends with a table the view cannot read and the ORM cannot
write to (every ORM insert also violated `anomaly_type NOT NULL`).

The static drift gate (`check_schema_drift.py`) passed throughout: it parses
the text of CREATE/ALTER TABLE statements and finds the columns in the
`20260514150000` CREATE TABLE. It cannot know that the statement was a no-op.
Only a real replay sees it.

## 3. Fix

`20260514150000_backfill_orm_only_tables.sql` now follows its CREATE TABLE with:

- one `ALTER TABLE demand_anomalies ADD COLUMN IF NOT EXISTS …` per missing
  column (types from the ORM and from `20260323000000`);
- a DO block that drops `NOT NULL` on the legacy `anomaly_type` column when it
  exists, and sets the ORM's `NOT NULL` constraints only when the table is empty
  (cannot fail on a database holding rows).

### Why edit an applied migration rather than add a new file

Supabase applies a migration file when its version is **absent** from
`supabase_migrations.schema_migrations`; it does not checksum files already
applied. Two options were weighed:

| Option | Production | Fresh replay |
|---|---|---|
| New file with a timestamp before `20260801100000` | Out of order: the CLI refuses to push it without `--include-all`, and if forced it executes (harmless here, but it *does* run on production) | fixed |
| **Edit `20260514150000` in place** (chosen) | Version already recorded → **never re-executed: no-op** | fixed |

The chosen option is a strict no-op on production, keeps every file name and
order, and follows the precedent of HOS-111, which hardened
`20260323000000` in place on 15/05/2026 for the same reason. The statements are
idempotent, so a long-lived database that did replay the file would be
unchanged.

## 4. Verification

- `scripts/ci/replay_migrations.sh` on a throwaway Postgres 16: **FAIL** at
  `20260801100000` before the fix, **REPLAY OK (44 migrations)** after.
- Re-running the edited migration on a converged database that holds a row:
  passes, nothing changes.
- ORM vs replayed schema (every table in `Base.metadata`): no missing column.
  The only missing table is `users` (created by fastapi-users at first run,
  already listed in `schema_drift_ignore.json`). Remaining differences are
  representational and compatible: ORM `JSON` vs DB `JSONB`, ORM `Float` vs DB
  `NUMERIC` on `restaurant_profiles`, ORM naive vs DB aware timestamps on
  `restaurant_profiles.created_at/updated_at`. None breaks a replay; left as is.
- Views and materialized views all build on the replay: `decision_ledger`,
  `memory_instrumentation_daily`, `recommendation_acceptance_daily`,
  `abstention_daily`, `latency_slo_daily`.
- Legacy columns from `20260323120000` (`anomaly_type`, `expected_covers`,
  `weather_factors`, …) remain on a fresh replay, nullable. Production's
  exact column list was not inspected from here; the fix only adds what the
  ORM and the view need.

## 5. Rule going forward

A migration that is conditional (DO block, `IF EXISTS` on a prerequisite) can be
skipped on a fresh database and still pass the static gate. Before merging a
migration that reads a column created elsewhere, run
`scripts/ci/replay_migrations.sh` locally; the Supabase Preview check is the CI
equivalent.

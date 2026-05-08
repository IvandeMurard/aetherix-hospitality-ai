-- HOS-165 / HOS-159-C: normalize identifier types to match the convention
-- documented in docs/context/data-conventions.md.
--
-- Convention:
--   * `id` / `property_id` columns       → UUID
--   * `tenant_id` / `hotel_id` columns   → TEXT (human-readable slug)
--
-- This migration is idempotent: every step inspects the live column type
-- via information_schema before issuing DDL, so re-running it is a no-op.
-- Existing data is preserved (no DROP COLUMN, no NOT NULL added without a
-- DEFAULT).

-- ---------------------------------------------------------------------------
-- 1. RestaurantProfile.id : align to UUID (closes ORM drift HOS-163)
--    The base table (20250203000000) creates `id` as UUID, but the SQLAlchemy
--    model declared it as String. If a staging schema was patched manually and
--    `id` is currently TEXT, convert it via `id::uuid`.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    v_type text;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'restaurant_profiles'
      AND column_name  = 'id';

    IF v_type IS NULL THEN
        RAISE NOTICE 'restaurant_profiles.id not found — skipping (table missing?)';
    ELSIF v_type <> 'uuid' THEN
        RAISE NOTICE 'restaurant_profiles.id is %, converting to uuid', v_type;
        EXECUTE 'ALTER TABLE restaurant_profiles
                   ALTER COLUMN id TYPE UUID USING id::uuid';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. RestaurantProfile.property_id : explicit cross-table alias of `id`.
--    Other tables (DemandAnomaly, StaffingRecommendation, …) carry a
--    `property_id` UUID; surfacing the same column on `restaurant_profiles`
--    lets joins read naturally as `property_id → property_id`.
-- ---------------------------------------------------------------------------
ALTER TABLE restaurant_profiles
    ADD COLUMN IF NOT EXISTS property_id UUID;

-- Backfill: keep property_id == id by default (semantic alias). Idempotent —
-- this UPDATE is a no-op once the values already match.
UPDATE restaurant_profiles
   SET property_id = id
 WHERE property_id IS DISTINCT FROM id;

-- Add UNIQUE constraint only if absent (cannot use `IF NOT EXISTS` directly
-- on ADD CONSTRAINT in older Postgres versions).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'uq_restaurant_profiles_property_id'
    ) THEN
        EXECUTE 'ALTER TABLE restaurant_profiles
                   ADD CONSTRAINT uq_restaurant_profiles_property_id
                   UNIQUE (property_id)';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Align tenant_id → TEXT on tables where it currently lives as UUID.
--    `tenant_id` is the human-readable slug (e.g. "demo_hotel"). Any FK
--    pointing tenant_id → tenants(id) must be dropped; tenant_id ought to
--    reference restaurant_profiles(tenant_id) instead, but adding that FK is
--    deferred until production data is fully aligned.
--    Some legacy migrations also create RLS policies that compare
--    tenant_id against a UUID expression; those are dropped here so the
--    column type can change. They are intentionally not recreated — the
--    current `User` model has no `tenant_id` column, so the policy was
--    already non-functional.
-- ---------------------------------------------------------------------------

-- 3a. demand_anomalies.tenant_id
DO $$
DECLARE
    v_type text;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'demand_anomalies'
      AND column_name  = 'tenant_id';

    IF v_type = 'uuid' THEN
        ALTER TABLE demand_anomalies
            DROP CONSTRAINT IF EXISTS demand_anomalies_tenant_id_fkey;
        EXECUTE 'DROP POLICY IF EXISTS "Tenant Isolation" ON demand_anomalies';
        EXECUTE 'ALTER TABLE demand_anomalies
                   ALTER COLUMN tenant_id TYPE TEXT USING tenant_id::text';
    END IF;
END $$;

-- 3b. staffing_recommendations.tenant_id
DO $$
DECLARE
    v_type text;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'staffing_recommendations'
      AND column_name  = 'tenant_id';

    IF v_type = 'uuid' THEN
        ALTER TABLE staffing_recommendations
            DROP CONSTRAINT IF EXISTS staffing_recommendations_tenant_id_fkey;
        EXECUTE 'ALTER TABLE staffing_recommendations
                   ALTER COLUMN tenant_id TYPE TEXT USING tenant_id::text';
    END IF;
END $$;

-- 3c. conversational_queries.tenant_id
DO $$
DECLARE
    v_type text;
BEGIN
    SELECT data_type INTO v_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'conversational_queries'
      AND column_name  = 'tenant_id';

    IF v_type = 'uuid' THEN
        EXECUTE 'ALTER TABLE conversational_queries
                   ALTER COLUMN tenant_id TYPE TEXT USING tenant_id::text';
    END IF;
END $$;

-- Align operational_memory schema with ORM (post-HOS-150 AC1).
--
-- Background: the original migration 20260323240000_add_operational_memory_table.sql
-- defines a `reflection` column, but migration 20260327000000 drops & recreates
-- operational_memory with `content NOT NULL` instead. The ORM was migrated to
-- `reflection` in HOS-150 AC1 (PR #82), but the remote staging DB still has
-- `content` because 20260323240000 was marked applied without ever being executed.
--
-- This migration:
--   1. Adds `reflection` column if missing
--   2. Backfills it from `content` for any existing rows
--   3. Relaxes the NOT NULL on legacy `content` to keep older rows valid
-- All idempotent.

ALTER TABLE operational_memory
    ADD COLUMN IF NOT EXISTS reflection TEXT;

-- Backfill: copy any existing content to reflection if reflection is empty.
UPDATE operational_memory
SET reflection = content
WHERE reflection IS NULL AND content IS NOT NULL;

-- Relax NOT NULL on legacy `content` column (ORM no longer writes to it).
-- Idempotent via information_schema check.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operational_memory'
          AND column_name = 'content'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE operational_memory ALTER COLUMN content DROP NOT NULL;
    END IF;
END $$;

-- Enforce NOT NULL on reflection after backfill (ORM expects it).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operational_memory'
          AND column_name = 'reflection'
          AND is_nullable = 'YES'
    ) THEN
        -- Set default empty string for any remaining NULLs before NOT NULL.
        UPDATE operational_memory SET reflection = '' WHERE reflection IS NULL;
        ALTER TABLE operational_memory ALTER COLUMN reflection SET NOT NULL;
    END IF;
END $$;

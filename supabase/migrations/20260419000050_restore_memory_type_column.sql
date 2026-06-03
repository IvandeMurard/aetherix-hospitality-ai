-- Fix: restore memory_type column on operational_memory
--
-- The earlier 20260327000000 migration drops and recreates operational_memory
-- without the memory_type column (which was originally introduced in
-- 20260323240000_add_operational_memory_table.sql). This breaks
-- 20260419000100_memory_instrumentation_metrics.sql which builds a
-- materialized view filtering on memory_type.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS.

ALTER TABLE operational_memory
    ADD COLUMN IF NOT EXISTS memory_type TEXT NOT NULL DEFAULT 'reflection';

CREATE INDEX IF NOT EXISTS operational_memory_type_idx
    ON operational_memory (hotel_id, memory_type, created_at DESC);

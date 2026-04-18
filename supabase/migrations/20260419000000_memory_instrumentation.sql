-- Memory instrumentation — P1-3 / ADR 0002
-- Enables real embedding writes + pending-embedding failure mode (ADR D9).

-- Relax NOT NULL on embedding so we can write a "pending" row on Mistral failure.
ALTER TABLE operational_memory ALTER COLUMN embedding DROP NOT NULL;

-- Flag rows where embedding failed and needs a backfill job.
ALTER TABLE operational_memory
    ADD COLUMN IF NOT EXISTS embedding_pending BOOLEAN NOT NULL DEFAULT FALSE;

-- Consistency check: a row must have EITHER a real embedding OR be pending.
ALTER TABLE operational_memory
    ADD CONSTRAINT embedding_or_pending
    CHECK (embedding IS NOT NULL OR embedding_pending = TRUE);

-- Efficient scan for the re-embed backfill worker.
CREATE INDEX IF NOT EXISTS operational_memory_pending_idx
    ON operational_memory (created_at)
    WHERE embedding_pending = TRUE;

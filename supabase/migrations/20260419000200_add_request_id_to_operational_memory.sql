-- P2-2: add request_id backlink to operational_memory
-- Enables Receipts to join memory writes back to the MCP tool call that created them.
-- Nullable — rows written before this migration have no backlink.
ALTER TABLE operational_memory
    ADD COLUMN IF NOT EXISTS request_id TEXT NOT NULL DEFAULT '';

-- Index for the JOIN in ReceiptsService.daily_receipt
CREATE INDEX IF NOT EXISTS idx_operational_memory_request_id
    ON operational_memory (request_id)
    WHERE request_id != '';

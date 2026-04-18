-- Memory instrumentation metrics view — P1-3 / ADR 0002 D10
-- Consumed by P1-4 ablation benchmark.

CREATE MATERIALIZED VIEW IF NOT EXISTS memory_instrumentation_daily AS
SELECT
    hotel_id,
    date_trunc('day', created_at)::date            AS date,
    count(*)                                        AS writes,
    count(*) FILTER (WHERE embedding_pending = TRUE) AS pending_writes,
    round(
        100.0 * count(*) FILTER (WHERE embedding_pending = TRUE) / nullif(count(*), 0), 2
    )                                               AS pending_pct
FROM operational_memory
WHERE memory_type IN ('feedback', 'reflection')
GROUP BY hotel_id, date_trunc('day', created_at)::date
ORDER BY hotel_id, date DESC;

CREATE UNIQUE INDEX IF NOT EXISTS memory_instrumentation_daily_pk
    ON memory_instrumentation_daily (hotel_id, date);

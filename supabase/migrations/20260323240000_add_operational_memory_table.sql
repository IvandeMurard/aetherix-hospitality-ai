-- Operational memory table — replaces Backboard.io as the cognitive memory layer.
--
-- Stores manager feedback, operational insights, and cached recommendations
-- with semantic embeddings for pgvector retrieval.
--
-- manager_feedback values:
--   'followed'  — manager accepted the recommendation (boost signal)
--   'rejected'  — manager dismissed the recommendation (penalty signal)
--   'neutral'   — no explicit feedback
--
-- memory_type values:
--   'reflection'           — operational insight or learned pattern
--   'recommendation_cache' — cached AI recommendation (reco_json populated)
--   'feedback'             — explicit manager feedback event

CREATE TABLE IF NOT EXISTS operational_memory (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    hotel_id         TEXT        NOT NULL,
    session_id       TEXT,
    reflection       TEXT        NOT NULL,
    reco_json        JSONB,
    manager_feedback TEXT        CHECK (manager_feedback IN ('followed', 'rejected', 'neutral')),
    outcome          TEXT,
    memory_type      TEXT        NOT NULL DEFAULT 'reflection',
    embedding        vector(1024) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index for semantic recall queries
CREATE INDEX IF NOT EXISTS operational_memory_embedding_hnsw_idx
    ON operational_memory USING hnsw (embedding vector_cosine_ops);

-- Partition-friendly filter indices
CREATE INDEX IF NOT EXISTS operational_memory_hotel_id_idx
    ON operational_memory (hotel_id);

CREATE INDEX IF NOT EXISTS operational_memory_feedback_idx
    ON operational_memory (hotel_id, manager_feedback);

CREATE INDEX IF NOT EXISTS operational_memory_type_idx
    ON operational_memory (hotel_id, memory_type, created_at DESC);

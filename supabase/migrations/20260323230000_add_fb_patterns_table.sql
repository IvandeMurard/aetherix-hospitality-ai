-- F&B patterns table for pgvector-based semantic retrieval.
-- Replaces the Qdrant `fb_patterns` collection (495+ embeddings, 1024d, Mistral).
--
-- HNSW index chosen for sub-millisecond ANN search at Phase 0/1 scale.
-- Exact search via IVFFlat is sufficient at <50K rows; HNSW gives better
-- recall and is cheaper to build at this volume.

CREATE TABLE IF NOT EXISTS fb_patterns (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type TEXT        NOT NULL,          -- breakfast | lunch | dinner
    occupancy_band TEXT,                         -- low | medium | high | peak
    day_of_week TEXT,                            -- monday … sunday
    payload     JSONB       NOT NULL DEFAULT '{}',  -- full metadata from Qdrant payload
    embedding   vector(1024) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- HNSW index for cosine distance (Mistral embed space)
CREATE INDEX IF NOT EXISTS fb_patterns_embedding_hnsw_idx
    ON fb_patterns USING hnsw (embedding vector_cosine_ops);

-- Filter index used in WHERE service_type = $1 queries
CREATE INDEX IF NOT EXISTS fb_patterns_service_type_idx
    ON fb_patterns (service_type);

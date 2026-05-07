-- Add embedding column to case_record so search_cases can layer in vector
-- cosine similarity alongside FTS + trigram. Uses 384-dim embeddings
-- (sentence-transformers/all-MiniLM-L6-v2) — light enough to encode the
-- ~5K-case corpus on CPU in ~10 minutes, good-enough quality for English
-- legal-summary retrieval at v0.1 scale.

ALTER TABLE case_record ADD COLUMN IF NOT EXISTS embedding vector(384);

CREATE INDEX IF NOT EXISTS case_record_embedding_hnsw_idx
    ON case_record
    USING hnsw (embedding vector_cosine_ops);

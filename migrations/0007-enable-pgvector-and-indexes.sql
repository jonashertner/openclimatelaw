CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document ADD COLUMN embedding vector(1024);
ALTER TABLE statute  ADD COLUMN embedding vector(1024);

-- HNSW indexes for cosine similarity. m=16, ef_construction=64 are pgvector defaults
-- and a reasonable starting point for the v0.1 scale (~15k document embeddings).
CREATE INDEX document_embedding_hnsw_idx ON document
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX statute_embedding_hnsw_idx ON statute
    USING hnsw (embedding vector_cosine_ops);

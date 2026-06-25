-- Passage-level units of document.text for statement-level (pinpoint) retrieval.
-- Each row is a paragraph-sized span with char offsets into document.text, a
-- per-passage FTS index, and an optional embedding for semantic pinpointing.
CREATE TABLE document_passage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    para_index INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    embedding vector(384),
    UNIQUE (document_id, para_index)
);

CREATE INDEX document_passage_case_idx ON document_passage(case_id);
CREATE INDEX document_passage_fts_idx ON document_passage
    USING GIN (to_tsvector('simple', text));
CREATE INDEX document_passage_hnsw_idx ON document_passage
    USING hnsw (embedding vector_cosine_ops);

-- Document table. `embedding` column is added in migration 0007 once pgvector is enabled,
-- to keep this migration runnable on a stock Postgres image during dev/test.

CREATE TABLE document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    category_code TEXT NOT NULL REFERENCES vocabulary_document_category(code),
    title TEXT NOT NULL,
    filed_date DATE,
    filed_by TEXT,
    upstream_url TEXT NOT NULL,
    storage_url TEXT,                              -- R2 URL of mirrored PDF, NULL until ingested
    text TEXT,                                      -- extracted full text
    text_lang TEXT,
    text_extraction_method TEXT
        CHECK (text_extraction_method IS NULL OR
               text_extraction_method IN ('pymupdf', 'tesseract', 'upstream_provided')),
    text_translation_en TEXT,                       -- MT to English when text_lang != 'en'
    text_content_hash TEXT,                         -- sha256 of text; cache key for translation/embeddings
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX document_case_idx ON document(case_id);
CREATE INDEX document_category_idx ON document(category_code);
CREATE INDEX document_text_fts_idx ON document
    USING GIN (to_tsvector('simple', coalesce(text, '')));
CREATE INDEX document_translation_fts_idx ON document
    USING GIN (to_tsvector('english', coalesce(text_translation_en, '')));

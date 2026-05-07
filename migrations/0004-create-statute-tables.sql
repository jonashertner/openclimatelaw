-- Statute tables. `statute` represents laws and regulations. `case_statute` is the
-- bridge table linking cases to statutes they enforce, challenge, interpret, cite, or reference.
-- Both tables cascade-delete because statute and case are the owners.

CREATE TABLE statute (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cclw_id TEXT UNIQUE,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    short_title TEXT NOT NULL,
    long_title TEXT,
    enacted_date DATE,
    status TEXT NOT NULL,                            -- CCLW status enum, sourced verbatim
    text TEXT,
    text_lang TEXT,
    text_content_hash TEXT,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX statute_jurisdiction_idx ON statute(jurisdiction_code);
CREATE INDEX statute_text_fts_idx ON statute
    USING GIN (to_tsvector('simple', coalesce(text, '')));
CREATE INDEX statute_short_title_fts_idx ON statute
    USING GIN (to_tsvector('simple', short_title));

CREATE TABLE case_statute (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    statute_id UUID NOT NULL REFERENCES statute(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL CHECK (
        relationship IN ('enforces', 'challenges', 'interprets', 'cited', 'referenced')
    ),
    source_of_link TEXT NOT NULL,
    PRIMARY KEY (case_id, statute_id, relationship)
);

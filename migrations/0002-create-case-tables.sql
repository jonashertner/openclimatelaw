-- Case tables. `case_record` is the canonical case (named `case_record` because
-- `case` is a Postgres reserved word). Sabin's case_id is the natural key when present.

CREATE TABLE case_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sabin_id TEXT UNIQUE,
    canonical_title TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    court_id TEXT REFERENCES vocabulary_court(id),
    filing_date DATE,
    decision_date DATE,
    status_code TEXT REFERENCES vocabulary_status(code),
    outcome_code TEXT REFERENCES vocabulary_outcome(code),
    summary TEXT,
    summary_lang TEXT NOT NULL DEFAULT 'en',
    primary_source TEXT NOT NULL CHECK (
        primary_source IN ('sabin', 'climate_rights', 'c2li', 'melbourne', 'redline')
    ),
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX case_record_jurisdiction_idx ON case_record(jurisdiction_code);
CREATE INDEX case_record_court_idx ON case_record(court_id);
CREATE INDEX case_record_filing_date_idx ON case_record(filing_date);
CREATE INDEX case_record_summary_fts_idx ON case_record
    USING GIN (to_tsvector('simple', coalesce(summary, '')));

CREATE TABLE case_party (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    side TEXT NOT NULL CHECK (side IN ('plaintiff', 'defendant', 'intervenor', 'amicus')),
    name TEXT NOT NULL,
    party_type TEXT,                              -- 'individual' | 'ngo' | 'corporation' | 'state' | 'sub_state'
    ord INT NOT NULL,                             -- preserves source ordering
    PRIMARY KEY (case_id, side, ord)
);

CREATE INDEX case_party_name_idx ON case_party USING GIN (to_tsvector('simple', name));

CREATE TABLE case_claim_type (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    claim_type_code TEXT NOT NULL REFERENCES vocabulary_claim_type(code),
    PRIMARY KEY (case_id, claim_type_code)
);

CREATE TABLE citation_string (
    case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    lang TEXT NOT NULL,
    format TEXT NOT NULL,                          -- 'sabin' | 'bluebook' | 'oscola' | 'iclq' | source-native
    text TEXT NOT NULL,
    PRIMARY KEY (case_id, lang, format)
);

CREATE INDEX citation_string_text_idx ON citation_string(text);

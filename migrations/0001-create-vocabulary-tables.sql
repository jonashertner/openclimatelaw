-- Vocabulary tables: controlled values mirrored from upstream sources (Sabin, CCLW, etc).
-- Each vocabulary record carries a source_version so we can detect upstream taxonomy changes.

CREATE TABLE vocabulary_jurisdiction (
    code TEXT PRIMARY KEY,                       -- ISO 3166-1 alpha-2, or special codes (ICJ, IACTHR, ECTHR, etc.)
    name TEXT NOT NULL,
    kind TEXT NOT NULL,                          -- 'national' | 'sub_national' | 'international' | 'regional'
    source TEXT NOT NULL,                        -- 'sabin' | 'cclw' | 'manual'
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_court (
    id TEXT PRIMARY KEY,                         -- Sabin's court id
    name TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL REFERENCES vocabulary_jurisdiction(code),
    level TEXT,                                  -- 'supreme' | 'appellate' | 'trial' | 'tribunal' | 'other'
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_claim_type (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_status (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_outcome (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vocabulary_document_category (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

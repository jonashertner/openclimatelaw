-- pg_trgm extension + GIN trigram index on canonical_title.
-- Enables fuzzy/typo-tolerant matching alongside the existing FTS GIN index
-- on summary. search_cases combines both: FTS handles topic queries,
-- trigram handles partial / misspelled case-name queries.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS case_record_canonical_title_trgm_idx
    ON case_record
    USING GIN (canonical_title gin_trgm_ops);

-- Also useful: trigram on summary for fuzzy phrase matching.
CREATE INDEX IF NOT EXISTS case_record_summary_trgm_idx
    ON case_record
    USING GIN (summary gin_trgm_ops);

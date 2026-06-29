-- Structured, verifiable doctrinal record per case (the "doctrinal assistant" layer).
-- Each quoted element is checked verbatim against the source; quotes_verified/quotes_total
-- record the grounding. significance is interpretive synthesis (no quote). Derived by an
-- LLM with provenance — never presented as upstream-authored.
CREATE TABLE case_doctrine (
    case_id              UUID PRIMARY KEY REFERENCES case_record(id) ON DELETE CASCADE,
    disposition_outcome  TEXT,                         -- plaintiff_won|defendant_won|mixed|settled|na|unknown
    disposition_posture  TEXT,
    disposition_quote    TEXT,
    holdings             JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{point, quote, verified}]
    legal_test           TEXT,
    legal_test_quote     TEXT,
    legal_bases          JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [text]
    relief               TEXT,
    relief_quote         TEXT,
    significance         TEXT,                         -- synthesis; unverified by design
    source_kind          TEXT NOT NULL,               -- 'case_summary' | 'summary+document'
    model                TEXT NOT NULL,
    quotes_total         INT NOT NULL DEFAULT 0,
    quotes_verified      INT NOT NULL DEFAULT 0,
    extracted_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

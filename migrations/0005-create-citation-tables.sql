-- Citation graph. `cited_case_id` is non-null when target is in our DB;
-- `cited_authority` is non-null when the cited target is external (foreign court,
-- treaty, statute, etc.). Both can be null only if neither was extracted (rare).

CREATE TABLE citation_edge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citing_case_id UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    citing_document_id UUID REFERENCES document(id) ON DELETE SET NULL,
    cited_case_id UUID REFERENCES case_record(id) ON DELETE SET NULL,
    cited_authority TEXT,
    citation_string TEXT NOT NULL,
    span_in_document JSONB,                          -- {char_start, char_end}
    source_of_edge TEXT NOT NULL CHECK (
        source_of_edge IN ('cpr', 'sabin_structured', 'inferred_nlp', 'manual')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX citation_edge_citing_idx ON citation_edge(citing_case_id);
CREATE INDEX citation_edge_cited_idx ON citation_edge(cited_case_id);

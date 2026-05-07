CREATE TABLE merge_candidate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id_a UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    case_id_b UUID NOT NULL REFERENCES case_record(id) ON DELETE CASCADE,
    score FLOAT NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
    features JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'merged', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    CONSTRAINT merge_candidate_distinct CHECK (case_id_a <> case_id_b)
);

CREATE INDEX merge_candidate_status_idx ON merge_candidate(status);
CREATE INDEX merge_candidate_pair_idx ON merge_candidate(case_id_a, case_id_b);

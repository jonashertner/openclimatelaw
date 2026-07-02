-- Dedup embedding store for semantic pinpoint. 78% of the 4.98M passages are duplicate
-- content, so we embed ~1.1M distinct content_hashes (with multilingual-e5-small, 384-dim)
-- and join by content_hash. find_relevant_passage is per-case (a few hundred passages), so
-- no global ANN index is needed — the per-case join + brute-force cosine is fast.
CREATE TABLE passage_embedding (
    content_hash  text PRIMARY KEY,
    embedding     vector(384) NOT NULL,
    model         text NOT NULL DEFAULT 'multilingual-e5-small',
    created_at    timestamptz NOT NULL DEFAULT now()
);

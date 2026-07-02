-- Index document_passage.content_hash so the dedup embedding backfill can pull passage text
-- per batch (WHERE content_hash = ANY(...)) without seq-scanning 4.98M rows each time, and
-- so find_relevant_passage's content_hash join is fast.
CREATE INDEX document_passage_content_hash_idx ON document_passage (content_hash);

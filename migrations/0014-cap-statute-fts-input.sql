-- to_tsvector rejects input larger than ~1MB; large CCLW laws (multi-MB text) broke
-- the statute FTS index on insert. Cap the indexed text to a safe UTF-8 byte budget
-- (262000 chars * 4 bytes <= 1048575). FTS over the first ~262k chars is ample for search.
DROP INDEX IF EXISTS statute_text_fts_idx;
CREATE INDEX statute_text_fts_idx ON statute
    USING GIN (to_tsvector('simple', left(coalesce(text, ''), 262000)));

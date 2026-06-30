-- Optional full-logging columns for the testing phase: the raw caller IP and the tool
-- arguments (e.g. the query text). Populated only when USAGE_LOG_FULL is on; left NULL in
-- privacy-first mode (which keeps only the salted ip_hash and no arguments).
ALTER TABLE usage_event ADD COLUMN ip text;
ALTER TABLE usage_event ADD COLUMN arguments jsonb;

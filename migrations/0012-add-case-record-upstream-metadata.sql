-- Add a JSONB column on case_record to retain the full upstream metadata
-- payload from Sabin / climatecasechart.com (and equivalent from CCLW etc.
-- in future). The structured columns we already have (status, filing_date,
-- jurisdiction, claim_types) are projected from this blob, but the blob
-- itself is the source of truth for fields we don't yet model:
--
--   - case_number  (real upstream docket number, used for citation enrichment)
--   - core_object  (one-sentence holding/issue text)
--   - principal_law refs  (in concept_preferred_label as 'principal_law/...')
--   - events       (timeline: filing year, decisions, appeals)
--   - concepts     (full hierarchy with relation/subconcept_of links)
--   - id, external_id, original_case_name, attribution, collections
--
-- Storing the blob lets us add structured columns/tables later without a
-- re-scrape. Nullable so existing rows aren't disturbed.

ALTER TABLE case_record
    ADD COLUMN IF NOT EXISTS upstream_metadata JSONB;

COMMENT ON COLUMN case_record.upstream_metadata IS
    'Full upstream payload (e.g., Sabin family.metadata + concepts + events). '
    'Source of truth for fields not yet projected into structured columns.';

-- GIN index for occasional ad-hoc lookups by metadata key (e.g., principal_law).
CREATE INDEX IF NOT EXISTS case_record_upstream_metadata_gin
    ON case_record USING gin (upstream_metadata jsonb_path_ops);

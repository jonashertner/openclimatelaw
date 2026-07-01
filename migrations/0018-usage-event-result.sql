-- Response logging for quality control: a compact summary of what each tool call RETURNED
-- (count / total / no_match / top_confidence / returned_chars / violations) plus, in full
-- mode, a truncated JSON preview. This is public case/law text + result metadata, not user
-- data — it lets us see when users got poor results (e.g. find_relevant_passage no_match)
-- without replaying their session.
ALTER TABLE usage_event ADD COLUMN result jsonb;

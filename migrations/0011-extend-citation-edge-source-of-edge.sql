-- Extend the source_of_edge enum on citation_edge to include 'title_match'.
-- The title_match extractor (ingest.citation_graph_titles) populates edges by
-- finding occurrences of other cases' canonical titles in summaries and
-- document text. Distinct from 'inferred_nlp' (formal-cite regex extraction)
-- so consumers can distinguish the source quality.

ALTER TABLE citation_edge DROP CONSTRAINT IF EXISTS citation_edge_source_of_edge_check;

ALTER TABLE citation_edge ADD CONSTRAINT citation_edge_source_of_edge_check
    CHECK (source_of_edge IN ('cpr', 'sabin_structured', 'inferred_nlp', 'manual', 'title_match'));

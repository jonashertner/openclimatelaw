# Climate Litigation Database — Data-Quality QA Report

> Prepared by OpenClimateLaw as a contribution to the Sabin Center + Climate Policy Radar.
> Findings come from building a citation-safe research layer over the corpus (5,027 cases /
> 81,345 documents ingested, as-of 2026-05-07). Offered in the spirit of giving back: each item is
> something we can contribute a fix or a patch for. Counts are from our mirror; please validate
> against the canonical platform.

## High-impact

1. **`decision_date` mis-mapping (we have a fix).** Many records carried a *metadata-modification
   timestamp* as the decision date, so recently-touched cases displayed 2026 "decision" dates (e.g.
   filed-status cases showing 2026-04-xx). We re-derive `decision_date` from the **latest `Decision`
   event** in each proceeding's event timeline (preferring an event whose text names a *judgment* over a
   later post-judgment item, so e.g. KlimaSeniorinnen reads its 2024-04-09 merits judgment, not the
   2025-03-06 Committee-of-Ministers execution decision), and leave it NULL when there is no decision.
   Result on our mirror: **~2,150 dates corrected (1,721 spurious dates cleared to NULL), 3,056 true
   decision dates retained.** Happy to share the derivation logic upstream.

2. **Cross-source duplicates.** ~595 duplicate-title groups. In particular, the 215 Climate Rights
   Database records appear to duplicate Sabin cases — 195 of them coded jurisdiction `XX`, with stub
   summaries ("See [url]…"). In an *unfiltered* query against the raw mirror these out-rank the canonical
   record (e.g. *Urgenda*); OpenClimateLaw's search already suppresses them, but a stable
   `import_id`-based dedup key would let you collapse them at the source.

3. **`outcome` unpopulated (100% null) and `parties` empty.** "Who won?" is the first question a
   litigator asks. These are derivable (a confidence-gated classifier over decision text for outcome;
   party parsing for parties) and we'd keep any derived value verifiable/attributed.

4. **~21% of documents have no extracted text.** Concentrated in scanned/older/non-US PDFs. An OCR
   fallback (e.g. OCRmyPDF/Tesseract) would recover most; the schema already supports it.

## Coverage / freshness

5. **Apex landmarks — present, but with CRD-stub noise alongside.** *Verein KlimaSeniorinnen v.
   Switzerland* and the *2025 ICJ Advisory Opinion* are present as canonical Sabin records (correct
   courts, citation_strings, and — after our date fix — correct dates). The duplicate Climate Rights
   blog-analysis stubs ("Part 1/2/3 of 3") sit alongside them and pollute unfiltered search; collapsing
   those (item 2) is the cleanup.

6. **`jurisdiction` code `XX`** is used for international/cross-border records (195), which makes the
   documented jurisdiction filter miss them. A normalized code (e.g. `INT`, or court-body codes like
   `ICJ`/`ECTHR`) would make them filterable.

7. **Thin formal-citation graph.** Case-to-case links are almost entirely title-match; very few formal
   citations are extracted. Enriching from a citator (e.g. CourtListener/RECAP for US) would
   strengthen influence analysis.

## What we're offering
- The `decision_date` derivation + a dedup pass as upstream-ready patches.
- A citation-safe MCP/agent interface to the **official** corpus, so the database is represented
  faithfully (no fabricated citations/quotes) inside LLM tools.
- Ongoing QA reports on each refresh.

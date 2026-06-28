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
   event** in each proceeding's event timeline, and leave it NULL when there is no decision. Result on
   our mirror: **2,050 dates corrected (1,721 spurious dates cleared to NULL), 3,056 true decision
   dates retained.** Happy to share the derivation logic upstream.

2. **Cross-source duplicates.** ~595 duplicate-title groups. In particular, every Climate Rights
   Database record (215) appears to duplicate a Sabin case — coded jurisdiction `XX`, with stub
   summaries ("See [url]…") — and out-ranks the canonical record in naive search (e.g. *Urgenda*). A
   stable `import_id`-based dedup key would collapse these; we currently suppress them in our search.

3. **`outcome` unpopulated (100% null) and `parties` empty.** "Who won?" is the first question a
   litigator asks. These are derivable (a confidence-gated classifier over decision text for outcome;
   party parsing for parties) and we'd keep any derived value verifiable/attributed.

4. **~21% of documents have no extracted text.** Concentrated in scanned/older/non-US PDFs. An OCR
   fallback (e.g. OCRmyPDF/Tesseract) would recover most; the schema already supports it.

## Coverage / freshness

5. **Apex landmarks missing as canonical records.** *Verein KlimaSeniorinnen v. Switzerland* and the
   *2025 ICJ Advisory Opinion on Obligations of States* surface only as blog-analysis stubs in our
   mirror, not as primary case records. (May be an artifact of our ingest timing — flagging so it can
   be checked on the canonical platform.)

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

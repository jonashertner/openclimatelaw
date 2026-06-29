# Data-Quality Observations — Climate Litigation Database + CCLW

> Prepared by OpenClimateLaw for the **Sabin Center** and **Climate Policy Radar**, offered as a
> contribution — not a critique. Findings come from building a citation-safe research layer over both
> corpora (**5,027 cases / 81,345 court documents + 5,347 CCLW laws**, as-of **2026-05-07**).
>
> **Please validate before acting.** Our snapshot predates the 25 Sept 2025 relaunch (~7 weeks stale)
> and is built from a mirror, so each item is a *candidate to confirm* on the live platform, not a
> confirmed defect. Counts are from our mirror. We're glad to share the exact record IDs / queries
> behind any item — and to contribute the fix.

## Part A — Climate Litigation Database (Sabin)

### Fields & structure
1. **`decision_date` conflates merits judgments with procedural and execution events.** Motions
   (remand, protective order, discovery), bare "order" entries with empty descriptions, and
   post-judgment supervision items all carry `event_type="Decision"`, so a case's "decision date" can
   be a procedural docket date. *E.g.* Shoalwater Bay v. Exxon shows a 2026-04-29 "decision" from a
   procedural order though the merits aren't resolved; KlimaSeniorinnen could read its 2025-03-06
   execution decision over its 2024-04-09 merits judgment. *Suggestion:* a distinct event category
   (merits / procedural / execution) and/or a `final_decision_date` + finality flag. (We work around
   it by preferring judgment-text events and excluding procedural ones — happy to share the logic.)
2. **`status_code` can disagree with the actual posture.** Cases at a higher court read "decided"
   while upstream `metadata.status` says "Pending" (Milieudefensie v. Shell, at the Hoge Raad) or
   "Dismissed" (Lliuya v. RWE). *Suggestion:* one reconciled status vocabulary + finality, so
   "decided" means *finally* decided.
3. **`filing_date` is year-only, stored as January 1** (~93% of records) — within-year ordering is
   lost and thousands of "1 January" filings appear. *Suggestion:* a date-precision flag, not a hard
   01-01.
4. **Document `category_code` is often inaccurate.** Briefs, motions, replies, notices — and at least
   one *"Plaintiffs' Proposed Findings of Fact"* (a party submission) — are tagged `opinion`; many
   documents are titled only "order" with no description. A careless consumer could quote a party
   brief as the court. *Suggestion:* distinguish court opinions/orders from party filings.
5. **`claim_type` mixes real categories with leaked metadata and overlaps at several granularities.**
   Non-claim keys (`year`, `keywords`, `blog`, `uncategorized`, `deciding-body`, `rights-at-stake`,
   `state-concerned`, individual country names) sit alongside genuine claim types; and e.g.
   `right-to-a-healthy-environment-global` vs `…-environment`, or `public-trust-claims-us` vs
   `public-trust-global` vs `public-trust-doctrine`, fragment one concept. *Suggestion:* a controlled,
   hierarchical claim-type vocabulary.
6. **`principal_laws` misses bases stated in the summary, and leaks jurisdiction nodes.** Asmania v.
   Holcim names Art. 28 ZGB and Art. 41 OR in its summary but carries no principal_laws; and
   `principal_law/United States` appears next to `jurisdiction/United States`. *Suggestion:* tighten
   concept extraction; keep jurisdictions out of principal-law.
7. **Outcome and parties aren't machine-readable.** "Who won" and plaintiff/defendant aren't
   structured. (We derived both as a demonstration — outcomes via a confidence-gated, quote-verified
   classifier anchored to the *latest* disposition; parties by caption parsing — and label them as
   **ours**, with provenance, never as yours.) *Worth considering:* a structured disposition + party
   model, even partial, for the decided/landmark set.

### Identity & coverage
8. **Duplicate and mirror records.** Flagships appear under multiple family IDs — *Held v. State* (4),
   *Juliana* (5), *Massachusetts v. EPA* (2 sharing a docket) — and language variants exist as
   separate records (English *Juliana* vs the Spanish-titled record under `XA`). They split search and
   influence. *Suggestion:* a stable identity / dedup key (e.g. CPR `import_id`) + a language-variant
   link.
9. **International / regional cases share the catch-all jurisdiction `XA`** (ICJ, ITLOS, ECtHR,
   IACtHR), so they can't be filtered by jurisdiction code — only `court_id` distinguishes them.
   *Suggestion:* body-specific codes.
10. **The international advisory opinions are present but hard to find.** The 2025 ICJ AO is in the
    corpus (52 documents) but filed under "Request for an advisory opinion…", so a natural query
    surfaces commentary *about* it above the record; the ITLOS opinion and the latest IACtHR OC appear
    only as commentary stubs. *Suggestion:* integrate + title the international/advisory stream so it
    surfaces as the landmark it is.
11. **~21% of documents have no extracted text** (scanned / older / non-US PDFs). *Suggestion:* an OCR
    fallback recovers most — the schema already supports it; we can contribute it.
12. **Thin formal-citation graph** — case-to-case links are almost entirely title-match; few formal
    citations are extracted. *Suggestion:* enrich from a citator (CourtListener / RECAP for the US).

## Part B — Climate Change Laws of the World (CPR)

> From ingesting the open `ClimatePolicyRadar/all-document-text-data` "Laws and Policies" corpus
> (5,347 laws across ~200 jurisdictions) and bridging it to litigation.

1. **The corpus is predominantly non-statutory.** "Laws and Policies" mixes statutes/regulations with
   policies, plans, strategies and NDCs; the instrument type isn't exposed in a way that lets a
   consumer filter "actual statutes" from policy documents. *Suggestion:* a clear instrument-type
   field (statute / regulation / policy / strategy), surfaced on the record.
2. **The general statutes climate litigation turns on are largely absent.** The most-litigated US
   climate statutes — the **Clean Air Act, NEPA, the ESA, the APA** — aren't in CCLW, which focuses on
   climate-specific framework laws. So a case↔law bridge can't connect US cases to the laws they
   actually invoke. *Suggestion:* note the scope explicitly, or extend coverage to those general
   statutes.
3. **Multilingual statutes interleave all official languages in one document.** The South Africa
   Climate Change Act 2024 record interleaves all 11 official languages, so reading by character offset
   lands in the wrong language and there's no per-language segmentation. *Suggestion:* a language field
   per segment, or separate per-language documents.
4. **The case↔law concept mapping isn't published.** CPR's internal annotations linking cases to the
   laws they cite would make the litigation↔legislation bridge comprehensive — today we match by exact
   title + jurisdiction, high-precision but partial (~145 links). *Suggestion / ask:* share the concept
   mapping + `import_id`s.
5. **Non-ISO geography codes** (`XKX` Kosovo, `EUR` EU-wide, `XAA`) need special handling.
   *Suggestion:* document the code set.

## What we're offering to contribute
- The `decision_date` derivation (merits-vs-procedural), a dedup pass, an OCR-text fallback, and party
  parsing — as upstream-ready patches.
- A **citation-safe MCP/agent interface to the official corpora**, so both databases are represented
  faithfully (no fabricated citations or quotes) inside the LLM tools practitioners increasingly use.
- Ongoing QA reports on each refresh.

> Note on scope: items above are **source-data** observations, distinct from OpenClimateLaw's own
> earlier ingestion bugs (e.g. our initial `decision_date` mis-mapping), which we've fixed on our side.

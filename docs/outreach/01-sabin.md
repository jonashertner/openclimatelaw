# Outreach — Sabin Center for Climate Change Law

**To:** Michael Burger (Executive Director) — `mb3331@columbia.edu` (verify on Columbia directory)
**Cc:** Maria Antonia Tigre (Director, Global Climate Litigation) — `mt2876@columbia.edu` (verify)
**Bcc / general:** `manager@climatecasechart.com`
**Subject:** OpenClimateLaw — proposal for AI-native, anti-hallucination access to the Climate Litigation Database

> Verify both addresses on the Columbia directory before sending.
> Lead with Michael; Maria Antonia is the substantive litigation contact.

---

Dear Michael, dear Maria Antonia,

I'm writing to introduce **OpenClimateLaw** — a public, free, AI-native research layer over the Sabin Center's Climate Litigation Database — and to propose a deeper collaboration between our projects.

**By way of introduction.** I'm Jonas Hertner, the principal of [regenerative.law](https://regenerative.law), under whose sponsorship this work is being done. I also build and operate [opencaselaw.ch](https://opencaselaw.ch) — a public legal-research platform covering 969,000+ Swiss federal and cantonal decisions, 5,510 federal laws, 15,722 cantonal laws, 1,058 scholarly commentaries, and a 9-million-edge citation graph, all served through a public MCP endpoint at `mcp.opencaselaw.ch` and used by Swiss practitioners and researchers. Both opencaselaw.ch and openclimatelaw.org share a single mission: **to make legally rigorous primary sources first-class citizens in AI-assisted research**, with attribution, provenance, and anti-hallucination guarantees that make the output safe to cite.

The Climate Litigation Database is, in our view, the most editorially careful corpus of climate litigation that exists anywhere. The taxonomy work, the principal-law cross-references, the careful curation of court documents — none of that has an equivalent. So we anchored OpenClimateLaw on it, with explicit attention to handling it the way Sabin would want it handled.

## What's already live

The MCP endpoint — `https://mcp.openclimatelaw.org/mcp` — is live and exposes 9 tools to any MCP-capable agent (Claude, ChatGPT, Gemini, Copilot, Cursor, Continue, Cline, Goose, Zed, plus any client speaking the protocol). The corpus today:

- **5,046 cases** across **67 jurisdictions** — 4,831 from your database (we ingested the entire `family` corpus from `climatecasechart.com`'s `__NEXT_DATA__`) plus 215 from the Climate Rights Database at the University of Zurich for complementary coverage of rights-based litigation
- **41,395 court documents**, of which **24,250** have full extracted text (judgments, briefs, complaints, motions, petitions — sourced directly from `wp-content/uploads` on your domain via PDF download + pymupdf extraction)
- **14,000+ citation edges** between cases (built via Aho-Corasick canonical-title matching across summaries and document text, plus formal-cite extraction)
- **Sentence-transformer embeddings** for every case (384-dim, all-MiniLM-L6-v2) enabling semantic "find related cases" across language and phrasing differences
- **Per-case `principal_law` extraction** projected from your `metadata.concept_preferred_label` payload, **case_number** capture (so citations can include verbatim docket numbers), and **core_object** (your one-sentence holding text)

## The 9 tools — what they do, and what they unlock

The technical contribution is not the data itself — that's yours — but a research layer that makes it **AI-safe**. The tools fall into four groups:

**Discovery** — finding the right case to cite

- `search_cases(query, jurisdiction?, claim_type?, status?, limit)` — hybrid search combining Postgres full-text (×10 weight), `pg_trgm` trigram similarity (catches typos and partial titles), and pgvector cosine on sentence-transformer embeddings (catches "Indigenous communities rising sea levels" → *Pabai Pabai* + *Daniel Billy*). All three signals scored together; results ordered by combined relevance.
- `get_case(case_id_or_sabin_id)` — full record by canonical UUID or Sabin family ID. Returns case_number, core_object, principal_laws (extracted from your concept hierarchy), parties, claim types, documents (with upstream URLs back to `climatecasechart.com`), citation strings, and field-level provenance.

**Graph navigation** — what a case cites and is cited by

- `find_citations(case_id, limit)` — forward edges. Each result tagged with `source_of_edge` so the LLM (and reader) knows whether the link came from formal-cite extraction (ECLI/BVerfGE/BGE/US-reporter regex on text) or from canonical-title matching.
- `find_cited_by(case_id, limit)` — backward edges. *"How often is Urgenda cited by other climate cases?"* → answered concretely.
- `find_related_cases(case_id, jurisdiction?, claim_type?, status?, limit)` — semantic similarity via embedding cosine. Useful when title or claim-type filters miss the conceptual match. Demonstrated to surface cross-language analogues (e.g. Urgenda → Klimaatzaak (Belgium), Shell appeal, Luca Salis (DE)).

**Anti-hallucination contract — the part LLMs don't currently have**

- `cite(case_id, lang, format)` — returns the verbatim `citation_string` for a case in the requested language and format. **The agent is contractually required not to construct a citation from training data** — every citation must come from this tool, against a previously retrieved case. R1 in our R1–R5 ruleset.
- `check_claim_support(quote, source_id, source_kind)` — validates that a quoted string appears verbatim in `case_summary`, `document_text`, or `citation_string`. *Never quote what wasn't retrieved.* (R2)
- `attest_response(draft_text, retrieved_ids)` — scans an LLM's draft response for citation-shaped strings (ECLI, BVerfGE, US reporter, paragraph references) and flags any not present in the retrieved cases' citation strings. **End-to-end attestation that the answer is grounded.**

**Statistics & navigation**

- `get_statistics(scope, group_by)` — structured aggregates over the corpus: case_count / document_count / jurisdiction_count, broken down by jurisdiction / claim_type / year / status / outcome. Usable as a dashboard data layer.

The R1–R5 contract is what makes this different from existing climate-law search tools. Most LLM-driven legal research today produces fluent answers with **fabricated citations** — invented ECLI numbers, made-up paragraph references, paraphrased holdings attributed to the wrong case. A practitioner using such an output in a brief is a malpractice risk. Our endpoint is built so that any LLM connected to it can return a citation-safe answer end-to-end.

## How we access your data — fully transparent

We do not consume any third-party API. Specifically:

- **Source-of-truth:** `www.climatecasechart.com`. We fetch each case detail page (`/document/<slug>`), parse the `family` record from the page's embedded `__NEXT_DATA__`, and download court documents from `wp-content/uploads/` on your domain. We capture `metadata` (case_number, core_object, principal_law refs), `concepts` (full hierarchy), and `events` (timeline) in addition to the structured fields you already expose.
- **Politeness:** identifying `User-Agent` (`OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)`), 1 req/s on case pages, ≤4 concurrent PDF downloads, exponential backoff on 429/5xx. Respects `robots.txt` (allows `/`).
- **Provenance:** every record we serve carries the source URL on `climatecasechart.com` and an explicit attribution to the Sabin Center. Every `get_case` result points users back to your canonical page for the substantive content.
- **No re-licensing:** we redistribute under the same CC-BY 4.0 you publish under, with full attribution preserved.

This is intentionally the same pattern we use for `mcp.opencaselaw.ch` (Swiss legal data): scrape the publisher's published surface, store and serve the canonical record, redistribute as an open artifact with attribution.

## The proposal — three asks

### 1. Bulk export — the friendliest path forward

The case-detail pages give us the structured record + most PDFs, but a periodic bulk export would (a) be friendlier to your infrastructure than per-page scraping, (b) capture fields not surfaced in the rendered page, and (c) give us deterministic provenance ("snapshot dated X, hash Y") instead of "whatever the page returned at retrieval time." Your data-download form at `https://form.jotform.com/252292116187356` looks like the formal channel — could you confirm whether that's the right place to make a "bulk export, ongoing sync" request, or if there's a better contact for an institutional data-sharing arrangement?

### 2. Joint HuggingFace dataset under CC-BY 4.0 (suggestion)

We follow the same pattern at opencaselaw.ch of publishing the canonical corpus as a versioned **HuggingFace dataset** so researchers can `datasets.load_dataset(...)` and rebuild offline without going through any single API. This is the same distribution channel ClimatePolicyRadar uses for the CCLW corpus (`ClimatePolicyRadar/all-document-text-data`).

If you'd be open to it, we'd happily do all the engineering work to publish the Sabin corpus as a joint HF dataset under your existing CC-BY 4.0 terms — Sabin Center as the primary author of the dataset card, OpenClimateLaw as the technical maintainer. The dataset would credit Sabin and your editorial team prominently, ship versioned snapshots tied to the upstream `__NEXT_DATA__` fetches, and bundle structured records with court-document text. Researchers and ML practitioners reach for HF datasets the way casual users reach for `climatecasechart.com`; this is a complementary distribution channel, not a substitute.

We'd only do this with your buy-in. If you'd prefer the data stay only on `climatecasechart.com`, we honor that — we'd still serve via the MCP for AI agents but wouldn't publish the dataset.

### 3. Partnership / co-listing

If you're open to it:

- Add Sabin's logo and a "Powered by Sabin Center for Climate Change Law" credit prominently on `openclimatelaw.org`.
- Coordinate the AI-agent-facing surface so it points users back to `climatecasechart.com` in every result (already the case in `get_case` and in our citation strings; happy to make this even more prominent).
- Contribute back any taxonomy extensions, structural improvements, or data-quality findings we identify during ingestion (we're already noticing a handful — for instance, a half-dozen filing-date typos in the current data, and ~5 "duplicate-family" cases where the same lawsuit appears under multiple slugs).

## Veto rights — fully reversible

If anything in our current ingestion or attribution choices conflicts with your preferences, **we'll change it within hours**. The MCP can be paused or pointed elsewhere immediately. The whole project is open source (MIT) at `github.com/jonashertner/openclimatelaw` — what we're doing is fully transparent and auditable, including the scraper, the exact fields we capture, and the prompts that govern the anti-hallucination contract.

## Proposed next step

A 30-minute video call would let me demo the MCP live (we can ask Claude or ChatGPT to draft a memo on *Held v. Montana* with end-to-end citation attestation in real time), walk through the architecture, and answer any technical or institutional questions you have. If a call is harder to schedule, even a brief reply confirming whether the bulk-export request is reasonable to pursue (and to whom on your team I should send the formal request) would be very helpful.

Either way, I'd be grateful for any guidance on how best to honor the Climate Litigation Database in this work.

Warm regards,

**Jonas Hertner**
Principal, regenerative.law
Builder, opencaselaw.ch & openclimatelaw.org

`jonashertner@protonmail.ch`
https://openclimatelaw.org · https://opencaselaw.ch · https://regenerative.law
https://github.com/jonashertner/openclimatelaw (MIT, open source)

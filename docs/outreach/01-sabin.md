# Outreach — Sabin Center for Climate Change Law

**To:** Michael Burger (Executive Director) — `mb3331@columbia.edu` (verify on Columbia directory before sending)
**Cc:** Maria Antonia Tigre (Director, Global Climate Litigation) — `mt2876@columbia.edu` (verify)
**Bcc:** `manager@climatecasechart.com`
**From:** `jh@jonashertner.com`
**Subject:** OpenClimateLaw — a research-grade, citation-safe AI layer over the Climate Litigation Database

---

Dear Michael, dear Maria Antonia,

I am writing to introduce **OpenClimateLaw** ([openclimatelaw.org](https://openclimatelaw.org)) — a public, free research layer that makes the Sabin Center's Climate Litigation Database accessible to AI systems with verifiable, source-anchored citations — and to propose a deeper collaboration between our projects.

**A brief introduction.** I am Jonas Hertner, principal of [regenerative.law](https://regenerative.law), under whose sponsorship this work is undertaken. I also build and operate [opencaselaw.ch](https://opencaselaw.ch), a public legal-research platform covering 969,000+ Swiss federal and cantonal decisions, 5,510 federal laws, 15,722 cantonal laws, 1,058 scholarly commentaries, and a 9-million-edge citation graph, served as a public MCP endpoint at `mcp.opencaselaw.ch` and used by Swiss practitioners and academics. Both opencaselaw.ch and openclimatelaw.org share a single mission: **to make rigorously sourced primary legal materials usable by AI systems without sacrificing the attribution and verifiability that make them trustworthy in the first place.**

We anchored OpenClimateLaw on the Climate Litigation Database because, in our view, no other corpus of climate litigation comes close to matching it on editorial care: the taxonomy work, the principal-law cross-references, the curation of court documents. A research layer worth building deserves a foundation worth building on.

## What is live today

The MCP endpoint at `https://mcp.openclimatelaw.org/mcp` is live and exposes nine tools to any MCP-capable agent (Claude, ChatGPT, Gemini, Copilot, Cursor, Continue, and any other client speaking the protocol). The corpus today holds **5,046 cases across 67 jurisdictions** — 4,831 from your database, plus 215 from the Climate Rights Database at the University of Zurich for complementary coverage of rights-based claims. Behind those cases sit **41,000+ court documents (24,000+ with full extracted text)**, a citation graph of **14,000+ inter-case edges**, and sentence-transformer embeddings on every case for semantic similarity search.

The nine tools fall into four groups:

- **Discovery.** `search_cases` combines full-text, fuzzy/typo-tolerant trigram, and semantic-embedding signals (so "Indigenous communities rising sea levels" retrieves *Pabai Pabai* and *Daniel Billy*); `get_case` returns the full record by canonical ID or by Sabin ID, including parties, claim types, documents, citation strings, and — newly — the `case_number`, `core_object`, and `principal_laws` projected from your `concept_preferred_label` and metadata payload.
- **Graph navigation.** `find_citations` and `find_cited_by` expose the inter-case citation graph, with each edge tagged by how it was derived (canonical-title match, formal-cite extraction, or structured Sabin source). `find_related_cases` surfaces semantic analogues across language and phrasing differences (e.g. *Urgenda* → *Klimaatzaak*, the Shell appeal, *Luca Salis*).
- **Citation safety.** `cite` returns verbatim citation strings from a previously retrieved case (the agent is contractually required not to construct citations from training data). `check_claim_support` verifies that a quoted string appears verbatim in a retrieved summary, document text, or citation string. `attest_response` scans an LLM's draft answer for citation-shaped strings and flags any that do not appear in the retrieved cases. End-to-end, the contract is that **the AI cannot fabricate a citation, fabricate a quote, or smuggle either past attestation**. This is the technical contribution that distinguishes the project from existing climate-law search tools.
- **Aggregates.** `get_statistics` returns structured counts and groupings (by jurisdiction, claim type, year, status, outcome) for use as a data layer in dashboards or research notebooks.

The practical effect is that a practitioner who asks an AI assistant to draft a memo on, say, *Held v. Montana* gets a memo whose every citation is traceable to your verbatim citation string and whose every quoted passage actually exists in the underlying judgment. We believe this is a precondition for AI-assisted legal research to be safe in practice — and we believe it should be a public good rather than a paid service, which is why OpenClimateLaw is free and unauthenticated.

## How we access your data — fully transparent

We do not consume any third-party API. Specifically, our scraper fetches each case detail page on `www.climatecasechart.com` directly, parses the structured family record from the page, and downloads court documents from `wp-content/uploads/` on your domain. We identify ourselves with a contact-bearing User-Agent (`OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jh@jonashertner.com)`), throttle to roughly one request per second, run no more than four concurrent PDF downloads, and back off exponentially on 429/5xx. Every record we serve carries the source URL on `climatecasechart.com` and an explicit attribution to the Sabin Center; every search result and `get_case` response points users back to the canonical Sabin page for substantive content. We redistribute under the same CC-BY 4.0 license you publish under, with full attribution preserved. The full source code is at `github.com/jonashertner/openclimatelaw` (MIT) — what we are doing is auditable end-to-end.

## The proposal — three asks

**1. Bulk export.** A periodic dump (CSV / JSONL / parquet — whatever format works for you) would be friendlier to your infrastructure than per-page scraping, capture fields not surfaced in the rendered page, and let us stamp records with deterministic provenance. Your data-download form at `https://form.jotform.com/252292116187356` looks like the formal channel — could you confirm whether that is the right place for an institutional "bulk export, ongoing sync" request, or whether someone on your team is the better contact?

**2. Joint HuggingFace dataset under CC-BY 4.0 (suggestion, conditional on your buy-in).** ClimatePolicyRadar publishes the CCLW corpus as `ClimatePolicyRadar/all-document-text-data` and we follow the same pattern at opencaselaw.ch. If you would be open to it, we would happily do all the engineering work to publish the Sabin corpus as a joint HuggingFace dataset under your existing CC-BY 4.0 terms — Sabin Center as the primary author of the dataset card, OpenClimateLaw as the technical maintainer. We would only do this with your buy-in; if you prefer the canonical distribution to remain solely on `climatecasechart.com`, we honor that without question.

**3. Co-listing / partnership.** If you are open to it, we would be honored to credit the Sabin Center prominently on `openclimatelaw.org` (logo, "Powered by Sabin Center for Climate Change Law"), to coordinate further so that the AI-agent-facing surface points users back to `climatecasechart.com` even more visibly than it already does, and to contribute back any taxonomy refinements or data-quality findings we identify during ingestion.

## Veto rights

If anything in our current ingestion or attribution choices does not sit well with you, we will change it within hours. The MCP can be paused or pointed elsewhere immediately, and the project is open source so what we are doing is fully transparent.

## Proposed next step

A 30-minute video call would let me demonstrate the MCP live, walk through the architecture, and answer any questions. If a call is harder to schedule, even a brief reply confirming whether the bulk-export request is reasonable to pursue (and to whom on your team I should send it) would be very helpful.

I would be grateful for any guidance on how best to serve the Climate Litigation Database in this work.

With best regards,

**Jonas Hertner**
Principal, regenerative.law
Builder, opencaselaw.ch & openclimatelaw.org

`jh@jonashertner.com`
[openclimatelaw.org](https://openclimatelaw.org) · [opencaselaw.ch](https://opencaselaw.ch) · [regenerative.law](https://regenerative.law)
[github.com/jonashertner/openclimatelaw](https://github.com/jonashertner/openclimatelaw) (MIT)

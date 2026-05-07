# Outreach — Climate Rights Database / CRRP

**To:** Climate Rights and Remedies Project (CRRP), University of Zurich
   - Verify lead contact via [rwi.uzh.ch](https://www.rwi.uzh.ch/) directory
   - Likely institutional addresses: `info@climaterights.uzh.ch`, `helen.keller@rwi.uzh.ch`

**Cc:** Helen Keller (Principal Investigator) *— verify*
**From:** `jh@jonashertner.com`
**Subject:** A demonstration MCP layer over the Climate Rights Database — for CRRP review

---

Dear Professor Keller and the CRRP team,

I am Jonas Hertner, a lawyer, writing on behalf of [regenerative.law](https://regenerative.law). regenerative.law is the legal pillar of [regenerative.eco](https://regenerative.eco), an impact-investing initiative of a Switzerland-based family office. One of regenerative.eco's principal commitments is the promotion of climate litigation as a tool for accountability and transition — and within that commitment, we treat **accessibility of climate-case information** as a problem worth working on directly: not just funding the litigators, but making the global record of what has been argued and decided as widely and easily reachable as possible, both for human users and for the AI systems they increasingly use to do legal research.

It is in that context that we are writing to you. The **Climate Rights Database** fills a niche that the Sabin Center's general litigation database, comprehensive and excellent though it is, does not pretend to cover with the same depth: the human-rights dimension of climate cases analyzed against specific instruments and rights at stake. That perspective is precisely what makes CRD valuable as a complement, and why we want to integrate it properly rather than superficially.

## A suggestion — and a demonstration for your review

We would like to suggest that the data already published on `climaterightsdatabase.com` could be made **even more widely accessible** by exposing it through what is called a Model Context Protocol (MCP) server: a standardized, well-documented endpoint that AI systems (Claude, ChatGPT, Gemini, Copilot, and others) can connect to natively, and that human users can equally consume through any of those clients. MCP is the emerging standard for letting language models read structured external data with proper attribution and source-anchoring.

To demonstrate concretely what this could look like — and to give you something you can test rather than imagine — **we have taken the liberty of building a working demonstration**, deployed at:

> `https://mcp.openclimatelaw.org/mcp`
> (landing page: [openclimatelaw.org](https://openclimatelaw.org))

The demonstration is explicitly framed as a non-public research preview, not a launched service. We are sharing it with you for review, testing, and feedback — not promoting it externally.

## What the demonstration does

The MCP exposes nine tools to any compatible client. They fall into four groups:

- **Discovery.** `search_cases` combines full-text, fuzzy/typo-tolerant, and semantic-embedding search across case titles and summaries. `get_case` returns the full record by ID — parties, claim types, documents, citation strings, jurisdiction, and field-level provenance.
- **Graph navigation.** `find_citations` and `find_cited_by` expose the inter-case citation graph, with each edge tagged by how it was derived. `find_related_cases` surfaces semantic analogues across language and phrasing differences.
- **Citation safety.** `cite` returns the verbatim `citation_string` of a previously retrieved case — the agent is contractually required not to construct citations from training data. `check_claim_support` verifies that a quoted string appears verbatim in a retrieved summary, document, or citation. `attest_response` scans an LLM's draft for citation-shaped strings and flags any that are not present in the retrieved cases. End-to-end, the AI cannot fabricate a citation, fabricate a quote, or smuggle either past attestation.
- **Aggregates.** `get_statistics` returns structured counts and groupings (by jurisdiction, claim type, year, status, outcome).

The corpus today holds 5,046 cases across 67 jurisdictions — 4,831 from the Sabin Center's Climate Litigation Database (full metadata + summaries + court-document text) and **215 from your Climate Rights Database** — with sentence-transformer embeddings on every case for semantic similarity search.

## How the demonstration currently treats your data

This is the part we most want your guidance on. **Our current CRD ingestion is metadata-only and respectful of your unstated licence posture.** Concretely:

- We currently consume CRD via your WordPress REST API (`/wp-json/wp/v2/posts`).
- We capture title (decoded from `title.rendered`), jurisdiction (classified from your `categories` taxonomy), filing year, claim/topic taxonomy, and the upstream URL pointing back to `climaterightsdatabase.com/<slug>`.
- **We do not copy your case summaries** (the `content.rendered` field) into our store. When a user queries our MCP for a CRD-sourced case, the `summary` field returns a redirect message: *"Source: Climate Rights Database. See https://climaterightsdatabase.com/\<slug\> for the case summary."*
- Every record carries CRD attribution and points users back to your canonical page for substantive content.

This is the defensible posture absent an explicit redistribution licence on your site, and it is the posture we default to: **your prose belongs to you, and we do not copy it without permission.** We made a deliberate choice not to assume licensing terms in the absence of a clear signal.

## What deeper integration would look like with your buy-in

If the CRD content is publishable under CC-BY 4.0 (or another open licence), or if you would grant a specific permission for OpenClimateLaw, the following becomes possible:

- **Full case-summary text** ingested and queryable through `search_cases` (currently the search index for CRD records is limited to titles — adding summaries would substantially improve discoverability for human-rights claims).
- **Cross-corpus semantic similarity.** `find_related_cases` would surface CRD cases as analogues for Sabin-side cases and vice versa, building a unified rights-based and general climate-litigation discovery surface.
- **Citation graph extension.** Our title-matching extractor would surface where CRD cases cite — or are cited by — Sabin-side cases, building a unified graph rather than two disconnected ones.
- **Citation-safety contract for CRD content.** `check_claim_support` could validate that an LLM's quoted text actually appears in your published case summary. Right now this safeguard only operates against Sabin-sourced text; extending it would close a real gap in AI-assisted research on rights-based climate litigation.

## Two questions

**1. What licence governs the CRD content?** If your case summaries are published under CC-BY 4.0 (or CC-BY-NC, CC-BY-SA, etc.), we would happily ingest them with full attribution and proper licence-tag preservation. If you prefer they remain on `climaterightsdatabase.com` and we keep our current redirect-only posture, that is also entirely fine — we would just like to know explicitly so we are not guessing.

**2. Is a bulk export available, or worth building?** A periodic export (CSV / JSON / SQLite — whatever format works for you) would let us preserve structured fields not exposed by the default REST endpoint (rights at stake, deciding bodies, state concerned), give us deterministic provenance, and be friendlier to your infrastructure than continuous polling. If a bulk export does not currently exist on your end and producing one would require nontrivial work, **regenerative.law is happy to write the export script and run it under your direction** as part of our sponsorship of this initiative.

## What we propose

If, after testing, you find the approach valuable, we would be honored to do either of the following — in whatever combination the CRRP prefers:

1. **Sponsor this as a free public service** for the climate-rights and broader climate-litigation community. regenerative.law would underwrite the operation — infrastructure, data refresh, ongoing maintenance — under your guidance and with full attribution. Governed by an MoU we draft in consultation with you, including takedown rights, attribution requirements, and any constraints on use you wish to impose.

2. **Explore any other collaboration that makes sense to the Project** — co-listing arrangements, support for specific research initiatives, coordination with the Sabin Center's database, or any other shape that serves your mission.

We are deliberately flexible on form. The underlying commitment is to make CRD's editorial work as broadly accessible as possible without compromising the integrity that makes it valuable.

## Veto rights

Because the demonstration currently consumes CRD's REST API at a metadata level, you have full control over what we do with it. If anything in the present ingestion or attribution does not sit well with the CRRP, we will pause, modify, or take it down within hours. The MCP can be turned off entirely at your request — no debate, no negotiation.

## Proposed next step

A brief reply on the two questions above would be very helpful. If a 20-minute video call would be easier, I would be happy to walk through the demonstration and the CRD-specific ingestion code together.

With best regards,

**Jonas Hertner**
Lawyer · regenerative.law (part of [regenerative.eco](https://regenerative.eco))

`jh@jonashertner.com`
[openclimatelaw.org](https://openclimatelaw.org) (research preview) · [opencaselaw.ch](https://opencaselaw.ch) (a related Swiss-law project I also operate)
[github.com/jonashertner/openclimatelaw](https://github.com/jonashertner/openclimatelaw) (MIT, open source)

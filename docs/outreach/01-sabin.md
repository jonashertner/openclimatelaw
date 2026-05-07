# Outreach — Sabin Center for Climate Change Law

**To:** Michael Burger (Executive Director) — `mb3331@columbia.edu` *(verify on Columbia directory before sending)*
**Cc:** Maria Antonia Tigre (Director, Global Climate Litigation) — `mt2876@columbia.edu` *(verify)*
**Bcc:** `manager@climatecasechart.com`
**From:** `jh@jonashertner.com`
**Subject:** A demonstration MCP layer over the Climate Litigation Database — for the Sabin Center's review

---

Dear Michael, dear Maria Antonia,

I am Jonas Hertner, a lawyer, writing on behalf of [regenerative.law](https://regenerative.law). regenerative.law is the legal pillar of [regenerative.eco](https://regenerative.eco), an impact-investing initiative of a Switzerland-based family office. One of regenerative.eco's principal commitments is the promotion of climate litigation as a tool for accountability and transition — and within that commitment, we treat **accessibility of climate-case information** as a problem worth working on directly: not just funding the litigators, but making the global record of what has been argued and decided as widely and easily reachable as possible, both for human users and for the AI systems they increasingly use to do legal research.

It is in that context that we are writing to you. We place great value on the **Climate Litigation Database** — both for its substantive completeness and for the editorial care that distinguishes it from anything else in the field. Within the broader landscape of climate-litigation data, no other corpus comes close to it on taxonomy, principal-law cross-referencing, or curation of court documents. It is, in our view, the indispensable foundation.

## A suggestion — and a demonstration for your review

We would like to suggest that the data already published on `climatecasechart.com` could be made **even more widely accessible** by exposing it through what is called a Model Context Protocol (MCP) server: a standardized, well-documented endpoint that AI systems (Claude, ChatGPT, Gemini, Copilot, Cursor, and others) can connect to natively, and that human users can equally consume through any of those clients. MCP is the emerging standard for letting language models read structured external data with proper attribution and source-anchoring.

To demonstrate concretely what this could look like — and to give you something you can test rather than imagine — **we have taken the liberty of building a working demonstration**, deployed at:

> `https://mcp.openclimatelaw.org/mcp`
> (landing page: [openclimatelaw.org](https://openclimatelaw.org))

The demonstration is explicitly framed as a non-public research preview, not a launched service. We are sharing it with you for review, testing, and feedback — not promoting it externally.

## What the demonstration does

The MCP exposes nine tools to any compatible client. They fall into four groups:

- **Discovery.** `search_cases` combines full-text, fuzzy/typo-tolerant, and semantic-embedding search (so a query like "Indigenous communities rising sea levels" retrieves *Pabai Pabai* and *Daniel Billy*); `get_case` returns a full record including parties, claim types, documents, citation strings, and — projected from your `metadata.concept_preferred_label` payload — the case's `case_number`, `core_object` (one-sentence holding), and `principal_laws`.
- **Graph navigation.** `find_citations` and `find_cited_by` expose the inter-case citation graph (built via canonical-title matching using Aho-Corasick plus formal-cite extraction), with each edge tagged by how it was derived. `find_related_cases` surfaces semantic analogues across language and phrasing differences (e.g. *Urgenda* → *Klimaatzaak*, the Shell appeal, *Luca Salis*).
- **Citation safety.** `cite` returns the verbatim `citation_string` of a previously retrieved case — the agent is contractually required not to construct citations from training data. `check_claim_support` verifies that a quoted string appears verbatim in a retrieved summary, document, or citation. `attest_response` scans an LLM's draft for citation-shaped strings and flags any that are not present in the retrieved cases. End-to-end, the AI cannot fabricate a citation, fabricate a quote, or smuggle either past attestation. We see this as the precondition for AI-assisted legal research to be safe in practice — and the technical contribution that distinguishes the demonstration from existing climate-law search tools.
- **Aggregates.** `get_statistics` returns structured counts and groupings (by jurisdiction, claim type, year, status, outcome).

The corpus today holds 5,046 cases across 67 jurisdictions — 4,831 from your database plus 215 from the Climate Rights Database at the University of Zurich for complementary rights-based coverage — with 41,000+ court documents (24,000+ with full extracted text) and a citation graph of 14,000+ inter-case edges.

The practical effect is that a practitioner who asks an AI assistant to draft a memo on, say, *Held v. Montana* receives a memo whose every citation is traceable to your verbatim citation string and whose every quoted passage actually exists in the underlying judgment.

## How the demonstration accesses your data — fully transparent

The demonstration consumes no third-party API. It fetches each case detail page on `www.climatecasechart.com` directly, parses the structured family record from the page, and downloads court documents only from `wp-content/uploads/` on your domain. Identifying contact-bearing User-Agent, ~one request per second, ≤4 concurrent PDF downloads, exponential back-off on 429/5xx. Every record carries explicit Sabin Center attribution and points users back to your canonical page for substantive content. Redistribution follows the same CC-BY 4.0 licence Sabin publishes the data under. The full source code is open under the MIT licence at [github.com/jonashertner/openclimatelaw](https://github.com/jonashertner/openclimatelaw) — what we are doing is auditable end-to-end.

## How we'd like to help

This is an informal outreach, not a structured proposal. If, after testing, you find this approach useful, we would simply like to support your work in whatever way is most helpful. We would be honored to underwrite the operating costs of an MCP service like this one — infrastructure, data refresh, ongoing maintenance — so it can run as a free resource for the climate-litigation community, under your guidance and with full attribution. We would equally be glad to contribute engineering capacity to anything else that serves your mission: a bulk-export ingestion path that is friendlier to your infrastructure than per-page scraping, a joint HuggingFace dataset under your existing CC-BY 4.0 (along the same lines as `ClimatePolicyRadar/all-document-text-data`), co-listing, or any other form that is useful to you.

We are not attached to any particular shape. The underlying commitment is straightforward: the work the Sabin Center does in this field deserves the broadest possible reach, and we would like to help you achieve that on whatever terms you find appropriate.

## Veto rights

Because the demonstration currently scrapes and indexes data published on `climatecasechart.com`, you have full control over what we do with it. If anything in the present ingestion or attribution does not sit well with the Sabin Center, we will pause, modify, or take it down within hours. The MCP can be turned off entirely at your request — no debate, no negotiation.

## Proposed next step

A 30-minute video call would let me walk through the demonstration live, answer technical and institutional questions, and hear what shape of collaboration — if any — would be useful to the Center. Even a brief reply confirming whether this direction is of interest would be very welcome.

I would be grateful for your guidance on how best to honor the Climate Litigation Database in this work.

With best regards,

**Jonas Hertner**
Lawyer · regenerative.law (part of [regenerative.eco](https://regenerative.eco))

`jh@jonashertner.com`
[openclimatelaw.org](https://openclimatelaw.org) (research preview) · [opencaselaw.ch](https://opencaselaw.ch) (a related Swiss-law project I also operate)
[github.com/jonashertner/openclimatelaw](https://github.com/jonashertner/openclimatelaw) (MIT, open source)

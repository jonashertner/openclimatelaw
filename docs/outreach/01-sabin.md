# Outreach — Sabin Center for Climate Change Law

**To:** Michael Burger (Executive Director) — `mb3331@columbia.edu` (verify)
**Cc:** Maria Antonia Tigre (Director of Global Climate Litigation) — `mt2876@columbia.edu` (verify)
**Subject:** OpenClimateLaw — public MCP server built on the Climate Litigation Database

> Verify recipient addresses on Columbia's directory before sending.
> Sabin's general contact is `manager@climatecasechart.com`.

---

Dear Michael, Maria Antonia,

I'm writing about a project that has just gone live at **https://openclimatelaw.org** — a public, free Model Context Protocol (MCP) server that makes the Sabin Center's Climate Litigation Database queryable by AI agents (Claude, ChatGPT, Gemini, GitHub Copilot, and any MCP-compatible client) with strong anti-hallucination guarantees.

The data is sourced **directly from `www.climatecasechart.com`** under the CC-BY 4.0 licence published on the site. The MCP server holds the full Sabin litigation corpus — case metadata, summaries, and the full text of court documents (decisions, briefs, complaints) hosted in `/wp-content/uploads/` on Sabin's domain. The endpoint is `https://mcp.openclimatelaw.org/mcp`; you can connect any MCP-capable client to it now. Full attribution to the Sabin Center is embedded in every citation string returned.

## What we add

The technical contribution is **server-enforced citation safety** for AI-driven legal research:

- `cite()` returns verbatim citation strings from a retrieved case — LLMs can't fabricate them.
- `check_claim_support()` validates a quotation appears verbatim in `case_summary` / `document_text` / `citation_string`. Now that we've ingested the actual court-document PDFs, this works against real judicial language, not just Sabin's editorial summaries.
- `attest_response()` scans a draft for citation-shaped strings (ECLI, BVerfGE, BGE, US reporter) and flags any not present in retrieved cases.

We anchored on the Sabin database because your editorial standards make it the right foundation: when an LLM cites *Urgenda Foundation v. State of the Netherlands, ECLI:NL:HR:2019:2007*, we want the citation to be your verbatim string, not a model-generated approximation.

## Our access pattern (so it's clear, not assumed)

We do not consume any third-party API. Specifically:

- **Source-of-truth:** `www.climatecasechart.com` itself. We fetch each case detail page (`/document/<slug>`), parse the structured family record from the page's embedded `__NEXT_DATA__`, and download court documents from `wp-content/uploads/` on your domain.
- **Politeness:** identifying `User-Agent` (`OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)`), 1 req/s on case pages, ≤4 concurrent PDF downloads, exponential backoff on 429/5xx. Respects `robots.txt` (which currently allows `/`).
- **Provenance:** every record we serve carries the source URL on `climatecasechart.com` and a CC-BY 4.0 attribution string.
- **Bulk distribution:** we plan to publish the scraped corpus as a versioned HuggingFace dataset (under the same CC-BY 4.0 you publish under), so researchers can `datasets.load_dataset(...)` it directly without going through us, and so the artifact is durable independent of any API or proxy.

This is intentionally the same pattern we use for `mcp.opencaselaw.ch` (Swiss legal data): scrape the publisher's published surface, store + serve the canonical record, redistribute as an open artifact.

## What we'd like to discuss

We'd like to explore a more formal collaboration. Two specific asks:

### 1. Bulk export

The case-detail pages give us the structured record + most PDFs. But there's almost certainly more in your internal pipeline — pre-publication versions, structured fields not exposed in the rendered page, parties separated cleanly, principal-law cross-references — that a **bulk export would surface without requiring us to scrape page-by-page**. The data-download form at `https://form.jotform.com/252292116187356` looks like the formal channel. Is that the right place to make a "bulk export, ongoing sync" request rather than a one-off researcher request?

A periodic dump (CSV / JSONL / parquet, whatever format works for you) would also be friendlier to your infrastructure than our per-page fetching, and would let us stamp records with deterministic provenance (snapshot dated X, hash Y) instead of "whatever the page returned at retrieval time."

### 2. Co-listing / partnership

If you're open to it, we'd love to:

- Add Sabin's logo and a "Powered by Sabin Center" credit prominently on `openclimatelaw.org`.
- Coordinate the AI-agent-facing surface so it complements rather than competes with `climatecasechart.com` — we point users *back* to the canonical Sabin case page in every result.
- Contribute back any taxonomy extensions, structural improvements, or data-quality findings we identify during ingestion (we're already noticing a handful of these).

## Veto rights

If anything in our current ingestion or attribution choices conflicts with your preferences, we'll change them within hours. The MCP can be paused or pointed elsewhere immediately. The whole project is open-source (MIT, github.com/jonashertner/openclimatelaw), so what we're doing is fully transparent and auditable.

## Proposed next step

A 30-minute call would let me demo the MCP live, show usage metrics, walk through the citation-safety tooling, and answer any technical questions. If a call is harder to schedule, even a brief reply confirming whether the bulk-export request is reasonable to pursue (and to whom on your team I should send the formal data-download request) would be helpful.

Best,

**Jonas Hertner**
`jonashertner@protonmail.ch` · https://openclimatelaw.org · https://github.com/jonashertner/openclimatelaw

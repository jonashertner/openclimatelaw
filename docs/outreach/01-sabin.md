# Outreach — Sabin Center for Climate Change Law

**To:** Michael Burger (Executive Director) — `mb3331@columbia.edu` (verify)
**Cc:** Maria Antonia Tigre (Director of Global Climate Litigation) — `mt2876@columbia.edu` (verify)
**Subject:** OpenClimateLaw — public MCP server built on the Climate Litigation Database

> Verify recipient addresses on Columbia's directory before sending.
> Sabin's general contact is `manager@climatecasechart.com`.

---

Dear Michael, Maria Antonia,

I'm writing about a project that has just gone live at **https://openclimatelaw.org** — a public, free Model Context Protocol (MCP) server that makes the Sabin Center's Climate Litigation Database queryable by AI agents (Claude, ChatGPT, Gemini, GitHub Copilot, and any MCP-compatible client) with strong anti-hallucination guarantees.

The database has been ingested under the CC-BY 4.0 licence published on `climatecasechart.com`, via Climate Policy Radar's public families API. As of today the server holds **4,831 cases / 16,931 documents / 65 jurisdictions**. The MCP endpoint is `https://mcp.openclimatelaw.org/mcp`; you can connect any MCP-capable client to it now. Full attribution to the Sabin Center is embedded in every citation string the MCP returns.

## What we add beyond climatecasechart.com

The technical contribution is **server-enforced citation safety**, designed for the moment when LLMs start writing climate-litigation research at scale:

- `cite()` returns verbatim citation strings from a retrieved case — LLMs can't fabricate them.
- `check_claim_support()` validates a quotation appears verbatim in `case_summary` / `document_text` / `citation_string`.
- `attest_response()` scans a draft for citation-shaped strings (ECLI, BVerfGE, BGE, US reporter formats) and flags any not present in retrieved cases.

We anchored on the Sabin database because your editorial standards make it the right foundation: when an LLM cites "*Urgenda Foundation v. State of the Netherlands, ECLI:NL:HR:2019:2007*", we want the citation to be your verbatim string, not a model-generated approximation.

## What we'd love to discuss

We'd like to explore a more formal collaboration. Specifically, we'd be very interested in **a bulk export of the underlying case data** — the kind of dump that the `climatecasechart.com` data-download form points to — so we can run a deeper structural ingest than CPR's API exposes.

**Why bulk export rather than continued API polling:**

1. **Court-document text.** CPR's families API exposes case metadata and Sabin-authored summaries beautifully, but the *underlying judicial documents* (decisions, briefs, complaints) live behind each `documents[].slug` URL. Bulk access to those documents would let us build full-text search and verbatim-quote validation on actual judicial language — which is what climate-litigation researchers actually want from an LLM-driven workflow.

2. **Cleanly separated parties.** The CPR `family` record concatenates parties; bulk export of the underlying records (plaintiff/defendant/intervenor) would let us preserve who-sued-whom structure that case-strategy questions need.

3. **Robust sync.** A daily-diff against a published dump is more resilient and lower-overhead for your infrastructure than our per-page API polling (we politely throttle to 1 req/s, but a bulk option avoids the hot path entirely).

4. **Long-tail metadata.** Per-case structural fields that aren't in the public API today (e.g. case-status enum granularity, principal_law links, full procedural history) would let us populate richer tools.

## What we offer back

- **Co-branding / acknowledgment** as the data centerpiece — already credited prominently on the landing page and in every citation string returned by the MCP. Happy to add Sabin's logo to the apex domain.
- **Open-source code** under MIT at `https://github.com/jonashertner/openclimatelaw`. The anti-hallucination contract layer is fully reusable for any LLM-facing surface you may build.
- **Contribution back** of taxonomy extensions and structural improvements we identify during ingestion. We'll surface jurisdiction-coverage gaps, status-enum drift, etc. to you as PRs.
- **Open data redistribution** under the same CC-BY 4.0 terms you publish under, with attribution preserved.
- **Veto rights:** if any of our current ingestion or attribution choices conflict with your preferences, we'll change them tomorrow. The MCP can be paused or pointed at a different upstream within hours.

## Proposed next step

A 30-minute call would let me demo the MCP live, show usage metrics, walk through the citation-safety tooling, and answer any technical questions. I can also send the same demo as a screencast if a call is harder to schedule.

If a call isn't useful, even a brief reply confirming whether the bulk-export request is reasonable to pursue (and to whom on your team / at CPR I should send the formal data-download request) would be helpful.

Best,

**Jonas Hertner**
`jonashertner@protonmail.ch` · https://openclimatelaw.org · https://github.com/jonashertner/openclimatelaw

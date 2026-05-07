# Outreach — Climate Rights Database / CRRP

**To:** Climate Rights and Remedies Project (CRRP), University of Zurich
   - Verify lead contact via [rwi.uzh.ch](https://www.rwi.uzh.ch/) directory
   - Likely institutional addresses: `info@climaterights.uzh.ch`, `helen.keller@rwi.uzh.ch`
**Cc:** Helen Keller (Principal Investigator) — verify
**From:** `jh@jonashertner.com`
**Subject:** OpenClimateLaw — proposing a license-respecting deeper integration of the Climate Rights Database

---

Dear Professor Keller and the CRRP team,

I am writing to introduce **OpenClimateLaw** ([openclimatelaw.org](https://openclimatelaw.org)) — a public, free research layer over climate-litigation data, with verifiable, source-anchored citations for AI systems — and to propose a license-respecting deepening of how it integrates the Climate Rights Database.

**A brief introduction.** I am Jonas Hertner, principal of [regenerative.law](https://regenerative.law), under whose sponsorship this work is undertaken. I also build and operate [opencaselaw.ch](https://opencaselaw.ch), a public legal-research platform covering 969,000+ Swiss federal and cantonal decisions, 5,510 federal laws, 15,722 cantonal laws, 1,058 scholarly commentaries, and a 9-million-edge citation graph, served as a public MCP endpoint and used by Swiss practitioners and academics. Both opencaselaw.ch and openclimatelaw.org share a single mission: **to make rigorously sourced primary legal materials usable by AI systems without sacrificing the attribution and verifiability that make them trustworthy in the first place.**

CRD's editorial focus on rights-based climate litigation fills a niche that the Sabin Center's database, comprehensive and excellent though it is, does not pretend to cover with the same depth: the human-rights dimension of climate cases analyzed against specific instruments and rights-at-stake. That perspective is precisely what makes CRD valuable as a complement, and why we want to integrate it properly rather than superficially.

## Where things stand today

The MCP endpoint at `https://mcp.openclimatelaw.org/mcp` is live and exposes nine tools to any MCP-capable agent (Claude, ChatGPT, Gemini, Copilot, and others). The corpus today holds **5,046 cases across 67 jurisdictions** — 4,831 from the Sabin Center's Climate Litigation Database and **215 from your Climate Rights Database** — backed by 41,000+ court documents (24,000+ with full extracted text), a 14,000+ edge inter-case citation graph, and sentence-transformer embeddings on every case for semantic similarity search.

Critically, **our current CRD ingestion is metadata-only and respectful of your unstated license posture.** Concretely:

- We currently consume CRD via your WordPress REST API (`/wp-json/wp/v2/posts`).
- We capture title (decoded from `title.rendered`), jurisdiction (classified from your `categories` taxonomy), filing year, claim/topic taxonomy, and the upstream URL pointing back to `climaterightsdatabase.com/<slug>`.
- **We do not copy your case summaries** (the `content.rendered` field) into our store. When a user queries our MCP for a CRD-sourced case, the `summary` field returns a redirect message: *"Source: Climate Rights Database. See https://climaterightsdatabase.com/<slug> for the case summary."*
- Every record carries CRD attribution and points users back to your canonical page for substantive content.

This is the defensible posture absent an explicit redistribution license on your site, and it is the posture we default to: **your prose belongs to you, and we do not copy it without permission**.

## What deeper integration would look like with your buy-in

If the CRD content is publishable under CC-BY 4.0 (or another open license), or if you would grant a specific permission for OpenClimateLaw, the following becomes possible:

- **Full case-summary text** ingested and queryable through `search_cases` (currently the search index for CRD records is limited to titles — adding summaries would substantially improve discoverability for human-rights claims).
- **Cross-corpus semantic similarity.** `find_related_cases` would surface CRD cases as analogues for Sabin-side cases and vice versa, building a unified rights-based and general climate-litigation discovery surface.
- **Citation graph extension.** Our title-matching extractor would surface where CRD cases cite — or are cited by — Sabin-side cases, building a unified graph rather than two disconnected ones.
- **Citation-safety contract for CRD content.** `check_claim_support` could validate that an LLM's quoted text actually appears in your published case summary. Right now this safeguard only operates against Sabin-sourced text; extending it to CRD would close a real gap in AI-assisted research on rights-based climate litigation.

## Two questions

**1. What license governs the CRD content?** If your case summaries are published under CC-BY 4.0 (or CC-BY-NC, CC-BY-SA, etc.), we would happily ingest them with full attribution and proper license-tag preservation. If you prefer they remain on `climaterightsdatabase.com` and we keep our current redirect-only posture, that is also entirely fine — we would just like to know explicitly so we are not guessing.

**2. Is a bulk export available?** If we move beyond metadata-only ingestion, a periodic bulk export (CSV / JSON / SQLite — whatever format works for you) would be more useful than continued REST API polling: it captures structured fields not exposed by the default REST endpoint (rights at stake, deciding bodies, state concerned), gives us deterministic provenance, and is friendlier to your infrastructure than continuous polling. If a bulk export does not currently exist on your end and producing one would require nontrivial work, **I am happy to write the export script myself** against a schema you confirm and run it under your direction.

## What we offer

Source attribution in every record we serve, traffic referral back to your canonical pages, optional co-branding on the apex landing page (`openclimatelaw.org`) alongside the Sabin Center credit, full transparency via the open-source code at `github.com/jonashertner/openclimatelaw` (MIT), and veto rights — if anything in our current ingestion or attribution conflicts with your preferences, we change it immediately. The whole project is auditable end-to-end.

## Proposed next step

A brief reply on the two questions above would be very helpful. If a 20-minute video call would be easier, I am happy to walk through the MCP and the CRD-specific ingestion code together.

With best regards,

**Jonas Hertner**
Principal, regenerative.law
Builder, opencaselaw.ch & openclimatelaw.org

`jh@jonashertner.com`
[openclimatelaw.org](https://openclimatelaw.org) · [opencaselaw.ch](https://opencaselaw.ch) · [regenerative.law](https://regenerative.law)
[github.com/jonashertner/openclimatelaw](https://github.com/jonashertner/openclimatelaw) (MIT)

# Outreach — Climate Rights Database / CRRP

**To:** Climate Rights and Remedies Project (CRRP), University of Zurich
   - General contact form: https://climaterightsdatabase.com/contact
   - Likely institutional addresses: `info@climaterights.uzh.ch`, `helen.keller@rwi.uzh.ch`
**Cc:** Helen Keller (Principal Investigator) — verify on [rwi.uzh.ch](https://www.rwi.uzh.ch/) directory
**Subject:** OpenClimateLaw — proposing a deeper, license-respecting integration of the Climate Rights Database

> CRD is operated by the Climate Rights and Remedies Project at the University of Zurich
> (climaterights.uzh.ch). Helen Keller leads it; verify her current contact via the UZH directory.

---

Dear CRRP team,

I'm writing to introduce **OpenClimateLaw** — a public, free, AI-native research layer over climate-litigation data — and to propose a license-respecting deepening of how it integrates the Climate Rights Database.

**By way of introduction.** I'm Jonas Hertner, the principal of [regenerative.law](https://regenerative.law), under whose sponsorship this work is being done. I also build and operate [opencaselaw.ch](https://opencaselaw.ch) — a public legal-research platform covering 969,000+ Swiss federal and cantonal decisions, 5,510 federal laws, 15,722 cantonal laws, and a 9-million-edge citation graph, served through a public MCP endpoint. Both opencaselaw.ch and openclimatelaw.org share a single mission: **to make legally rigorous primary sources first-class citizens in AI-assisted research**, with attribution, provenance, and anti-hallucination guarantees that make the output safe for practitioners to cite.

CRD's editorial focus on rights-based climate litigation fills a niche the Sabin Center's database — comprehensive and excellent though it is — does not pretend to cover with the same depth: the human-rights dimension of climate cases as analyzed against specific instruments and rights-at-stake. That perspective is precisely what makes CRD valuable as a complement.

## What's already live, and where CRD currently sits in our stack

The MCP endpoint — `https://mcp.openclimatelaw.org/mcp` — is live and exposes 9 tools to any MCP-capable agent (Claude, ChatGPT, Gemini, Copilot, plus any other MCP client). The corpus today:

- **5,046 cases** across **67 jurisdictions** — 4,831 from the Sabin Center's Climate Litigation Database and **215 from your Climate Rights Database**
- **41,395 court documents** (24,250 with full extracted text from PDF judgments, briefs, motions)
- **14,000+ citation edges** between cases (canonical-title matching + formal-cite extraction)
- **Sentence-transformer embeddings** for every case enabling semantic similarity search

**Critically, our current CRD ingestion is metadata-only and respectful of your unstated license posture.** Concretely:

- We currently consume CRD via your WordPress REST API (`/wp-json/wp/v2/posts`).
- We capture: case title (decoded from `title.rendered`), jurisdiction (classified from your `categories` taxonomy), filing year (from year-named categories), claim/topic taxonomy (also from categories), and the upstream URL pointing back to `climaterightsdatabase.com/<slug>`.
- **We do not copy your case summaries** (the `content.rendered` field) into our store.
- When a user queries our MCP for a CRD-sourced case, the `summary` field returns a redirect message: *"Source: Climate Rights Database. See https://climaterightsdatabase.com/<slug> for the case summary."* We point users to your canonical page for the substantive content.
- Every record stores a `citation_string` referencing CRD as the source, and the upstream URL is included in every search result and `get_case` response.

This is the defensible posture absent an explicit redistribution license on your site, and it's the one we'd default to: **your prose belongs to you, and we don't copy it without permission**.

## What "deeper integration" would look like with your buy-in

If the CRD content is publishable under CC-BY 4.0 (or another open license), or if you'd grant a specific permission for OpenClimateLaw, here's what shifts:

- **Full case summary text** ingested and queryable through `search_cases` (currently the search index for CRD records is limited to titles — adding summaries would enormously improve discoverability for human-rights claims).
- **Cross-corpus embedding similarity** — `find_related_cases` would surface CRD cases as analogues for Sabin-side cases and vice versa. Right now this works but is hampered by CRD records being thin.
- **Citation graph extension** — our title-matching extractor would surface where CRD cases cite (or are cited by) Sabin-side cases, building a unified rights-based + general climate litigation graph.
- **Anti-hallucination contract extends to CRD content** — `check_claim_support` could validate that an LLM's quoted text actually appears in your published case summary. Right now this only works against Sabin-sourced text.

## Two questions

### 1. What license governs the CRD content?

If your case summaries are published under CC-BY 4.0 (or CC-BY-NC, CC-BY-SA, etc.), we'd happily ingest them with full attribution and proper license-tag preservation. If you'd prefer they remain on `climaterightsdatabase.com` and we keep our current redirect-only posture, that's also fine — we'd just like to know explicitly so we're not guessing.

### 2. Is a bulk export available?

If we move beyond metadata-only ingestion, **a periodic bulk export** (CSV / JSON / SQLite — whatever format works for you) would be more useful than continued WP REST API polling, for several reasons:

- **Structured fields beyond categories.** Your filtering UI mentions deciding bodies, rights at stake, year ranges, keywords, and state concerned. Some of these likely live in custom fields (ACF, perhaps) that aren't exposed by the default REST API. A bulk dump would let us preserve that structure.
- **Linked documents.** If you maintain links to court decisions or NGO submissions per case, bulk access would let us include them.
- **Versioning + provenance.** A dated snapshot gives us deterministic provenance ("ingested CRD-export-2026-05-07") instead of "whatever the API returned at the time."
- **Lower load on your site.** A monthly export is friendlier to your infrastructure than continuous polling.

## What we offer in return

- **Source attribution** in every record returned by our MCP — already in place. Every search result, every `get_case`, every citation_string credits CRD.
- **Traffic referral** — every result for a CRD-sourced record points users back to your URL for the substantive content. We're a discovery layer, not a substitute.
- **Co-branding** on the apex landing page (`openclimatelaw.org`) — happy to add a "CRD / CRRP, University of Zurich" credit prominently alongside Sabin Center.
- **Open-source code** at `github.com/jonashertner/openclimatelaw` (MIT). The ingestion adapter for CRD is auditable; if anything in it troubles you, we can pause or modify within hours.
- **Engineering capacity** — if a bulk export doesn't currently exist on your end and would require nontrivial work to produce, I'm happy to write the export script (against a schema you confirm) and run it under your direction.
- **Veto rights** — if anything in our current ingestion or attribution conflicts with your preferences, we'll change it immediately.

## Proposed next step

Even a brief reply on the two questions above would be very helpful. If a 20-minute Zoom would be easier, I'm happy to walk through the MCP live and the CRD-specific ingestion code together. The whole project is transparent — the GitHub repository documents exactly what we capture and how we serve it.

Warm regards,

**Jonas Hertner**
Principal, regenerative.law
Builder, opencaselaw.ch & openclimatelaw.org

`jonashertner@protonmail.ch`
https://openclimatelaw.org · https://opencaselaw.ch · https://regenerative.law
https://github.com/jonashertner/openclimatelaw (MIT, open source)

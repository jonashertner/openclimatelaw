# Outreach — Climate Rights Database

**To:** CRD maintainers — find on https://climaterightsdatabase.com/contact (or `info@climaterights.uzh.ch`)
**Subject:** OpenClimateLaw — please advise on data licensing + bulk export

> CRD is run by the Climate Rights and Remedies Project (CRRP) at the University of Zurich
> (climaterights.uzh.ch). Lead investigators are Helen Keller and the CRRP team.

---

Dear CRD team,

I run a public MCP server at **https://openclimatelaw.org** that makes climate litigation data accessible to AI agents (Claude, ChatGPT, Gemini, etc.) with anti-hallucination safeguards. The Sabin Center's database is the centerpiece (under CC-BY 4.0). We'd love to include yours more deeply, but want to honor your work properly first.

## Where things stand right now

We currently ingest CRD via your WordPress REST API (`/wp-json/wp/v2/posts`), but only at a **metadata level**:

- Case title (decoded from `title.rendered`)
- Jurisdiction (classified from your `categories` taxonomy)
- Filing year (from year-named categories)
- Claim/topic taxonomy (also from categories)
- Upstream URL pointing back to `climaterightsdatabase.com/<slug>`

Critically, **we do not copy your case summaries** (the `content.rendered` field) into our store. When a user queries our MCP for a CRD case, the `summary` field returns a redirect message: *"Source: Climate Rights Database. See https://climaterightsdatabase.com/… for the case summary."* This is the defensible posture absent an explicit redistribution licence on your site, and it's the right one — your prose belongs to you and we don't want to copy it without permission.

The current ingest covers all 215 cases. Every record stores a `citation_string` referencing CRD as the source.

## Two questions

### 1. What licence governs the CRD content?

If your case summaries are published under CC-BY (or another open licence), we'd happily ingest them with full attribution. If you'd prefer they remain on `climaterightsdatabase.com` and we keep our current redirect posture, that's also fine — just let us know explicitly.

### 2. Is a bulk export available?

If we move beyond metadata-only ingestion, **a periodic bulk export** (CSV / JSON / SQLite, whatever format works for you) would be more useful than continued WP REST API polling, for several reasons:

- **Structured fields beyond categories.** Your filtering UI mentions deciding bodies, rights at stake, year ranges, keywords, and state concerned. Some of these may live in custom fields not exposed by the default REST API. A bulk dump would let us preserve that structure.
- **Linked documents.** If you maintain links to court decisions or NGO submissions per case, bulk access would let us include them.
- **Versioning + provenance.** A dated snapshot gives us deterministic provenance ("ingested CRD-export-2026-05-07") instead of "whatever the API returned at the time".
- **Lower load on your site.** A monthly export is friendlier to your infrastructure than continuous polling.

## What we offer

- **Source attribution** in every record returned by our MCP (already in place).
- **Traffic referral** — every `get_case` for a CRD-sourced record points users back to your URL for the substantive content. We're a discovery layer, not a substitute.
- **Co-branding** on the apex landing page (`openclimatelaw.org`) — happy to add a CRD/CRRP credit prominently.
- **Open-source code** at `github.com/jonashertner/openclimatelaw` (MIT). The ingestion adapter for CRD lives at `ingest/satellites/climate_rights.py` if you'd like to review what we're consuming.
- **Veto rights.** If anything in our current ingestion troubles you, we can pause or modify within hours.

## Proposed next step

Even a brief reply on these two questions would be very helpful. If a call is easier, I'm happy to walk through the MCP and the CRD-specific ingestion code on a 20-minute Zoom.

Best,

**Jonas Hertner**
`jonashertner@protonmail.ch` · https://openclimatelaw.org · https://github.com/jonashertner/openclimatelaw

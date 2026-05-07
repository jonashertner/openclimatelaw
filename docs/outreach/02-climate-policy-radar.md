# Outreach — Climate Policy Radar

**To:** CPR technical leadership — `info@climatepolicyradar.org` (or `tech@`?)
**Subject:** OpenClimateLaw — third-party MCP built on the CPR families API

> Best CPR contact may be the address listed on https://www.climatepolicyradar.org/contact.
> Their GitHub org is https://github.com/climatepolicyradar — could open an issue on
> `navigator-backend` as an alternative discovery channel.

---

Hi CPR team,

Heads-up — I've just deployed a public MCP server at **https://openclimatelaw.org** that ingests the Sabin litigation corpus through your families API:

```
GET https://api.climatepolicyradar.org/families/?corpus.import_id=Academic.corpus.Litigation.n0000
```

The full 4,830-case corpus is served via MCP at `https://mcp.openclimatelaw.org/mcp`, with CC-BY 4.0 attribution to Sabin embedded in every citation string returned. The server is open-source (MIT, `github.com/jonashertner/openclimatelaw`), uses an identifying User-Agent (`OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)`), and throttles to 1 req/sec on your endpoints.

## Two things I'd appreciate input on

### 1. Posture check

Is this kind of API consumption + redistribution-via-MCP within the scope you intend the families endpoint to support? My reading of the CC-BY 4.0 terms on `app.climatepolicyradar.org/terms-of-use` is that this is fine — but I'd like explicit confirmation rather than assumption. If our current implementation conflicts with CPR's intent, we'll adjust within hours.

### 2. Bulk export

**Is there a published bulk dump of the litigation corpus** (or the broader CPR Database) we could pull from instead of paginated API calls?

A daily or weekly snapshot would:

- **Reduce load on your API** — no per-page polling hot path. The current ingest takes 49 page requests; a single bulk pull would replace that entirely.
- **Improve our reliability** — independent of your API uptime/SLA.
- **Give us deeper structural access** — if your dump format includes per-document text or richer metadata than the families endpoint exposes, we'd love to ingest that too. (E.g., full text of judicial documents linked from each `documents[].slug`, properly separated plaintiffs/defendants, principal_law cross-references.)
- **Simplify version tracking** — a snapshot stamped with a date and hash gives us deterministic provenance instead of "whatever the API returned at retrieval time".

I see your `cparchive` repo takes monthly screenshots, and `gcf-data-mapper` works with structured climate data. Is there an analogous published export for the Sabin litigation corpus, or for CPR's full database? If not, would it be useful for you if we contributed tooling to publish one?

## What we built (quick context)

The MCP server enforces three anti-hallucination rules around your data:

- `cite(case_id, lang, format)` — verbatim citation_string lookup. R1.
- `check_claim_support(quote, source_id, source_kind)` — verbatim-substring validation. R2.
- `attest_response(draft_text, retrieved_ids)` — scans for citation-shaped strings (ECLI, BVerfGE, BGE, US reporter) and flags any not in retrieved cases. R1 enforcement.

The point is to make LLM-driven climate research safe — citations come from your data layer or they don't exist. Happy to share traffic metrics, ingestion code, or talk technical specifics about how we're consuming the API.

Open to a quick call or async via email/GitHub. If your preferred contact channel is different from this one, point me at it.

Best,

**Jonas Hertner**
`jonashertner@protonmail.ch` · https://openclimatelaw.org · https://github.com/jonashertner/openclimatelaw

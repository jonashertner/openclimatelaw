# Leave-behind — send within ~24h of the call

> Send as the email body (or a one-page PDF). **Adapt the first line** to what actually resonated on
> the call, and trim any "guidance" item they reacted coolly to. Keep it to one page — it exists so
> Mike / Maria / Michal can forward it internally without re-explaining.

---

**Subject:** OpenClimateLaw — recap, what we're offering, and how you'd steer it

Dear Maria, Mike, and Margaret — and Michal, Kyra, and Dominyka,

Thank you for the time today. As promised, a short recap of what we showed and what we're proposing —
something you can share with colleagues. **Nothing here moves without your say-so.**

**What it is.** A non-public research demonstration of a *citation-safe* Model Context Protocol (MCP)
layer over your data — so any AI assistant (Claude, ChatGPT, Gemini, Copilot, …) can search, read, and
quote climate cases and laws **without fabricating citations or holdings.** It now spans both corpora:
the Sabin Climate Litigation Database (litigation) and CPR's Climate Change Laws of the World
(legislation), with every reference traceable to your verbatim citation and every quote verified
against the underlying text.

- Preview: `https://mcp.openclimatelaw.org/mcp` · landing: `https://openclimatelaw.org` ·
  source (MIT, auditable): `github.com/jonashertner/openclimatelaw`

**What we're offering.** This is purely nonprofit — we are not monetising anything.
- We would **underwrite the running costs** — infrastructure, data refresh, maintenance — so it runs
  as a **free resource for the climate-litigation community, under your guidance, with full
  attribution.**
- We'd gladly contribute **engineering capacity** wherever it helps your mission: a **bulk-export
  ingestion path** friendlier to your infrastructure than per-page fetching; a **HuggingFace dataset
  under your CC-BY 4.0** (the shape of CPR's `all-document-text-data`); co-listing; or anything else.

**Your control — the terms.**
- It is **your data.** Every record is attributed to you and links back to your canonical page; we
  redistribute under the same **CC-BY 4.0** licence you apply.
- The code is **open-source (MIT) and auditable end to end.**
- **You hold the veto.** If you want it changed or switched off, it's done — no debate, no
  negotiation. It remains a non-public preview unless and until you are comfortable otherwise.

**One honest note for the CPR team.** To show how litigation connects to legislation, we also indexed
your open CCLW corpus — under exactly the same terms (attribution, your control, your veto). We'd
value your guidance on it as much as Sabin's on the litigation side.

**Where your guidance would help most** (collaboration, not conditions):
- An **official data feed** (API or bulk export) so we ingest from the source rather than mirror it —
  the path to freshness, and gentler on your infrastructure.
- The **international / advisory-opinion stream** — the ICJ opinion is already in the corpus; we'd
  welcome your steer on surfacing it well and on adding the ITLOS and latest IACtHR opinions.
- (CPR) Your **case ↔ law concept mapping**, which would make the litigation-to-legislation links
  comprehensive, plus adopting your `import_id` as our deduplication key.

**The only thing we're asking** is your reaction and, if useful to you, approval-in-principle to make
your data reachable this way. Everything else follows your lead — including doing nothing, if that is
your preference.

With gratitude for the work you do, and for considering this.

Warm regards,
Jonas

*Jonas Hertner, Attorney · jh@jonashertner.com · +41 43 215 08 50 · on behalf of regenerative.law*

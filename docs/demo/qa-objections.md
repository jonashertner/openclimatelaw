# Q&A / objection-handling — Sabin + CPR call

> **The reflex that answers almost anything hard:** *"It's your data, fully attributed, open-source,
> and you hold the veto — the worst case is you tell us to stop, and we stop."* For every question:
> lead with the genuine strength, name the limit **honestly**, land on their control. This audience
> can check everything — **never overclaim.** Under-promising earns the second call.

## Intent & legitimacy

**"Is this commercial? What's the catch?"**
Purely nonprofit. regenerative.law is the legal arm of an impact initiative; we already fund climate
litigation, and making the record reachable is part of that mission. No product, no fee, no upsell —
we'd *underwrite* the cost, not charge for it.

**"What do you actually get out of this?"**
Reach for the work you do. Our return is mission impact, not revenue. If it amplifies your databases
and helps the field, that's the entire point.

**"Why did you build and index this before asking us?"**
Two honest reasons. Your data is published under CC-BY 4.0, so a demonstration is within the licence —
and, more importantly, we wanted to give you something to *test* rather than a deck to imagine. It's
deliberately non-public, and we're asking now, before anything goes further. If the answer is no,
it's off.

## Positioning — "does this compete with us?"

**"Isn't this a replacement for climatecasechart.com / our own search?"**
The opposite. Every record links *back* to your canonical page — the substantive home stays yours.
This is the access layer for the AI tools people already use: it sends them *to* you with attribution,
instead of *around* you with hallucinations.

**(CPR) "Are you competing with CCLW or our products?"**
No — we'd rather consume your feed and co-list with you. You own the data and the relationship; we're
plumbing. The litigation↔legislation bridge actually makes *your* corpus visible to a new audience.

**"How is this different from just putting our data in a RAG chatbot?"**
The difference is the *contract*, not the retrieval. Ordinary RAG still lets the model paraphrase,
mis-cite, and invent a pinpoint. Here the model is *structurally* prevented from citing or quoting
anything not in your data, and made to refuse rather than guess. Retrieval is common; the
no-fabrication guarantee is the point.

## Accuracy & liability (Sabin's core concern)

**"What if the AI gets a case wrong? Our name is attached."**
That is the exact problem this prevents. The AI **cannot cite a case that isn't in your data, cannot
quote a passage that isn't in the judgment, and refuses to guess** instead of inventing — and because
it's open-source, you can verify that guarantee rather than take our word. It makes AI *safer* over
your data than the status quo, where models answer from memory and fabricate.

**"But it isn't perfect — what about errors?"**
Correct, and we won't pretend otherwise. We can't make the underlying records more accurate than they
are; what we guarantee is *traceability* — every citation and quote points back to your verbatim
source, so a human can check it in seconds. Where we *derive* anything, we label it as derived and you
can have us drop it.

**"You're labelling case outcomes — are you putting words in our mouth?"**
No, and this matters. Outcomes and parties are marked as **our** derivation — the record shows
`source: llm`, the model, and a verbatim supporting quote — never as yours. They're confidence-gated
(blank rather than a guess), and you can have the field removed entirely. It aids discovery, flagged
honestly.

**"How current is it?"**
Today's snapshot is dated, and we show the as-of date in the tool itself. That's precisely why we'd
value an official feed — freshness is a data-access question, and you'd control the cadence.

## Data access, scraping & licensing

**"Is your scraping a burden on our servers?"**
We're careful — we identify ourselves, throttle to ~one request/second, cap concurrent downloads, and
back off on any error. But we'd genuinely prefer not to scrape at all: a bulk export or small API is
gentler on your infrastructure and fresher for users. That's one of the things we're offering to build.

**"What about licensing and attribution?"**
We redistribute under the same CC-BY 4.0 you apply, attribute Sabin (and CPR for legislation) on every
record, and link back to your pages. Climate Rights Database material is metadata-only with redirects.
The code is MIT and public.

## Coverage & data quality (esp. Maria)

**"Do you have the ICJ / ITLOS / IACtHR advisory opinions?"**
The ICJ advisory opinion is in the corpus, with its documents — though it's filed under "Request for
an advisory opinion," so it doesn't surface as cleanly as it should, which we'd fix. The ITLOS opinion
and the latest IACtHR OC are thin in what we mirrored. The international / advisory-opinion stream is
where your guidance would be most valuable — it's your area, and the field's most-cited recent work.

**"You found issues in our data?"**
Only in the spirit of a careful steward — we kept a short list as we ingested and we'll hand it over.
It's a sign we're reading your data closely, not a critique.

## Sustainability & control

**"What if you lose interest or the funding stops?"**
You're never dependent on us. It's open-source — you can run it, hand it on, or we hand it off
cleanly. We'd commit to underwriting it as a stable free resource; the aim is durability, not a demo
that vanishes.

**"Can people misuse it — scrape everything through you?"**
It's public CC-BY data, served read-only, with attribution preserved and your canonical links intact —
nothing private, nothing you haven't already published. And if any use ever concerns you, the veto
covers it.

## Technical (CPR may probe — answer plainly, don't oversell)

**"How do you dedup / build the citation graph / do semantic search?"**
Honestly: dedup is by family IDs where we have them — which is why we'd adopt your `import_id`. The
citation graph is heuristic and thin for flagship cases today — not a feature we'd lean on.
Discovery-level semantic search works well; pinpoint-within-a-judgment is strong for English-language
US cases and weaker elsewhere until we finish embedding the corpus. We're not overselling any of it.

**"Why MCP — is this a passing fad?"**
MCP is the emerging open standard for how AI assistants read external data, supported across the major
providers. Being the trusted, attributed source as that scales is exactly what protects your data's
integrity in the AI era.

## The reset line (if a question turns adversarial)

*"I hear the concern, and the honest answer is simple: this only continues on terms you're comfortable
with. It's your data, it's attributed, it's open-source, and you can switch it off tomorrow. We're not
here to take anything — we're here to amplify your work, and only if you want us to."*

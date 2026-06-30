# pyright: basic
"""OpenAI ChatGPT connector compatibility — the `search` and `fetch` tools.

ChatGPT's custom MCP connectors (deep research / company knowledge) require exactly two
read-only tools with a fixed shape: `search(query)` -> {results:[{id,title,url}]} and
`fetch(id)` -> {id,title,text,url,metadata}. These wrap the native tools so OpenClimateLaw
works as a ChatGPT connector across the WHOLE corpus — litigation *and* legislation — and
returns rich, citable text. Every other client uses the richer native tools directly.
See https://developers.openai.com/api/docs/mcp
"""

import re
from typing import Any

from server.tools.cases import get_case
from server.tools.search import search_cases
from server.tools.statutes import get_statute, search_statutes

_URL_RE = re.compile(r"https?://[^\s)\]]+")
_FALLBACK_URL = "https://climatecasechart.com/"
_CCLW_URL = "https://climate-laws.org/"  # CCLW laws carry no per-law source URL
_CASE_TEXT_CAP = 8000
_STATUTE_TEXT_CAP = 6000


def _source_url(citation_text: str | None) -> str:
    """Pull the upstream source URL out of a citation_string, else the corpus home."""
    if citation_text:
        m = _URL_RE.search(citation_text)
        if m:
            return m.group(0).rstrip(".,);")
    return _FALLBACK_URL


def _is_statute_id(id: str) -> bool:
    return bool(id) and id.upper().startswith("CCLW")


def _case_text(g: dict[str, Any]) -> str:
    """A self-contained, citable brief: structured header + the verbatim summary."""
    parts: list[str] = [g.get("canonical_title") or ""]
    meta = [
        f"{label}: {g[key]}"
        for label, key in (
            ("Court", "court_id"),
            ("Jurisdiction", "jurisdiction_code"),
            ("Filed", "filing_date"),
            ("Decided", "decision_date"),
            ("Status", "status_code"),
        )
        if g.get(key)
    ]
    if meta:
        parts.append(" · ".join(meta))
    parties = g.get("parties") or []
    if parties:
        by_side: dict[str, list[str]] = {}
        for p in parties:
            by_side.setdefault(p.get("side") or "party", []).append(p.get("name") or "")
        parts.append(
            "Parties — "
            + "; ".join(f"{s}: {', '.join(n for n in names if n)}" for s, names in by_side.items())
        )
    if g.get("outcome_code"):
        parts.append(f"Outcome (derived by OpenClimateLaw): {g['outcome_code']}")
    cites = g.get("citation_strings") or []
    if cites:
        parts.append("Citation: " + cites[0].get("text", ""))
    if g.get("core_object"):
        parts.append("Issue / holding: " + g["core_object"])
    laws = [s.get("short_title") for s in (g.get("linked_statutes") or []) if s.get("short_title")]
    if laws:
        parts.append("Laws invoked: " + "; ".join(laws))
    summary = g.get("summary") or ""
    if summary:
        parts.append("\nSummary:\n" + summary[:_CASE_TEXT_CAP])
    return "\n".join(p for p in parts if p)


async def search(query: str) -> dict[str, Any]:
    """Search the climate corpus — cases and laws — returning id/title/url (ChatGPT contract)."""
    q = (query or "").strip()
    if not q:
        return {"results": []}
    results: list[dict[str, Any]] = []
    try:
        cases = await search_cases(query=q, limit=8)
        for r in cases.get("results", []):
            results.append(
                {
                    "id": r.get("sabin_id") or r.get("id"),
                    "title": r.get("canonical_title"),
                    "url": _source_url(r.get("citation_string")),
                }
            )
    except Exception:
        pass
    try:
        laws = await search_statutes(query=q, limit=4)
        for r in laws.get("results", []):
            jur = r.get("jurisdiction_code")
            title = r.get("short_title") or "Untitled law"
            results.append(
                {
                    "id": r.get("cclw_id") or r.get("id"),
                    "title": f"{title} (law, {jur})" if jur else f"{title} (law)",
                    "url": _CCLW_URL,
                }
            )
    except Exception:
        pass
    return {"results": results}


async def _fetch_statute(id: str) -> dict[str, Any]:
    s = await get_statute(id, max_chars=_STATUTE_TEXT_CAP)
    if s is None:
        return {"id": id, "title": "Not found", "text": "", "url": _CCLW_URL, "metadata": {}}
    title = s.get("short_title") or s.get("long_title") or id
    header = [title]
    if s.get("long_title") and s.get("long_title") != title:
        header.append(s["long_title"])
    meta_line = " · ".join(
        f"{k}: {s[v]}"
        for k, v in (
            ("Jurisdiction", "jurisdiction_code"),
            ("Enacted", "enacted_date"),
            ("Status", "status"),
        )
        if s.get(v)
    )
    if meta_line:
        header.append(meta_line)
    text = "\n".join(header) + ("\n\n" + s["text"] if s.get("text") else "")
    return {
        "id": s.get("cclw_id") or id,
        "title": title,
        "text": text,
        "url": _CCLW_URL,
        "metadata": {
            "type": "legislation",
            "jurisdiction": s.get("jurisdiction_code"),
            "enacted_date": s.get("enacted_date"),
            "status": s.get("status"),
            "total_chars": s.get("total_chars"),
        },
    }


async def _fetch_case(id: str) -> dict[str, Any]:
    case = await get_case(id, include_documents=False)
    if case is None:
        return {"id": id, "title": "Not found", "text": "", "url": _FALLBACK_URL, "metadata": {}}
    cites = case.get("citation_strings") or []
    cite_text = cites[0]["text"] if cites else None
    return {
        "id": case.get("sabin_id") or id,
        "title": case.get("canonical_title") or id,
        "text": _case_text(case) or (case.get("summary") or ""),
        "url": _source_url(cite_text),
        "metadata": {
            "type": "litigation",
            "jurisdiction": case.get("jurisdiction_code"),
            "court": case.get("court_id"),
            "status": case.get("status_code"),
            "outcome": case.get("outcome_code"),
            "decision_date": case.get("decision_date"),
            "citation": cite_text,
        },
    }


async def fetch(id: str) -> dict[str, Any]:
    """Fetch a case or law by an id from search (ChatGPT contract): id/title/text/url/metadata."""
    if _is_statute_id(id):
        return await _fetch_statute(id)
    return await _fetch_case(id)

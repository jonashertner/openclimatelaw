# pyright: basic
"""OpenAI ChatGPT connector compatibility — the `search` and `fetch` tools.

ChatGPT's custom MCP connectors (deep research / company knowledge) require exactly two
read-only tools with a fixed shape: `search(query)` returning `{results:[{id,title,url}]}`
and `fetch(id)` returning `{id,title,text,url,metadata}`. These thin wrappers over
search_cases + get_case make OpenClimateLaw work as a ChatGPT connector out of the box;
every other client uses the richer native tools. See https://developers.openai.com/api/docs/mcp
"""

import re
from typing import Any

from server.tools.cases import get_case
from server.tools.search import search_cases

_URL_RE = re.compile(r"https?://[^\s)\]]+")
_FALLBACK_URL = "https://climatecasechart.com/"


def _source_url(citation_text: str | None) -> str:
    """Pull the upstream source URL out of a citation_string, else the corpus home."""
    if citation_text:
        m = _URL_RE.search(citation_text)
        if m:
            return m.group(0).rstrip(".,);")
    return _FALLBACK_URL


async def search(query: str) -> dict[str, Any]:
    """Search the climate-litigation corpus; returns id/title/url per match (ChatGPT contract)."""
    res = await search_cases(query=query, limit=10)
    results = [
        {
            "id": r.get("sabin_id") or r.get("id"),
            "title": r.get("canonical_title"),
            "url": _source_url(r.get("citation_string")),
        }
        for r in res.get("results", [])
    ]
    return {"results": results}


async def fetch(id: str) -> dict[str, Any]:
    """Fetch one case's record (summary + metadata) by id from search (ChatGPT contract)."""
    case = await get_case(id, include_documents=False)
    if case is None:
        return {"id": id, "title": "Not found", "text": "", "url": _FALLBACK_URL, "metadata": {}}
    cites = case.get("citation_strings") or []
    cite_text = cites[0]["text"] if cites else None
    summary = case.get("summary") or case.get("core_object") or ""
    return {
        "id": case.get("sabin_id") or id,
        "title": case.get("canonical_title") or id,
        "text": summary,
        "url": _source_url(cite_text),
        "metadata": {
            "jurisdiction": case.get("jurisdiction_code"),
            "status": case.get("status_code"),
            "outcome": case.get("outcome_code"),
            "decision_date": case.get("decision_date"),
            "citation": cite_text,
        },
    }

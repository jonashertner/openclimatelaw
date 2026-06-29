# pyright: basic
"""Semantic grounding judge — the layer the deterministic attest rails cannot do safely.

attest_response catches fabricated citation *strings* and *quotes* with regexes. It
cannot catch a fabricated case NAME ("In Smith v. United Kingdom (2019)...") or a
fabricated HOLDING about a real instrument ("the UK Supreme Court struck down the CCA
2008 in 2019") — a purely heuristic rail for that was tried and rejected (false
positives). This tool uses Claude (claude-sonnet-4-6) to check the draft's case
references / holdings / specific facts against the ONLY authorized sources (the
retrieved case summaries + citations) and report what is unsupported.

ADVISORY + SAFE BY DEFAULT: if no Anthropic key is configured it returns
{available: false} and does nothing — so it ships dormant and is activated by setting
ANTHROPIC_API_KEY in the server environment (use a freshly-rotated key).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

MODEL = "claude-sonnet-4-6"

_TOOL: Any = {
    "name": "report_grounding",
    "description": "Report assertions in the draft that the provided sources do NOT support.",
    "input_schema": {
        "type": "object",
        "properties": {
            "unsupported_claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {
                            "type": "string",
                            "description": "the assertion, quoted from the draft",
                        },
                        "issue": {
                            "type": "string",
                            "enum": [
                                "case_not_in_sources",
                                "holding_not_supported",
                                "fact_not_supported",
                                "misattributed",
                            ],
                        },
                        "explanation": {"type": "string"},
                    },
                    "required": ["claim", "issue", "explanation"],
                },
            }
        },
        "required": ["unsupported_claims"],
    },
}

_PROMPT = (
    "You are a citation-safety auditor for climate-litigation legal writing. You are given a "
    "DRAFT and the ONLY authorized SOURCES (retrieved case summaries + their verbatim "
    "citations). Flag every assertion in the draft that the sources do NOT support:\n"
    "- a case referenced by name/citation not among the sources (case_not_in_sources);\n"
    "- a holding/outcome attributed to a source case the summary does not state "
    "(holding_not_supported);\n"
    "- a specific fact — date, number, party, remedy — not in the sources (fact_not_supported);\n"
    "- a real source case with a claim misattributed to it (misattributed).\n"
    "Do NOT flag general legal background, hedged statements, or claims the sources DO "
    "support. If everything is supported, return an empty list. Quote each offending claim "
    "verbatim from the draft.\n\n"
)


def _key() -> str | None:
    tok = os.environ.get("ANTHROPIC_API_KEY")
    if not tok:
        p = Path(os.path.expanduser("~/.anthropic_key"))
        if p.exists():
            tok = p.read_text().strip()
    return tok or None


async def _load_sources(retrieved_ids: list[str]) -> list[str]:
    from server.db import get_pool

    if not retrieved_ids:
        return []
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT c.canonical_title, c.summary, "
            "(SELECT string_agg(cs.text, ' | ') FROM citation_string cs WHERE cs.case_id = c.id) "
            "FROM case_record c WHERE c.id::text = ANY(%s) OR c.sabin_id = ANY(%s)",
            (retrieved_ids, retrieved_ids),
        )
        rows = await cur.fetchall()
    return [
        f"CASE: {title}\nCITATIONS: {cites or '(none)'}\n"
        f"SUMMARY: {(summary or '(no summary)')[:6000]}"
        for title, summary, cites in rows
    ]


async def verify_grounding(draft_text: str, retrieved_ids: list[str]) -> dict[str, Any]:
    """Semantically check draft claims against retrieved sources; flag unsupported ones.

    Returns {available, supported, unsupported_claims, model}. available=false (a no-op)
    when no Anthropic key is configured.
    """
    key = _key()
    if not key:
        return {
            "available": False,
            "supported": None,
            "unsupported_claims": [],
            "note": "grounding judge disabled — set ANTHROPIC_API_KEY in the server env to enable",
        }
    sources = await _load_sources(retrieved_ids)
    sources_text = "\n\n---\n\n".join(sources) if sources else "(no sources were provided)"

    import anthropic

    client = anthropic.Anthropic(api_key=key)

    def _call() -> Any:
        return client.messages.create(
            model=MODEL,
            max_tokens=1500,
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "report_grounding"},
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT
                    + "SOURCES:\n"
                    + sources_text
                    + "\n\nDRAFT:\n"
                    + draft_text[:8000],
                }
            ],
        )

    try:
        resp = await asyncio.to_thread(_call)
    except Exception as e:
        return {
            "available": True,
            "supported": None,
            "error": repr(e)[:160],
            "unsupported_claims": [],
        }

    claims: list[dict[str, Any]] = []
    for block in resp.content:
        if block.type == "tool_use":
            claims = list(block.input.get("unsupported_claims", []))
    return {
        "available": True,
        "supported": len(claims) == 0,
        "unsupported_claims": claims,
        "model": MODEL,
    }

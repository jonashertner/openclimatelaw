# pyright: basic
"""PROTOTYPE — structured, verifiable doctrinal extraction on landmark cases.

Demonstrates the "doctrinal assistant" idea: turn a case summary into a STRUCTURED record
(disposition · holdings · legal test · legal bases · relief · significance) where every
factual element carries a VERBATIM quote that we then verify against the source. The
interpretive bit (significance) is clearly marked as synthesis. This is "grounded
synthesis" — the model interprets, but each claim is checked, not trusted.

Reads landmark summaries from the live MCP (read-only) and calls claude-sonnet-4-6
locally (~/.anthropic_key). No prod writes, no deploy — a prototype to evaluate.

    uv run python scripts/proto_holdings.py
"""

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client

URL = "https://mcp.openclimatelaw.org/mcp"
MODEL = "claude-sonnet-4-6"

LANDMARKS = [
    "Sabin.family.2823.0",  # Urgenda v. Netherlands
    "Sabin.family.15540.0",  # KlimaSeniorinnen v. Switzerland
    "Sabin.family.21145.0",  # Held v. State (Montana)
    "Sabin.family.637.0",  # Massachusetts v. EPA
    "Sabin.family.8918.0",  # Milieudefensie v. Shell (tricky posture)
]

_FOLD = {0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'", 0x2013: "-", 0x2014: "-"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_FOLD)).strip().lower()


def _verified(quote: str, summary: str) -> bool:
    return bool(quote) and _norm(quote) in _norm(summary)


def _key() -> str:
    p = Path.home() / ".anthropic_key"
    tok = p.read_text().strip() if p.exists() else ""
    if not tok:
        raise SystemExit("no ~/.anthropic_key")
    return tok


_TOOL: Any = {
    "name": "record_doctrine",
    "description": "Record the structured doctrine of a climate case from its summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "disposition": {
                "type": "object",
                "properties": {
                    "outcome": {
                        "type": "string",
                        "enum": [
                            "plaintiff_won",
                            "defendant_won",
                            "mixed",
                            "settled",
                            "na",
                            "unknown",
                        ],
                    },
                    "posture": {
                        "type": "string",
                        "description": "latest stage, e.g. 'Supreme Court, on appeal'",
                    },
                    "quote": {
                        "type": "string",
                        "description": "verbatim phrase from the summary stating the result",
                    },
                },
                "required": ["outcome", "posture", "quote"],
            },
            "holdings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "point": {
                            "type": "string",
                            "description": "a key legal holding, in your words",
                        },
                        "quote": {
                            "type": "string",
                            "description": "a VERBATIM phrase from the summary supporting it",
                        },
                    },
                    "required": ["point", "quote"],
                },
            },
            "legal_test": {
                "type": "object",
                "properties": {"test": {"type": "string"}, "quote": {"type": "string"}},
                "description": "the legal test/standard the court applied, if stated",
            },
            "legal_bases": {
                "type": "array",
                "items": {"type": "string"},
                "description": "the statutes / rights / provisions the decision rests on",
            },
            "relief": {
                "type": "object",
                "properties": {"relief": {"type": "string"}, "quote": {"type": "string"}},
                "description": "what the court ordered, if any",
            },
            "significance": {
                "type": "string",
                "description": "one sentence: doctrinal significance (your synthesis; no quote)",
            },
        },
        "required": ["disposition", "holdings", "legal_bases", "significance"],
    },
}

_PROMPT = (
    "Extract the structured DOCTRINE of this climate-litigation case from its summary.\n"
    "- Classify the LATEST, operative disposition — never an overturned lower-court order; if the "
    "matter is pending on appeal, say so in posture and use outcome 'na' unless the latest ruling "
    "resolved the merits.\n"
    "- holdings: the operative legal holdings (2-4). legal_test: the standard the court applied. "
    "legal_bases: the statutes/rights/provisions relied on. relief: what was ordered.\n"
    "- EVERY 'quote' field MUST be copied VERBATIM from the summary. If you cannot find a verbatim "
    "quote for a field, omit it (except 'significance', which is your one-sentence synthesis).\n\n"
    "SUMMARY:\n"
)


def extract_doctrine(client: Any, summary: str) -> dict[str, Any]:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1800,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_doctrine"},
        messages=[{"role": "user", "content": _PROMPT + summary}],
    )
    for b in resp.content:
        if b.type == "tool_use":
            return dict(b.input)
    return {}


def _mark(quote: str, summary: str) -> str:
    return "\033[32m✓\033[0m" if _verified(quote, summary) else "\033[31m✗ (paraphrase)\033[0m"


def render(title: str, citation: str, d: dict[str, Any], summary: str) -> tuple[str, int, int]:
    checked = 0
    verified = 0
    out = [f"\n{'═' * 78}\n{title}\n  cite: {citation[:96]}"]

    disp = d.get("disposition") or {}
    q = disp.get("quote", "")
    checked += 1
    verified += _verified(q, summary)
    out.append(f"\n  DISPOSITION: {disp.get('outcome')} — {disp.get('posture')}")
    out.append(f'      {_mark(q, summary)} "{q[:110]}"')

    out.append("\n  HOLDINGS:")
    for h in d.get("holdings") or []:
        q = h.get("quote", "")
        checked += 1
        verified += _verified(q, summary)
        out.append(f"    • {h.get('point')}")
        out.append(f'        {_mark(q, summary)} "{q[:110]}"')

    lt = d.get("legal_test") or {}
    if lt.get("test"):
        q = lt.get("quote", "")
        checked += 1
        verified += _verified(q, summary)
        out.append(f"\n  LEGAL TEST: {lt.get('test')}")
        out.append(f'      {_mark(q, summary)} "{q[:110]}"')

    bases = d.get("legal_bases") or []
    out.append(f"\n  LEGAL BASES: {' · '.join(bases)}  \033[2m(model-identified)\033[0m")

    rel = d.get("relief") or {}
    if rel.get("relief"):
        q = rel.get("quote", "")
        checked += 1
        verified += _verified(q, summary)
        out.append(f"\n  RELIEF: {rel.get('relief')}")
        out.append(f'      {_mark(q, summary)} "{q[:110]}"')

    synth = "\033[2m(synthesis — unverified by design)\033[0m"
    out.append(f"\n  SIGNIFICANCE: {d.get('significance')}  {synth}")
    out.append(f"\n  → quote verification: {verified}/{checked} verbatim-grounded")
    return "\n".join(out), checked, verified


async def main() -> int:
    import anthropic

    client = anthropic.Anthropic(api_key=_key())
    tot_c = tot_v = 0
    async with Client(URL) as c:
        for sid in LANDMARKS:
            r = await c.call_tool(
                "get_case", {"case_id_or_sabin_id": sid, "include_documents": False}
            )
            sc = r.structured_content or {}
            case = sc.get("result", sc)
            summary = case.get("summary") or ""
            cite = (case.get("citation_strings") or [{}])[0].get("text", "")
            if not summary:
                print(f"\n{sid}: no summary")
                continue
            d = await asyncio.to_thread(extract_doctrine, client, summary)
            card, ch, ve = render(case.get("canonical_title", sid), cite, d, summary)
            print(card)
            tot_c += ch
            tot_v += ve
    print(
        f"\n{'═' * 78}\nTOTAL: {tot_v}/{tot_c} quotes verified verbatim "
        f"({round(100 * tot_v / tot_c) if tot_c else 0}%) across {len(LANDMARKS)} landmark cases"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

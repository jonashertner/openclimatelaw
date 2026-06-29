# pyright: basic
"""Extract a structured, verifiable doctrinal record per case (the doctrinal-assistant layer).

For each case, Claude (claude-sonnet-4-6) reads the summary + bounded decision-text excerpts
and returns a structured record: disposition (+ posture), holdings, legal test, legal bases,
relief, significance. Every quoted element is then VERIFIED verbatim against that same source;
holdings carry a per-item `verified` flag and the record carries quotes_verified/quotes_total.
significance is interpretive synthesis (no quote). Written to case_doctrine with provenance —
grounded synthesis, never presented as upstream-authored. Refuse-to-guess.

Auth: ~/.anthropic_key or $ANTHROPIC_API_KEY.
Run: uv run python -m ingest.doctrine [--ids a,b,c] [--limit N] [--reclassify]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger("ingest.doctrine")

MODEL = "claude-sonnet-4-6"
_DOC_PER = 80_000  # cap per document
_DOC_DOCS = 3  # number of (longest) text documents to include
_FOLD = {0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'", 0x2013: "-", 0x2014: "-"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_FOLD)).strip().lower()


def _verified(quote: str | None, pool_norm: str) -> bool:
    return bool(quote) and _norm(quote) in pool_norm


def _key() -> str:
    tok = os.environ.get("ANTHROPIC_API_KEY")
    if not tok:
        p = Path(os.path.expanduser("~/.anthropic_key"))
        if p.exists():
            tok = p.read_text().strip()
    if not tok:
        raise RuntimeError("no Anthropic key: set $ANTHROPIC_API_KEY or write ~/.anthropic_key")
    return tok


_TOOL: Any = {
    "name": "record_doctrine",
    "description": "Record the structured doctrine of a climate case from the provided text.",
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
                        "description": "verbatim phrase stating the result",
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
                            "description": "a VERBATIM phrase from the text supporting it",
                        },
                    },
                    "required": ["point", "quote"],
                },
            },
            "legal_test": {
                "type": "object",
                "properties": {"test": {"type": "string"}, "quote": {"type": "string"}},
                "description": "the legal test/standard applied, if stated",
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
    "Extract the structured DOCTRINE of this climate-litigation case from the SOURCE below "
    "(a curated summary, plus decision-text excerpts where available).\n"
    "- Classify the LATEST, operative disposition — never an overturned lower-court order; if the "
    "matter is pending on appeal, say so in posture and use outcome 'na' unless the latest ruling "
    "resolved the merits.\n"
    "- holdings: the operative legal holdings (2-4). legal_test: the standard the court applied. "
    "legal_bases: the statutes/rights/provisions relied on. relief: what was ordered.\n"
    "- EVERY 'quote' field MUST be copied VERBATIM from the SOURCE. If you cannot find a verbatim "
    "quote for a field, omit it (except 'significance', which is your one-sentence synthesis).\n\n"
    "SOURCE:\n"
)


def extract_doctrine(client: Any, source: str) -> dict[str, Any]:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_doctrine"},
        messages=[{"role": "user", "content": _PROMPT + source}],
    )
    for b in resp.content:
        if b.type == "tool_use":
            return dict(b.input)
    return {}


def _obj(x: Any) -> dict[str, Any]:
    """Coerce a possibly-malformed tool field to a dict (the model occasionally deviates)."""
    return x if isinstance(x, dict) else {}


def pack(d: dict[str, Any], pool_norm: str) -> dict[str, Any]:
    """Verify each quoted element against the source pool; return a case_doctrine row dict.

    Defensive against the model returning a string where an object is expected (holdings
    items, disposition, etc.) — those degrade gracefully rather than crash the run.
    """
    total = verified = 0
    disp = _obj(d.get("disposition"))

    def check(q: Any) -> bool:
        nonlocal total, verified
        total += 1
        ok = _verified(q if isinstance(q, str) else None, pool_norm)
        verified += ok
        return ok

    check(disp.get("quote"))
    holdings = []
    for h in d.get("holdings") or []:
        h = h if isinstance(h, dict) else {"point": str(h), "quote": ""}
        holdings.append(
            {"point": h.get("point"), "quote": h.get("quote"), "verified": check(h.get("quote"))}
        )
    lt = _obj(d.get("legal_test"))
    if lt.get("test"):
        check(lt.get("quote"))
    rel = _obj(d.get("relief"))
    if rel.get("relief"):
        check(rel.get("quote"))
    bases = d.get("legal_bases")
    bases = bases if isinstance(bases, list) else ([bases] if bases else [])
    return {
        "disposition_outcome": disp.get("outcome"),
        "disposition_posture": disp.get("posture"),
        "disposition_quote": disp.get("quote"),
        "holdings": json.dumps(holdings),
        "legal_test": lt.get("test"),
        "legal_test_quote": lt.get("quote"),
        "legal_bases": json.dumps([str(b) for b in bases]),
        "relief": rel.get("relief"),
        "relief_quote": rel.get("quote"),
        "significance": d.get("significance"),
        "quotes_total": total,
        "quotes_verified": verified,
    }


_UPSERT = """
    INSERT INTO case_doctrine
        (case_id, disposition_outcome, disposition_posture, disposition_quote, holdings,
         legal_test, legal_test_quote, legal_bases, relief, relief_quote, significance,
         source_kind, model, quotes_total, quotes_verified, extracted_at)
    VALUES (%(case_id)s, %(disposition_outcome)s, %(disposition_posture)s, %(disposition_quote)s,
            %(holdings)s::jsonb, %(legal_test)s, %(legal_test_quote)s, %(legal_bases)s::jsonb,
            %(relief)s, %(relief_quote)s, %(significance)s, %(source_kind)s, %(model)s,
            %(quotes_total)s, %(quotes_verified)s, now())
    ON CONFLICT (case_id) DO UPDATE SET
        disposition_outcome=EXCLUDED.disposition_outcome,
        disposition_posture=EXCLUDED.disposition_posture,
        disposition_quote=EXCLUDED.disposition_quote, holdings=EXCLUDED.holdings,
        legal_test=EXCLUDED.legal_test, legal_test_quote=EXCLUDED.legal_test_quote,
        legal_bases=EXCLUDED.legal_bases, relief=EXCLUDED.relief,
        relief_quote=EXCLUDED.relief_quote, significance=EXCLUDED.significance,
        source_kind=EXCLUDED.source_kind, model=EXCLUDED.model,
        quotes_total=EXCLUDED.quotes_total, quotes_verified=EXCLUDED.quotes_verified,
        extracted_at=now()
"""


async def _load_source(cur: Any, case_id: str) -> tuple[str, str]:
    await cur.execute("SELECT summary FROM case_record WHERE id::text = %s", (case_id,))
    row = await cur.fetchone()
    summary = (row[0] if row else "") or ""
    await cur.execute(
        "SELECT left(text, %s) FROM document WHERE case_id = %s::uuid AND text IS NOT NULL "
        "ORDER BY length(text) DESC LIMIT %s",
        (_DOC_PER, case_id, _DOC_DOCS),
    )
    docs = [r[0] for r in await cur.fetchall()]
    if docs:
        return summary + "\n\n--- DECISION TEXT (excerpts) ---\n" + "\n\n".join(
            docs
        ), "summary+document"
    return summary, "case_summary"


async def backfill_doctrine(
    *,
    ids: list[str] | None = None,
    limit: int | None = None,
    reclassify: bool = False,
    concurrency: int = 4,
) -> dict[str, int]:
    import anthropic

    from server.db import get_pool

    client = anthropic.Anthropic(api_key=_key())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if ids:
            await cur.execute(
                "SELECT id::text FROM case_record WHERE id::text = ANY(%s) OR sabin_id = ANY(%s)",
                (ids, ids),
            )
            targets = [r[0] for r in await cur.fetchall()]
        else:
            where = "c.status_code = 'decided' AND c.summary IS NOT NULL AND length(c.summary) > 0"
            if not reclassify:
                where += " AND c.id NOT IN (SELECT case_id FROM case_doctrine)"
            # Prioritise the most-documented (most-litigated) decided cases — the citation
            # graph is too thin to rank by influence, so document count is the best proxy.
            await cur.execute(
                f"SELECT c.id::text FROM case_record c WHERE {where} "  # noqa: S608
                "ORDER BY (SELECT count(*) FROM document d WHERE d.case_id = c.id) DESC, c.id "
                "LIMIT %s",
                (limit,),
            )
            targets = [r[0] for r in await cur.fetchall()]

    sem = asyncio.Semaphore(max(1, concurrency))
    counts = {"written": 0, "skipped": 0}

    async def one(case_id: str) -> None:
        async with sem:
            async with pool.connection() as c0, c0.cursor() as cur0:
                source, source_kind = await _load_source(cur0, case_id)
            if not source.strip():
                counts["skipped"] += 1
                return
            try:
                d = await asyncio.to_thread(extract_doctrine, client, source)
                if not d.get("holdings") and not _obj(d.get("disposition")).get("quote"):
                    counts["skipped"] += 1
                    return
                row = pack(d, _norm(source))
                row.update({"case_id": case_id, "source_kind": source_kind, "model": MODEL})
                async with pool.connection() as w, w.cursor() as wc:
                    await wc.execute(_UPSERT, row)
                    await w.commit()
            except Exception as e:
                log.warning("doctrine_error", case_id=case_id, error=repr(e)[:140])
                counts["skipped"] += 1
                return
            counts["written"] += 1
            log.info(
                "doctrine",
                case_id=case_id[:8],
                verified=row["quotes_verified"],
                total=row["quotes_total"],
            )

    await asyncio.gather(*[one(t) for t in targets])
    log.info("doctrine_complete", scanned=len(targets), **counts)
    return {"scanned": len(targets), **counts}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Extract structured doctrine via Claude.")
    parser.add_argument(
        "--ids", type=str, default=None, help="comma-separated case ids / sabin ids"
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reclassify", action="store_true")
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)
    ids = [s.strip() for s in args.ids.split(",")] if args.ids else None

    async def runner() -> dict[str, int]:
        try:
            return await backfill_doctrine(ids=ids, limit=args.limit, reclassify=args.reclassify)
        finally:
            await close_pool()

    print(f"DONE: {asyncio.run(runner())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

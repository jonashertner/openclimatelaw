# pyright: basic
"""Derive case outcome_code with a confidence-gated, verifiable LLM classifier.

Sabin doesn't structure case outcomes (0% populated). For each decided case we ask
Claude (claude-sonnet-4-6) to classify the outcome from the summary and return a
VERBATIM supporting quote + a confidence. We write outcome_code ONLY when confidence
is high AND the quote actually appears in the summary (the same verbatim check the
grounding rails use) — otherwise we leave it NULL. The supporting quote + model go
into provenance, so every derived outcome is checkable. Refuse-to-guess.

Auth: ~/.anthropic_key or $ANTHROPIC_API_KEY.
Run: uv run python -m ingest.outcome [--limit N] [--dry-run]
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

log = structlog.get_logger("ingest.outcome")

MODEL = "claude-sonnet-4-6"
_VALID = {
    "plaintiff_won",
    "defendant_won",
    "mixed",
    "settled_favorable",
    "settled_unfavorable",
    "na",
}

_FOLD = {0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'", 0x2013: "-", 0x2014: "-"}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_FOLD)).strip().lower()


_TOOL = {
    "name": "record_outcome",
    "description": "Record the litigation outcome of a climate case from its summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "outcome_code": {
                "type": "string",
                "enum": [
                    "plaintiff_won",
                    "defendant_won",
                    "mixed",
                    "settled_favorable",
                    "settled_unfavorable",
                    "na",
                    "unknown",
                ],
            },
            "supporting_quote": {
                "type": "string",
                "description": "A short VERBATIM phrase copied from the summary that states the "
                "result. Empty if the summary does not state a result.",
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["outcome_code", "confidence", "supporting_quote"],
    },
}

_PROMPT = (
    "Classify the OUTCOME of this climate-litigation case from its summary. Classify the LATEST, "
    "OPERATIVE disposition — the most recent court's ruling described — NOT an earlier instance "
    "that was later appealed, reversed, or vacated. If a higher court REVERSED or VACATED a lower "
    "court's order, the outcome reflects the higher court's ruling, not the overturned one. If the "
    "matter is still PENDING on appeal or otherwise NOT FINAL, use 'na' unless the latest ruling "
    "clearly resolved the merits. Consider the plaintiff's goal: if the plaintiff sought "
    "stronger climate action / relief and the latest ruling granted it, that is plaintiff_won; "
    "if the latest ruling rejected the plaintiff's climate claim, that is defendant_won; mixed "
    "if the latest ruling is genuinely split (e.g. a duty affirmed but the requested remedy "
    "refused). Use settled_favorable/settled_unfavorable only if settled; na for procedural/"
    "advisory/no-merits or non-final dispositions; unknown if the summary does not clearly state "
    "the result. The supporting_quote MUST be copied verbatim from the summary AND must come "
    "from that latest disposition. Use high confidence only when the summary explicitly states "
    "who prevailed at that latest stage.\n\nSUMMARY:\n"
)


def _key() -> str:
    tok = os.environ.get("ANTHROPIC_API_KEY")
    if not tok:
        p = Path(os.path.expanduser("~/.anthropic_key"))
        if p.exists():
            tok = p.read_text().strip()
    if not tok:
        raise RuntimeError("no Anthropic key: set $ANTHROPIC_API_KEY or write ~/.anthropic_key")
    return tok


def classify_outcome(client: Any, summary: str) -> dict[str, Any]:
    # Send the FULL summary — no truncation. Summaries top out ~17k chars (well within
    # the model's context), and the latest, operative disposition is often at the END, so
    # any head-truncation risked coding an overturned lower-court result (e.g. Shell).
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_outcome"},
        messages=[{"role": "user", "content": _PROMPT + summary}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    return {}


def accept(verdict: dict[str, Any], summary: str) -> bool:
    """Write only a high-confidence, valid outcome whose quote verifies in the summary."""
    oc = verdict.get("outcome_code")
    quote = verdict.get("supporting_quote") or ""
    if oc not in _VALID or verdict.get("confidence") != "high":
        return False
    if oc == "na":  # 'na' is a real verdict but needs no quote
        return True
    return bool(quote) and _normalize(quote) in _normalize(summary)


async def backfill_outcomes(
    *,
    limit: int | None = None,
    dry_run: bool = False,
    concurrency: int = 6,
    reclassify: bool = False,
) -> dict[str, int]:
    """Derive outcome_code for decided cases. By default only fills cases that lack one;
    with reclassify=True it re-derives ALL decided cases in place (overwriting a stale
    label, and clearing one that no longer passes the gate) — used to correct labels
    after a classifier fix."""
    import anthropic

    from server.db import get_pool

    client = anthropic.Anthropic(api_key=_key())
    pool = await get_pool()
    where = "status_code = 'decided' AND summary IS NOT NULL AND length(summary) > 0"
    if not reclassify:
        where += " AND outcome_code IS NULL"
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT id::text, summary FROM case_record WHERE {where} ORDER BY id LIMIT %s",
            (limit,),
        )
        rows = await cur.fetchall()

    sem = asyncio.Semaphore(max(1, concurrency))
    counters = {"written": 0, "skipped": 0, "cleared": 0}

    async def process(case_id: str, summary: str) -> None:
        async with sem:
            try:
                verdict = await asyncio.to_thread(classify_outcome, client, summary)
            except Exception as e:
                log.warning("classify_error", case_id=case_id, error=repr(e)[:120])
                counters["skipped"] += 1
                return
        ok = accept(verdict, summary)
        if dry_run:
            counters["written" if ok else "skipped"] += 1
            return
        if not ok:
            # In reclassify mode, a case that previously had a label but no longer passes
            # must have that stale label cleared; otherwise leave it untouched.
            if reclassify:
                async with pool.connection() as wconn, wconn.cursor() as wcur:
                    await wcur.execute(
                        "UPDATE case_record SET outcome_code = NULL, "
                        "provenance = provenance - 'outcome_code' "
                        "WHERE id::text = %s AND outcome_code IS NOT NULL",
                        (case_id,),
                    )
                    if wcur.rowcount:
                        counters["cleared"] += 1
                    await wconn.commit()
            counters["skipped"] += 1
            return
        prov = json.dumps(
            {
                "source": "llm",
                "model": MODEL,
                "confidence": verdict.get("confidence"),
                "supporting_quote": (verdict.get("supporting_quote") or "")[:500],
            }
        )
        # Write each verdict immediately on a short-lived connection, so progress
        # persists incrementally and the run is resumable after any interruption.
        async with pool.connection() as wconn, wconn.cursor() as wcur:
            await wcur.execute(
                "UPDATE case_record SET outcome_code = %s, "
                "provenance = provenance || jsonb_build_object('outcome_code', %s::jsonb) "
                "WHERE id::text = %s",
                (verdict["outcome_code"], prov, case_id),
            )
            await wconn.commit()
        counters["written"] += 1
        if counters["written"] % 50 == 0:
            log.info("progress", **counters)

    await asyncio.gather(*[process(cid, s) for cid, s in rows])
    log.info("outcome_complete", scanned=len(rows), **counters)
    return {
        "written": counters["written"],
        "skipped": counters["skipped"],
        "cleared": counters["cleared"],
        "scanned": len(rows),
    }


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Classify case outcomes via Claude.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reclassify", action="store_true", help="re-derive ALL decided cases in place"
    )
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await backfill_outcomes(
                limit=args.limit, dry_run=args.dry_run, reclassify=args.reclassify
            )
        finally:
            await close_pool()

    print(f"DONE: {asyncio.run(runner())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

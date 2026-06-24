# pyright: basic
"""Grow the citation_edge graph by case-title substring matching.

Complements ingest.citation_graph (formal cite formats — ECLI/BVerfGE/BGE/
US-reporter) which only catches cases whose citation_string already
contains a recognizable formal cite (≈Urgenda alone in our data).

This module uses Aho-Corasick for true linear-time multi-pattern matching:
build one automaton from every case's canonical_title (filtered ≥25 chars
to avoid generic short titles), then scan each case's summary + first 500K
of document text in O(text_len + matches) regardless of pattern count.

Each automaton hit → a citation_edge with source_of_edge='title_match'.
Edges are committed per citing-case so an interrupt doesn't roll back the
whole graph build.

Run via: uv run python -m ingest.citation_graph_titles
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import ahocorasick
import structlog

MIN_TITLE_LENGTH = 25
MAX_TITLE_LENGTH = 200
DOC_TEXT_SCAN_LIMIT = 500_000


def _is_word_boundary(text: str, start: int, end: int) -> bool:
    """Check that match[start:end] is bounded by non-word characters or string edges.

    Aho-Corasick matches anywhere — without a boundary check, the pattern
    'Held v. State' would match inside 'Withheld v. State of X'. We require
    the char immediately before start and immediately after end to be a
    non-word character (or the edge of the string).
    """
    before_ok = start == 0 or not (text[start - 1].isalnum() or text[start - 1] == "_")
    after_ok = end >= len(text) or not (text[end].isalnum() or text[end] == "_")
    return before_ok and after_ok


async def build_title_citation_graph(*, clear_first: bool = True) -> dict[str, int]:
    from server.db import get_pool

    log = structlog.get_logger("ingest.citation_graph_titles")
    pool = await get_pool()

    # ── Phase 1: load titles, build automaton ──────────────────────────────
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id::text, canonical_title FROM case_record
                WHERE length(canonical_title) BETWEEN %s AND %s
                """,
                (MIN_TITLE_LENGTH, MAX_TITLE_LENGTH),
            )
            title_rows = await cur.fetchall()

    log.info("titles_loaded", n=len(title_rows))

    title_to_ids: dict[str, list[str]] = {}
    for cid, title in title_rows:
        title_to_ids.setdefault(title, []).append(cid)

    automaton: ahocorasick.Automaton = ahocorasick.Automaton()
    for title, ids in title_to_ids.items():
        automaton.add_word(title, (title, ids))
    automaton.make_automaton()
    log.info("automaton_built", n_unique_titles=len(title_to_ids))

    # ── Phase 2: optionally clear prior title_match edges ──────────────────
    if clear_first:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM citation_edge WHERE source_of_edge = 'title_match'")
            await conn.commit()
        log.info("cleared_existing_title_match_edges")

    # ── Phase 3: scan every case (commit per-case to be interrupt-safe) ────
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id::text, summary
                FROM case_record
                WHERE summary IS NOT NULL AND length(summary) > 50
                """
            )
            cases = await cur.fetchall()
    log.info("cases_to_scan", n=len(cases))

    edges_inserted = 0
    cases_scanned = 0

    for citing_id, summary in cases:
        edges: set[tuple[str, str]] = set()

        # Scan summary
        for end_idx, (matched_title, ids) in automaton.iter(summary):
            start_idx = end_idx - len(matched_title) + 1
            if not _is_word_boundary(summary, start_idx, end_idx + 1):
                continue
            for cited_id in ids:
                if cited_id != citing_id:
                    edges.add((cited_id, matched_title))

        # Scan document text(s). Cast the parameter to uuid so the planner
        # uses document_case_idx instead of seq-scanning every row — this
        # was a 1000x speed-up for cases with many documents (some have 244).
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT substring(text FROM 1 FOR %s) FROM document
                    WHERE case_id = %s::uuid AND text IS NOT NULL AND length(text) > 50
                    """,
                    (DOC_TEXT_SCAN_LIMIT, citing_id),
                )
                for (doc_text,) in await cur.fetchall():
                    for end_idx, (matched_title, ids) in automaton.iter(doc_text):
                        start_idx = end_idx - len(matched_title) + 1
                        if not _is_word_boundary(doc_text, start_idx, end_idx + 1):
                            continue
                        for cited_id in ids:
                            if cited_id != citing_id:
                                edges.add((cited_id, matched_title))

        # Insert deduped edges, commit per-case
        if edges:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    for cited_id, matched_title in edges:
                        await cur.execute(
                            """
                            INSERT INTO citation_edge (
                                citing_case_id, cited_case_id, citation_string,
                                source_of_edge
                            )
                            VALUES (%s::uuid, %s::uuid, %s, 'title_match')
                            """,
                            (citing_id, cited_id, matched_title[:500]),
                        )
                        edges_inserted += 1
                await conn.commit()

        cases_scanned += 1
        if cases_scanned % 500 == 0:
            log.info(
                "progress",
                cases_scanned=cases_scanned,
                edges_inserted=edges_inserted,
            )

    log.info(
        "title_graph_built",
        cases_scanned=cases_scanned,
        edges_inserted=edges_inserted,
    )
    return {"cases_scanned": cases_scanned, "edges_inserted": edges_inserted}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(
        description="Grow citation_edge graph by case-title substring matching (Aho-Corasick)."
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing title_match edges before insertion.",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await build_title_citation_graph(clear_first=not args.no_clear)
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

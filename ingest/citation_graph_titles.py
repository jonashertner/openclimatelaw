# pyright: basic
"""Grow the citation_edge graph by title-substring matching.

Complements ingest.citation_graph (which uses formal cite formats —
ECLI/BVerfGE/BGE/US-reporter). That approach captures only cases whose
citation_string already contains a recognizable formal cite, which means
roughly Urgenda alone in our current data.

This module builds a single big regex from every case's canonical_title
(filtered to titles ≥25 characters to avoid generic short titles like
'Held v. State' that would over-match), then scans every case's summary
and document text for occurrences. Each match → a citation_edge with
source_of_edge='title_match'.

Run via: uv run python -m ingest.citation_graph_titles
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

import structlog

MIN_TITLE_LENGTH = 25
MAX_TITLE_LENGTH = 200  # extremely long titles are usually generic descriptions


async def build_title_citation_graph(*, clear_first: bool = True) -> dict[str, int]:
    """Insert citation_edges by matching other cases' titles in this case's text."""
    from server.db import get_pool

    log = structlog.get_logger("ingest.citation_graph_titles")
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # 1. Pull all (id, canonical_title) for cases with sufficiently long titles
            await cur.execute(
                f"""
                SELECT id::text, canonical_title FROM case_record
                WHERE length(canonical_title) BETWEEN {MIN_TITLE_LENGTH} AND {MAX_TITLE_LENGTH}
                ORDER BY length(canonical_title) DESC
                """
            )
            title_rows = await cur.fetchall()
            log.info("titles_loaded", n=len(title_rows))

            # 2. Build title → case_ids map. Multiple cases share a title (same lawsuit
            # named over time) so we collect into a list per title.
            title_to_ids: dict[str, list[str]] = {}
            for cid, title in title_rows:
                title_to_ids.setdefault(title, []).append(cid)

            # 3. Compile one big regex with longest titles first (greedy matching)
            sorted_titles = sorted(title_to_ids.keys(), key=len, reverse=True)
            log.info("compiling_pattern", n_unique_titles=len(sorted_titles))
            try:
                # Word-boundary-anchored to avoid matching mid-word
                pattern = re.compile(
                    r"\b(" + "|".join(re.escape(t) for t in sorted_titles) + r")\b"
                )
            except re.error as e:
                log.error("pattern_compile_failed", error=str(e))
                return {"cases_scanned": 0, "edges_inserted": 0}
            log.info("pattern_compiled", pattern_size=pattern.pattern.__len__())

            # 4. Optionally clear prior title_match edges
            if clear_first:
                await cur.execute("DELETE FROM citation_edge WHERE source_of_edge = 'title_match'")
                log.info("cleared_existing_title_match_edges")

            # 5. Walk every case, scan summary + each document text
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
                for m in pattern.finditer(summary):
                    matched_title = m.group(1)
                    for cited_id in title_to_ids.get(matched_title, ()):
                        if cited_id != citing_id:
                            edges.add((cited_id, matched_title))

                # Scan document text — but limit length to keep regex tractable
                await cur.execute(
                    """
                    SELECT substring(text FROM 1 FOR 500000) FROM document
                    WHERE case_id::text = %s AND text IS NOT NULL AND length(text) > 50
                    """,
                    (citing_id,),
                )
                for (doc_text,) in await cur.fetchall():
                    for m in pattern.finditer(doc_text):
                        matched_title = m.group(1)
                        for cited_id in title_to_ids.get(matched_title, ()):
                            if cited_id != citing_id:
                                edges.add((cited_id, matched_title))

                # Insert deduped edges
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

                cases_scanned += 1
                if cases_scanned % 200 == 0:
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
        description="Grow citation_edge graph by case-title substring matching."
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

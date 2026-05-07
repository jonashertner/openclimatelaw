# pyright: basic
"""Build the citation_edge graph by extracting case-to-case references from
case summaries and document text.

Algorithm:
1. Build a lookup map: citation-format-string → case_id, by running
   find_citation_spans() over every existing citation_string. This gives us
   a way to resolve a detected ECLI/BVerfGE/BGE/US-reporter back to a
   case in our database.
2. For each case, scan its summary AND every document's text for
   citation-shaped strings.
3. For each detected span, look up the cited case in the map.
4. Insert a citation_edge row (citing_case_id, cited_case_id,
   citation_string, source_of_edge='inferred_nlp').

Idempotent: clears existing 'inferred_nlp' edges before re-running so
repeated runs converge.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict

import structlog

from server.tools.contracts.citation_formats import find_citation_spans


async def build_lookup_map() -> dict[str, set[str]]:
    """Return citation-text → set of case_id strings that match.

    A single citation token (e.g. 'ECLI:NL:HR:2019:2007') typically resolves
    to ONE case, but in degenerate cases multiple cases may share a citation
    string substring; we keep all matches.
    """
    from server.db import get_pool

    log = structlog.get_logger("ingest.citation_graph")
    pool = await get_pool()
    cite_map: dict[str, set[str]] = defaultdict(set)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT case_id::text, text FROM citation_string WHERE text IS NOT NULL"
            )
            rows = await cur.fetchall()
            for case_id, text in rows:
                for span in find_citation_spans(text):
                    cite_map[span.text].add(case_id)
    log.info("lookup_map_built", n_keys=len(cite_map), n_citation_strings=len(rows))
    return dict(cite_map)


async def extract_edges_for_case(
    cur,
    citing_case_id: str,
    summary: str | None,
    cite_map: dict[str, set[str]],
) -> list[tuple[str, str, str]]:
    """Yield (cited_case_id, citation_string, source_kind) for one case.

    Scans both the case summary and any document.text rows.
    Returns a list of unique (citing, cited, citation_text) tuples.
    """
    edges: set[tuple[str, str, str]] = set()

    # Scan summary
    if summary:
        for span in find_citation_spans(summary):
            for cited in cite_map.get(span.text, ()):
                if cited != citing_case_id:
                    edges.add((cited, span.text, "summary"))

    # Scan document texts for this case
    await cur.execute(
        """
        SELECT text FROM document
        WHERE case_id::text = %s AND text IS NOT NULL
        """,
        (citing_case_id,),
    )
    for (doc_text,) in await cur.fetchall():
        for span in find_citation_spans(doc_text):
            for cited in cite_map.get(span.text, ()):
                if cited != citing_case_id:
                    edges.add((cited, span.text, "document_text"))

    return list(edges)


async def build_citation_graph(*, clear_first: bool = True) -> dict[str, int]:
    """End-to-end: clear existing inferred edges, scan all cases, insert edges."""
    from server.db import get_pool

    log = structlog.get_logger("ingest.citation_graph")
    pool = await get_pool()

    cite_map = await build_lookup_map()

    edges_inserted = 0
    cases_scanned = 0
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if clear_first:
                await cur.execute("DELETE FROM citation_edge WHERE source_of_edge = 'inferred_nlp'")
                log.info("cleared_existing_inferred_edges")

            # Walk all cases that have a summary or any document text
            await cur.execute(
                """
                SELECT DISTINCT c.id::text, c.summary
                FROM case_record c
                LEFT JOIN document d ON d.case_id = c.id AND d.text IS NOT NULL
                WHERE c.summary IS NOT NULL OR d.text IS NOT NULL
                """
            )
            cases = await cur.fetchall()
            log.info("cases_to_scan", n=len(cases))

            for citing_id, summary in cases:
                edges = await extract_edges_for_case(cur, citing_id, summary, cite_map)
                for cited_id, citation_text, _kind in edges:
                    await cur.execute(
                        """
                        INSERT INTO citation_edge (
                            citing_case_id, cited_case_id, citation_string,
                            source_of_edge
                        )
                        VALUES (%s::uuid, %s::uuid, %s, 'inferred_nlp')
                        """,
                        (citing_id, cited_id, citation_text[:500]),
                    )
                    edges_inserted += 1
                cases_scanned += 1
                if cases_scanned % 100 == 0:
                    log.info(
                        "progress",
                        cases_scanned=cases_scanned,
                        edges_inserted=edges_inserted,
                    )

    log.info(
        "citation_graph_built",
        cases_scanned=cases_scanned,
        edges_inserted=edges_inserted,
    )
    return {"cases_scanned": cases_scanned, "edges_inserted": edges_inserted}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(
        description="Build citation_edge graph by extracting cite spans from text."
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear existing inferred_nlp edges before insertion.",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await build_citation_graph(clear_first=not args.no_clear)
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

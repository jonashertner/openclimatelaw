# pyright: basic
"""Backfill passage embeddings (multilingual-e5-small) into passage_embedding, deduped by
content_hash. 78% of the 4.98M passages are duplicate content, so this embeds ~1.1M distinct.
Resumable (skips content_hashes already embedded). Runs where the DB is reachable (the VPS).

    uv run python -m ingest.embed_passages [--case-ids id,id] [--limit N] [--batch 16]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

log = structlog.get_logger("ingest.embed_passages")


async def backfill(
    case_ids: list[str] | None = None, limit: int | None = None, batch: int = 16
) -> dict[str, int]:
    from server.db import close_pool, get_pool
    from server.embed import embed_passages

    pool = await get_pool()
    # STREAM to stay within the VPS's ~4 GB: fetch only the list of unembedded distinct
    # content_hashes first (~70 MB for 1.1M hashes — never the 1.1M passage TEXTS), then pull
    # text per batch via the content_hash index. Resumable: a restart re-derives the todo.
    case_clause, case_params = "", []
    if case_ids:
        case_clause = (
            " AND (p.case_id::text = ANY(%s) OR p.case_id IN "
            "(SELECT id FROM case_record WHERE sabin_id = ANY(%s)))"
        )
        case_params = [case_ids, case_ids]
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT DISTINCT p.content_hash FROM document_passage p "
            "LEFT JOIN passage_embedding pe ON pe.content_hash = p.content_hash "
            f"WHERE pe.content_hash IS NULL{case_clause}",
            tuple(case_params),
        )
        hashes = [r[0] for r in await cur.fetchall()]
    if limit:
        hashes = hashes[:limit]

    total = len(hashes)
    written = 0
    log.info("embed_start", distinct_todo=total, batch=batch)
    for i in range(0, total, batch):
        bh = hashes[i : i + batch]
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT DISTINCT ON (content_hash) content_hash, text "
                "FROM document_passage WHERE content_hash = ANY(%s)",
                (bh,),
            )
            got = await cur.fetchall()
        vecs = await asyncio.to_thread(embed_passages, [r[1] or "" for r in got])
        if vecs is None:
            log.error("embed_unavailable")
            break
        rows = [
            (got[j][0], "[" + ",".join(f"{x:.7f}" for x in v) + "]") for j, v in enumerate(vecs)
        ]
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO passage_embedding (content_hash, embedding) VALUES (%s, %s::vector) "
                "ON CONFLICT (content_hash) DO NOTHING",
                rows,
            )
            await conn.commit()
        written += len(rows)
        if (i // batch) % 200 == 0:
            log.info("embed_progress", done=written, of=total)
    await close_pool()
    log.info("embed_complete", written=written, of=total)
    return {"distinct": total, "written": written}


def main() -> int:
    from server._logging import configure_logging

    ap = argparse.ArgumentParser(description="Backfill passage embeddings (e5-small, deduped).")
    ap.add_argument(
        "--case-ids", type=str, default=None, help="comma-separated case ids / sabin ids"
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    configure_logging(level="INFO", json=False)
    ids = [s.strip() for s in args.case_ids.split(",")] if args.case_ids else None
    print(f"DONE: {asyncio.run(backfill(case_ids=ids, limit=args.limit, batch=args.batch))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

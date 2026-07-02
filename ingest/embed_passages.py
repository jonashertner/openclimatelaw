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
    # Distinct content_hashes not yet embedded — one representative text each. Optionally
    # restrict to specific cases (for fast validation before the full run).
    where = "pe.content_hash IS NULL"
    params: list[object] = []
    if case_ids:
        where += (
            " AND (p.case_id::text = ANY(%s) OR p.case_id IN "
            "(SELECT id FROM case_record WHERE sabin_id = ANY(%s)))"
        )
        params += [case_ids, case_ids]
    sql = (
        "SELECT DISTINCT ON (p.content_hash) p.content_hash, p.text "
        "FROM document_passage p "
        "LEFT JOIN passage_embedding pe ON pe.content_hash = p.content_hash "
        f"WHERE {where} ORDER BY p.content_hash"
    )
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, tuple(params))
        todo = await cur.fetchall()

    total = len(todo)
    written = 0
    log.info("embed_start", distinct_todo=total, batch=batch)
    for i in range(0, total, batch):
        chunk = todo[i : i + batch]
        hashes = [r[0] for r in chunk]
        texts = [r[1] or "" for r in chunk]
        vecs = await asyncio.to_thread(embed_passages, texts)
        if vecs is None:
            log.error("embed_unavailable")
            break
        rows = [
            (h, "[" + ",".join(f"{x:.7f}" for x in v) + "]")
            for h, v in zip(hashes, vecs, strict=False)
        ]
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO passage_embedding (content_hash, embedding) VALUES (%s, %s::vector) "
                "ON CONFLICT (content_hash) DO NOTHING",
                rows,
            )
            await conn.commit()
        written += len(rows)
        if (i // batch) % 25 == 0:
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

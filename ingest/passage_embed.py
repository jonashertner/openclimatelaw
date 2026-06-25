# pyright: basic
"""Generate sentence-transformer embeddings for document passages (semantic pinpoint).

Model: sentence-transformers/all-MiniLM-L6-v2 (384-dim) — the same model used for
case-summary embeddings, so passage and query vectors share a space.

Stores vectors in document_passage.embedding (vector(384), migration 0013), enabling
the semantic arm of find_relevant_passage. Streams one batch at a time (never loads
the whole corpus) and commits per batch, so a multi-million-row run is memory-safe
and resumable: each pass selects passages still lacking an embedding.

Run via: uv run python -m ingest.passage_embed [--batch-size N] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog


async def backfill_passage_embeddings(
    *, batch_size: int = 64, limit: int | None = None
) -> dict[str, int]:
    """Encode passages lacking an embedding, writing document_passage.embedding."""
    from sentence_transformers import SentenceTransformer

    from server.db import get_pool

    log = structlog.get_logger("ingest.passage_embed")
    log.info("loading_model", model="sentence-transformers/all-MiniLM-L6-v2")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    pool = await get_pool()
    embedded = 0
    async with pool.connection() as conn:
        while True:
            if limit is not None and embedded >= limit:
                break
            n = batch_size if limit is None else min(batch_size, limit - embedded)
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id::text, text FROM document_passage "
                    "WHERE embedding IS NULL ORDER BY id LIMIT %s",
                    (n,),
                )
                rows = await cur.fetchall()
            if not rows:
                break
            texts = [(r[1] or "")[:1500] for r in rows]
            vectors = model.encode(texts, normalize_embeddings=True).tolist()
            async with conn.cursor() as cur:
                for (pid, _text), emb in zip(rows, vectors, strict=True):
                    literal = "[" + ",".join(f"{v:.7f}" for v in emb) + "]"
                    await cur.execute(
                        "UPDATE document_passage SET embedding = %s::vector WHERE id::text = %s",
                        (literal, pid),
                    )
            await conn.commit()
            embedded += len(rows)
            if (embedded // batch_size) % 20 == 0:
                log.info("progress", embedded=embedded)

    log.info("embed_complete", embedded=embedded)
    return {"embedded": embedded}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Embed document passages for semantic pinpoint.")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await backfill_passage_embeddings(batch_size=args.batch_size, limit=args.limit)
        finally:
            await close_pool()

    result = asyncio.run(runner())
    print(f"DONE: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

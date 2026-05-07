# pyright: basic
"""Generate sentence-transformer embeddings for every case summary.

Model: sentence-transformers/all-MiniLM-L6-v2
- 384-dim, ~80MB, fast on CPU
- Strong English semantic similarity baseline
- Free, self-hosted (no API keys)

Stores embeddings in case_record.embedding (added by migration 0010).
Used by search_cases to layer vector cosine similarity on top of FTS +
trigram for hybrid retrieval.

Idempotent: fetches all cases with non-null summaries that don't yet have
an embedding (or all of them if --re-embed). Writes via UPDATE.

Run via: uv run python -m ingest.embed [--re-embed] [--batch-size N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog


async def embed_all(*, re_embed: bool = False, batch_size: int = 32) -> dict[str, int]:
    """Encode every case summary, write to case_record.embedding."""
    from sentence_transformers import SentenceTransformer

    from server.db import get_pool

    log = structlog.get_logger("ingest.embed")
    log.info("loading_model", model="sentence-transformers/all-MiniLM-L6-v2")
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    log.info("model_loaded", dim=model.get_sentence_embedding_dimension())

    pool = await get_pool()

    # Pull cases needing embeddings
    where = "WHERE summary IS NOT NULL AND length(summary) > 0"
    if not re_embed:
        where += " AND embedding IS NULL"

    total_updated = 0
    total_skipped = 0
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT id::text, summary FROM case_record {where}")
            cases = await cur.fetchall()
            log.info("cases_to_embed", n=len(cases))

            if not cases:
                return {"updated": 0, "skipped": 0}

            # Batch-encode for speed
            for i in range(0, len(cases), batch_size):
                batch = cases[i : i + batch_size]
                ids = [r[0] for r in batch]
                # Truncate very long summaries — MiniLM has 512-token context
                summaries = [(r[1] or "")[:1500] for r in batch]
                embeddings = model.encode(summaries, normalize_embeddings=True).tolist()

                # Update each row
                for cid, emb in zip(ids, embeddings, strict=True):
                    # pgvector accepts the literal string '[v1,v2,...]'
                    emb_literal = "[" + ",".join(f"{v:.7f}" for v in emb) + "]"
                    await cur.execute(
                        "UPDATE case_record SET embedding = %s::vector WHERE id::text = %s",
                        (emb_literal, cid),
                    )
                total_updated += len(batch)
                if (i // batch_size) % 5 == 0:
                    log.info("progress", encoded=total_updated, of=len(cases))

    log.info("embed_complete", updated=total_updated, skipped=total_skipped)
    return {"updated": total_updated, "skipped": total_skipped}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Encode case summaries into vector embeddings.")
    parser.add_argument(
        "--re-embed",
        action="store_true",
        help="Re-encode all cases (default: only those without an embedding).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Encoder batch size (default 32).",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await embed_all(re_embed=args.re_embed, batch_size=args.batch_size)
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

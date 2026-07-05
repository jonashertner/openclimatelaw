"""Split extracted document text into addressable passages for pinpoint retrieval.

A passage is a paragraph-sized span of `document.text` with character offsets back
into the original text (so a quote can be re-located). The splitter is deliberate
and offset-exact; the backfill populates `document_passage` and (optionally) the
per-passage embeddings used for semantic pinpointing.
"""

import hashlib
import re

_MIN_PASSAGE_CHARS = 40
_BLANK_LINE = re.compile(r"\n[ \t]*\n")


def _append(out: list[tuple[int, int, str]], text: str, start: int, end: int) -> None:
    raw = text[start:end]
    stripped = raw.strip()
    if len(stripped) < _MIN_PASSAGE_CHARS:
        return
    lead = len(raw) - len(raw.lstrip())
    s = start + lead
    out.append((s, s + len(stripped), stripped))


def split_into_passages(text: str) -> list[tuple[int, int, str]]:
    """Split `text` on blank lines into passages of >= 40 chars.

    Returns a list of (char_start, char_end, passage_text) where
    `text[char_start:char_end] == passage_text` exactly.
    """
    out: list[tuple[int, int, str]] = []
    pos = 0
    for m in _BLANK_LINE.finditer(text):
        _append(out, text, pos, m.start())
        pos = m.end()
    _append(out, text, pos, len(text))
    return out


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Fetch candidate IDs only — never the text. Materialising every document's text
# at once (the previous fetchall over `d.text`) OOM-kills on the full ~5GB corpus.
_SELECT_DOC_IDS = """
    SELECT d.id::text
    FROM document d
    WHERE d.text IS NOT NULL AND length(d.text) > 0
      AND (NOT %(only_missing)s::boolean
           OR NOT EXISTS (SELECT 1 FROM document_passage p WHERE p.document_id = d.id))
    ORDER BY d.id
    LIMIT %(limit)s
"""

_SELECT_ONE_DOC = "SELECT case_id::text, text FROM document WHERE id = %s::uuid"

_INSERT_PASSAGE = """
    INSERT INTO document_passage
        (document_id, case_id, para_index, char_start, char_end, text, content_hash)
    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)
    ON CONFLICT (document_id, para_index) DO NOTHING
"""


async def backfill_passages(
    *, only_missing: bool = True, limit: int | None = None, embed: bool = True
) -> dict[str, int]:
    """Split every document's text into `document_passage` rows.

    Streams: fetches candidate document IDs first (lightweight), then processes one
    document's text at a time — bounded memory, so the full corpus does not OOM.
    Idempotent via ON CONFLICT, committing per document so an interrupted run resumes.

    embed=True (default) then embeds any newly-created passages (dedup by content_hash,
    via ingest.embed_passages) so a freshly-ingested case gets semantic pinpoint too —
    without it, new passages silently regress to lexical-only. The embed step is itself
    idempotent (skips already-embedded hashes), so it only pays for the new content.
    Returns {documents, passages, embedded}.
    """
    from server.db import get_pool

    real_pool = await get_pool()
    docs = 0
    total = 0
    async with real_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_SELECT_DOC_IDS, {"only_missing": only_missing, "limit": limit})
            doc_ids = [r[0] for r in await cur.fetchall()]
        for doc_id in doc_ids:
            async with conn.cursor() as cur:
                await cur.execute(_SELECT_ONE_DOC, (doc_id,))
                row = await cur.fetchone()
            if row is None or not row[1]:
                continue
            case_id, text = row
            parts = split_into_passages(text)
            if not parts:
                continue
            async with conn.cursor() as cur:
                for i, (cs, ce, ptext) in enumerate(parts):
                    await cur.execute(
                        _INSERT_PASSAGE,
                        (doc_id, case_id, i, cs, ce, ptext, content_hash(ptext)),
                    )
                    total += 1
            await conn.commit()
            docs += 1

    embedded = 0
    if embed and total:
        from ingest.embed_passages import backfill as embed_backfill

        res = await embed_backfill()  # dedup + resumable → embeds only the new hashes
        embedded = res.get("written", 0)
    return {"documents": docs, "passages": total, "embedded": embedded}


def main() -> int:
    import argparse
    import asyncio

    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Backfill document_passage from document.text.")
    parser.add_argument(
        "--all", action="store_true", help="Re-process documents that already have passages."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embedding newly-created passages (text-only; semantic pinpoint won't work).",
    )
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await backfill_passages(
                only_missing=not args.all, limit=args.limit, embed=not args.no_embed
            )
        finally:
            await close_pool()

    result = asyncio.run(runner())
    print(f"DONE: {result}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

# pyright: basic
"""Backfill case parties from the canonical title ('Plaintiff v. Defendant').

Sabin's bulk records don't expose structured parties (0% populated). For the common
'X v. Y' caption we split on the 'v.' connector into a plaintiff and a defendant.
Captions without a 'v.' (e.g. 'In re X', advisory opinions) are skipped — left for a
later, richer parser. Idempotent: only fills cases that have no parties yet.

Run: uv run python -m ingest.parties
"""

from __future__ import annotations

import asyncio
import re
import sys

import structlog

log = structlog.get_logger("ingest.parties")

_VS = re.compile(r"\s+vs?\.?\s+", re.IGNORECASE)


def parse_parties(title: str) -> list[tuple[str, str]]:
    """'X v. Y' -> [('plaintiff','X'), ('defendant','Y')]; [] if there is no 'v.'."""
    m = _VS.search(title or "")
    if not m:
        return []
    left = (title[: m.start()]).strip().strip(",")
    right = (title[m.end() :]).strip().strip(",")
    out: list[tuple[str, str]] = []
    if left:
        out.append(("plaintiff", left))
    if right:
        out.append(("defendant", right))
    return out


async def backfill_parties() -> dict[str, int]:
    from server.db import get_pool

    pool = await get_pool()
    cases = 0
    parties = 0
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id::text, canonical_title FROM case_record c "
                "WHERE canonical_title IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM case_party p WHERE p.case_id = c.id)"
            )
            rows = await cur.fetchall()
        for case_id, title in rows:
            parsed = parse_parties(title)
            if not parsed:
                continue
            async with conn.cursor() as cur:
                for side, name in parsed:
                    await cur.execute(
                        "INSERT INTO case_party (case_id, side, name, ord) "
                        "VALUES (%s::uuid, %s, %s, 0) ON CONFLICT DO NOTHING",
                        (case_id, side, name[:500]),
                    )
                    parties += 1
            await conn.commit()
            cases += 1
    log.info("parties_complete", cases=cases, parties=parties)
    return {"cases": cases, "parties": parties}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await backfill_parties()
        finally:
            await close_pool()

    print(f"DONE: {asyncio.run(runner())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

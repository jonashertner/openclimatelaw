# pyright: basic
"""Re-derive case_record.decision_date from the stored event timeline.

decision_date was bulk-mapped from last_updated_date (a metadata-modification
timestamp), which surfaces ingest/scrape timestamps as if they were judgment
dates (visible in sort='newest'). This backfill recomputes decision_date as the
latest 'Decision' event in upstream_metadata->'events', and NULLs it where the
proceeding has no recorded decision — the honest value. Reads only data already
stored; no re-scrape. Streaming + idempotent.

Run via: uv run python -m ingest.backfill_dates [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from ingest.sabin.cpr import latest_decision_date


async def backfill_decision_dates(*, limit: int | None = None) -> dict[str, int]:
    from server.db import get_pool

    log = structlog.get_logger("ingest.backfill_dates")
    pool = await get_pool()
    scanned = 0
    changed = 0
    cleared = 0
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id::text, decision_date, upstream_metadata->'events' "
                "FROM case_record ORDER BY id LIMIT %s",
                (limit,),
            )
            rows = await cur.fetchall()
        for case_id, current, events in rows:
            scanned += 1
            derived = latest_decision_date(events)
            if derived == current:
                continue
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE case_record SET decision_date = %s WHERE id::text = %s",
                    (derived, case_id),
                )
            changed += 1
            if derived is None:
                cleared += 1
        await conn.commit()
    log.info("backfill_dates_complete", scanned=scanned, changed=changed, cleared=cleared)
    return {"scanned": scanned, "changed": changed, "cleared": cleared}


async def clear_nonfinal_decision_dates() -> dict[str, int]:
    """decision_date must mean a COURT DECISION date. Filed/pending and settled cases have
    no court decision, so any date there is a procedural/scrape artifact (e.g. a DETEC
    administrative decision on a case pending at a higher court) that pollutes the 'newest'
    sort. Clear it — filing_date still carries the timeline."""
    from server.db import get_pool

    log = structlog.get_logger("ingest.backfill_dates")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE case_record SET decision_date = NULL "
            "WHERE status_code IS DISTINCT FROM 'decided' AND decision_date IS NOT NULL"
        )
        cleared = cur.rowcount
        await conn.commit()
    log.info("clear_nonfinal_complete", cleared=cleared)
    return {"cleared": cleared}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Re-derive decision_date from event timeline.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--clear-nonfinal",
        action="store_true",
        help="NULL decision_date on non-decided (filed/settled) cases",
    )
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            if args.clear_nonfinal:
                return await clear_nonfinal_decision_dates()
            return await backfill_decision_dates(limit=args.limit)
        finally:
            await close_pool()

    result = asyncio.run(runner())
    print(f"DONE: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

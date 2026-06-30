# pyright: basic
"""Usage report over the usage_event table.

uv run python scripts/usage_report.py [--days N] [--limit N]
# on the VPS:
docker exec openclimatelaw-server-1 uv run python scripts/usage_report.py --days 7
"""

import argparse
import asyncio
import sys
from typing import Any


async def _rows(cur: Any, sql: str, params: Any) -> list[Any]:
    await cur.execute(sql, params)
    return await cur.fetchall()


async def report(days: int, limit: int) -> int:
    from server.db import close_pool, get_pool

    p = {"days": days, "limit": limit}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        win = "ts > now() - make_interval(days => %(days)s)"

        (ov,) = await _rows(
            cur,
            f"SELECT count(*), count(*) FILTER (WHERE ok), count(DISTINCT session_id), "
            f"count(DISTINCT coalesce(ip_hash, ip)), min(ts), max(ts) FROM usage_event WHERE {win}",
            p,
        )
        total, oks, sessions, users, first, last = ov
        print(f"\n{'=' * 66}\nUSAGE — last {days} days\n{'=' * 66}")
        if not total:
            print("  no tool calls recorded in this window yet.")
            await close_pool()
            return 0
        okpct = round(100 * (oks or 0) / total)
        print(
            f"  tool calls: {total}   ok: {okpct}%   distinct sessions: {sessions}   "
            f"distinct users: {users}"
        )
        print(f"  first: {first}   last: {last}")

        print("\n  by day:")
        for d, n, s in await _rows(
            cur,
            f"SELECT date_trunc('day', ts)::date, count(*), count(DISTINCT session_id) "
            f"FROM usage_event WHERE {win} GROUP BY 1 ORDER BY 1",
            p,
        ):
            print(f"    {d}   {n:>5} calls   {s} sessions")

        print("\n  top tools:")
        for tool, n, ms in await _rows(
            cur,
            f"SELECT tool, count(*), round(avg(duration_ms)) FROM usage_event WHERE {win} "
            f"GROUP BY tool ORDER BY 2 DESC LIMIT %(limit)s",
            p,
        ):
            print(f"    {tool:<24} {n:>5}   ~{ms or 0} ms avg")

        print("\n  clients:")
        for name, n, s in await _rows(
            cur,
            f"SELECT coalesce(client_name,'?')||' '||coalesce(client_version,''), count(*), "
            f"count(DISTINCT session_id) FROM usage_event WHERE {win} GROUP BY 1 ORDER BY 2 DESC "
            f"LIMIT %(limit)s",
            p,
        ):
            print(f"    {name:<28} {n:>5} calls   {s} sessions")

        errs = await _rows(
            cur,
            f"SELECT tool, error_kind, count(*) FROM usage_event WHERE {win} AND NOT ok "
            f"GROUP BY 1,2 ORDER BY 3 DESC LIMIT %(limit)s",
            p,
        )
        if errs:
            print("\n  errors:")
            for tool, kind, n in errs:
                print(f"    {tool:<24} {kind or '?':<22} {n}")

        # full-logging extras (present only when USAGE_LOG_FULL was on)
        queries = await _rows(
            cur,
            f"SELECT arguments->>'query', count(*) FROM usage_event WHERE {win} "
            f"AND arguments ? 'query' AND length(arguments->>'query') > 0 "
            f"GROUP BY 1 ORDER BY 2 DESC LIMIT %(limit)s",
            p,
        )
        if queries:
            print("\n  top queries (full-logging):")
            for q, n in queries:
                print(f"    {n:>4}x  {q[:60]}")

        recent = await _rows(
            cur,
            f"SELECT to_char(ts,'MM-DD HH24:MI'), tool, coalesce(client_name,'?'), "
            f"coalesce(ip,'-'), coalesce(left(arguments::text,60),'') FROM usage_event "
            f"WHERE {win} ORDER BY ts DESC LIMIT %(limit)s",
            p,
        )
        print("\n  recent activity:")
        for t, tool, client, ip, arg in recent:
            print(f"    {t}  {tool:<20} {client:<12} {ip:<16} {arg}")

    await close_pool()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenClimateLaw usage report")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()
    return asyncio.run(report(args.days, args.limit))


if __name__ == "__main__":
    sys.exit(main())

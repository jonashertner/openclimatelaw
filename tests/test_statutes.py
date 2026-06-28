from collections.abc import AsyncGenerator

import pytest

from ingest.cclw import map_jurisdiction
from server.db import get_pool
from server.tools.statutes import get_statute, search_statutes


def test_map_jurisdiction() -> None:
    assert map_jurisdiction(["ALB"])[0] == "AL"
    assert map_jurisdiction(["ZAF"]) == ("ZA", "South Africa", "national")
    assert map_jurisdiction(["XKX"])[0] == "XK"
    assert map_jurisdiction(["ZZZ"])[0] == "XX"  # unmappable -> fallback
    assert map_jurisdiction([])[0] == "XX"


@pytest.fixture
async def seeded_statute() -> AsyncGenerator[str]:
    pool = await get_pool()
    text = "An Act to establish the Zylonia Carbon Budget and emissions reduction targets. " * 20
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO statute "
                "(cclw_id, jurisdiction_code, short_title, status, text, text_lang, provenance) "
                "VALUES (%s, 'US', 'Zylonia Carbon Budget Act', 'Legislative', %s, 'en', "
                "'{}'::jsonb) RETURNING id::text",
                ("CCLW.test.zylonia", text),
            )
            row = await cur.fetchone()
            assert row is not None
            sid = row[0]
        await conn.commit()
    yield sid
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM statute WHERE cclw_id = 'CCLW.test.zylonia'")
        await conn.commit()


@pytest.mark.asyncio
async def test_search_statutes_finds_law(seeded_statute: str) -> None:
    r = await search_statutes("Carbon Budget emissions reduction targets")
    assert r["count"] >= 1
    assert any(x["cclw_id"] == "CCLW.test.zylonia" for x in r["results"])


@pytest.mark.asyncio
async def test_get_statute_paginates(seeded_statute: str) -> None:
    r = await get_statute("CCLW.test.zylonia", max_chars=50)
    assert r is not None
    assert r["short_title"] == "Zylonia Carbon Budget Act"
    assert r["returned_chars"] == 50
    assert r["has_more"] is True
    assert r["total_chars"] > 50


@pytest.mark.asyncio
async def test_get_statute_not_found() -> None:
    assert await get_statute("CCLW.nope.000000") is None

# pyright: reportPrivateUsage=false
from collections.abc import AsyncGenerator

import pytest

from server.db import get_pool
from server.tools.chatgpt import _source_url, fetch, search


def test_source_url_extracts_from_citation() -> None:
    cite = "Foo v. Bar, 1 U.S. 1 (Sabin Center, https://www.climatecasechart.com/case/foo)."
    assert _source_url(cite) == "https://www.climatecasechart.com/case/foo"
    assert _source_url(None) == "https://climatecasechart.com/"
    assert _source_url("no url in here") == "https://climatecasechart.com/"


@pytest.fixture
async def seeded_case() -> AsyncGenerator[str]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO case_record (sabin_id, canonical_title, jurisdiction_code, "
                "status_code, primary_source, summary) VALUES ('tcg-1', "
                "'ChatGPTProbe v. State', 'US', 'decided', 'sabin', "
                "'A test summary mentioning emissions.') RETURNING id::text"
            )
            row = await cur.fetchone()
            assert row is not None
            cid = row[0]
            await cur.execute(
                "INSERT INTO citation_string (case_id, lang, format, text) VALUES "
                "(%s::uuid, 'en', 'sabin', 'ChatGPTProbe v. State (Sabin Center, "
                "https://www.climatecasechart.com/case/probe)')",
                (cid,),
            )
        await conn.commit()
    yield "tcg-1"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM case_record WHERE sabin_id = 'tcg-1'")
        await conn.commit()


@pytest.mark.asyncio
async def test_search_contract(seeded_case: str) -> None:
    r = await search("ChatGPTProbe")
    assert isinstance(r.get("results"), list)
    hit = next((x for x in r["results"] if x["id"] == "tcg-1"), None)
    assert hit is not None
    assert set(hit.keys()) == {"id", "title", "url"}  # exact ChatGPT contract
    assert hit["url"] == "https://www.climatecasechart.com/case/probe"


@pytest.mark.asyncio
async def test_fetch_contract(seeded_case: str) -> None:
    r = await fetch("tcg-1")
    assert set(r.keys()) == {"id", "title", "text", "url", "metadata"}  # exact ChatGPT contract
    assert r["id"] == "tcg-1"
    assert "emissions" in r["text"]
    # rich, citable text: structured header + the verbatim summary
    assert "ChatGPTProbe v. State" in r["text"] and "Summary:" in r["text"]
    assert r["url"].startswith("https://www.climatecasechart.com")
    assert r["metadata"]["type"] == "litigation"


@pytest.mark.asyncio
async def test_fetch_missing_id() -> None:
    r = await fetch("does-not-exist-xyz")
    assert set(r.keys()) == {"id", "title", "text", "url", "metadata"}
    assert r["title"] == "Not found"


@pytest.fixture
async def seeded_statute() -> AsyncGenerator[str]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO statute (cclw_id, jurisdiction_code, short_title, status, "
                "text_lang, text) VALUES ('CCLW.test.1.0', 'GB', 'Test Climate Act', "
                "'passed', 'en', 'Section 1. Emissions shall be reduced by 2030.')"
            )
        await conn.commit()
    yield "CCLW.test.1.0"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM statute WHERE cclw_id = 'CCLW.test.1.0'")
        await conn.commit()


@pytest.mark.asyncio
async def test_fetch_routes_statute_id(seeded_statute: str) -> None:
    # an id with the CCLW prefix must resolve to the legislation layer, not a case
    r = await fetch("CCLW.test.1.0")
    assert set(r.keys()) == {"id", "title", "text", "url", "metadata"}
    assert r["metadata"]["type"] == "legislation"
    assert "Emissions shall be reduced" in r["text"]
    assert r["title"] == "Test Climate Act"

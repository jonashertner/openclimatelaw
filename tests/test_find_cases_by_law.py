import json
from collections.abc import AsyncGenerator

import pytest

from server.db import get_pool
from server.tools.laws import find_cases_by_law

_MD = json.dumps(
    {
        "metadata": {
            "concept_preferred_label": [
                "principal_law/Zylonia Climate Act 2030",
                "jurisdiction/US",
            ]
        }
    }
)


@pytest.fixture
async def seeded_law_case() -> AsyncGenerator[None]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO case_record "
                "(sabin_id, canonical_title, jurisdiction_code, status_code, "
                " primary_source, upstream_metadata) "
                "VALUES (%s, %s, 'US', 'decided', 'sabin', %s::jsonb)",
                ("tlaw-zylonia", "Zylonia Coalition v. State", _MD),
            )
        await conn.commit()
    yield
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM case_record WHERE sabin_id = 'tlaw-zylonia'")
        await conn.commit()


@pytest.mark.asyncio
async def test_find_cases_by_law_matches(seeded_law_case: None) -> None:
    r = await find_cases_by_law("Zylonia Climate Act")  # case-insensitive substring
    assert r["count"] >= 1
    assert "tlaw-zylonia" in [x["sabin_id"] for x in r["results"]]


@pytest.mark.asyncio
async def test_find_cases_by_law_no_match(seeded_law_case: None) -> None:
    r = await find_cases_by_law("Phantom Statute XYZ 9999")
    assert r["count"] == 0


@pytest.mark.asyncio
async def test_find_cases_by_law_empty_query() -> None:
    r = await find_cases_by_law("")
    assert r["count"] == 0

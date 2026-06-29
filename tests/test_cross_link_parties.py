import json
from collections.abc import AsyncGenerator

import pytest

from ingest.cross_link import backfill_case_statutes
from ingest.parties import backfill_parties, parse_parties
from server.db import get_pool
from server.tools.cases import get_case


def test_parse_parties() -> None:
    assert parse_parties("Urgenda Foundation v. State of the Netherlands") == [
        ("plaintiff", "Urgenda Foundation"),
        ("defendant", "State of the Netherlands"),
    ]
    assert parse_parties("Acme Corp vs. Energy Board") == [
        ("plaintiff", "Acme Corp"),
        ("defendant", "Energy Board"),
    ]
    assert parse_parties("In re Foo Pipeline") == []
    assert parse_parties("") == []


@pytest.fixture
async def seeded_case_and_statute() -> AsyncGenerator[None]:
    pool = await get_pool()
    md = json.dumps({"metadata": {"concept_preferred_label": ["principal_law/Test Climate Act"]}})
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO statute "
                "(cclw_id, jurisdiction_code, short_title, status, text, provenance) "
                "VALUES ('CCLW.test.xlink', 'US', 'Test Climate Act', 'Legislative', "
                "'text', '{}'::jsonb)"
            )
            await cur.execute(
                "INSERT INTO case_record (sabin_id, canonical_title, jurisdiction_code, "
                "status_code, primary_source, upstream_metadata) "
                "VALUES ('txlink-case', 'Coalition v. State of Test', 'US', 'decided', "
                "'sabin', %s::jsonb)",
                (md,),
            )
        await conn.commit()
    yield
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM case_record WHERE sabin_id = 'txlink-case'")
            await cur.execute("DELETE FROM statute WHERE cclw_id = 'CCLW.test.xlink'")
        await conn.commit()


@pytest.mark.asyncio
async def test_cross_link_case_to_statute(seeded_case_and_statute: None) -> None:
    await backfill_case_statutes()
    case = await get_case("txlink-case")
    assert case is not None
    assert any(ls["cclw_id"] == "CCLW.test.xlink" for ls in case["linked_statutes"])


@pytest.mark.asyncio
async def test_backfill_parties_from_title(seeded_case_and_statute: None) -> None:
    await backfill_parties()
    case = await get_case("txlink-case")
    assert case is not None
    sides = {p["side"]: p["name"] for p in case["parties"]}
    assert sides.get("plaintiff") == "Coalition"
    assert sides.get("defendant") == "State of Test"

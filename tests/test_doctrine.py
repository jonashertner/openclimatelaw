from collections.abc import AsyncGenerator

import pytest

from ingest.doctrine import _verified, pack  # pyright: ignore[reportPrivateUsage]
from server.db import get_pool
from server.tools.doctrine import get_case_doctrine

_POOL = (
    "the court held the state has a duty of care to reduce emissions by at least 25% by "
    "end-2020, and dismissed the state's appeal."
).lower()


def test_verified_quote() -> None:
    assert _verified("duty of care to reduce emissions", _POOL)
    assert not _verified("the state must pay reparations to every citizen", _POOL)
    assert not _verified("", _POOL)


def test_pack_counts_verification() -> None:
    d = {
        "disposition": {
            "outcome": "plaintiff_won",
            "posture": "Supreme Court",
            "quote": "dismissed the state's appeal",
        },
        "holdings": [
            {
                "point": "duty of care exists",
                "quote": "duty of care to reduce emissions",
            },  # verifies
            {"point": "fabricated", "quote": "the state must pay reparations"},  # does not
        ],
        "legal_bases": ["Article 8 ECHR"],
        "significance": "landmark",
    }
    row = pack(d, _POOL)
    assert row["quotes_total"] == 3  # disposition + 2 holdings
    assert row["quotes_verified"] == 2  # disposition quote + holding 1
    import json

    holdings = json.loads(row["holdings"])
    assert holdings[0]["verified"] is True
    assert holdings[1]["verified"] is False


@pytest.fixture
async def seeded_doctrine() -> AsyncGenerator[str]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO case_record (sabin_id, canonical_title, jurisdiction_code, "
                "status_code, primary_source) VALUES ('tdoc-1', 'Doctrine Test v. State', 'US', "
                "'decided', 'sabin') RETURNING id::text"
            )
            row = await cur.fetchone()
            assert row is not None
            cid = row[0]
            holdings = (
                '[{"point": "duty of care", "quote": "ordered the state to act", '
                '"verified": true}]'
            )
            await cur.execute(
                "INSERT INTO case_doctrine (case_id, disposition_outcome, disposition_quote, "
                "holdings, legal_bases, significance, source_kind, model, quotes_total, "
                "quotes_verified) VALUES (%s::uuid, 'plaintiff_won', 'the court ordered the "
                "state to act', %s::jsonb, %s::jsonb, 'landmark', 'case_summary', "
                "'claude-sonnet-4-6', 1, 1)",
                (cid, holdings, '["Article 8 ECHR"]'),
            )
        await conn.commit()
    yield cid
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM case_record WHERE sabin_id = 'tdoc-1'")
        await conn.commit()


@pytest.mark.asyncio
async def test_get_case_doctrine(seeded_doctrine: str) -> None:
    r = await get_case_doctrine("tdoc-1")
    assert r is not None
    assert r["available"] is True
    assert r["disposition"]["outcome"] == "plaintiff_won"
    assert r["holdings"][0]["verified"] is True
    assert "Article 8 ECHR" in r["legal_bases"]
    assert r["provenance"]["quotes_verified"] == 1


@pytest.mark.asyncio
async def test_get_case_doctrine_absent(seeded_doctrine: str) -> None:
    # the case exists but query a different one with no doctrine row → available:false
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO case_record (sabin_id, canonical_title, jurisdiction_code, "
                "status_code, primary_source) VALUES ('tdoc-2', 'No Doctrine v. X', 'US', "
                "'decided', 'sabin')"
            )
        await conn.commit()
    r = await get_case_doctrine("tdoc-2")
    assert r is not None and r["available"] is False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM case_record WHERE sabin_id = 'tdoc-2'")
        await conn.commit()

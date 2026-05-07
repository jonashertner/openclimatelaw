import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import ParsedCase, parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool

URGENDA_SABIN_ID = "urgenda-foundation-v-state-of-the-netherlands"


@pytest.fixture(autouse=True)
async def _cleanup_urgenda() -> AsyncGenerator[None]:  # pyright: ignore[reportUnusedFunction]
    """Remove any Urgenda row (and cascaded children) before and after each test."""
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM case_record WHERE sabin_id = %s", (URGENDA_SABIN_ID,))
    yield
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM case_record WHERE sabin_id = %s", (URGENDA_SABIN_ID,))


@pytest.fixture
async def parsed_urgenda() -> ParsedCase:
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    return parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="fixture-2026-05-06",
    )


@pytest.mark.asyncio
async def test_upsert_inserts_new_case(parsed_urgenda: ParsedCase) -> None:
    pool = await get_pool()
    case_id = await upsert_case(pool, parsed_urgenda)
    assert case_id is not None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT canonical_title FROM case_record WHERE id = %s", (case_id,))
            row = await cur.fetchone()
            assert row is not None
            assert "Urgenda" in row[0]

            await cur.execute("SELECT count(*) FROM case_party WHERE case_id = %s", (case_id,))
            count_row = await cur.fetchone()
            assert count_row is not None
            (n_parties,) = count_row
            assert n_parties == 3

            await cur.execute("SELECT count(*) FROM case_claim_type WHERE case_id = %s", (case_id,))
            count_row = await cur.fetchone()
            assert count_row is not None
            (n_claims,) = count_row
            assert n_claims == 3

            await cur.execute("SELECT count(*) FROM document WHERE case_id = %s", (case_id,))
            count_row = await cur.fetchone()
            assert count_row is not None
            (n_docs,) = count_row
            assert n_docs == 3

            await cur.execute("SELECT count(*) FROM citation_string WHERE case_id = %s", (case_id,))
            count_row = await cur.fetchone()
            assert count_row is not None
            (n_cite,) = count_row
            assert n_cite == 2


@pytest.mark.asyncio
async def test_upsert_is_idempotent(parsed_urgenda: ParsedCase) -> None:
    pool = await get_pool()
    case_id_1 = await upsert_case(pool, parsed_urgenda)
    case_id_2 = await upsert_case(pool, parsed_urgenda)
    assert case_id_1 == case_id_2

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            sabin_id: str = parsed_urgenda.case["sabin_id"]
            await cur.execute(
                "SELECT count(*) FROM case_record WHERE sabin_id = %s",
                (sabin_id,),
            )
            count_row = await cur.fetchone()
            assert count_row is not None
            (n,) = count_row
            assert n == 1

            await cur.execute("SELECT count(*) FROM case_party WHERE case_id = %s", (case_id_1,))
            count_row = await cur.fetchone()
            assert count_row is not None
            (n_parties,) = count_row
            assert n_parties == 3

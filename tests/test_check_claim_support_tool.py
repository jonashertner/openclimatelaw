import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.check_support import check_claim_support


@pytest.fixture
async def upserted_urgenda_id() -> AsyncGenerator[str]:
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record, retrieved_at=datetime(2026, 5, 6, tzinfo=UTC), upstream_version="fixture"
    )
    case_id = await upsert_case(pool, parsed)
    yield case_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM case_record WHERE sabin_id = %s",
                ("urgenda-foundation-v-state-of-the-netherlands",),
            )


@pytest.mark.asyncio
async def test_check_claim_support_passes_for_real_summary_substring(
    upserted_urgenda_id: str,
) -> None:
    quote = "the right to family life from the dangers of climate change"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="case_summary"
    )
    assert result["supported"] is True


@pytest.mark.asyncio
async def test_check_claim_support_fails_for_invented_quote(upserted_urgenda_id: str) -> None:
    quote = "the court ordered immediate cessation of all fossil-fuel extraction"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="case_summary"
    )
    assert result["supported"] is False
    assert "case_summary" in result["reason"]


@pytest.mark.asyncio
async def test_check_claim_support_passes_for_citation_string_substring(
    upserted_urgenda_id: str,
) -> None:
    quote = "ECLI:NL:HR:2019:2007"
    result = await check_claim_support(
        quote=quote, source_id=upserted_urgenda_id, source_kind="citation_string"
    )
    assert result["supported"] is True


@pytest.mark.asyncio
async def test_check_claim_support_fails_when_source_not_found() -> None:
    result = await check_claim_support(
        quote="anything", source_id="nonexistent", source_kind="case_summary"
    )
    assert result["supported"] is False
    assert "not found" in result["reason"].lower()


@pytest.mark.asyncio
async def test_check_claim_support_invalid_source_kind_raises() -> None:
    with pytest.raises(ValueError, match="invalid source_kind"):
        await check_claim_support(quote="x", source_id="any", source_kind="bogus_kind")

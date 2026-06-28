import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.cite import cite


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
async def test_cite_returns_sabin_format_in_english(upserted_urgenda_id: str) -> None:
    result = await cite(case_id=upserted_urgenda_id, lang="en", format="sabin")
    assert result is not None
    assert "ECLI:NL:HR:2019:2007" in result["citation_string"]
    assert result["lang"] == "en"
    assert result["format"] == "sabin"


@pytest.mark.asyncio
async def test_cite_returns_native_format_in_dutch(upserted_urgenda_id: str) -> None:
    result = await cite(
        case_id="urgenda-foundation-v-state-of-the-netherlands", lang="nl", format="native"
    )
    assert result is not None
    assert "HR 20 december 2019" in result["citation_string"]


@pytest.mark.asyncio
async def test_cite_falls_back_when_format_not_available(upserted_urgenda_id: str) -> None:
    # An unsupported format must NOT return a silent null (which could tempt fabrication);
    # it falls back to the case's best available citation, flagged as a fallback.
    result = await cite(case_id=upserted_urgenda_id, lang="en", format="oscola")
    assert result is not None
    assert result["fallback"] is True
    assert result["requested_format"] == "oscola"
    assert result["citation_string"]


@pytest.mark.asyncio
async def test_cite_returns_none_when_case_not_found() -> None:
    result = await cite(case_id="nonexistent", lang="en", format="sabin")
    assert result is None

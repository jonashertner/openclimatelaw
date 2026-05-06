import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.tools.contracts.attest import attest_response


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
async def test_attest_passes_when_no_citations_present() -> None:
    result = await attest_response(
        draft_text="The court ruled in favour of the plaintiffs.",
        retrieved_ids=[],
    )
    assert result["passed"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_attest_passes_when_citation_matches_retrieved(
    upserted_urgenda_id: str,
) -> None:
    draft = (
        "The Supreme Court of the Netherlands held in ECLI:NL:HR:2019:2007 that "
        "the state has a positive obligation to protect the right to life."
    )
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[upserted_urgenda_id],
    )
    assert result["passed"] is True
    assert result["violations"] == []


@pytest.mark.asyncio
async def test_attest_flags_unretrieved_citation() -> None:
    draft = "Citing ECLI:DE:BVERFG:2021:rs20210324.1bvr265618 for the proposition that..."
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[],
    )
    assert result["passed"] is False
    assert len(result["violations"]) == 1
    v = result["violations"][0]
    assert v["text"] == "ECLI:DE:BVERFG:2021:rs20210324.1bvr265618"
    assert v["format"] == "ecli"


@pytest.mark.asyncio
async def test_attest_flags_invented_us_reporter_citation(
    upserted_urgenda_id: str,
) -> None:
    draft = "see Massachusetts v. EPA, 549 U.S. 497 (2007)"
    result = await attest_response(
        draft_text=draft,
        retrieved_ids=[upserted_urgenda_id],
    )
    assert result["passed"] is False
    assert any(v["format"] == "us_reporter" for v in result["violations"])

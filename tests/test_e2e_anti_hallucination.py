import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastmcp import Client

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import get_pool
from server.main import build_mcp


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
async def test_full_anti_hallucination_workflow(upserted_urgenda_id: str) -> None:
    """Simulate an LLM workflow: get_case -> cite -> compose response -> attest_response."""
    mcp = build_mcp()
    async with Client(mcp) as client:
        # Step 1: LLM retrieves the case.
        case_result = await client.call_tool(
            "get_case", {"case_id_or_sabin_id": upserted_urgenda_id}
        )
        assert case_result.structured_content is not None
        case = case_result.structured_content["result"]

        # Step 2: LLM asks for a verbatim citation in en/sabin.
        cite_result = await client.call_tool(
            "cite",
            {"case_id": upserted_urgenda_id, "lang": "en", "format": "sabin"},
        )
        assert cite_result.structured_content is not None
        citation = cite_result.structured_content["result"]["citation_string"]

        # Step 3: LLM composes a response embedding the citation.
        draft = (
            f"The Supreme Court of the Netherlands held in {citation} that the state "
            f"must reduce greenhouse-gas emissions. {case['summary'][:120]}"
        )

        # Step 4: attest_response validates.
        # Note: attest_response returns dict (never None), so FastMCP surfaces the dict
        # directly in structured_content without a "result" wrapper.
        attest_result = await client.call_tool(
            "attest_response",
            {"draft_text": draft, "retrieved_ids": [upserted_urgenda_id]},
        )
        assert attest_result.structured_content is not None
        assert attest_result.structured_content["passed"] is True

        # Step 5: A bad draft (un-retrieved citation) fails attestation.
        bad_draft = "Citing 549 U.S. 497 (2007), the court reasoned..."
        bad_attest = await client.call_tool(
            "attest_response",
            {"draft_text": bad_draft, "retrieved_ids": [upserted_urgenda_id]},
        )
        assert bad_attest.structured_content is not None
        assert bad_attest.structured_content["passed"] is False
        violations = bad_attest.structured_content["violations"]
        assert any("U.S. 497" in v["text"] for v in violations)

        # Step 6: check_claim_support catches a misquote.
        # Note: check_claim_support returns dict (never None), so no "result" wrapper.
        bad_quote = "the court ordered immediate cessation of all fossil-fuel extraction"
        check_result = await client.call_tool(
            "check_claim_support",
            {
                "quote": bad_quote,
                "source_id": upserted_urgenda_id,
                "source_kind": "case_summary",
            },
        )
        assert check_result.structured_content is not None
        assert check_result.structured_content["supported"] is False

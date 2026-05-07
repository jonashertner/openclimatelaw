import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server.db import close_pool, get_pool
from server.main import build_mcp


@pytest.mark.asyncio
async def test_ingest_then_query_via_mcp_client():
    # Ingest the Urgenda fixture
    pool = await get_pool()
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="fixture-e2e",
    )
    case_id = await upsert_case(pool, parsed)

    try:
        # Query via FastMCP Client (in-process)
        mcp = build_mcp()
        async with Client(mcp) as client:
            # get_statistics should now show >=1 case, >=3 documents, >=1 jurisdiction
            stats_result = await client.call_tool("get_statistics", {"scope": "all"})
            stats = stats_result.structured_content
            assert stats is not None
            assert stats["totals"]["case_count"] >= 1
            assert stats["totals"]["document_count"] >= 3
            assert stats["totals"]["jurisdiction_count"] >= 1

            # get_case by UUID
            case_by_uuid_result = await client.call_tool(
                "get_case", {"case_id_or_sabin_id": case_id}
            )
            assert case_by_uuid_result.structured_content is not None
            case_by_uuid_data: Any = case_by_uuid_result.structured_content.get("result")
            assert case_by_uuid_data is not None
            assert "Urgenda" in case_by_uuid_data["canonical_title"]

            # get_case by sabin_id
            case_by_sabin_result = await client.call_tool(
                "get_case",
                {"case_id_or_sabin_id": "urgenda-foundation-v-state-of-the-netherlands"},
            )
            assert case_by_sabin_result.structured_content is not None
            case_by_sabin: Any = case_by_sabin_result.structured_content.get("result")
            assert case_by_sabin is not None
            assert case_by_sabin["id"] == case_id
            expected_claim_types = ["constitutional", "human_rights", "tort"]
            assert sorted(case_by_sabin["claim_types"]) == expected_claim_types
            assert case_by_sabin["status_code"] == "decided"
            assert case_by_sabin["outcome_code"] == "plaintiff_won"
            assert "summary" in case_by_sabin["provenance"]
            assert case_by_sabin["provenance"]["summary"]["source"] == "sabin"
    finally:
        # Cleanup so other tests start with empty DB
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM case_record WHERE sabin_id = %s",
                    ("urgenda-foundation-v-state-of-the-netherlands",),
                )
        await close_pool()

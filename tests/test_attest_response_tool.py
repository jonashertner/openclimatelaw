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


@pytest.mark.asyncio
async def test_attest_flags_fabricated_quote_near_citation(
    upserted_urgenda_id: str,
) -> None:
    draft = (
        "In ECLI:NL:HR:2019:2007 the court stated: "
        '"the State must pay five billion euros in immediate climate reparations to every citizen."'
    )
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_passes_verbatim_quote_from_summary(
    upserted_urgenda_id: str,
) -> None:
    from server.tools.cases import get_case

    case = await get_case(upserted_urgenda_id)
    assert case is not None
    # A clean, verbatim phrase from the summary (word-joined so whitespace normalises).
    chunk = " ".join((case["summary"] or "").split()[3:18])
    draft = f'In ECLI:NL:HR:2019:2007 the court reasoned: "{chunk}"'
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is True, result["violations"]


@pytest.mark.asyncio
async def test_attest_flags_long_fabricated_quote(upserted_urgenda_id: str) -> None:
    # A 600+ char fabricated holding must NOT escape the rail via a length ceiling.
    fake = "The State is hereby ordered to " + "pay sweeping climate reparations forthwith " * 14
    draft = f'In ECLI:NL:HR:2019:2007 the court held: "{fake}"'
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_flags_mixed_delimiter_quote(upserted_urgenda_id: str) -> None:
    # Opening curly quote, closing straight quote (a common smart-quote artifact).
    fake = "the State must pay five billion euros in immediate climate reparations to every citizen"
    draft = f'In ECLI:NL:HR:2019:2007 the court held: “{fake}"'
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_flags_fabricated_quote_with_no_nearby_citation(
    upserted_urgenda_id: str,
) -> None:
    # No citation anywhere in the draft — the quote must STILL be audited (decoupled
    # from citation proximity). This was the false-negative hole the audit found.
    draft = (
        'The court declared: "the State must pay five billion euros in immediate '
        'climate reparations to every citizen of the realm forthwith."'
    )
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_flags_doubled_single_quote_delimiter(
    upserted_urgenda_id: str,
) -> None:
    # Doubled curly-single quotes used as a double-quote delimiter must not bypass the
    # rail (the false-negative the adversarial review found).
    fake = "the State must reduce emissions by ninety-five percent within five years"
    dq = chr(0x2019) * 2  # doubled right-single-quote used as a double-quote delimiter
    draft = f"The court reasoned that {dq}{fake}{dq} and rejected all objections."
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_flags_curly_open_doubled_single_close(
    upserted_urgenda_id: str,
) -> None:
    # Opening curly-double quote, closing doubled curly-single.
    fake = "the State must reduce emissions by ninety-five percent within five years"
    draft = f"The court held: {chr(0x201C)}{fake}{chr(0x2019) * 2}"
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v["category"] == "quote" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_flags_fabricated_uk_neutral_citation(
    upserted_urgenda_id: str,
) -> None:
    draft = "See Plan B Earth v Prime Minister [2099] EWHC 9999 (Admin), binding authority."
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is False
    assert any(v.get("format") == "uk_neutral" for v in result["violations"])


@pytest.mark.asyncio
async def test_attest_passes_quote_from_document_text(
    upserted_urgenda_id: str,
) -> None:
    # A verbatim quote that appears only in the DECISION document (not the summary)
    # must verify — the quote rail now loads document text, not just summaries.
    pool = await get_pool()
    sentence = (
        "This precise operative sentence appears only in the decision document "
        "and nowhere in the case summary."
    )
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO document (case_id, category_code, title, upstream_url, text) "
                "VALUES (%s::uuid, 'opinion', 'Test Decision', 'https://example.org/d', %s)",
                (upserted_urgenda_id, f"Preamble text. {sentence} Concluding text."),
            )
        await conn.commit()
    draft = f'In ECLI:NL:HR:2019:2007 the court held: "{sentence}"'
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is True, result["violations"]


@pytest.mark.asyncio
async def test_attest_passes_verbatim_quote_with_zero_width_char(
    upserted_urgenda_id: str,
) -> None:
    from server.tools.cases import get_case

    case = await get_case(upserted_urgenda_id)
    assert case is not None
    chunk = " ".join((case["summary"] or "").split()[3:18])
    zw = chunk[:10] + "​" + chunk[10:]  # zero-width space artifact
    draft = f'In ECLI:NL:HR:2019:2007 the court reasoned: "{zw}"'
    result = await attest_response(draft, [upserted_urgenda_id])
    assert result["passed"] is True, result["violations"]

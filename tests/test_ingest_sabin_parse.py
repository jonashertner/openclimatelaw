import json
from datetime import UTC, datetime
from pathlib import Path

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import ParsedCase, parse_sabin_record


def test_parse_returns_canonical_dicts():
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed: ParsedCase = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="fixture-2026-05-06",
    )
    case = parsed.case
    assert case["sabin_id"] == "urgenda-foundation-v-state-of-the-netherlands"
    assert case["canonical_title"].startswith("Urgenda")
    assert case["jurisdiction_code"] == "NL"
    assert case["court_id"] == "nl-hoge-raad"
    assert case["status_code"] == "decided"
    assert case["outcome_code"] == "plaintiff_won"
    assert case["primary_source"] == "sabin"
    assert "summary" in case["provenance"]
    assert case["provenance"]["summary"]["source"] == "sabin"

    sides = sorted({p["side"] for p in parsed.parties})
    assert sides == ["defendant", "plaintiff"]
    assert all("ord" in p for p in parsed.parties)

    assert sorted(parsed.claim_type_codes) == ["constitutional", "human_rights", "tort"]

    assert len(parsed.documents) == 3
    assert all("upstream_url" in d for d in parsed.documents)
    assert parsed.documents[0]["category_code"] == "opinion"

    cs_langs = sorted({c["lang"] for c in parsed.citation_strings})
    assert cs_langs == ["en", "nl"]


def test_parse_assigns_sequential_ord_per_side():
    fixture = json.loads(Path("tests/fixtures/sabin_urgenda.json").read_text())
    record = SabinCaseRecord.model_validate(fixture)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="v1",
    )
    plaintiff_ords = sorted(p["ord"] for p in parsed.parties if p["side"] == "plaintiff")
    defendant_ords = sorted(p["ord"] for p in parsed.parties if p["side"] == "defendant")
    assert plaintiff_ords == list(range(len(plaintiff_ords)))
    assert defendant_ords == list(range(len(defendant_ords)))

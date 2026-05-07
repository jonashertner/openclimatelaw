import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingest.sabin.models import SabinCaseRecord, SabinDocument, SabinParty


def test_party_minimum_required_fields():
    p = SabinParty(name="Urgenda Foundation", side="plaintiff")
    assert p.name == "Urgenda Foundation"
    assert p.side == "plaintiff"
    assert p.party_type is None


def test_party_rejects_invalid_side():
    with pytest.raises(ValidationError):
        SabinParty(name="X", side="defendant_or_other")  # type: ignore[arg-type]


def test_document_minimum_required_fields():
    d = SabinDocument(
        title="District Court Decision",
        category="opinion",
        upstream_url="https://climatecasechart.com/case/urgenda/decision-1",  # type: ignore[arg-type]
    )
    assert d.title == "District Court Decision"


def test_case_record_round_trips_from_fixture():
    fixture = Path("tests/fixtures/sabin_urgenda.json")
    if not fixture.exists():
        pytest.skip(f"fixture not yet authored: {fixture}")
    payload = json.loads(fixture.read_text())
    case = SabinCaseRecord.model_validate(payload)
    assert case.sabin_id is not None
    assert case.canonical_title
    assert case.jurisdiction_code == "NL"
    assert any(p.side == "plaintiff" for p in case.parties)
    assert any(p.side == "defendant" for p in case.parties)
    assert case.status_code in {"filed", "pending", "decided", "settled", "dismissed", "withdrawn"}
    assert len(case.documents) >= 1

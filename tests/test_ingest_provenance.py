from datetime import UTC, datetime

import pytest

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry


def test_provenance_entry_serializes_to_dict():
    entry = ProvenanceEntry(
        source="sabin",
        retrieved_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
        upstream_version="fixture-2026-05-06",
    )
    d = entry.to_dict()
    assert d["source"] == "sabin"
    assert d["retrieved_at"] == "2026-05-06T12:00:00+00:00"
    assert d["upstream_version"] == "fixture-2026-05-06"


def test_provenance_builder_tracks_multiple_fields():
    entry = ProvenanceEntry(
        source="sabin",
        retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
        upstream_version="v1",
    )
    pb = ProvenanceBuilder()
    pb.set("summary", entry)
    pb.set("status", entry)
    out = pb.build()
    assert set(out.keys()) == {"summary", "status"}
    assert out["summary"]["source"] == "sabin"
    assert out["status"]["upstream_version"] == "v1"


def test_provenance_builder_overwrite_replaces_entry():
    pb = ProvenanceBuilder()
    pb.set("summary", ProvenanceEntry("sabin", datetime(2026, 1, 1, tzinfo=UTC), "v1"))
    pb.set("summary", ProvenanceEntry("manual", datetime(2026, 2, 1, tzinfo=UTC), "v2"))
    out = pb.build()
    assert out["summary"]["source"] == "manual"
    assert out["summary"]["upstream_version"] == "v2"


def test_provenance_entry_invalid_source_raises():
    with pytest.raises(ValueError, match="invalid source"):
        ProvenanceEntry(
            source="bogus",  # type: ignore[arg-type]
            retrieved_at=datetime(2026, 5, 6, tzinfo=UTC),
            upstream_version="v1",
        )

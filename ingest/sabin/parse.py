from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry
from ingest.sabin.models import SabinCaseRecord


@dataclass
class ParsedCase:
    """Canonical dicts ready for UPSERT into the schema."""

    case: dict[str, Any]
    parties: list[dict[str, Any]]
    claim_type_codes: list[str]
    documents: list[dict[str, Any]]
    citation_strings: list[dict[str, Any]]


def parse_sabin_record(
    record: SabinCaseRecord, retrieved_at: datetime, upstream_version: str
) -> ParsedCase:
    """Translate a Sabin-shaped Pydantic model into canonical-schema dicts."""

    pb = ProvenanceBuilder()
    sabin_provenance = ProvenanceEntry(
        source="sabin", retrieved_at=retrieved_at, upstream_version=upstream_version
    )
    for field_name in (
        "canonical_title",
        "jurisdiction_code",
        "court_id",
        "filing_date",
        "decision_date",
        "status_code",
        "outcome_code",
        "summary",
    ):
        if getattr(record, field_name) is not None:
            pb.set(field_name, sabin_provenance)

    case: dict[str, Any] = {
        "sabin_id": record.sabin_id,
        "canonical_title": record.canonical_title,
        "jurisdiction_code": record.jurisdiction_code,
        "court_id": record.court_id,
        "filing_date": record.filing_date,
        "decision_date": record.decision_date,
        "status_code": record.status_code,
        "outcome_code": record.outcome_code,
        "summary": record.summary,
        "summary_lang": record.summary_lang,
        "primary_source": "sabin",
        "provenance": pb.build(),
    }

    side_counters: dict[str, int] = defaultdict(int)
    parties: list[dict[str, Any]] = []
    for party in record.parties:
        ord_value = side_counters[party.side]
        side_counters[party.side] += 1
        parties.append(
            {
                "side": party.side,
                "name": party.name,
                "party_type": party.party_type,
                "ord": ord_value,
            }
        )

    documents: list[dict[str, Any]] = []
    for doc in record.documents:
        documents.append(
            {
                "title": doc.title,
                "category_code": doc.category,
                "upstream_url": str(doc.upstream_url),
                "filed_date": doc.filed_date,
                "filed_by": doc.filed_by,
                "provenance": pb.build(),
            }
        )

    citation_strings: list[dict[str, Any]] = []
    for cs in record.citation_strings:
        citation_strings.append({"lang": cs.lang, "format": cs.format, "text": cs.text})

    return ParsedCase(
        case=case,
        parties=parties,
        claim_type_codes=list(record.claim_types),
        documents=documents,
        citation_strings=citation_strings,
    )

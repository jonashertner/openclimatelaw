from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

PartySide = Literal["plaintiff", "defendant", "intervenor", "amicus"]
PartyType = Literal["individual", "ngo", "corporation", "state", "sub_state"]
DocumentCategory = Literal[
    "opinion", "order", "complaint", "brief", "agency_record", "settlement", "judgment", "dissent"
]


class SabinParty(BaseModel):
    name: str
    side: PartySide
    party_type: PartyType | None = None


class SabinDocument(BaseModel):
    title: str
    category: DocumentCategory
    upstream_url: HttpUrl
    filed_date: date | None = None
    filed_by: str | None = None


class SabinCitationString(BaseModel):
    lang: str = Field(min_length=2, max_length=5)
    format: str
    text: str


class SabinCaseRecord(BaseModel):
    """The shape of one Sabin case as exposed by climatecasechart.com."""

    sabin_id: str
    canonical_title: str
    jurisdiction_code: str = Field(min_length=2, max_length=10)
    court_id: str | None = None
    filing_date: date | None = None
    decision_date: date | None = None
    status_code: str
    outcome_code: str | None = None
    summary: str | None = None
    summary_lang: str = "en"
    parties: list[SabinParty] = Field(default_factory=list)  # type: ignore[arg-type]
    claim_types: list[str] = Field(default_factory=list)  # type: ignore[arg-type]
    documents: list[SabinDocument] = Field(default_factory=list)  # type: ignore[arg-type]
    citation_strings: list[SabinCitationString] = Field(default_factory=list)  # type: ignore[arg-type]
    upstream_url: HttpUrl | None = None

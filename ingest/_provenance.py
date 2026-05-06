from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ProvenanceSource = Literal["sabin", "climate_rights", "c2li", "melbourne", "redline", "manual"]
VALID_PROVENANCE_SOURCES: set[str] = {
    "sabin",
    "climate_rights",
    "c2li",
    "melbourne",
    "redline",
    "manual",
}


@dataclass(frozen=True)
class ProvenanceEntry:
    """A single field-level provenance record."""

    source: ProvenanceSource
    retrieved_at: datetime
    upstream_version: str

    def __post_init__(self) -> None:
        if self.source not in VALID_PROVENANCE_SOURCES:
            raise ValueError(
                f"invalid source: {self.source!r} "
                f"(must be one of {sorted(VALID_PROVENANCE_SOURCES)})"
            )
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "retrieved_at": self.retrieved_at.isoformat(),
            "upstream_version": self.upstream_version,
        }


@dataclass
class ProvenanceBuilder:
    """Accumulator for field-level provenance, serialised to a JSONB-shaped dict."""

    _entries: dict[str, ProvenanceEntry] = field(
        default_factory=lambda: {}  # type: ignore[var-annotated]
    )

    def set(self, field_name: str, entry: ProvenanceEntry) -> None:
        self._entries[field_name] = entry

    def build(self) -> dict[str, dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._entries.items()}

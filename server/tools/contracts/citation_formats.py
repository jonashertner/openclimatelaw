import re
from dataclasses import dataclass

_PATTERNS: dict[str, re.Pattern[str]] = {
    # ECLI: European Case Law Identifier. Country (2 letters), Court (1-7 alnum),
    # Year (4 digits), ordinal (1-25 alnum chars).
    "ecli": re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Z0-9.]{1,25}\b"),
    # BVerfGE: German Federal Constitutional Court. "BVerfGE 157, 30" or "BVerfGE 157, 30 (1)".
    "bverfge": re.compile(r"\bBVerfGE\s+\d{1,3},\s*\d{1,4}(?:\s*\(\d+\))?\b"),
    # BGE: Swiss Federal Court. "BGE 145 IV 100".
    "bge": re.compile(r"\bBGE\s+\d{1,3}\s+(?:I|II|III|IV|V)\s+\d{1,4}\b"),
    # US reporter style. Volume + reporter abbrev + page, optional (Year). E.g.
    # "549 U.S. 497", "123 F.3d 456 (2d Cir. 2020)".
    "us_reporter": re.compile(
        r"\b\d{1,4}\s+(?:U\.S\.|F\.\d?[a-z]?|F\.\s*Supp\.|S\.\s*Ct\.)\s+\d{1,4}"
        r"(?:\s*\([^)]{1,40}\))?\b"
    ),
}


@dataclass(frozen=True)
class CitationSpan:
    format_name: str
    start: int
    end: int
    text: str


def find_citation_spans(text: str) -> list[CitationSpan]:
    """Scan `text` for known citation formats; return all non-overlapping matches."""
    spans: list[CitationSpan] = []
    for format_name, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            spans.append(
                CitationSpan(
                    format_name=format_name,
                    start=match.start(),
                    end=match.end(),
                    text=match.group(0),
                )
            )
    spans.sort(key=lambda s: s.start)
    return spans

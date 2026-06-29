import re
from dataclasses import dataclass

# Citation-format patterns for the attestation rail. Each is anchored and specific
# enough that plain prose does not match (a bracketed year alone is not a citation —
# a court abbreviation must follow). Climate litigation is global, so we cover the
# major common-law neutral-citation systems + the EU + the formats already supported.
_PATTERNS: dict[str, re.Pattern[str]] = {
    # ECLI: European Case Law Identifier. Country, Court, Year, ordinal.
    "ecli": re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]{1,7}:\d{4}:[A-Za-z0-9.]{1,25}\b"),
    # BVerfGE: German Federal Constitutional Court. "BVerfGE 157, 30 (1)".
    "bverfge": re.compile(r"\bBVerfGE\s+\d{1,3},\s*\d{1,4}(?:\s*\(\d+\))?\b"),
    # BGE: Swiss Federal Court. "BGE 145 IV 100".
    "bge": re.compile(r"\bBGE\s+\d{1,3}\s+(?:I|II|III|IV|V)\s+\d{1,4}\b"),
    # US reporters: U.S., S. Ct., L. Ed.(2d), F. Supp.(2d/3d), F.2d/3d/4th. Optional (court Year).
    "us_reporter": re.compile(
        r"\b\d{1,4}\s+(?:U\.S\.|S\.\s*Ct\.|L\.\s*Ed\.\s*2d|L\.\s*Ed\.|"
        r"F\.\s*Supp\.\s*\dd|F\.\s*Supp\.|F\.\s*\d[a-z]{1,2})\s+\d{1,4}"
        r"(?:\s*\([^)]{1,40}\))?\b"
    ),
    # UK / Scotland neutral citation: "[2024] UKSC 20", "[2021] EWHC 1234 (Admin)".
    "uk_neutral": re.compile(
        r"\[\d{4}\]\s+(?:UKSC|UKPC|UKHL|EWCA|EWHC|EWFC|EWCOP|CSOH|CSIH|UKUT|UKFTT)\s+\d{1,5}"
        r"(?:\s*\((?:Admin|Comm|Ch|QB|KB|Pat|TCC|Civ|Crim|Fam|IAC)\))?"
    ),
    # Australia / New Zealand neutral citation: "[2024] HCA 9", "[2021] NSWLEC 5".
    "au_nz_neutral": re.compile(
        r"\[\d{4}\]\s+(?:HCA|FCAFC|FCA|NSWLEC|NSWCA|NSWSC|VSC|VSCA|QSC|QCA|"
        r"NZSC|NZCA|NZHC|NZEnvC)\s+\d{1,5}"
    ),
    # Canada neutral citation: "2019 SCC 5", "2021 FCA 100" (year first, no brackets).
    "ca_neutral": re.compile(r"\b\d{4}\s+(?:SCC|FCA|FC|ONCA|ONSC|BCCA|BCSC|QCCA|ABCA)\s+\d{1,4}\b"),
    # Ireland neutral citation: "[2020] IESC 49".
    "ie_neutral": re.compile(r"\[\d{4}\]\s+(?:IESC|IECA|IEHC)\s+\d{1,4}"),
    # South Africa neutral citation: "[2017] ZACC 12".
    "za_neutral": re.compile(r"\[\d{4}\]\s+(?:ZACC|ZASCA|ZAGPPHC|ZAWCHC|ZAGPJHC)\s+\d{1,4}"),
    # India Supreme Court Cases: "(2019) 5 SCC 123".
    "in_scc": re.compile(r"\(\d{4}\)\s+\d{1,2}\s+SCC\s+\d{1,4}"),
    # EU Court of Justice / General Court case number: "C-123/20", "T-45/19".
    "cjeu": re.compile(r"\b[CTF]-\d{1,4}/\d{2}\b"),
}


@dataclass(frozen=True)
class CitationSpan:
    format_name: str
    start: int
    end: int
    text: str


def find_citation_spans(text: str) -> list[CitationSpan]:
    """Scan `text` for known citation formats; return non-overlapping matches by position."""
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
    spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
    # Drop spans overlapping an already-kept (earlier, longer) span, so one citation
    # matched by two patterns is reported once.
    kept: list[CitationSpan] = []
    last_end = -1
    for s in spans:
        if s.start >= last_end:
            kept.append(s)
            last_end = s.end
    return kept

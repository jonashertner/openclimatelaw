# pyright: basic
"""DEPRECATED — direct-from-source scraper has replaced this.

This module's `bulk_ingest()` orchestrator is no longer invoked. We've moved
to `ingest.sabin.scraper` which scrapes www.climatecasechart.com directly
(parsing the same family record from the page's __NEXT_DATA__ JSON, plus
downloading PDFs from climatecasechart.com/wp-content/uploads/...).

Why deprecated:
- We don't want a third-party API (CPR) as a hard dependency.
- The Sabin website + WordPress-uploaded PDFs are the durable source-of-truth.
- Bulk distribution via HF dataset is the canonical artifact, not API polling.

Helper functions kept here are still used by the new scraper because the
JSON shape of the embedded __NEXT_DATA__ family record is identical to the
CPR API response — Sabin's site is rendered by the same backend, but we
consume the rendered HTML, not the API:

- parse_family_record (reused; was parse_cpr_family)
- autoupsert_vocabularies (reused)
- upsert_parsed_case_minimal (reused; extended to optionally write document text)
- slugify, map_status_freetext_to_code, alpha3_to_alpha2, _parse_date (reused)

The constants below (CPR_API_BASE, DEFAULT_CORPUS_ID, fetch_families_page,
iter_all_families, bulk_ingest) are kept for archive value but should not
be invoked in production code paths.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry
from ingest.sabin.parse import ParsedCase

CPR_API_BASE = "https://api.climatepolicyradar.org"
CCC_BASE = "https://www.climatecasechart.com"
DEFAULT_CORPUS_ID = "Academic.corpus.Litigation.n0000"
PAGE_SIZE = 100
USER_AGENT = "OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)"
POLITE_DELAY = 1.0  # seconds between requests
DEFAULT_RETRIEVED_AT = lambda: datetime.now(tz=UTC)  # noqa: E731

# Map ISO 3166-1 alpha-3 → alpha-2. Subset; extend as needed at upsert time.
ISO_ALPHA3_TO_ALPHA2: dict[str, str] = {
    "USA": "US",
    "DEU": "DE",
    "GBR": "GB",
    "FRA": "FR",
    "ITA": "IT",
    "ESP": "ES",
    "NLD": "NL",
    "BEL": "BE",
    "CHE": "CH",
    "AUT": "AT",
    "POL": "PL",
    "PRT": "PT",
    "AUS": "AU",
    "NZL": "NZ",
    "CAN": "CA",
    "BRA": "BR",
    "ARG": "AR",
    "CHL": "CL",
    "MEX": "MX",
    "COL": "CO",
    "PER": "PE",
    "ECU": "EC",
    "VEN": "VE",
    "JPN": "JP",
    "KOR": "KR",
    "CHN": "CN",
    "IND": "IN",
    "IDN": "ID",
    "PHL": "PH",
    "PAK": "PK",
    "BGD": "BD",
    "VNM": "VN",
    "THA": "TH",
    "MYS": "MY",
    "SGP": "SG",
    "ZAF": "ZA",
    "KEN": "KE",
    "NGA": "NG",
    "EGY": "EG",
    "MAR": "MA",
    "GHA": "GH",
    "SWE": "SE",
    "NOR": "NO",
    "FIN": "FI",
    "DNK": "DK",
    "ISL": "IS",
    "IRL": "IE",
    "RUS": "RU",
    "TUR": "TR",
    "ISR": "IL",
    "ARE": "AE",
    "SAU": "SA",
    "FJI": "FJ",
    "TUV": "TV",
    "VUT": "VU",
    "SLB": "SB",
    "WSM": "WS",
}


# Map free-text Sabin "status" sentences → our status enum.
def map_status_freetext_to_code(status_text: str | None) -> str:
    """Heuristically map Sabin's free-text status to our enum.

    Sabin records carry status as a sentence (e.g. "Plaintiffs' motion for summary
    judgment denied...") rather than an enum value. We default to 'decided' when
    any status text is present (because Sabin only adds the field after a court
    has acted), 'pending' otherwise.
    """
    if not status_text:
        return "pending"
    t = status_text.lower()
    if "settled" in t or "settlement" in t:
        return "settled"
    if "dismissed" in t or "denied" in t or "rejected" in t or "withdrawn" in t:
        return "decided"  # outcome encoded separately if we ever extract
    if "filed" in t and "decid" not in t and "rule" not in t:
        return "filed"
    return "decided"


def slugify(text: str) -> str:
    """Slugify a free-text label for use as a vocabulary code."""
    n = unicodedata.normalize("NFKD", text)
    n = n.encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").lower()
    return n[:120] if n else "unknown"


def alpha3_to_alpha2(geographies: list[str]) -> str:
    """Pick the country-level jurisdiction from CPR's geographies list.

    CPR returns ['USA', 'US-AZ'] etc. — country first, sub-national second.
    We use the country-level code, mapped to ISO alpha-2.
    """
    if not geographies:
        return "XX"  # unknown
    primary = geographies[0]
    if "-" in primary:
        primary = primary.split("-")[0]
    return ISO_ALPHA3_TO_ALPHA2.get(primary, primary[:2].upper())


def extract_concepts(concepts: list[dict[str, Any]], relation: str) -> list[dict[str, Any]]:
    return [c for c in concepts if c.get("relation") == relation]


def parse_family_record(
    family: dict[str, Any], retrieved_at: datetime, upstream_version: str
) -> ParsedCase | None:
    """Translate one Sabin/CPR family record into our canonical ParsedCase.

    Used by both ingest.sabin.cpr.bulk_ingest (deprecated) and
    ingest.sabin.scraper.scrape_one_case (current). The JSON shape is
    identical; the only difference is whether it came from CPR's API or
    from __NEXT_DATA__ embedded in a climatecasechart.com case page.

    Returns None if the record is malformed (skip rather than crash on bulk run).
    """
    try:
        sabin_id = family["import_id"]
        title = family["title"]
        if not (sabin_id and title):
            return None
    except KeyError:
        return None

    geographies = family.get("geographies") or []
    juris_code = alpha3_to_alpha2(geographies)

    concepts = family.get("concepts") or []
    juris_concepts = extract_concepts(concepts, "jurisdiction")
    # Pick the most specific (last in list usually has the deepest court)
    court_id: str | None = None
    if juris_concepts:
        # Prefer one that's not just a country name
        deepest = next(
            (c for c in juris_concepts if c.get("subconcept_of_labels")), juris_concepts[0]
        )
        court_id = slugify(deepest.get("preferred_label") or deepest.get("id") or "")
        if not court_id:
            court_id = None

    category_concepts = extract_concepts(concepts, "category")
    claim_codes = list(
        {slugify(c.get("preferred_label") or c.get("id") or "") for c in category_concepts}
    )
    claim_codes = [c for c in claim_codes if c]

    metadata = family.get("metadata") or {}
    status_list = metadata.get("status") or []
    status_text = status_list[0] if status_list else None
    status_code = map_status_freetext_to_code(status_text)

    summary = family.get("summary")
    published_date = family.get("published_date")
    last_updated = family.get("last_updated_date")

    # Preserve full upstream payload for fields we don't yet model as columns:
    # case_number, core_object, principal_law refs, events timeline, full
    # concepts hierarchy. Source of truth for future feature layers.
    upstream_metadata: dict[str, Any] = {
        "metadata": metadata,
        "concepts": family.get("concepts") or [],
        "events": family.get("events") or [],
    }
    for opt_key in ("attribution", "collections", "organisations"):
        if family.get(opt_key) is not None:
            upstream_metadata[opt_key] = family[opt_key]

    pb = ProvenanceBuilder()
    sabin_prov = ProvenanceEntry(
        source="sabin",
        retrieved_at=retrieved_at,
        upstream_version=upstream_version,
    )
    for f in (
        "canonical_title",
        "jurisdiction_code",
        "court_id",
        "filing_date",
        "status_code",
        "summary",
    ):
        pb.set(f, sabin_prov)

    case_dict: dict[str, Any] = {
        "sabin_id": sabin_id,
        "canonical_title": title,
        "jurisdiction_code": juris_code,
        "court_id": court_id,
        "filing_date": _parse_date(published_date),
        "decision_date": _parse_date(last_updated),
        "status_code": status_code,
        "outcome_code": None,
        "summary": summary,
        "summary_lang": "en",
        "primary_source": "sabin",
        "provenance": pb.build(),
        "upstream_metadata": upstream_metadata,
    }

    # Parties: CPR's family record doesn't expose plaintiff/defendant cleanly.
    # Skip parties for v0.1 bulk; can be enriched later from Sabin's per-case page.
    parties: list[dict[str, Any]] = []

    # Documents: each document has slug + title; synthesize upstream_url
    docs: list[dict[str, Any]] = []
    for doc in family.get("documents") or []:
        slug = doc.get("slug")
        if not slug:
            continue
        docs.append(
            {
                "category_code": "opinion",  # CPR doesn't break this down; default to opinion
                "title": doc.get("title") or slug,
                "filed_date": _parse_date(doc.get("last_updated_date")),
                "filed_by": None,
                "upstream_url": f"{CCC_BASE}/document/{slug}",
                "provenance": pb.build(),
            }
        )

    # Citation string: synthesize from upstream attribution.
    # Enrich with case_number when present (e.g., docket, ECLI, etc.) so the
    # cite is parseable by formal-cite extractors and useful to lawyers.
    family_slug = family.get("slug") or ""
    case_url = f"{CCC_BASE}/document/{family_slug}" if family_slug else CCC_BASE
    case_number_list = metadata.get("case_number") or []
    case_number = case_number_list[0] if case_number_list else None
    if case_number:
        cite_text = f"{title}, {case_number} (Sabin Center for Climate Change Law, {case_url})"
    else:
        cite_text = f"{title} (Sabin Center for Climate Change Law, {case_url})"
    citation_strings = [
        {"lang": "en", "format": "sabin", "text": cite_text},
    ]

    return ParsedCase(
        case=case_dict,
        parties=parties,
        claim_type_codes=claim_codes,
        documents=docs,
        citation_strings=citation_strings,
    )


def _parse_date(value: str | None) -> Any:
    """Parse an ISO datetime/date string to a date or return None.

    Sanity-clamps implausible years: returns None for filing dates with year
    < 1900 (we've seen at least one upstream typo: "1016-09-15" on Sabin
    family.3560.0 — almost certainly meant 2016).
    """
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError, AttributeError, TypeError:
        return None
    if d.year < 1900:
        return None
    return d


async def fetch_families_page(
    client: httpx.AsyncClient, page: int, *, corpus_id: str = DEFAULT_CORPUS_ID
) -> list[dict[str, Any]]:
    """Fetch one page of families. Returns [] when past the last page."""
    log = structlog.get_logger("ingest.sabin.cpr")
    for attempt in range(5):
        try:
            r = await client.get(
                f"{CPR_API_BASE}/families/",
                params={
                    "corpus.import_id": corpus_id,
                    "page": page,
                    "page_size": PAGE_SIZE,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
            )
            if r.status_code == 429:
                wait = 2**attempt
                log.warning("rate_limited", attempt=attempt, wait=wait)
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("data") or []
        except httpx.HTTPError as e:
            log.warning("http_error", attempt=attempt, error=str(e))
            if attempt == 4:
                raise
            await asyncio.sleep(2**attempt)
    return []


async def iter_all_families(
    client: httpx.AsyncClient, *, corpus_id: str = DEFAULT_CORPUS_ID
) -> AsyncIterator[dict[str, Any]]:
    """Yield every family in a corpus, paginating with politeness."""
    log = structlog.get_logger("ingest.sabin.cpr")
    page = 1
    while True:
        records = await fetch_families_page(client, page, corpus_id=corpus_id)
        if not records:
            log.info("pagination_complete", final_page=page - 1)
            return
        log.info("page_fetched", page=page, count=len(records))
        for r in records:
            yield r
        if len(records) < PAGE_SIZE:
            log.info("pagination_complete", final_page=page)
            return
        page += 1
        await asyncio.sleep(POLITE_DELAY)


async def autoupsert_vocabularies(
    pool: AsyncConnectionPool, parsed_cases: list[ParsedCase]
) -> None:
    """Insert any vocabulary rows that the parsed cases reference but don't yet exist.

    Idempotent. Source for these auto-created rows is 'sabin' with the current
    bulk-run upstream_version. Rows that already exist are left alone.
    """
    jurisdictions: set[str] = set()
    courts: dict[str, str] = {}  # court_id -> jurisdiction_code (best-known)
    claim_types: set[str] = set()
    statuses = {"filed", "pending", "decided", "settled", "dismissed", "withdrawn"}
    document_categories = {"opinion"}

    for p in parsed_cases:
        jurisdictions.add(p.case["jurisdiction_code"])
        if p.case.get("court_id"):
            courts[p.case["court_id"]] = p.case["jurisdiction_code"]
        for ct in p.claim_type_codes:
            claim_types.add(ct)

    if not (jurisdictions or courts or claim_types):
        return

    sv = "sabin-bulk-2026-05"
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                for code in sorted(jurisdictions):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_jurisdiction
                            (code, name, kind, source, source_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, "national", "sabin", sv),
                    )
                for court_id, juris_code in sorted(courts.items()):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_court
                            (id, name, jurisdiction_code, source, source_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (court_id, court_id, juris_code, "sabin", sv),
                    )
                for code in sorted(claim_types):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_claim_type (code, name, source, source_version)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, "sabin", sv),
                    )
                for code in sorted(statuses):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_status (code, name, source, source_version)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, "sabin", sv),
                    )
                for code in sorted(document_categories):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_document_category
                            (code, name, source, source_version)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, "sabin", sv),
                    )


async def upsert_parsed_case_minimal(pool: AsyncConnectionPool, parsed: ParsedCase) -> str:
    """UPSERT a ParsedCase. Same as ingest.sabin.upsert.upsert_case but inlined here
    to avoid coupling — and we skip parties (CPR doesn't expose them cleanly)."""
    case = parsed.case
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO case_record (
                        sabin_id, canonical_title, jurisdiction_code, court_id,
                        filing_date, decision_date, status_code, outcome_code,
                        summary, summary_lang, primary_source, provenance,
                        upstream_metadata, updated_at
                    )
                    VALUES (%(sabin_id)s, %(canonical_title)s, %(jurisdiction_code)s,
                            %(court_id)s, %(filing_date)s, %(decision_date)s,
                            %(status_code)s, %(outcome_code)s, %(summary)s,
                            %(summary_lang)s, %(primary_source)s, %(provenance)s,
                            %(upstream_metadata)s, now())
                    ON CONFLICT (sabin_id) DO UPDATE SET
                        canonical_title = EXCLUDED.canonical_title,
                        jurisdiction_code = EXCLUDED.jurisdiction_code,
                        court_id = EXCLUDED.court_id,
                        filing_date = EXCLUDED.filing_date,
                        decision_date = EXCLUDED.decision_date,
                        status_code = EXCLUDED.status_code,
                        outcome_code = EXCLUDED.outcome_code,
                        summary = EXCLUDED.summary,
                        summary_lang = EXCLUDED.summary_lang,
                        primary_source = EXCLUDED.primary_source,
                        provenance = EXCLUDED.provenance,
                        upstream_metadata = EXCLUDED.upstream_metadata,
                        updated_at = now()
                    RETURNING id
                    """,
                    {
                        **case,
                        "provenance": Jsonb(case["provenance"]),
                        "upstream_metadata": Jsonb(case.get("upstream_metadata") or {}),
                    },
                )
                row = await cur.fetchone()
                assert row is not None
                case_id = str(row[0])

                await cur.execute("DELETE FROM case_claim_type WHERE case_id = %s", (case_id,))
                await cur.execute("DELETE FROM document WHERE case_id = %s", (case_id,))
                await cur.execute("DELETE FROM citation_string WHERE case_id = %s", (case_id,))

                for code in parsed.claim_type_codes:
                    await cur.execute(
                        "INSERT INTO case_claim_type (case_id, claim_type_code) VALUES (%s, %s)"
                        " ON CONFLICT DO NOTHING",
                        (case_id, code),
                    )

                for doc in parsed.documents:
                    await cur.execute(
                        """
                        INSERT INTO document (
                            case_id, category_code, title, filed_date, filed_by,
                            upstream_url, text, text_lang, text_extraction_method,
                            provenance, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            case_id,
                            doc["category_code"],
                            doc["title"],
                            doc["filed_date"],
                            doc["filed_by"],
                            doc["upstream_url"],
                            doc.get("text"),
                            doc.get("text_lang"),
                            doc.get("text_extraction_method"),
                            Jsonb(doc["provenance"]),
                        ),
                    )

                for cs in parsed.citation_strings:
                    await cur.execute(
                        "INSERT INTO citation_string (case_id, lang, format, text)"
                        " VALUES (%s, %s, %s, %s)"
                        " ON CONFLICT DO NOTHING",
                        (case_id, cs["lang"], cs["format"], cs["text"]),
                    )
    return case_id


async def bulk_ingest(
    *,
    corpus_id: str = DEFAULT_CORPUS_ID,
    upstream_version: str | None = None,
    max_records: int | None = None,
) -> dict[str, int]:
    """Ingest the entire Sabin corpus from CPR's API.

    Args:
        corpus_id: CPR corpus identifier (default = Sabin litigation).
        upstream_version: Tag stored in provenance (default: today's date).
        max_records: Stop after N records (for smoke-testing). None = ingest all.

    Returns:
        {fetched, parsed, upserted, skipped}
    """
    from server.db import get_pool

    log = structlog.get_logger("ingest.sabin.cpr")
    upstream_version = upstream_version or f"sabin-bulk-{datetime.now(tz=UTC).date().isoformat()}"
    retrieved_at = datetime.now(tz=UTC)

    pool = await get_pool()
    fetched = parsed = upserted = skipped = 0
    batch: list[ParsedCase] = []
    BATCH_SIZE = 50

    async with httpx.AsyncClient() as client:
        async for family in iter_all_families(client, corpus_id=corpus_id):
            fetched += 1
            pc = parse_family_record(family, retrieved_at, upstream_version)
            if pc is None:
                skipped += 1
                continue
            parsed += 1
            batch.append(pc)
            if len(batch) >= BATCH_SIZE:
                await autoupsert_vocabularies(pool, batch)
                for p in batch:
                    await upsert_parsed_case_minimal(pool, p)
                upserted += len(batch)
                log.info("batch_upserted", fetched=fetched, upserted=upserted, skipped=skipped)
                batch = []
            if max_records is not None and fetched >= max_records:
                break

    if batch:
        await autoupsert_vocabularies(pool, batch)
        for p in batch:
            await upsert_parsed_case_minimal(pool, p)
        upserted += len(batch)

    log.info("ingest_complete", fetched=fetched, parsed=parsed, upserted=upserted, skipped=skipped)
    return {"fetched": fetched, "parsed": parsed, "upserted": upserted, "skipped": skipped}


def main() -> int:
    import argparse

    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Bulk-ingest Sabin litigation corpus from CPR.")
    parser.add_argument(
        "--corpus-id",
        default=DEFAULT_CORPUS_ID,
        help="CPR corpus identifier",
    )
    parser.add_argument(
        "--upstream-version",
        default=None,
        help="Provenance tag (default: sabin-bulk-YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Smoke-test cap (None = ingest all)",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await bulk_ingest(
                corpus_id=args.corpus_id,
                upstream_version=args.upstream_version,
                max_records=args.max_records,
            )
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

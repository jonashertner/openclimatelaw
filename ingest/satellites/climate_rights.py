# pyright: basic
"""Ingest the Climate Rights Database (climaterightsdatabase.com).

CRD is a WordPress site exposing ~215 case posts via the standard
/wp-json/wp/v2 REST API. There is no explicit licence on the case data, so
we ingest METADATA ONLY (title, dates, jurisdiction/claim taxonomy from WP
categories, link to CRD) and DO NOT copy the prose summary into our store.
Users querying our MCP for a CRD case get pointed back to CRD via the
upstream_url for the substantive content. This is the defensible posture
absent permission and matches the spec's "live-proxy fallback" pattern.

Mapping CRD WP fields → our canonical schema:
- id ("call4-et-al-v-japan")        → sabin_id-equivalent identifier (prefixed "crd:<id>")
- title.rendered                    → canonical_title (HTML-entity decoded)
- date                              → filing_date
- modified                          → updated_at (provenance)
- categories[]                      → jurisdiction_code / claim_types / court_id (classified)
- link                              → upstream_url for documents and provenance
- content.rendered                  → DEPLIBERATELY NOT INGESTED (no licence)
"""

from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from ingest._provenance import ProvenanceBuilder, ProvenanceEntry
from ingest.sabin.parse import ParsedCase

CRD_API_BASE = "https://climaterightsdatabase.com/wp-json/wp/v2"
USER_AGENT = "OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)"
PAGE_SIZE = 100
POLITE_DELAY = 1.0

# Country names → ISO 3166-1 alpha-2. Built from CRD's category list.
COUNTRY_NAME_TO_ALPHA2: dict[str, str] = {
    "argentina": "AR",
    "australia": "AU",
    "austria": "AT",
    "belgium": "BE",
    "brazil": "BR",
    "canada": "CA",
    "chile": "CL",
    "colombia": "CO",
    "denmark": "DK",
    "ecuador": "EC",
    "egypt": "EG",
    "fiji": "FJ",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "ghana": "GH",
    "guyana": "GY",
    "india": "IN",
    "indonesia": "ID",
    "ireland": "IE",
    "italy": "IT",
    "japan": "JP",
    "kenya": "KE",
    "luxembourg": "LU",
    "mexico": "MX",
    "morocco": "MA",
    "netherlands": "NL",
    "new zealand": "NZ",
    "nigeria": "NG",
    "norway": "NO",
    "pakistan": "PK",
    "panama": "PA",
    "papua new guinea": "PG",
    "peru": "PE",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "russia": "RU",
    "south africa": "ZA",
    "south korea": "KR",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "thailand": "TH",
    "turkey": "TR",
    "tuvalu": "TV",
    "uganda": "UG",
    "ukraine": "UA",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "us": "US",
    "uruguay": "UY",
    "vanuatu": "VU",
}

# Special non-national codes for international/regional bodies and tribunals.
INTERNATIONAL_BODY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"international court of justice", re.I), "ICJ"),
    (re.compile(r"inter[- ]american court", re.I), "IACTHR"),
    (re.compile(r"european court of human rights", re.I), "ECTHR"),
    (re.compile(r"un human rights committee|unhrc", re.I), "UNHRC"),
    (re.compile(r"committee on the rights of the child", re.I), "UNCRC"),
    (re.compile(r"committee on the elimination of discrimination against women", re.I), "CEDAW"),
    (re.compile(r"african court", re.I), "ACtHPR"),
    (re.compile(r"international tribunal for the law of the sea|itlos", re.I), "ITLOS"),
    (re.compile(r"court of justice of the european union|cjeu", re.I), "EU-CJEU"),
]


def slugify(text: str) -> str:
    import unicodedata

    n = unicodedata.normalize("NFKD", text)
    n = n.encode("ascii", "ignore").decode("ascii")
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").lower()
    return n[:120] if n else "unknown"


def decode_html(text: str) -> str:
    """Decode HTML entities and strip simple tags."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def classify_category(cat: dict[str, Any]) -> dict[str, Any]:
    """Classify a CRD category as year / country / international body / court / claim type."""
    name = (cat.get("name") or "").strip()
    slug = (cat.get("slug") or "").strip()
    n_lower = name.lower()

    # Year: pure 4-digit (slug "2018", "2017-year", etc.)
    if m := re.search(r"\b(19|20)\d{2}\b", slug):
        return {"kind": "year", "year": int(m.group())}

    # International body
    for pat, code in INTERNATIONAL_BODY_PATTERNS:
        if pat.search(name) or pat.search(slug):
            return {"kind": "international_body", "code": code, "court_label": name}

    # Country
    if n_lower in COUNTRY_NAME_TO_ALPHA2:
        return {"kind": "country", "code": COUNTRY_NAME_TO_ALPHA2[n_lower]}

    # Court (heuristic on name)
    if any(k in n_lower for k in ("court", "tribunal", "council", "committee", "commission")):
        return {"kind": "court", "label": name, "id": slugify(name)}

    # Else: claim_type / topic
    return {"kind": "topic", "label": name, "code": slugify(name)}


async def fetch_all_categories(client: httpx.AsyncClient) -> dict[int, dict[str, Any]]:
    """Fetch every CRD category, return id → category dict."""
    log = structlog.get_logger("ingest.crd")
    cats: dict[int, dict[str, Any]] = {}
    page = 1
    while True:
        r = await client.get(
            f"{CRD_API_BASE}/categories",
            params={"per_page": PAGE_SIZE, "page": page},
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        if r.status_code == 400:
            # WP returns 400 when paging past the last page
            break
        r.raise_for_status()
        items = r.json()
        if not items:
            break
        for c in items:
            cats[c["id"]] = c
        log.info("categories_fetched", page=page, count=len(items))
        if len(items) < PAGE_SIZE:
            break
        page += 1
        await asyncio.sleep(POLITE_DELAY)
    return cats


async def fetch_all_posts(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch all CRD posts (cases). Returns list of post dicts."""
    log = structlog.get_logger("ingest.crd")
    posts: list[dict[str, Any]] = []
    page = 1
    while True:
        r = await client.get(
            f"{CRD_API_BASE}/posts",
            params={"per_page": PAGE_SIZE, "page": page, "_embed": "false"},
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        if r.status_code == 400:
            break
        r.raise_for_status()
        items = r.json()
        if not items:
            break
        posts.extend(items)
        log.info("posts_fetched", page=page, count=len(items))
        if len(items) < PAGE_SIZE:
            break
        page += 1
        await asyncio.sleep(POLITE_DELAY)
    return posts


def parse_crd_post(
    post: dict[str, Any],
    categories: dict[int, dict[str, Any]],
    retrieved_at: datetime,
    upstream_version: str,
) -> ParsedCase | None:
    title = decode_html(post.get("title", {}).get("rendered") or "")
    if not title:
        return None
    crd_id = post["slug"]
    sabin_id = f"crd:{crd_id}"  # use sabin_id as the unified canonical ID; prefixed for source

    # Classify all categories
    classified = [
        classify_category(categories[c]) for c in post.get("categories", []) if c in categories
    ]

    # Pick a country jurisdiction (first national or international body)
    juris_code = "XX"
    for c in classified:
        if c["kind"] == "country":
            juris_code = c["code"]
            break
        if c["kind"] == "international_body":
            juris_code = c["code"]
            break

    # Pick the best court / tribunal
    court_id: str | None = None
    for c in classified:
        if c["kind"] == "international_body":
            court_id = slugify(c.get("court_label") or c["code"])
            break
        if c["kind"] == "court":
            court_id = c["id"]
            break

    # Filing year from category, fallback to post date
    filing_date: date | None = None
    for c in classified:
        if c["kind"] == "year":
            filing_date = date(c["year"], 1, 1)
            break
    if filing_date is None:
        post_date = post.get("date")
        if post_date:
            try:
                filing_date = datetime.fromisoformat(post_date.replace("Z", "+00:00")).date()
            except ValueError, AttributeError:
                pass

    # Claim types from topics
    claim_codes = sorted({c["code"] for c in classified if c["kind"] == "topic"})

    pb = ProvenanceBuilder()
    crd_prov = ProvenanceEntry(
        source="climate_rights",
        retrieved_at=retrieved_at,
        upstream_version=upstream_version,
    )
    for f in (
        "canonical_title",
        "jurisdiction_code",
        "court_id",
        "filing_date",
        "status_code",
    ):
        pb.set(f, crd_prov)

    upstream_url = post.get("link") or f"https://climaterightsdatabase.com/?p={post.get('id')}"
    case_dict = {
        "sabin_id": sabin_id,  # unique per source by construction
        "canonical_title": title,
        "jurisdiction_code": juris_code,
        "court_id": court_id,
        "filing_date": filing_date,
        "decision_date": None,
        "status_code": "decided",  # CRD doesn't track status; default to decided
        "outcome_code": None,
        # NOTE: deliberately NOT copying CRD's prose summary into our DB.
        # Users get pointed to upstream_url via the document below.
        "summary": f"Source: Climate Rights Database. See {upstream_url} for the case summary.",
        "summary_lang": "en",
        "primary_source": "climate_rights",
        "provenance": pb.build(),
    }

    # Single "document" — points back to CRD's case page (not a court document).
    documents = [
        {
            "category_code": "opinion",
            "title": f"{title} (CRD page)",
            "filed_date": filing_date,
            "filed_by": None,
            "upstream_url": upstream_url,
            "provenance": pb.build(),
        }
    ]

    citation_strings = [
        {
            "lang": "en",
            "format": "crd",
            "text": f"{title} (Climate Rights Database, {upstream_url})",
        }
    ]

    return ParsedCase(
        case=case_dict,
        parties=[],
        claim_type_codes=claim_codes,
        documents=documents,
        citation_strings=citation_strings,
    )


async def autoupsert_vocabularies(
    pool: AsyncConnectionPool, parsed_cases: list[ParsedCase]
) -> None:
    """Auto-upsert vocab rows for newly-seen jurisdictions, courts, claim types."""
    jurisdictions: set[str] = set()
    courts: dict[str, str] = {}
    claim_types: set[str] = set()
    for p in parsed_cases:
        jurisdictions.add(p.case["jurisdiction_code"])
        if p.case.get("court_id"):
            courts[p.case["court_id"]] = p.case["jurisdiction_code"]
        for ct in p.claim_type_codes:
            claim_types.add(ct)

    sv = "crd-bulk-2026-05"
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                for code in sorted(jurisdictions):
                    kind = (
                        "international"
                        if code
                        in {
                            "ICJ",
                            "IACTHR",
                            "ECTHR",
                            "UNHRC",
                            "UNCRC",
                            "CEDAW",
                            "ACtHPR",
                            "ITLOS",
                            "EU-CJEU",
                        }
                        else "national"
                    )
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_jurisdiction
                            (code, name, kind, source, source_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, kind, "climate_rights", sv),
                    )
                for court_id, juris_code in sorted(courts.items()):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_court
                            (id, name, jurisdiction_code, source, source_version)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (court_id, court_id, juris_code, "climate_rights", sv),
                    )
                for code in sorted(claim_types):
                    await cur.execute(
                        """
                        INSERT INTO vocabulary_claim_type (code, name, source, source_version)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (code) DO NOTHING
                        """,
                        (code, code, "climate_rights", sv),
                    )


async def upsert_parsed_case_minimal(pool: AsyncConnectionPool, parsed: ParsedCase) -> str:
    case = parsed.case
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO case_record (
                        sabin_id, canonical_title, jurisdiction_code, court_id,
                        filing_date, decision_date, status_code, outcome_code,
                        summary, summary_lang, primary_source, provenance, updated_at
                    )
                    VALUES (%(sabin_id)s, %(canonical_title)s, %(jurisdiction_code)s,
                            %(court_id)s, %(filing_date)s, %(decision_date)s,
                            %(status_code)s, %(outcome_code)s, %(summary)s,
                            %(summary_lang)s, %(primary_source)s, %(provenance)s, now())
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
                        updated_at = now()
                    RETURNING id
                    """,
                    {**case, "provenance": Jsonb(case["provenance"])},
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
                            upstream_url, provenance, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                        """,
                        (
                            case_id,
                            doc["category_code"],
                            doc["title"],
                            doc["filed_date"],
                            doc["filed_by"],
                            doc["upstream_url"],
                            Jsonb(doc["provenance"]),
                        ),
                    )
                for cs in parsed.citation_strings:
                    await cur.execute(
                        "INSERT INTO citation_string (case_id, lang, format, text)"
                        " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (case_id, cs["lang"], cs["format"], cs["text"]),
                    )
    return case_id


async def bulk_ingest(
    *,
    upstream_version: str | None = None,
    max_records: int | None = None,
) -> dict[str, int]:
    from server.db import get_pool

    log = structlog.get_logger("ingest.crd")
    upstream_version = upstream_version or f"crd-bulk-{datetime.now(tz=UTC).date().isoformat()}"
    retrieved_at = datetime.now(tz=UTC)

    pool = await get_pool()
    fetched = parsed = upserted = skipped = 0

    async with httpx.AsyncClient() as client:
        log.info("fetching_categories")
        categories = await fetch_all_categories(client)
        log.info("categories_done", count=len(categories))

        log.info("fetching_posts")
        posts = await fetch_all_posts(client)
        log.info("posts_done", count=len(posts))

        if max_records is not None:
            posts = posts[:max_records]

        batch: list[ParsedCase] = []
        for post in posts:
            fetched += 1
            pc = parse_crd_post(post, categories, retrieved_at, upstream_version)
            if pc is None:
                skipped += 1
                continue
            parsed += 1
            batch.append(pc)
            if len(batch) >= 50:
                await autoupsert_vocabularies(pool, batch)
                for p in batch:
                    await upsert_parsed_case_minimal(pool, p)
                upserted += len(batch)
                log.info("batch_upserted", fetched=fetched, upserted=upserted)
                batch = []

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

    parser = argparse.ArgumentParser(description="Bulk-ingest Climate Rights Database.")
    parser.add_argument("--upstream-version", default=None)
    parser.add_argument("--max-records", type=int, default=None)
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await bulk_ingest(
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

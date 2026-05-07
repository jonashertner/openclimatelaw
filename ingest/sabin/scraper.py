# pyright: basic
"""Direct-from-Sabin scraper — replaces the CPR-API path.

Sources data exclusively from www.climatecasechart.com (Sabin's domain):
- Case detail pages at https://www.climatecasechart.com/document/<slug> are
  server-rendered Next.js pages; the full structured family record is embedded
  in a <script id="__NEXT_DATA__"> JSON blob. Same shape as CPR's families API.
- Court documents (PDFs of decisions, briefs, complaints) are linked from the
  page; many are hosted directly on Sabin's WordPress at
  /wp-content/uploads/case-documents/. We pull only those (NOT the
  cdn.climatepolicyradar.org mirror copies — strict no-CPR-dependency).

For each PDF found we extract text via pymupdf and store it in
document.text, so the anti-hallucination contract's check_claim_support()
can validate quotes against actual judicial language, not just Sabin's
editorial summaries.

Politeness: 1 req/s for HTML pages, ≤5 concurrent PDF downloads, identifying
User-Agent, exponential backoff on 429/5xx. Respects robots.txt
(Allow: /).

Source provenance: {source: "sabin", upstream_version: "scrape-YYYY-MM-DD"}.

Run via:
  uv run python -m ingest.sabin.scraper [--max-records N] [--slug-source db|file]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

from ingest.sabin.cpr import (
    autoupsert_vocabularies,
    parse_family_record,
    upsert_parsed_case_minimal,
)
from ingest.sabin.parse import ParsedCase

CCC_BASE = "https://www.climatecasechart.com"
USER_AGENT = "OpenClimateLaw-bot/0.1 (+https://openclimatelaw.org; jonashertner@protonmail.ch)"
PAGE_DELAY = 1.0  # seconds between HTML page fetches
PDF_CONCURRENCY = 4
PDF_DIR = Path("/app/data/sabin-pdfs")  # docker volume in production

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)
WP_PDF_RE = re.compile(
    r'https?://(?:www\.)?climatecasechart\.com/wp-content/uploads/[^\s"\'<>]+\.pdf',
    re.I,
)


async def fetch_case_html(client: httpx.AsyncClient, slug: str) -> str | None:
    """Fetch one case's detail page; returns HTML or None on miss/error."""
    log = structlog.get_logger("ingest.sabin.scraper")
    url = f"{CCC_BASE}/document/{slug}"
    for attempt in range(4):
        try:
            r = await client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
                follow_redirects=True,
            )
            if r.status_code == 404:
                log.warning("case_not_found", slug=slug)
                return None
            if r.status_code == 429:
                wait = 2**attempt
                log.warning("rate_limited", slug=slug, wait=wait)
                await asyncio.sleep(wait)
                continue
            r.raise_for_status()
            return r.text
        except httpx.HTTPError as e:
            log.warning("fetch_error", slug=slug, attempt=attempt, error=str(e))
            if attempt == 3:
                return None
            await asyncio.sleep(2**attempt)
    return None


def extract_next_data_family(html: str) -> dict[str, Any] | None:
    """Pull the family record out of Next.js __NEXT_DATA__."""
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data.get("props", {}).get("pageProps", {}).get("family")


def extract_pdf_urls(html: str) -> list[str]:
    """Extract climatecasechart.com-hosted PDF URLs (Sabin's WordPress originals).

    Excludes cdn.climatepolicyradar.org URLs — we strictly avoid CPR-domain
    dependencies. If a case's only PDF is on CPR's CDN, we surface it via the
    family record's documents[].slug -> climatecasechart.com page link, but
    we don't download the binary itself.
    """
    urls = WP_PDF_RE.findall(html)
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        # Normalize www
        u = u.replace("https://climatecasechart.com/", "https://www.climatecasechart.com/")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def download_pdf(client: httpx.AsyncClient, url: str, target: Path) -> bool:
    """Download a PDF to target. Idempotent (skip if exists)."""
    log = structlog.get_logger("ingest.sabin.scraper")
    if target.exists() and target.stat().st_size > 0:
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=120.0,
            follow_redirects=True,
        ) as r:
            r.raise_for_status()
            with open(target.with_suffix(target.suffix + ".part"), "wb") as f:
                async for chunk in r.aiter_bytes(64 * 1024):
                    f.write(chunk)
        target.with_suffix(target.suffix + ".part").rename(target)
        return True
    except Exception as e:
        log.warning("pdf_download_failed", url=url, error=str(e))
        # Clean up partial
        partial = target.with_suffix(target.suffix + ".part")
        if partial.exists():
            partial.unlink()
        return False


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF via pymupdf. Returns empty string on failure."""
    log = structlog.get_logger("ingest.sabin.scraper")
    try:
        import pymupdf

        doc = pymupdf.open(pdf_path)
        try:
            return "\n\n".join(str(page.get_text("text")) for page in doc)
        finally:
            doc.close()
    except Exception as e:
        log.warning("pdf_extract_failed", path=str(pdf_path), error=str(e))
        return ""


def categorize_pdf_filename(filename: str) -> str:
    """Heuristically map a PDF filename to our document category enum."""
    f = filename.lower()
    if "complaint" in f:
        return "complaint"
    if "brief" in f or "amicus" in f:
        return "brief"
    if "order" in f or "ruling" in f or "memorandum" in f:
        return "order"
    if "judgment" in f or "judgement" in f:
        return "judgment"
    if "settlement" in f:
        return "settlement"
    if "dissent" in f:
        return "dissent"
    return "opinion"


async def scrape_one_case(
    client: httpx.AsyncClient,
    slug: str,
    pdf_dir: Path,
    retrieved_at: datetime,
    upstream_version: str,
    pdf_sem: asyncio.Semaphore,
) -> ParsedCase | None:
    """Fetch + parse + download PDFs + extract text for one case."""
    log = structlog.get_logger("ingest.sabin.scraper")
    html = await fetch_case_html(client, slug)
    if html is None:
        return None

    family = extract_next_data_family(html)
    if family is None:
        log.warning("no_family_data_in_html", slug=slug)
        return None

    parsed = parse_family_record(family, retrieved_at, upstream_version)
    if parsed is None:
        return None

    # Bump provenance source_version to reflect direct-scrape pathway.
    for entry in parsed.case["provenance"].values():
        entry["upstream_version"] = upstream_version

    # Find Sabin-hosted PDFs and append them as document records with extracted text.
    pdf_urls = extract_pdf_urls(html)
    if pdf_urls:
        case_pdf_dir = pdf_dir / slug

        async def fetch_and_extract(url: str) -> dict[str, Any] | None:
            async with pdf_sem:
                filename = url.rsplit("/", 1)[-1]
                target = case_pdf_dir / filename
                ok = await download_pdf(client, url, target)
                if not ok:
                    return None
                text = extract_pdf_text(target)
                if not text:
                    return None
                return {
                    "category_code": categorize_pdf_filename(filename),
                    "title": filename,
                    "filed_date": None,
                    "filed_by": None,
                    "upstream_url": url,
                    "text": text,
                    "text_lang": "en",
                    "text_extraction_method": "pymupdf",
                    "provenance": parsed.case["provenance"],
                }

        results = await asyncio.gather(*[fetch_and_extract(u) for u in pdf_urls])
        for entry in results:
            if entry is not None:
                parsed.documents.append(entry)

    return parsed


async def get_known_slugs() -> list[str]:
    """Read existing Sabin slugs from our DB.

    Slug is the path segment used in climatecasechart.com URLs. We synthesized
    it during the CPR-API ingest as the document's upstream_url tail. Easier:
    re-derive from the case_record's primary_source='sabin' rows by extracting
    the slug from any document.upstream_url already present.
    """
    from server.db import get_pool

    pool = await get_pool()
    slugs: list[str] = []
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT regexp_replace(
                    upstream_url,
                    '^https?://(www\\.)?climatecasechart\\.com/document/',
                    ''
                ) AS slug
                FROM document
                WHERE upstream_url ~ 'climatecasechart\\.com/document/'
                ORDER BY slug
                """
            )
            rows = await cur.fetchall()
            slugs = [r[0] for r in rows if r[0]]
    return slugs


async def scrape_all(
    *,
    slugs: list[str] | None = None,
    upstream_version: str | None = None,
    max_records: int | None = None,
    pdf_dir: Path = PDF_DIR,
) -> dict[str, int]:
    """Scrape all known case slugs from climatecasechart.com directly."""
    from server.db import get_pool

    log = structlog.get_logger("ingest.sabin.scraper")
    upstream_version = upstream_version or f"sabin-scrape-{datetime.now(tz=UTC).date().isoformat()}"
    retrieved_at = datetime.now(tz=UTC)

    if slugs is None:
        log.info("loading_slugs_from_db")
        slugs = await get_known_slugs()
        log.info("slugs_loaded", count=len(slugs))

    if max_records is not None:
        slugs = slugs[:max_records]

    pdf_dir.mkdir(parents=True, exist_ok=True)

    pool = await get_pool()
    fetched = parsed = upserted = skipped = 0
    pdf_sem = asyncio.Semaphore(PDF_CONCURRENCY)

    async with httpx.AsyncClient(http2=False) as client:
        for i, slug in enumerate(slugs):
            fetched += 1
            pc = await scrape_one_case(
                client, slug, pdf_dir, retrieved_at, upstream_version, pdf_sem
            )
            if pc is None:
                skipped += 1
                continue
            parsed += 1
            await autoupsert_vocabularies(pool, [pc])
            await upsert_parsed_case_minimal(pool, pc)
            upserted += 1
            if (i + 1) % 25 == 0:
                log.info(
                    "progress",
                    fetched=fetched,
                    parsed=parsed,
                    upserted=upserted,
                    skipped=skipped,
                    last_slug=slug,
                )
            await asyncio.sleep(PAGE_DELAY)

    log.info(
        "scrape_complete",
        fetched=fetched,
        parsed=parsed,
        upserted=upserted,
        skipped=skipped,
    )
    return {"fetched": fetched, "parsed": parsed, "upserted": upserted, "skipped": skipped}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(
        description="Scrape Sabin / Climate Litigation Database directly from "
        "www.climatecasechart.com."
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Smoke-test cap on number of slugs to fetch.",
    )
    parser.add_argument(
        "--upstream-version",
        default=None,
        help="Provenance tag (default: sabin-scrape-YYYY-MM-DD).",
    )
    parser.add_argument(
        "--slugs",
        nargs="*",
        default=None,
        help="Explicit slugs to scrape (otherwise loaded from DB).",
    )
    parser.add_argument(
        "--pdf-dir",
        default=str(PDF_DIR),
        help=f"Local directory for downloaded PDFs (default: {PDF_DIR}).",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await scrape_all(
                slugs=args.slugs,
                upstream_version=args.upstream_version,
                max_records=args.max_records,
                pdf_dir=Path(args.pdf_dir),
            )
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

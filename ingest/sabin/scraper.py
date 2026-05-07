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


def _safe_dir_name(slug: str, max_len: int = 200) -> str:
    """Return a filesystem-safe directory name for a slug.

    Long slugs (Brazilian cases can be 300+ chars) exceed Linux's 255-byte
    filename limit. For oversize slugs, keep the first max_len-9 chars
    (still readable) and append '-' + 8-char SHA256 prefix for uniqueness.
    """
    if len(slug.encode("utf-8")) <= max_len:
        return slug
    import hashlib

    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()[:8]
    return f"{slug[: max_len - 9]}-{digest}"


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
    """Extract text from a PDF via pymupdf. Returns empty string on failure.

    Strips NUL (0x00) bytes — Postgres TEXT columns reject them — and
    normalizes whitespace lightly. Other low-control characters are kept.
    """
    log = structlog.get_logger("ingest.sabin.scraper")
    try:
        import pymupdf

        doc = pymupdf.open(pdf_path)
        try:
            text = "\n\n".join(str(page.get_text("text")) for page in doc)
        finally:
            doc.close()
        # Postgres TEXT can't store NULs; pymupdf occasionally emits them.
        return text.replace("\x00", "")
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
        # Some Sabin slugs exceed Linux's 255-byte filename limit (Brazilian
        # multi-defendant cases can be 300+ chars). Hash long slugs to keep
        # the per-case PDF directory name short and stable.
        case_pdf_dir = pdf_dir / _safe_dir_name(slug)

        async def fetch_and_extract(url: str) -> dict[str, Any] | None:
            async with pdf_sem:
                filename = url.rsplit("/", 1)[-1]
                target = case_pdf_dir / filename
                ok = await download_pdf(client, url, target)
                if not ok:
                    return None
                try:
                    text = extract_pdf_text(target)
                finally:
                    # The text is now in memory and will be persisted to
                    # postgres by the caller — we don't need the PDF on disk.
                    # Without this, ~14 PDFs/case x 4,800 cases x ~1 MB
                    # accumulates to ~65 GB and fills the VPS.
                    target.unlink(missing_ok=True)
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


async def get_known_slugs(*, only_missing_metadata: bool = False) -> list[str]:
    """Read existing Sabin family slugs from citation_string.text.

    During the prior CPR-API ingest we stored each case's family slug inside
    the citation_string text as a URL of the form
    "...climatecasechart.com/document/<family-slug>)". Extract those.

    Args:
        only_missing_metadata: when True, return only slugs of cases whose
            upstream_metadata column is NULL — i.e. cases that haven't been
            re-processed by the current scraper. Use this on restart to
            avoid re-downloading PDFs for cases already enriched.

    (We don't have a dedicated family_slug column on case_record yet — adding
    one would be cleaner long-term but for the bootstrap migration this works.)
    """
    from server.db import get_pool

    pool = await get_pool()
    slugs: list[str] = []
    extra_where = "AND c.upstream_metadata IS NULL" if only_missing_metadata else ""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                rf"""
                SELECT DISTINCT (regexp_match(
                    cs.text,
                    'climatecasechart\.com/document/([^)\s]+)'
                ))[1] AS slug
                FROM citation_string cs
                JOIN case_record c ON c.id = cs.case_id
                WHERE c.primary_source = 'sabin'
                  AND cs.text ~ 'climatecasechart\.com/document/'
                  {extra_where}
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
    only_missing_metadata: bool = False,
) -> dict[str, int]:
    """Scrape all known case slugs from climatecasechart.com directly."""
    from server.db import get_pool

    log = structlog.get_logger("ingest.sabin.scraper")
    upstream_version = upstream_version or f"sabin-scrape-{datetime.now(tz=UTC).date().isoformat()}"
    retrieved_at = datetime.now(tz=UTC)

    if slugs is None:
        log.info("loading_slugs_from_db", only_missing_metadata=only_missing_metadata)
        slugs = await get_known_slugs(only_missing_metadata=only_missing_metadata)
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
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help=(
            "Only process cases whose upstream_metadata column is NULL. "
            "Use on restart to avoid re-downloading PDFs for cases already enriched."
        ),
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
                only_missing_metadata=args.only_missing,
            )
        finally:
            await close_pool()

    summary = asyncio.run(runner())
    print(f"DONE: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

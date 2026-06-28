# pyright: basic
"""Ingest the CCLW (Climate Change Laws of the World) legislation layer.

Source: ClimatePolicyRadar/all-document-text-data on Hugging Face (gated, CC-BY).
The dataset is block-level (~70M text blocks, 3.6 GB parquet) across several
corpora; we take corpus_type_name='Laws and Policies', aggregate each law's text
blocks into one document, and upsert into the `statute` table (which migration 0004
built for exactly this). Missing country codes are added to vocabulary_jurisdiction
on the fly (ISO3 -> our alpha-2 via pycountry).

Auth: reads ~/.hf_token or $HF_TOKEN. Run via:
    uv run python -m ingest.cclw [--limit N] [--dest DIR] [--sample FILE ...]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

log = structlog.get_logger("ingest.cclw")

DATASET = "ClimatePolicyRadar/all-document-text-data"

# Non-ISO / regional geography codes CCLW uses that pycountry won't resolve.
_GEO_OVERRIDE: dict[str, tuple[str, str, str]] = {
    "XKX": ("XK", "Kosovo", "national"),
    "EUR": ("XA", "European Union", "regional"),
    "XAA": ("XA", "International", "international"),
}


def _hf_token() -> str:
    tok = os.environ.get("HF_TOKEN")
    if not tok:
        path = Path(os.path.expanduser("~/.hf_token"))
        if path.exists():
            tok = path.read_text().strip()
    if not tok:
        raise RuntimeError("no HF token: set $HF_TOKEN or write it to ~/.hf_token")
    return tok


def map_jurisdiction(geographies: Any) -> tuple[str, str, str]:
    """ISO3 geography list -> (alpha2_code, name, kind). Falls back to XX (unspecified)."""
    import pycountry

    if not geographies:
        return ("XX", "Unspecified", "international")
    g = str(geographies[0]).strip().upper()
    if g in _GEO_OVERRIDE:
        return _GEO_OVERRIDE[g]
    country = pycountry.countries.get(alpha_3=g)
    if country is not None:
        return (country.alpha_2, country.name, "national")
    return ("XX", "Unspecified", "international")


def _parquet_urls(token: str) -> list[str]:
    import httpx

    r = httpx.get(
        f"https://datasets-server.huggingface.co/parquet?dataset={DATASET}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
        follow_redirects=True,
    )
    r.raise_for_status()
    return [f["url"] for f in r.json()["parquet_files"]]


def _download(token: str, urls: list[str], dest_dir: Path) -> list[str]:
    import httpx

    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for i, url in enumerate(urls):
        p = dest_dir / f"cclw_{i:04d}.parquet"
        if not p.exists() or p.stat().st_size == 0:
            with httpx.stream(
                "GET",
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=600,
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                with open(p, "wb") as f:
                    for chunk in resp.iter_bytes(1 << 20):
                        f.write(chunk)
            log.info("downloaded", file=p.name, mb=p.stat().st_size // 1_000_000)
        paths.append(str(p))
    return paths


def _aggregate_laws(parquet_paths: list[str], limit: int | None):
    import duckdb

    files = "[" + ",".join("'" + p + "'" for p in parquet_paths) + "]"
    q = f"""
        SELECT "document_metadata.family_import_id" AS cclw_id,
               any_value("document_metadata.family_title") AS title,
               any_value("document_metadata.geographies") AS geo,
               any_value("document_metadata.publication_ts") AS pub,
               any_value("document_metadata.category") AS category,
               any_value("document_metadata.languages") AS langs,
               string_agg("text_block.text", chr(10)
                          ORDER BY "text_block.index") AS body
        FROM read_parquet({files})
        WHERE "document_metadata.corpus_type_name" = 'Laws and Policies'
          AND "document_metadata.family_import_id" IS NOT NULL
          AND "text_block.text" IS NOT NULL
        GROUP BY 1
    """
    if limit is not None:
        q += f" LIMIT {int(limit)}"
    con = duckdb.connect()
    cur = con.execute(q)
    while True:
        batch = cur.fetchmany(25)
        if not batch:
            break
        for cclw_id, title, geo, pub, category, langs, body in batch:
            yield {
                "cclw_id": cclw_id,
                "title": title,
                "geo": list(geo) if geo is not None else [],
                "pub": pub,
                "category": category,
                "langs": list(langs) if langs is not None else [],
                "body": body,
            }


def _to_date(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


_UPSERT = """
    INSERT INTO statute
        (cclw_id, jurisdiction_code, short_title, long_title, enacted_date, status,
         text, text_lang, text_content_hash, provenance)
    VALUES (%(cclw_id)s, %(jur)s, %(short)s, %(long)s, %(enacted)s, %(status)s,
            %(text)s, %(lang)s, %(hash)s, %(prov)s::jsonb)
    ON CONFLICT (cclw_id) DO UPDATE SET
        jurisdiction_code = EXCLUDED.jurisdiction_code,
        short_title = EXCLUDED.short_title,
        long_title = EXCLUDED.long_title,
        enacted_date = EXCLUDED.enacted_date,
        status = EXCLUDED.status,
        text = EXCLUDED.text,
        text_lang = EXCLUDED.text_lang,
        text_content_hash = EXCLUDED.text_content_hash,
        provenance = EXCLUDED.provenance,
        updated_at = now()
"""


async def ingest_cclw(
    *, parquet_paths: list[str] | None = None, dest_dir: str | None = None, limit: int | None = None
) -> dict[str, int]:
    import json

    from server.db import get_pool

    token = _hf_token()
    if parquet_paths is None:
        dd = Path(dest_dir or "/tmp/cclw_parquet")
        parquet_paths = _download(token, _parquet_urls(token), dd)
    log.info("aggregating_laws", shards=len(parquet_paths))

    pool = await get_pool()
    statutes = 0
    async with pool.connection() as conn:
        for law in _aggregate_laws(parquet_paths, limit):
            if not law["title"] or not law["body"]:
                continue
            code, name, kind = map_jurisdiction(law["geo"])
            text = law["body"]
            prov = json.dumps(
                {
                    "source": "cclw",
                    "family_import_id": law["cclw_id"],
                    "corpus": "Laws and Policies",
                }
            )
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO vocabulary_jurisdiction "
                    "(code, name, kind, source, source_version) "
                    "VALUES (%s, %s, %s, 'cclw', 'cclw-2026') "
                    "ON CONFLICT (code) DO NOTHING",
                    (code, name, kind),
                )
                await cur.execute(
                    _UPSERT,
                    {
                        "cclw_id": law["cclw_id"],
                        "jur": code,
                        "short": law["title"][:1000],
                        "long": None,
                        "enacted": _to_date(law["pub"]),
                        "status": (law["category"] or "Unknown")[:100],
                        "text": text,
                        "lang": (law["langs"][0] if law["langs"] else "en"),
                        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        "prov": prov,
                    },
                )
            await conn.commit()
            statutes += 1
            if statutes % 100 == 0:
                log.info("progress", statutes=statutes)
    log.info("cclw_complete", statutes=statutes)
    return {"statutes": statutes}


def main() -> int:
    from server._logging import configure_logging
    from server.db import close_pool

    parser = argparse.ArgumentParser(description="Ingest CCLW laws into the statute table.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dest", type=str, default=None, help="dir for downloaded parquet shards")
    parser.add_argument(
        "--sample", nargs="*", default=None, help="use these parquet files (skip download)"
    )
    args = parser.parse_args()
    configure_logging(level="INFO", json=False)

    async def runner() -> dict[str, int]:
        try:
            return await ingest_cclw(
                parquet_paths=args.sample, dest_dir=args.dest, limit=args.limit
            )
        finally:
            await close_pool()

    result = asyncio.run(runner())
    print(f"DONE: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from ingest.sabin.models import SabinCaseRecord
from ingest.sabin.parse import parse_sabin_record
from ingest.sabin.upsert import upsert_case
from server._logging import configure_logging, get_logger
from server.db import close_pool, get_pool


async def ingest_one(fixture_path: Path, upstream_version: str) -> str:
    log = get_logger("ingest.sabin.ingest_one")
    payload = json.loads(fixture_path.read_text())
    record = SabinCaseRecord.model_validate(payload)
    parsed = parse_sabin_record(
        record,
        retrieved_at=datetime.now(tz=UTC),
        upstream_version=upstream_version,
    )
    pool = await get_pool()
    try:
        case_id = await upsert_case(pool, parsed)
    finally:
        await close_pool()
    log.info("case_upserted", sabin_id=record.sabin_id, case_id=case_id)
    return case_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one Sabin case from a JSON fixture.")
    parser.add_argument("path", type=Path, help="Path to the JSON fixture")
    parser.add_argument(
        "--upstream-version",
        default=f"manual-{datetime.now(tz=UTC).date().isoformat()}",
        help="Upstream version label stored in provenance",
    )
    args = parser.parse_args()

    configure_logging(level="INFO", json=False)
    case_id = asyncio.run(ingest_one(args.path, args.upstream_version))
    print(f"case_id={case_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

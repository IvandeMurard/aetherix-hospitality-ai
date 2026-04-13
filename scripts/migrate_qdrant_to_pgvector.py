#!/usr/bin/env python3
"""One-shot migration script: Qdrant fb_patterns → Supabase pgvector.

Usage
-----
Run once from the repo root after applying the pgvector migrations:

    cd /path/to/repo
    python scripts/migrate_qdrant_to_pgvector.py [--dry-run] [--batch-size N]

Requirements
------------
- QDRANT_URL, QDRANT_API_KEY  — source collection
- DATABASE_URL                 — target Supabase PostgreSQL (asyncpg DSN)

The script is idempotent: each Qdrant point id is stored in the ``payload``
JSONB column so a second run will detect conflicts and skip existing rows via
``INSERT … ON CONFLICT DO NOTHING``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

COLLECTION = "fb_patterns"
BATCH_SIZE_DEFAULT = 100


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


async def migrate(dry_run: bool, batch_size: int) -> None:
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    database_url = os.getenv("DATABASE_URL")

    if not qdrant_url:
        logger.error("QDRANT_URL not set — aborting.")
        sys.exit(1)
    if not database_url:
        logger.error("DATABASE_URL not set — aborting.")
        sys.exit(1)

    qdrant = QdrantClient(url=qdrant_url, api_key=qdrant_key)

    # Count source records
    collection_info = qdrant.get_collection(COLLECTION)
    total = collection_info.points_count
    logger.info("Source: Qdrant collection '%s' — %d points", COLLECTION, total)

    if dry_run:
        logger.info("Dry-run mode: no writes will be performed.")

    # asyncpg for raw COPY-style inserts (fastest for bulk loads)
    pg_dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)

    try:
        inserted = 0
        skipped = 0
        offset = None  # Qdrant scroll cursor

        while True:
            scroll_result = qdrant.scroll(
                collection_name=COLLECTION,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            points, next_offset = scroll_result

            if not points:
                break

            rows_to_insert = []
            for point in points:
                payload = point.payload or {}
                service_type = payload.get("service_type", "unknown")
                occupancy_band = payload.get("occupancy_band")
                day_of_week = payload.get("day_of_week")
                # Preserve original Qdrant point id for idempotency
                payload["_qdrant_id"] = str(point.id)

                vec = _vec_literal(point.vector)
                rows_to_insert.append(
                    (service_type, occupancy_band, day_of_week, json.dumps(payload), vec)
                )

            if not dry_run and rows_to_insert:
                # Use unnest for bulk insert
                result = await conn.executemany(
                    """
                    INSERT INTO fb_patterns
                        (service_type, occupancy_band, day_of_week, payload, embedding)
                    VALUES
                        ($1, $2, $3, $4::jsonb, $5::vector)
                    ON CONFLICT DO NOTHING
                    """,
                    rows_to_insert,
                )
                inserted += len(rows_to_insert)
            else:
                skipped += len(rows_to_insert)

            logger.info(
                "Processed %d/%d points (inserted=%d, dry-run skipped=%d)",
                min(inserted + skipped, total),
                total,
                inserted,
                skipped,
            )

            if next_offset is None:
                break
            offset = next_offset

    finally:
        await conn.close()

    logger.info(
        "Migration complete — %d inserted, %d dry-run skipped.",
        inserted,
        skipped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Qdrant fb_patterns to pgvector")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be inserted without writing to Supabase",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE_DEFAULT,
        help=f"Points per Qdrant scroll page (default: {BATCH_SIZE_DEFAULT})",
    )
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run, batch_size=args.batch_size))


if __name__ == "__main__":
    main()

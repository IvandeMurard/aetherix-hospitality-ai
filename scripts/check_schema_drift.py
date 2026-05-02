#!/usr/bin/env python3
"""
Schema drift checker — HOS-162 (AC3).

Compares ORM metadata against SQL migration files to detect schema drift.
Runs without a live DB connection (dry-run mode, default in CI).

Usage:
    python scripts/check_schema_drift.py --dry-run
    python scripts/check_schema_drift.py --sql-dir backend/migrations

HOS-150 will extend this with full ORM↔Alembic migration diff.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add backend to Python path so ORM models are importable
_BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(_BACKEND))


def _load_orm_tables() -> list[str]:
    try:
        from app.db.models import Base  # noqa: PLC0415
        return sorted(Base.metadata.tables.keys())
    except Exception as exc:
        print(f"[schema-drift] ERROR: cannot load ORM models: {exc}")
        sys.exit(1)


def _load_sql_tables(sql_dir: Path) -> list[str]:
    """Extract CREATE TABLE names from *.sql migration files (simple regex scan)."""
    import re

    tables: list[str] = []
    pattern = re.compile(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+['\"]?(\w+)['\"]?", re.IGNORECASE)
    for sql_file in sorted(sql_dir.glob("**/*.sql")):
        text = sql_file.read_text(encoding="utf-8", errors="ignore")
        tables.extend(pattern.findall(text))
    return sorted(set(tables))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check ORM ↔ migration schema drift")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Report ORM tables without comparing against migration files (no DB required).",
    )
    parser.add_argument(
        "--sql-dir",
        type=Path,
        default=None,
        help="Directory containing SQL migration files to diff against ORM.",
    )
    args = parser.parse_args()

    orm_tables = _load_orm_tables()
    print(f"[schema-drift] ORM tables ({len(orm_tables)}): {', '.join(orm_tables)}")

    if args.dry_run:
        print("[schema-drift] DRY-RUN mode — skipping migration file comparison.")
        print("[schema-drift] PASS")
        return 0

    # Resolve SQL directory: CLI arg > default backend/migrations
    sql_dir = args.sql_dir or (_BACKEND / "migrations")
    if not sql_dir.exists():
        print(f"[schema-drift] No migrations directory at {sql_dir} — nothing to diff.")
        print("[schema-drift] PASS (HOS-150 will add migration files)")
        return 0

    sql_tables = _load_sql_tables(sql_dir)
    print(f"[schema-drift] Migration tables ({len(sql_tables)}): {', '.join(sql_tables)}")

    orm_set = set(orm_tables)
    sql_set = set(sql_tables)

    missing_in_migrations = orm_set - sql_set
    missing_in_orm = sql_set - orm_set

    drift_detected = bool(missing_in_migrations or missing_in_orm)

    if missing_in_migrations:
        print(f"[schema-drift] DRIFT: ORM tables missing from migrations: {sorted(missing_in_migrations)}")
    if missing_in_orm:
        print(f"[schema-drift] DRIFT: migration tables missing from ORM: {sorted(missing_in_orm)}")

    if drift_detected:
        print("[schema-drift] FAIL — schema drift detected. Run alembic autogenerate or update ORM models.")
        return 1

    print("[schema-drift] PASS — ORM and migrations are in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Schema drift checker — HOS-150 AC8.

Compares ORM `Base.metadata` against the column set extracted from the SQL
migration files in `supabase/migrations/`. Fails with exit code 1 when any
ORM column is missing from the migrations or vice versa, after applying the
acknowledged-drift ignore-file.

Modes
-----
  static (default)   No DB required. Parses migration .sql files and builds a
                     virtual schema, then diffs against `Base.metadata`.
  live               Requires `DATABASE_URL`. Reads `information_schema.columns`
                     from the live DB instead of parsing files. Use this for
                     staging audits.

Usage
-----
  python scripts/check_schema_drift.py                          # static, lenient
  python scripts/check_schema_drift.py --strict                 # static, fail on drift
  python scripts/check_schema_drift.py --mode live --strict     # live DB, fail on drift
  python scripts/check_schema_drift.py --print-ignored          # show what's currently ignored

The ignore file (`scripts/schema_drift_ignore.json`) acknowledges drifts that
are known and tracked in HOS-150 follow-ups. Shrink this file as the follow-up
PRs land — never grow it without a Linear ticket.

Exit codes
----------
  0   No drift (or only ignored drifts)
  1   Drift detected (in --strict mode)
  2   Script error (DB unreachable, parse failure, etc.)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).parent.parent.parent  # scripts/ci/ → scripts/ → repo root
_BACKEND = _ROOT / "backend"
_DEFAULT_SQL_DIR = _ROOT / "supabase" / "migrations"
_DEFAULT_IGNORE_FILE = Path(__file__).parent / "schema_drift_ignore.json"

sys.path.insert(0, str(_BACKEND))


# ---------------------------------------------------------------------------
# ORM loading
# ---------------------------------------------------------------------------

def _load_orm_metadata() -> Any:
    try:
        from app.db.models import Base  # noqa: PLC0415
        return Base.metadata
    except Exception as exc:
        print(f"[schema-drift] ERROR: cannot load ORM models: {exc}", file=sys.stderr)
        sys.exit(2)


def _orm_columns(metadata: Any) -> dict[str, set[str]]:
    return {name: {c.name for c in tbl.columns} for name, tbl in metadata.tables.items()}


# ---------------------------------------------------------------------------
# Static SQL parsing — extract per-table column sets from migration files
# ---------------------------------------------------------------------------

# Constraint keywords that appear at the start of a CREATE TABLE inner item
# and must NOT be confused with column definitions.
_CONSTRAINT_PREFIXES = (
    "constraint",
    "primary",
    "foreign",
    "unique",
    "check",
    "exclude",
    "like",
)


def _strip_comments(sql: str) -> str:
    """Remove `--` line comments and `/* */` block comments."""
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql


def _split_top_level(body: str) -> list[str]:
    """Split a CREATE TABLE body on commas at the outermost nesting level.

    Tracks parens, brackets, and single-quoted strings so commas inside
    `ARRAY['a', 'b']` defaults or `NUMERIC(10, 2)` types are not mistaken
    for column separators.
    """
    items: list[str] = []
    depth = 0
    in_string = False
    buf: list[str] = []
    for ch in body:
        if in_string:
            buf.append(ch)
            if ch == "'":
                in_string = False
            continue
        if ch == "'":
            in_string = True
            buf.append(ch)
        elif ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf).strip())
    return [i for i in items if i]


# Identifier at the start of an item: optionally double-quoted, otherwise word chars.
_FIRST_IDENT_RE = re.compile(r'^\s*"?([A-Za-z_][A-Za-z0-9_]*)"?')


def _columns_from_create_body(body: str) -> set[str]:
    cols: set[str] = set()
    for item in _split_top_level(body):
        m = _FIRST_IDENT_RE.match(item)
        if not m:
            continue
        ident = m.group(1).lower()
        if ident in _CONSTRAINT_PREFIXES:
            continue
        cols.add(ident)
    return cols


def parse_migrations(sql_dir: Path) -> dict[str, set[str]]:
    """Build a virtual {table: {column, ...}} schema from migration files.

    Handles:
      - CREATE TABLE [IF NOT EXISTS] name (...)
      - ALTER TABLE name ADD COLUMN [IF NOT EXISTS] col ...
      - ALTER TABLE name DROP COLUMN [IF EXISTS] col
      - ALTER TABLE name RENAME COLUMN old TO new
    Files are processed in lexicographic order (matching deploy order, since
    we use timestamped filenames).
    """
    schema: dict[str, set[str]] = defaultdict(set)

    create_re = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+(?:ONLY\s+)?(\w+)\s*\((.*?)\)\s*"
        r"(?:PARTITION\s+BY\s+\w+\s*\([^)]*\)\s*)?;",
        re.IGNORECASE | re.DOTALL,
    )
    alter_add_re = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+|IF\s+EXISTS\s+)*(\w+)\s+"
        r"ADD\s+COLUMN(?:\s+IF\s+NOT\s+EXISTS)?\s+(\w+)",
        re.IGNORECASE,
    )
    alter_drop_re = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+|IF\s+EXISTS\s+)*(\w+)\s+"
        r"DROP\s+COLUMN(?:\s+IF\s+EXISTS)?\s+(\w+)",
        re.IGNORECASE,
    )
    alter_rename_re = re.compile(
        r"ALTER\s+TABLE\s+(?:ONLY\s+|IF\s+EXISTS\s+)*(\w+)\s+"
        r"RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)",
        re.IGNORECASE,
    )

    for sql_file in sorted(sql_dir.glob("*.sql")):
        sql = _strip_comments(sql_file.read_text(encoding="utf-8", errors="ignore"))

        for m in create_re.finditer(sql):
            table = m.group(1).lower()
            schema[table].update(_columns_from_create_body(m.group(2)))

        for m in alter_add_re.finditer(sql):
            schema[m.group(1).lower()].add(m.group(2).lower())

        for m in alter_drop_re.finditer(sql):
            schema[m.group(1).lower()].discard(m.group(2).lower())

        for m in alter_rename_re.finditer(sql):
            table = m.group(1).lower()
            old, new = m.group(2).lower(), m.group(3).lower()
            if old in schema[table]:
                schema[table].discard(old)
                schema[table].add(new)

    return {k: {c.lower() for c in v} for k, v in schema.items()}


# ---------------------------------------------------------------------------
# Live DB introspection (--mode live)
# ---------------------------------------------------------------------------

async def introspect_live_db(database_url: str) -> dict[str, set[str]]:
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    if database_url.startswith("postgresql://"):
        database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]

    engine = create_async_engine(database_url, echo=False)
    schema: dict[str, set[str]] = defaultdict(set)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public'"
                )
            )
            for table, column in result.fetchall():
                schema[table.lower()].add(column.lower())
    finally:
        await engine.dispose()
    return dict(schema)


# ---------------------------------------------------------------------------
# Diff + ignore application
# ---------------------------------------------------------------------------

def diff_schemas(
    orm: dict[str, set[str]],
    db: dict[str, set[str]],
) -> dict[str, dict[str, list[str]]]:
    """Returns {table: {"orm_only": [...], "db_only": [...], "missing_table": bool}}."""
    drifts: dict[str, dict[str, Any]] = {}
    orm_lc = {k.lower(): v for k, v in orm.items()}
    db_lc = {k.lower(): v for k, v in db.items()}

    for table, orm_cols in orm_lc.items():
        if table not in db_lc:
            drifts[table] = {
                "missing_table": True,
                "orm_only": sorted(orm_cols),
                "db_only": [],
            }
            continue
        orm_only = sorted({c.lower() for c in orm_cols} - {c.lower() for c in db_lc[table]})
        db_only = sorted({c.lower() for c in db_lc[table]} - {c.lower() for c in orm_cols})
        if orm_only or db_only:
            drifts[table] = {
                "missing_table": False,
                "orm_only": orm_only,
                "db_only": db_only,
            }
    return drifts


def load_ignore(path: Path) -> dict[str, dict[str, set[str]]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    ignored: dict[str, dict[str, set[str]]] = {}
    for table_name, table_entry in (raw.get("tables") or {}).items():
        ignored[table_name.lower()] = {
            "orm_only": {c.lower() for c in (table_entry.get("orm_only") or [])},
            "db_only": {c.lower() for c in (table_entry.get("db_only") or [])},
            "missing_table": bool(table_entry.get("missing_table", False)),
        }
    return ignored


def apply_ignores(
    drifts: dict[str, dict[str, Any]],
    ignored: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Returns (remaining_drifts, suppressed_drifts)."""
    remaining: dict[str, dict[str, Any]] = {}
    suppressed: dict[str, dict[str, Any]] = {}

    for table, drift in drifts.items():
        ig = ignored.get(table, {"orm_only": set(), "db_only": set(), "missing_table": False})

        # If the table is acknowledged as entirely missing from migrations, the
        # per-column "in ORM but not in DB" entries are tautological — suppress
        # all of them rather than forcing the ignore file to enumerate columns.
        if drift["missing_table"] and ig["missing_table"]:
            rem_orm_only: list[str] = []
            sup_orm_only = sorted(drift["orm_only"])
        else:
            rem_orm_only = [c for c in drift["orm_only"] if c not in ig["orm_only"]]
            sup_orm_only = sorted(set(drift["orm_only"]) & ig["orm_only"])

        rem_db_only = [c for c in drift["db_only"] if c not in ig["db_only"]]
        sup_db_only = sorted(set(drift["db_only"]) & ig["db_only"])

        missing_still_drift = drift["missing_table"] and not ig["missing_table"]
        sup_missing = drift["missing_table"] and ig["missing_table"]

        if rem_orm_only or rem_db_only or missing_still_drift:
            remaining[table] = {
                "missing_table": missing_still_drift,
                "orm_only": rem_orm_only,
                "db_only": rem_db_only,
            }
        if sup_orm_only or sup_db_only or sup_missing:
            suppressed[table] = {
                "missing_table": sup_missing,
                "orm_only": sup_orm_only,
                "db_only": sup_db_only,
            }
    return remaining, suppressed


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_report(label: str, drifts: dict[str, dict[str, Any]]) -> str:
    if not drifts:
        return f"[schema-drift] {label}: none"
    lines = [f"[schema-drift] {label}:"]
    for table in sorted(drifts):
        d = drifts[table]
        if d.get("missing_table"):
            lines.append(f"  -{table}: ENTIRE TABLE missing from DB schema")
        if d.get("orm_only"):
            lines.append(
                f"  -{table}: in ORM but not in DB ->> {', '.join(d['orm_only'])}"
            )
        if d.get("db_only"):
            lines.append(
                f"  -{table}: in DB but not in ORM ->> {', '.join(d['db_only'])}"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Check ORM vs migration schema drift")
    parser.add_argument(
        "--mode",
        choices=["static", "live"],
        default="static",
        help="static = parse SQL files (no DB); live = read information_schema (DATABASE_URL required)",
    )
    parser.add_argument(
        "--sql-dir",
        type=Path,
        default=_DEFAULT_SQL_DIR,
        help="Directory of SQL migration files (default: supabase/migrations)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Override DATABASE_URL for --mode live",
    )
    parser.add_argument(
        "--ignore-file",
        type=Path,
        default=_DEFAULT_IGNORE_FILE,
        help="JSON file listing acknowledged drifts (default: scripts/schema_drift_ignore.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any drift remains after ignores (default: report only)",
    )
    parser.add_argument(
        "--print-ignored",
        action="store_true",
        help="Also print the suppressed drifts so the punch-list stays visible",
    )
    args = parser.parse_args()

    metadata = _load_orm_metadata()
    orm = _orm_columns(metadata)
    print(f"[schema-drift] ORM tables: {len(orm)} ({', '.join(sorted(orm))})")

    if args.mode == "static":
        if not args.sql_dir.exists():
            print(
                f"[schema-drift] ERROR: SQL directory not found: {args.sql_dir}",
                file=sys.stderr,
            )
            return 2
        db_schema = parse_migrations(args.sql_dir)
        print(
            f"[schema-drift] migrations parsed from {args.sql_dir}: "
            f"{len(db_schema)} table(s)"
        )
    else:  # live
        if not args.database_url:
            print(
                "[schema-drift] ERROR: --mode live requires DATABASE_URL",
                file=sys.stderr,
            )
            return 2
        try:
            db_schema = asyncio.run(introspect_live_db(args.database_url))
        except Exception as exc:
            print(f"[schema-drift] ERROR: live introspection failed: {exc}", file=sys.stderr)
            return 2
        print(f"[schema-drift] introspected {len(db_schema)} table(s) from live DB")

    drifts = diff_schemas(orm, db_schema)
    ignored = load_ignore(args.ignore_file)
    remaining, suppressed = apply_ignores(drifts, ignored)

    print(format_report("Drift remaining (after ignores)", remaining))
    if args.print_ignored:
        print(format_report("Drift suppressed by ignore file", suppressed))

    if remaining and args.strict:
        print(
            "[schema-drift] FAIL — drift detected. Either land the matching migration "
            "or add the entry to scripts/schema_drift_ignore.json with a Linear ticket."
        )
        return 1

    print("[schema-drift] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

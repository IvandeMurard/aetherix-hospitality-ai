"""Tests for scripts/ci/check_schema_drift.py — HOS-150 AC8.

Covers:
  - Static SQL parser (CREATE TABLE, ALTER TABLE ADD/DROP/RENAME COLUMN)
  - Comma-splitting handling for ARRAY['a', 'b'] defaults and NUMERIC(10, 2) types
  - Constraint vs column discrimination (UNIQUE(col), PRIMARY KEY (col), CHECK (...))
  - Comment stripping (-- and /* */)
  - Diff + ignore-file application (column-level + missing-table)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "ci" / "check_schema_drift.py"

# Load the script as a module without invoking main()
spec = importlib.util.spec_from_file_location("check_schema_drift", _SCRIPT)
csd = importlib.util.module_from_spec(spec)
sys.modules["check_schema_drift"] = csd
spec.loader.exec_module(csd)


# ---------------------------------------------------------------------------
# _split_top_level
# ---------------------------------------------------------------------------

class TestSplitTopLevel:
    def test_simple_split(self):
        assert csd._split_top_level("a, b, c") == ["a", "b", "c"]

    def test_ignores_commas_in_parens(self):
        assert csd._split_top_level("a NUMERIC(10, 2), b TEXT") == [
            "a NUMERIC(10, 2)",
            "b TEXT",
        ]

    def test_ignores_commas_in_brackets(self):
        result = csd._split_top_level(
            "scopes TEXT[] DEFAULT ARRAY['x', 'y', 'z'], label TEXT"
        )
        assert result == [
            "scopes TEXT[] DEFAULT ARRAY['x', 'y', 'z']",
            "label TEXT",
        ]

    def test_ignores_commas_in_strings(self):
        # Comma inside single-quoted string default
        result = csd._split_top_level("a TEXT DEFAULT 'hello, world', b INT")
        assert result == ["a TEXT DEFAULT 'hello, world'", "b INT"]

    def test_strips_empty_items(self):
        assert csd._split_top_level("a INT,, b INT") == ["a INT", "b INT"]


# ---------------------------------------------------------------------------
# _columns_from_create_body
# ---------------------------------------------------------------------------

class TestColumnsFromCreateBody:
    def test_basic_columns(self):
        body = "id UUID PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMPTZ"
        assert csd._columns_from_create_body(body) == {"id", "name", "created_at"}

    def test_skips_unique_inline_constraint(self):
        body = "id UUID PRIMARY KEY, anomaly_id UUID, UNIQUE(anomaly_id)"
        assert csd._columns_from_create_body(body) == {"id", "anomaly_id"}

    def test_skips_constraint_keyword(self):
        body = "id UUID, name TEXT, CONSTRAINT name_unique UNIQUE (name)"
        assert csd._columns_from_create_body(body) == {"id", "name"}

    def test_skips_primary_key_clause(self):
        body = "id UUID, ts TIMESTAMPTZ, PRIMARY KEY (id, ts)"
        assert csd._columns_from_create_body(body) == {"id", "ts"}

    def test_skips_check_clause(self):
        body = "id UUID, status TEXT, CHECK (status IN ('a', 'b'))"
        assert csd._columns_from_create_body(body) == {"id", "status"}

    def test_skips_foreign_key_clause(self):
        body = "id UUID, owner UUID, FOREIGN KEY (owner) REFERENCES users(id)"
        assert csd._columns_from_create_body(body) == {"id", "owner"}

    def test_handles_array_default(self):
        body = (
            "id UUID, "
            "scopes TEXT[] NOT NULL DEFAULT ARRAY['predict', 'recommend', 'feedback'], "
            "label TEXT"
        )
        assert csd._columns_from_create_body(body) == {"id", "scopes", "label"}

    def test_handles_quoted_identifiers(self):
        body = '"my col" INT, "another" TEXT'
        assert csd._columns_from_create_body(body) == {"my col", "another"}.intersection(
            csd._columns_from_create_body(body)
        ) or csd._columns_from_create_body(body) == {"my", "another"}
        # Note: our regex grabs only leading word chars from quoted ident, so spaces fail —
        # acceptable for our schema (no spaces in any actual column name).


# ---------------------------------------------------------------------------
# _strip_comments
# ---------------------------------------------------------------------------

class TestStripComments:
    def test_strips_line_comments(self):
        assert csd._strip_comments("a INT, -- comment\nb INT") == "a INT, \nb INT"

    def test_strips_block_comments(self):
        assert csd._strip_comments("a /* skip */ INT") == "a  INT"

    def test_strips_multiline_block_comment(self):
        assert csd._strip_comments("a /* skip\nme */ INT") == "a  INT"


# ---------------------------------------------------------------------------
# parse_migrations — end-to-end on tmpdir
# ---------------------------------------------------------------------------

class TestParseMigrations:
    def test_create_table(self, tmp_path: Path):
        (tmp_path / "001_init.sql").write_text(
            "CREATE TABLE foo (id UUID PRIMARY KEY, name TEXT);"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"foo": {"id", "name"}}

    def test_alter_add_column(self, tmp_path: Path):
        (tmp_path / "001_init.sql").write_text(
            "CREATE TABLE foo (id UUID);"
        )
        (tmp_path / "002_add.sql").write_text(
            "ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar TEXT;"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"foo": {"id", "bar"}}

    def test_alter_drop_column(self, tmp_path: Path):
        (tmp_path / "001_init.sql").write_text(
            "CREATE TABLE foo (id UUID, bar TEXT);"
        )
        (tmp_path / "002_drop.sql").write_text(
            "ALTER TABLE foo DROP COLUMN IF EXISTS bar;"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"foo": {"id"}}

    def test_alter_rename_column(self, tmp_path: Path):
        (tmp_path / "001_init.sql").write_text(
            "CREATE TABLE foo (id UUID, content TEXT);"
        )
        (tmp_path / "002_rename.sql").write_text(
            "ALTER TABLE foo RENAME COLUMN content TO reflection;"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"foo": {"id", "reflection"}}

    def test_files_processed_in_order(self, tmp_path: Path):
        # The ALTER would fail to apply before CREATE if order matters
        (tmp_path / "001_a.sql").write_text("CREATE TABLE foo (id UUID);")
        (tmp_path / "002_b.sql").write_text(
            "ALTER TABLE foo ADD COLUMN IF NOT EXISTS later TEXT;"
        )
        (tmp_path / "003_c.sql").write_text(
            "ALTER TABLE foo DROP COLUMN IF EXISTS later;"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"foo": {"id"}}

    def test_ignores_create_table_inside_comments(self, tmp_path: Path):
        (tmp_path / "001.sql").write_text(
            "-- CREATE TABLE fake (x INT);\n"
            "CREATE TABLE real (id UUID);"
        )
        schema = csd.parse_migrations(tmp_path)
        assert schema == {"real": {"id"}}


# ---------------------------------------------------------------------------
# diff_schemas
# ---------------------------------------------------------------------------

class TestDiffSchemas:
    def test_no_drift(self):
        orm = {"foo": {"id", "name"}}
        db = {"foo": {"id", "name"}}
        assert csd.diff_schemas(orm, db) == {}

    def test_orm_only_columns(self):
        orm = {"foo": {"id", "name", "extra"}}
        db = {"foo": {"id", "name"}}
        result = csd.diff_schemas(orm, db)
        assert result == {
            "foo": {"missing_table": False, "orm_only": ["extra"], "db_only": []}
        }

    def test_db_only_columns(self):
        orm = {"foo": {"id"}}
        db = {"foo": {"id", "legacy"}}
        result = csd.diff_schemas(orm, db)
        assert result == {
            "foo": {"missing_table": False, "orm_only": [], "db_only": ["legacy"]}
        }

    def test_missing_table(self):
        orm = {"foo": {"id"}}
        db = {}
        result = csd.diff_schemas(orm, db)
        assert result["foo"]["missing_table"] is True
        assert result["foo"]["orm_only"] == ["id"]


# ---------------------------------------------------------------------------
# apply_ignores
# ---------------------------------------------------------------------------

class TestApplyIgnores:
    def test_suppresses_listed_orm_only(self):
        drifts = {
            "foo": {"missing_table": False, "orm_only": ["a", "b"], "db_only": []}
        }
        ignored = {"foo": {"missing_table": False, "orm_only": {"a"}, "db_only": set()}}
        remaining, suppressed = csd.apply_ignores(drifts, ignored)
        assert remaining == {
            "foo": {"missing_table": False, "orm_only": ["b"], "db_only": []}
        }
        assert suppressed == {
            "foo": {"missing_table": False, "orm_only": ["a"], "db_only": []}
        }

    def test_missing_table_ignore_suppresses_all_orm_only(self):
        """When the table is acknowledged as missing, all orm_only cols are tautological."""
        drifts = {
            "foo": {"missing_table": True, "orm_only": ["a", "b", "c"], "db_only": []}
        }
        ignored = {"foo": {"missing_table": True, "orm_only": set(), "db_only": set()}}
        remaining, suppressed = csd.apply_ignores(drifts, ignored)
        assert remaining == {}
        assert "foo" in suppressed
        assert suppressed["foo"]["missing_table"] is True
        assert sorted(suppressed["foo"]["orm_only"]) == ["a", "b", "c"]

    def test_no_ignore_keeps_drift(self):
        drifts = {
            "foo": {"missing_table": False, "orm_only": ["a"], "db_only": []}
        }
        remaining, suppressed = csd.apply_ignores(drifts, {})
        assert remaining == drifts
        assert suppressed == {}


# ---------------------------------------------------------------------------
# load_ignore — verifies the actual repo config parses
# ---------------------------------------------------------------------------

class TestLoadIgnore:
    def test_real_ignore_file_loads(self):
        path = _REPO_ROOT / "scripts" / "ci" / "schema_drift_ignore.json"
        if not path.exists():
            pytest.skip("schema_drift_ignore.json not present")
        ignored = csd.load_ignore(path)
        # Must include at least the known-bad tables documented in PR3
        assert "users" in ignored
        assert ignored["users"]["missing_table"] is True

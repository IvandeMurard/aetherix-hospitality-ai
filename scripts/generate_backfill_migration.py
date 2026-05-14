"""Generate DDL for ORM-only tables that lack a Supabase migration.

This is a one-shot tool used to backfill the missing tables discovered
during Phase 0 staging deploy (see schema_drift_ignore.json punch-list).

Outputs SQL to stdout. Redirect to a migration file:
    python scripts/generate_backfill_migration.py > supabase/migrations/<TS>_backfill_orm_only_tables.sql
"""
import os
import sys
from pathlib import Path

# Placeholder env vars so backend imports do not fail (we never connect to DB).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost:5432/x")
os.environ.setdefault("SUPABASE_URL", "https://x.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "x")
os.environ.setdefault("ANTHROPIC_API_KEY", "x")
os.environ.setdefault("MISTRAL_API_KEY", "x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("AUTH_SECRET", "x" * 32)

# Add backend/ to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql

from app.db.models import Base

TARGET = [
    "demand_anomalies",
    "staffing_recommendations",
    "conversational_queries",
    "captation_baselines",
    "local_events",
    "pms_sync_logs",
    "recommendation_cache",
    "training_runs",
]

print("-- Backfill missing ORM-only tables (Phase 0 deploy)")
print("-- Auto-generated via scripts/generate_backfill_migration.py")
print("-- Source of truth: backend/app/db/models.py")
print("-- Idempotent: CREATE TABLE/INDEX IF NOT EXISTS")
print()

dialect = postgresql.dialect()

for name in TARGET:
    if name not in Base.metadata.tables:
        print(f"-- WARN: {name} not in Base.metadata, skipped")
        continue
    table = Base.metadata.tables[name]
    print(f"-- ============== {name} ==============")
    ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
    ddl = ddl.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
    # Remove trailing newlines/whitespace before terminator
    if not ddl.endswith(";"):
        ddl += ";"
    print(ddl)
    print()
    for idx in table.indexes:
        try:
            idx_ddl = str(CreateIndex(idx).compile(dialect=dialect)).strip()
            idx_ddl = idx_ddl.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
            idx_ddl = idx_ddl.replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
            if not idx_ddl.endswith(";"):
                idx_ddl += ";"
            print(idx_ddl)
        except Exception as e:
            print(f"-- skipped index {idx.name}: {e}")
    print()

#!/usr/bin/env bash
# HOS-368 — replay supabase/migrations/ on a scratch Postgres, the way the
# `rls-audit` CI job needs it. Reproducible locally:
#
#   docker run -d --name pgv -e POSTGRES_PASSWORD=pw -p 5432:5432 pgvector/pgvector:pg17
#   DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres scripts/ci/apply_migrations.sh
#
# Needs a Postgres with the pgvector extension available and `psql` on PATH.
# Each migration runs in its own transaction and the first error aborts the
# script: a migration that does not replay cleanly is a finding, not noise.
#
# DATABASE_URL must be a plain libpq URL (postgresql://...), not the SQLAlchemy
# "postgresql+asyncpg://" form.
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required (postgresql://user:pw@host:port/db)}"

# The migrations are idempotent and emit hundreds of "already exists, skipping"
# NOTICEs; keep warnings and errors only.
export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
migrations="$here/../../supabase/migrations"

echo "::group::Supabase bootstrap (roles, auth schema, extensions)"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$here/supabase_bootstrap.sql"
echo "::endgroup::"

# Lexical order == timestamp order (file names are YYYYMMDDHHMMSS_*.sql).
count=0
for f in $(ls "$migrations"/*.sql | sort); do
  echo "applying $(basename "$f")"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -1 -f "$f"
  count=$((count + 1))
done
echo "applied $count migrations"

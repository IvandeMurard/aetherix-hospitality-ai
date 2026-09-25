#!/usr/bin/env bash
# Replay every Supabase migration on a fresh, throwaway Postgres database.
#
# Why: the Supabase Preview check replays the whole chain on an empty database,
# while production only ever runs new migrations on top of its history. A
# migration can therefore pass in production and fail on a fresh replay (see
# docs/context/migration-replay-drift.md). The static drift gate
# (check_schema_drift.py) cannot see this: it parses CREATE/ALTER TABLE text and
# does not know that a DO-block migration was skipped.
#
# Requirements: a local Postgres >= 15 with the pgvector and uuid-ossp
# extensions available (Debian/Ubuntu: postgresql-16 postgresql-16-pgvector),
# and a role allowed to create databases.
#
# Usage:
#   PGHOST=/var/run/postgresql PGPORT=5432 PGUSER=postgres scripts/ci/replay_migrations.sh [dbname]
#
# Exit codes: 0 replay passed end to end · 1 a migration failed (named on stdout).
# The database is dropped and recreated on every run; never point this at a
# database you care about.
set -euo pipefail

DB="${1:-aetherix_replay}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PSQL=(psql -X -q -v ON_ERROR_STOP=1)

"${PSQL[@]}" -d postgres -c "DROP DATABASE IF EXISTS ${DB}" -c "CREATE DATABASE ${DB}"

# Minimal stand-in for what Supabase provides before the first migration:
# API roles, the auth schema helpers the RLS policies call, and the default
# extensions. Replay-only; never applied anywhere else.
"${PSQL[@]}" -d "${DB}" <<'SQL'
DO $$ BEGIN
    CREATE ROLE anon NOLOGIN;
    CREATE ROLE authenticated NOLOGIN;
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS
    $f$ SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid $f$;
CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS
    $f$ SELECT coalesce(NULLIF(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $f$;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
SQL

count=0
for f in "${ROOT}"/supabase/migrations/*.sql; do
    # One transaction per file, in filename order: what Supabase does.
    if ! out=$("${PSQL[@]}" -d "${DB}" --single-transaction -f "$f" 2>&1); then
        echo "FAIL $(basename "$f")"
        echo "$out" | grep -v NOTICE
        exit 1
    fi
    count=$((count + 1))
done
echo "REPLAY OK: ${count} migrations applied on a fresh database (${DB})"

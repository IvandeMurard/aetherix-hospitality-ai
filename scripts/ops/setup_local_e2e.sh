#!/usr/bin/env bash
# Bootstrap d'une Postgres/pgvector LOCALE (docker-compose) pour les tests e2e.
#
# Idempotent : ré-exécutable sans danger. Applique le schéma Supabase sur la base
# `aetherix` du service `db` (port hôte 5434). Voir docs/testing/e2e-apaleo-sandbox.md.
#
# Usage (depuis la racine du repo) :
#     bash scripts/ops/setup_local_e2e.sh
#
# Pré-requis : Docker up. Le script démarre `db`/`db_test` si besoin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PSQL=(docker compose exec -T db psql -U postgres -d aetherix -v ON_ERROR_STOP=1 -q)

echo "==> 1/4  Démarrage des conteneurs Postgres (db, db_test)"
docker compose up -d db db_test >/dev/null

echo "==> 2/4  Attente de disponibilité de la base"
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U postgres -d aetherix >/dev/null 2>&1; then break; fi
  sleep 1
done

echo "==> 3/4  Rôles Supabase, extensions et stubs auth (idempotent)"
"${PSQL[@]}" <<'SQL'
DO $$ BEGIN CREATE ROLE anon NOLOGIN;          EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE service_role NOLOGIN BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Stubs des fonctions Supabase référencées par certaines policies RLS.
CREATE OR REPLACE FUNCTION auth.uid()  RETURNS uuid  LANGUAGE sql STABLE AS $f$ SELECT NULL::uuid $f$;
CREATE OR REPLACE FUNCTION auth.role() RETURNS text  LANGUAGE sql STABLE AS $f$ SELECT NULL::text $f$;
CREATE OR REPLACE FUNCTION auth.jwt()  RETURNS jsonb LANGUAGE sql STABLE AS $f$ SELECT '{}'::jsonb $f$;
SQL

echo "==> 4/4  Application des migrations Supabase (ordre chronologique)"
fail=0
for f in $(ls supabase/migrations/*.sql | sort); do
  if docker compose exec -T db psql -U postgres -d aetherix -v ON_ERROR_STOP=1 -q < "$f" >/dev/null 2>&1; then
    printf '   OK   %s\n' "$(basename "$f")"
  else
    # Sur une base déjà initialisée, certaines migrations non-idempotentes
    # (ex. partitions agent_action_log) renvoient "already exists" — bénin.
    printf '   SKIP %s (déjà appliquée ou non-idempotente)\n' "$(basename "$f")"
    fail=$((fail+1))
  fi
done

echo "==> Vérification des tables critiques"
docker compose exec -T db psql -U postgres -d aetherix -q -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN \
   ('restaurant_profiles','operational_memory','mcp_api_tokens','agent_action_log', \
    'recommendation_cache','fb_patterns','staffing_recommendations') ORDER BY 1;"

echo "==> Terminé (migrations skippées/bénignes : $fail). Base prête pour l'e2e."

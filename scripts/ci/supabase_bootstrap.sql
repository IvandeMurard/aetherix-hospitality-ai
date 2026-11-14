-- CI-only stand-in for the parts of Supabase that the migrations in
-- supabase/migrations/ assume already exist on a managed project (HOS-368).
--
-- A plain `postgres` service container has none of them:
--   * the API roles  anon / authenticated / service_role  (policies name them);
--   * the `auth` schema with auth.uid() / auth.jwt() / auth.role()
--     (policies in the early migrations call them);
--   * the extensions Supabase preinstalls: uuid-ossp, pgcrypto.
-- pgvector is NOT stubbed here: the job uses the pgvector/pgvector image, so
-- `CREATE EXTENSION vector` in the migrations is the real one.
--
-- This file is a test fixture, never applied to a real database.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
  LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION auth.role() RETURNS text
  LANGUAGE sql STABLE AS
  $$ SELECT nullif(current_setting('request.jwt.claim.role', true), '')::text $$;

CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb
  LANGUAGE sql STABLE AS
  $$ SELECT coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb $$;

GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;

-- CI-ONLY COMPATIBILITY SHIM FOR A PLAIN POSTGRESQL SERVICE.
--
-- Supabase owns the auth schema in hosted and local Supabase environments.
-- NovelAI's committed RLS migrations reference auth.uid() and Supabase's anon
-- and authenticated database roles. Clean migration replay on vanilla
-- PostgreSQL therefore needs these inert signatures. Do not run this file
-- against Supabase and do not expand it into a second auth implementation.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS auth;
REVOKE ALL ON SCHEMA auth FROM PUBLIC;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
SET search_path = ''
AS $$
    SELECT NULL::uuid;
$$;

REVOKE ALL ON FUNCTION auth.uid() FROM PUBLIC;

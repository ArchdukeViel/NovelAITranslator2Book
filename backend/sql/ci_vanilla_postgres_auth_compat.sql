-- CI-ONLY COMPATIBILITY SHIM FOR A PLAIN POSTGRESQL SERVICE.
--
-- Supabase owns the auth schema in hosted and local Supabase environments.
-- NovelAI's committed RLS migration references auth.uid(), so clean migration
-- replay on vanilla PostgreSQL needs only this inert signature. Do not run this
-- file against Supabase and do not expand it into a second auth implementation.

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

-- Run with psql variable runtime_password; never commit or print its value.
-- Example: psql "$MIGRATION_DATABASE_URL" -v runtime_password="..." -f backend/sql/provision_novelai_runtime.sql
\if :{?runtime_password}
\else
\error 'runtime_password psql variable is required'
\endif

SELECT format(
    'CREATE ROLE novelai_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_runtime')
\gexec

SELECT format('ALTER ROLE novelai_runtime PASSWORD %L', :'runtime_password')
\gexec

GRANT novelai_app TO novelai_runtime;

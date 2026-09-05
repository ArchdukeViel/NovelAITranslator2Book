-- PostgreSQL Least-Privilege Role Provisioning Script
-- Reference: F-2 & F-12 (postgres-database-hardening-and-security)
--
-- Roles:
-- 1. novelai_migrator : DDL owner, executes Alembic migrations only.
-- 2. novelai_app      : Backend API DML (SELECT, INSERT, UPDATE, DELETE), 15s timeout.
-- 3. novelai_reader   : Reader service read-only (SELECT on public catalog), 8s timeout.
-- 4. novelai_worker   : Background asynchronous worker (DML on jobs/leases), 60s timeout.

BEGIN;

-- Revoke default public schema creation from unprivileged users
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 1. Migrator Role (DDL & Schema Management)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_migrator') THEN
        CREATE ROLE novelai_migrator WITH LOGIN INHERIT;
    END IF;
END
$$;
ALTER ROLE novelai_migrator SET statement_timeout = '120s';
ALTER ROLE novelai_migrator SET lock_timeout = '5s';
GRANT USAGE, CREATE ON SCHEMA public TO novelai_migrator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO novelai_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO novelai_migrator;

-- 2. Application Service Role (API DML, Zero DDL)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_app') THEN
        CREATE ROLE novelai_app WITH LOGIN INHERIT;
    END IF;
END
$$;
ALTER ROLE novelai_app SET statement_timeout = '15s';
ALTER ROLE novelai_app SET lock_timeout = '2s';
GRANT USAGE ON SCHEMA public TO novelai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO novelai_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO novelai_app;

-- 3. Reader Service Role (Read-Only Public Catalog)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_reader') THEN
        CREATE ROLE novelai_reader WITH LOGIN INHERIT;
    END IF;
END
$$;
ALTER ROLE novelai_reader SET statement_timeout = '8s';
ALTER ROLE novelai_reader SET lock_timeout = '1s';
GRANT USAGE ON SCHEMA public TO novelai_reader;
-- Read access to catalog and chapter metadata
GRANT SELECT ON ALL TABLES IN SCHEMA public TO novelai_reader;

-- 4. Worker Service Role (Queue and Leases DML)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'novelai_worker') THEN
        CREATE ROLE novelai_worker WITH LOGIN INHERIT;
    END IF;
END
$$;
ALTER ROLE novelai_worker SET statement_timeout = '60s';
ALTER ROLE novelai_worker SET lock_timeout = '2s';
GRANT USAGE ON SCHEMA public TO novelai_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO novelai_worker;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO novelai_worker;

-- Ensure future tables created by migrations automatically grant expected privileges
ALTER DEFAULT PRIVILEGES FOR ROLE novelai_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO novelai_app;
ALTER DEFAULT PRIVILEGES FOR ROLE novelai_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO novelai_app;

ALTER DEFAULT PRIVILEGES FOR ROLE novelai_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO novelai_reader;

ALTER DEFAULT PRIVILEGES FOR ROLE novelai_migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO novelai_worker;
ALTER DEFAULT PRIVILEGES FOR ROLE novelai_migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO novelai_worker;

COMMIT;

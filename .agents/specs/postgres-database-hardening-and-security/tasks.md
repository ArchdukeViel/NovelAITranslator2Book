# PostgreSQL Hardening & Security Architecture Tasks

Spec ID: postgres-database-hardening-and-security
Version: 1.0.0
Status: Complete
Updated: 2026-09-05

## Prerequisites & Baseline Audit

- [x] T-001: Inspect current PostgreSQL configuration and connection setup across repository
  - Verification: `powershell -ExecutionPolicy Bypass -Command "Get-ChildItem -Path deploy/postgres, backend/sql, tools/database"`
- [x] T-002: Verify current database tests pass before introducing hardening specs
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_db_models_novel.py`

## Phase 1: Authentication, Transport & Access Control (F-1, F-2, F-3)

- [x] T-003: Author PostgreSQL HBA configuration template with forced SCRAM-SHA-256 and SSL reject rules in `deploy/postgres/pg_hba.conf.example`
  - Verification: `Test-Path deploy/postgres/pg_hba.conf.example`
- [x] T-004: Create least-privilege role initialization script `backend/sql/02_least_privilege_roles.sql` granting minimal DML privileges to `novelai_app` and `novelai_reader`
  - Verification: `Test-Path backend/sql/02_least_privilege_roles.sql`
- [x] T-005: Audit all SQL stored procedures/triggers in `backend/sql/` and Alembic migrations for `SECURITY DEFINER` routines and pin `SET search_path = pg_catalog, pg_temp`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "rg -i 'SECURITY DEFINER' backend/sql/ backend/alembic/"`

## Phase 2: Connection Pooling, Budgeting & Timeouts (F-4, F-7)

- [x] T-006: Add connection budget unit test in `backend/tests/test_db_budget.py` verifying process count, pool sizes, and reserve against connection budget
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_db_budget.py`
- [x] T-007: Configure transaction-mode pooler connection safety (disable prepared statements when connecting to port 6543) in database engine factory
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_db_engine.py`
- [x] T-008: Set role-level statement timeouts in role provisioning script (`novelai_reader=8s`, `novelai_app=15s`, `novelai_worker=60s`)
  - Verification: `Select-String -Path backend/sql/02_least_privilege_roles.sql -Pattern 'statement_timeout'`

## Phase 3: Zero-Downtime Migrations & Schema Safety (F-5, F-8, F-17)

- [x] T-009: Update Alembic `env.py` to inject `lock_timeout = '2s'` and `statement_timeout = '10s'` in online migration runs
  - Verification: `Select-String -Path backend/alembic/env.py -Pattern 'lock_timeout'`
- [x] T-010: Create foreign key indexing test checking that all foreign keys in SQLAlchemy models have declared indexes
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_schema_foreign_key_indexes.py`
- [x] T-011: Create CI script checking single linear Alembic DAG head and migration downgrade reversibility drill
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/database/test_alembic_reversibility.ps1`

## Phase 4: Encryption, Diagnostics & Engine Tuning (F-6, F-9, F-10, F-11)

- [x] T-012: Verify `pg_stat_statements` extension preload and diagnostic views in `deploy/postgres/init/01-init.sql`
  - Verification: `Select-String -Path deploy/postgres/init/01-init.sql -Pattern 'pg_stat_statements'`
- [x] T-013: Create automated backup and restore validation drill script `tools/database/verify_backup_drill.ps1`
  - Verification: `Test-Path tools/database/verify_backup_drill.ps1`
- [x] T-014: Add application-layer secret encryption utilities and tests for credentials/tokens
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_secret_crypto.py`
- [x] T-015: Provide production PostgreSQL engine memory tuning profile in `deploy/postgres/postgresql.production.conf.example`
  - Verification: `Test-Path deploy/postgres/postgresql.production.conf.example`
- [x] T-016: Add optional read-replica URL configuration and read-session dependency in database session manager
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_db_replica_routing.py`

## Phase 5: Architecture Alignment & Worker Concurrency (F-12, F-13, F-14, F-15, F-16, F-18 through F-23)

- [x] T-017: Wire `READER_DATABASE_URL` setting and test `novelai.main_reader` connects with read-only privileges
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_reader_db_isolation.py`
- [x] T-018: Add unit test verifying row-level CAS lock in `R2GenerationActivationService` during novel generation activation
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_generation_activation_lock.py`
- [x] T-019: Audit and test `ActivityDatabase.claim_pending` for `FOR UPDATE SKIP LOCKED` non-blocking worker concurrency
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_activity_claim_concurrency.py`
- [x] T-020: Create migration adding tuned storage parameters (`autovacuum_vacuum_scale_factor = 0.01`) for `activity_records` and `scheduled_job_leases`
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_table_autovacuum_storage.py`
- [x] T-021: Add `SET LOCAL app.current_user_id` context propagation helper in `session_scope()` with session isolation test
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pytest.ps1 backend/tests/test_rls_session_context.py`
- [x] T-022: Ensure Compose config enforces `127.0.0.1` binding for CloudBeaver container port and disables anonymous access
  - Verification: `Select-String -Path deploy/compose.yml -Pattern 'CLOUDBEAVER_BIND_ADDRESS'`
- [x] T-023: Configure CloudBeaver schema filtering to hide `auth` and `private` schemas
  - Verification: `Select-String -Path deploy/postgres/cloudbeaver/cloudbeaver.conf -Pattern 'public'`
- [x] T-024: Enforce CloudBeaver query result row limit (`sqlResultSetRowsLimit: 1000`) to prevent OOM
  - Verification: `Select-String -Path deploy/postgres/cloudbeaver/cloudbeaver.conf -Pattern 'sqlResultSetRowsLimit'`
- [x] T-025: Enforce CloudBeaver SQL editor default autocommit to prevent idle locks
  - Verification: `Select-String -Path deploy/postgres/cloudbeaver/cloudbeaver.conf -Pattern 'autoSave'`
- [x] T-026: Enforce CloudBeaver export file quota (10MB limit) to protect disk storage
  - Verification: `Select-String -Path deploy/postgres/cloudbeaver/cloudbeaver.conf -Pattern 'dataExportFileSizeLimit'`
- [x] T-027: Provide pre-seeded CloudBeaver connection template for `novelai_reader` role
  - Verification: `Test-Path deploy/postgres/cloudbeaver/initial-data.conf`

## Quality Gates & Verification

- [x] T-028: Run full backend type check and lint
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/pyright.ps1` and `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 check .`
- [x] T-029: Run documentation contract validation check
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1`

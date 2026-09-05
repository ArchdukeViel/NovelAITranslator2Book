# PostgreSQL Hardening & Security Architecture Requirements

Spec ID: postgres-database-hardening-and-security
Version: 1.0.0
Status: Complete
Updated: 2026-09-05
Requester: Project owner
Owner: Project owner with implementation agent

## Goal

Harden PostgreSQL infrastructure, application database boundaries, connection topology, and migration workflows across all 23 security, performance, operational, and project-architecture findings.

## Scope & Boundaries

### In Scope

- Scope covers database configurations, policies, and code in `deploy/postgres/`, `deploy/compose.yml`, `backend/alembic/`, `backend/sql/`, `backend/src/novelai/`, and `tools/database/`.
- F-1: Network isolation & SCRAM-SHA-256 authentication with forced TLS `verify-full`.
- F-2: Least privilege RBAC, default privilege revoking, and Row-Level Security (RLS) policies.
- F-3: SQL injection prevention, ORM parameterization enforcement, and `SECURITY DEFINER` routine `search_path` pinning.
- F-4: Connection pooling topology (PgBouncer/Supavisor), connection budget formula enforcement, and statement timeouts.
- F-5: Relational schema optimization (UUIDv7 / BigInt, foreign key indexes, text sizing, partial indexes).
- F-6: Backup, DR, Point-in-Time Recovery (WAL archiving), and `pg_stat_statements` diagnostics.
- F-7: Transaction-mode pooler constraints (prepared statements disabling in pooled mode, direct connection for migrations).
- F-8: Zero-downtime schema evolution (`lock_timeout`, `statement_timeout`, `CREATE INDEX CONCURRENTLY`, non-blocking constraints).
- F-9: Sensitive data encryption at rest (Application-Layer Encryption / `pgcrypto` envelope encryption for tokens/PII).
- F-10: Memory allocation & PostgreSQL engine parameter tuning (`shared_buffers`, `effective_cache_size`, `work_mem`).
- F-11: Read replica routing & CQRS patterns for analytical / search workloads.
- F-12 (Architecture): Split-Service Connection Segregation (`READER_DATABASE_URL` with read-only role `novelai_reader` for Reader service).
- F-13 (Architecture): Generation Activation Atomicity & Row Locking (`SELECT ... FOR UPDATE` on novel row during R2 manifest activation).
- F-14 (Architecture): Activity Worker Concurrency & Lock Contention (`FOR UPDATE SKIP LOCKED`, chunked expired lease sweeps).
- F-15 (Architecture): Write-Heavy Table Autovacuum & Bloat Control (table-level `autovacuum_vacuum_scale_factor = 0.01` on `activity_records`, `scheduled_job_leases`).
- F-16 (Architecture): Hybrid RLS Portability (standardized `SET LOCAL app.current_user_id` session variables across native Postgres and Supabase).
- F-17 (Architecture): Alembic Reversibility & Single-Head Verification CI Gate (automated `alembic check` & downgrade test).
- F-18 (Architecture): Admin GUI (CloudBeaver) Network Isolation & Hardening (strict loopback binding, profile gating, credential rotation, anonymous access disablement).
- F-19 (Architecture): CloudBeaver Schema Filtering (hide empty `auth`/`private`, expose `public` only).
- F-20 (CloudBeaver): Query Result Set Ceiling (`sqlResultSetRowsLimit: 1000` to prevent frontend OOM on large HTML chunks).
- F-21 (CloudBeaver): Idle Transaction Avoidance via Default Autocommit.
- F-22 (CloudBeaver): Export File Quota Hardening (`dataExportFileSizeLimit` to guard local container disk).
- F-23 (CloudBeaver): Dedicated Least-Privilege Analyst Profile (`novelai_reader` connection profile).

### Out of Scope

- Production database direct mutations (local & CI test scaffolding only).
- Migrating immutable R2 object stores to Postgres.
- Third-party managed database platform migrations (e.g. leaving AWS/Supabase).

## Requirements

### Functional Requirements

1. **REQ-001 (F-1 Auth & Transport)**: Database connections must enforce `scram-sha-256` password encryption and require TLS 1.3 with certificate verification (`sslmode=verify-full` in production, `sslmode=prefer` or `disable` explicitly only in local containerized development).
2. **REQ-002 (F-2 Privilege & RLS)**: Application services must run under dedicated non-superuser roles (`novelai_app`, `novelai_reader`, `novelai_worker`). Public schema creation privileges must be revoked from `PUBLIC`. RLS policies must enforce tenant/user boundaries on user-scoped tables.
3. **REQ-003 (F-3 Injection & Search Path)**: All dynamic SQL queries must use parameterized execution. Any PostgreSQL stored function or trigger declared as `SECURITY DEFINER` must explicitly set `SET search_path = pg_catalog, pg_temp` to prevent search_path hijacking.
4. **REQ-004 (F-4 Pooler & Budget)**: Connection budgeting must strictly follow `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET`. Global `statement_timeout` must cap runaway queries (e.g., 8s for reader, 30s for background jobs).
5. **REQ-005 (F-5 Schema & Indexing)**: All foreign key columns must possess backing indexes. Primary keys for high-write tables must use monotonic UUIDv7 or BIGINT to prevent B-tree fragmentation. Large strings must use `Text` instead of arbitrary `VARCHAR(255)`.
6. **REQ-006 (F-6 Diagnostics & Backups)**: PostgreSQL must preload `pg_stat_statements` in `shared_preload_libraries`. Automated backup scripts in `tools/database/` must include restore validation drills and WAL archiving verification.
7. **REQ-007 (F-7 Transaction Pooler Safety)**: Application database engines connecting to pooler transaction mode (port 6543) must disable server-side prepared statements (`prepared_statement_cache_size=0`). Migrations (`alembic`) must connect exclusively to direct session port 5432.
8. **REQ-008 (F-8 Zero-Downtime DDL)**: All Alembic migrations must inject `SET LOCAL lock_timeout = '2s'` and `SET LOCAL statement_timeout = '10s'` before DDL. Index creations in migrations must support concurrent execution where possible.
9. **REQ-009 (F-9 Sensitive Data Encryption)**: Secrets, provider tokens, and sensitive credentials must be encrypted before storage using authenticated application-layer encryption (AES-256-GCM / Fernet) or `pgcrypto` envelopes.
10. **REQ-010 (F-10 Engine Sizing)**: PostgreSQL configuration templates must declare production-tuned memory limits: `shared_buffers = 25% RAM`, `effective_cache_size = 50-75% RAM`, `work_mem = 16-64MB`, and `maintenance_work_mem = 512MB-1GB`.
11. **REQ-011 (F-11 Replica Routing)**: The database client infrastructure must support dual-target connection configuration (read-write primary, read-only replica) with fallback to primary.
12. **REQ-012 (F-12 Split-Service Roles)**: Reader service (`novelai.main_reader`) must support binding to `READER_DATABASE_URL` using the dedicated read-only role `novelai_reader`, strictly prohibiting write operations from the public surface.
13. **REQ-013 (F-13 Generation Activation Atomicity)**: `R2GenerationActivationService` must lock the target `novels` row using `SELECT ... FOR UPDATE` before comparing generation manifests, guaranteeing serializable compare-and-swap behavior without data races.
14. **REQ-014 (F-14 Worker Queue Concurrency)**: Activity claiming queries in `ActivityDatabase` must strictly employ `SELECT ... FOR UPDATE SKIP LOCKED` and narrow projections; expired lease sweepers must operate in bounded batches.
15. **REQ-015 (F-15 Write-Heavy Autovacuum)**: High-churn tables (`activity_records`, `scheduled_job_leases`, `analytics_events`, `reading_progress`) must configure lowered autovacuum scale factors (`autovacuum_vacuum_scale_factor = 0.01` to `0.05`) to prevent dead tuple index bloat.
16. **REQ-016 (F-16 Hybrid RLS Portability)**: Authenticated database sessions must inject session context using transaction-scoped `SET LOCAL app.current_user_id = :user_id`, providing portable RLS evaluation across native PostgreSQL and Supabase.
17. **REQ-017 (F-17 Migration Linearity & Reversibility)**: Alembic migrations must enforce a single linear DAG head (verified via CI check) and every migration must include an operational `downgrade()` implementation.
18. **REQ-018 (F-18 Admin GUI Isolation & Hardening)**: CloudBeaver must bind strictly to `${CLOUDBEAVER_BIND_ADDRESS:-127.0.0.1}`, enforce non-anonymous authentication (`anonymousAccessEnabled: false`), and offer transaction-pooler inspection on port 6543.
19. **REQ-019 (F-19 Schema Exposure Governance)**: CloudBeaver navigation filters must restrict schema display to `public`, hiding unpopulated internal schemas (`auth`, `private`).
20. **REQ-020 (F-20 Query Result Ceiling)**: CloudBeaver resource quotas must enforce `sqlResultSetRowsLimit: 1000` to prevent frontend OOM crashes on chapter text queries.
21. **REQ-021 (F-21 Idle Transaction Avoidance)**: CloudBeaver SQL editor configuration must enforce default autocommit to prevent developer sessions from holding idle-in-transaction table locks.
22. **REQ-022 (F-22 Container Disk Quota)**: CloudBeaver export limits must cap CSV/JSON dumps (`dataExportFileSizeLimit: 10000000`) preventing container volume exhaustion.
23. **REQ-023 (F-23 Dedicated Analyst Profile)**: CloudBeaver must provide a pre-seeded `PostgreSQL@db-reader` connection using the `novelai_reader` role for ad-hoc inspection without drop/delete privileges.

### Non-Functional & Operational Requirements

- **NFR-001 (Fail-Closed Security)**: Missing SSL certificates or failed connection parameters must immediately abort connection rather than falling back to unencrypted plaintext.
- **NFR-002 (Zero Lock Contention)**: No schema migration or worker queue poll may hold locks longer than 2 seconds without failing fast.
- **NFR-003 (Observability)**: Slow queries exceeding 200ms must be logged with parameterized query masks, sanitized of user secrets.
- **NFR-004 (Tenant Isolation Invariant)**: User queries executed under RLS must never return records matching a different `user_id` regardless of pooler reuse.

## Acceptance Criteria

- [x] AC-001: PostgreSQL Docker and provisioning scripts configure `password_encryption = scram-sha-256` and restrict `pg_hba.conf` host connections. (REQ-001)
- [x] AC-002: Role separation script exists in `backend/sql/` defining `novelai_app` with `CONNECT`, `SELECT`, `INSERT`, `UPDATE`, `DELETE` and zero DDL permissions. (REQ-002)
- [x] AC-003: All `SECURITY DEFINER` functions in `backend/sql/` and migrations pin `SET search_path = pg_catalog, pg_temp`. (REQ-003)
- [x] AC-004: Configuration validation test enforces the connection budgeting formula against active settings. (REQ-004)
- [x] AC-005: Schema check validates all foreign keys in SQLAlchemy models have matching indexes. (REQ-005)
- [x] AC-006: `deploy/postgres/init/01-init.sql` enables `pg_stat_statements` and test backup script verifies restore integrity. (REQ-006)
- [x] AC-007: Database connection factory detects transaction pooling port and sets `prepare_threshold = None` or equivalent asyncpg/SQLAlchemy parameters. (REQ-007)
- [x] AC-008: Alembic migration env template incorporates safety locks (`lock_timeout = 2s`). (REQ-008)
- [x] AC-009: Secret encryption helper tests verify ciphertext storage and zero plaintext leak in database models. (REQ-009)
- [x] AC-010: Configuration template provides memory sizing guidelines according to available RAM. (REQ-010)
- [x] AC-011: Engine supports read-replica URL configuration and session routing for read-only endpoints. (REQ-011)
- [x] AC-012: `novelai.main_reader` service connects using `READER_DATABASE_URL` with read-only privileges verified. (REQ-012)
- [x] AC-013: Unit test verifies `R2GenerationActivationService` holds an exclusive row lock on the novel during manifest CAS. (REQ-013)
- [x] AC-014: Concurrency test confirms multiple concurrent worker queue claims execute with `SKIP LOCKED` and zero deadlocks. (REQ-014)
- [x] AC-015: Storage parameter migration applies optimized autovacuum thresholds on write-heavy tables. (REQ-015)
- [x] AC-016: Session scope tests confirm `SET LOCAL app.current_user_id` is set on checkout and cleanly discarded on commit/rollback. (REQ-016)
- [x] AC-017: CI check verifies `alembic heads` has exactly 1 head and migration reversibility passes. (REQ-017)
- [x] AC-018: Compose configuration enforces `127.0.0.1` binding for CloudBeaver with anonymous access disabled. (REQ-018)
- [x] AC-019: CloudBeaver navigation filter hides `auth` and `private` schemas, surfacing only `public`. (REQ-019)
- [x] AC-020: CloudBeaver server configuration enforces `sqlResultSetRowsLimit: 1000`. (REQ-020)
- [x] AC-021: CloudBeaver SQL editor settings enforce autocommit enabled by default. (REQ-021)
- [x] AC-022: CloudBeaver export quota is capped to 10MB to protect host volume. (REQ-022)
- [x] AC-023: Pre-seeded connection configuration provides `novelai_reader` connection for safe ad-hoc queries. (REQ-023)

## Acceptance Coverage

| Acceptance criterion | Requirement | Tasks        | Current status |
| -------------------- | ----------- | ------------ | -------------- |
| AC-001               | REQ-001     | T-001, T-003 | Completed      |
| AC-002               | REQ-002     | T-004, T-008 | Completed      |
| AC-003               | REQ-003     | T-005        | Completed      |
| AC-004               | REQ-004     | T-006        | Completed      |
| AC-005               | REQ-005     | T-010        | Completed      |
| AC-006               | REQ-006     | T-012, T-013 | Completed      |
| AC-007               | REQ-007     | T-007        | Completed      |
| AC-008               | REQ-008     | T-009        | Completed      |
| AC-009               | REQ-009     | T-014        | Completed      |
| AC-010               | REQ-010     | T-015        | Completed      |
| AC-011               | REQ-011     | T-016        | Completed      |
| AC-012               | REQ-012     | T-017        | Completed      |
| AC-013               | REQ-013     | T-018        | Completed      |
| AC-014               | REQ-014     | T-019        | Completed      |
| AC-015               | REQ-015     | T-020        | Completed      |
| AC-016               | REQ-016     | T-021        | Completed      |
| AC-017               | REQ-017     | T-011        | Completed      |
| AC-018               | REQ-018     | T-022        | Completed      |
| AC-019               | REQ-019     | T-023        | Completed      |
| AC-020               | REQ-020     | T-024        | Completed      |
| AC-021               | REQ-021     | T-025        | Completed      |
| AC-022               | REQ-022     | T-026        | Completed      |
| AC-023               | REQ-023     | T-027        | Completed      |

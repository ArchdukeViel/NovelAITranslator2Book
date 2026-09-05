# PostgreSQL Hardening & Security Architecture Design

Spec ID: postgres-database-hardening-and-security
Version: 1.0.0
Status: Complete
Updated: 2026-09-05

## Source of Truth Mapping

- Primary architecture: `docs/ARCHITECTURE.md` (Database boundaries, trust zones, connection pooling invariants)
- Configuration & secrets: `docs/CONFIGURATION.md` (DB credentials, pool budgets, SSL settings)
- Operational runbooks: `docs/OPERATIONS.md` (Backups, restore drills, health checks)
- Database schemas & scripts: `backend/alembic/`, `backend/sql/`, `deploy/postgres/`

## System Architecture & Component Interaction

```text
[ Reader / Web Client ]       [ Admin / Background Worker ]       [ Migration Runner ]
          │                                 │                              │
          │ (Port 6543)                     │ (Port 6543)                  │ (Port 5432 Direct)
          ▼                                 ▼                              │
┌────────────────────────────────────────────────────────┐                 │
│         Connection Pooler (PgBouncer / Supavisor)       │                 │
│         - Transaction Mode                             │                 │
│         - Prepared statements disabled                 │                 │
└───────────────────────────┬────────────────────────────┘                 │
                            │                                              │
                            │ (Pooled Backends)                            │
                            ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           PostgreSQL 17 Primary Database                         │
│  - SCRAM-SHA-256 Authentication & Forced TLS 1.3                                │
│  - Roles: novelai_app, novelai_reader, novelai_worker (Least Privilege)         │
│  - Row-Level Security (RLS) & SET search_path = pg_catalog, pg_temp             │
│  - pg_stat_statements enabled                                                   │
│  - Engine Tuned: shared_buffers (25%), work_mem, autovacuum_vacuum_scale_factor   │
└───────────────────────────┬──────────────────────────────────────────────────────┘
                            │
                            │ Streaming WAL Replication
                            ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           PostgreSQL Read Replica                                │
│  - hot_standby = on                                                              │
│  - Serves heavy catalog reads, export queries, and analytics                     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Technical Specification by Audit Finding

### 1. Network Isolation & SCRAM-SHA-256 (F-1)

- **Engine config**: `password_encryption = scram-sha-256` in `postgresql.conf`.
- **HBA configuration (`pg_hba.conf`)**:
  ```text
  # TYPE  DATABASE        USER            ADDRESS                 METHOD
  local   all             postgres                                peer
  hostssl all             all             10.0.0.0/8              scram-sha-256
  hostssl all             all             172.16.0.0/12           scram-sha-256
  host    all             all             all                     reject
  ```
- **Client parameters**: Production database URLs enforce `?sslmode=verify-full&sslrootcert=/path/to/server-ca.pem`.

### 2. Authorization, Least Privilege & Row-Level Security (F-2)

- Revoke default public schema creation:
  ```sql
  REVOKE CREATE ON SCHEMA public FROM PUBLIC;
  REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
  ```
- Dedicated application roles:
  - `novelai_app`: DML (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) on app tables; zero DDL.
  - `novelai_reader`: Read-only (`SELECT`) on public novel and chapter catalog.
  - `novelai_migrator`: Full DDL permissions, used strictly during migration jobs.
- Row-Level Security (RLS) enforced across multi-tenant and user-owned tables:
  ```sql
  ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bookmarks FORCE ROW LEVEL SECURITY;
  CREATE POLICY bookmark_owner_policy ON bookmarks
    USING (user_id = current_setting('app.current_user_id', true));
  ```

### 3. SQL Injection Defense & Search Path Security (F-3)

- Application query execution restricted strictly to SQLAlchemy 2.0 type-checked statements (`select()`, `insert()`, `update()`), never raw string formatting.
- All database stored procedures / functions tagged `SECURITY DEFINER` must pin search paths:
  ```sql
  CREATE OR REPLACE FUNCTION update_timestamp()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path = pg_catalog, pg_temp
  AS $$
  BEGIN
    NEW.updated_at = clock_timestamp();
    RETURN NEW;
  END;
  $$;
  ```

### 4. Connection Pooling & Resource Caps (F-4)

- Enforce the connection budgeting invariant in `docs/ARCHITECTURE.md`:
  `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET`
- Per-role statement timeouts to prevent cascading worker exhaustion:
  ```sql
  ALTER ROLE novelai_reader SET statement_timeout = '8s';
  ALTER ROLE novelai_app SET statement_timeout = '15s';
  ALTER ROLE novelai_worker SET statement_timeout = '60s';
  ```

### 5. Schema & Indexing Best Practices (F-5)

- All foreign keys require indexes to avoid full table locks during parent deletes/updates.
- Sequential/monotonic identifiers (UUIDv7 or `BIGINT GENERATED ALWAYS AS IDENTITY`) for write-heavy tables to eliminate B-tree page splits.
- Columns storing unbounded text (titles, summaries, author notes, bodies) must use `Text`, never clamped `String(255)`.
- Partial indexes for filtered queries:
  ```sql
  CREATE INDEX idx_novels_published ON novels (id, published_at)
  WHERE publication_status = 'published';
  ```

### 6. Backups, DR & Observability (F-6)

- Enable `pg_stat_statements` preloading in `deploy/postgres/init/01-init.sql`:
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
  ```
- WAL archiving configured for continuous Point-In-Time Recovery (PITR).
- Provide automated restore test script `tools/database/verify_backup_drill.ps1` to regularly validate backup integrity.

### 7. Transaction Pooler Compatibility (F-7)

- In transaction pooling mode (PgBouncer/Supavisor port 6543):
  - Disable prepared statement caching in asyncpg / SQLAlchemy:
    `connect_args={"prepared_statement_cache_size": 0}` (or `prepare_threshold=None`).
  - Keep Alembic migrations strictly routed to port 5432 (direct session mode).

### 8. Zero-Downtime Migration Rules (F-8)

- Alembic `env.py` pre-migration injection:
  ```python
  def run_migrations_online() -> None:
      with connectable.connect() as connection:
          connection.execute(text("SET LOCAL lock_timeout = '2s';"))
          connection.execute(text("SET LOCAL statement_timeout = '10s';"))
          ...
  ```
- Schema evolution policies:
  - Add column with `NULL` or constant default (PostgreSQL >= 11 does not rewrite table).
  - Add foreign key with `NOT VALID`, then `VALIDATE CONSTRAINT` in separate step.
  - Create index using `CREATE INDEX CONCURRENTLY` (outside of migration transaction blocks).

### 9. Sensitive Data & Cryptography at Rest (F-9)

- Field-level encryption for provider API tokens, refresh tokens, and PII.
- Envelope encryption design: Master key in environment/KMS, decrypt in memory only when calling external providers.
- Password hashes use `bcrypt` or `argon2id` with proper salt rounds.

### 10. Memory & Engine Parameter Tuning (F-10)

- Config template for production instances:
  - `shared_buffers = 25% of total system RAM`
  - `effective_cache_size = 50% - 75% of total RAM`
  - `work_mem = 32MB`
  - `maintenance_work_mem = 512MB`
  - `autovacuum_vacuum_scale_factor = 0.05` (5% dead tuples threshold instead of 20%)
  - `autovacuum_analyze_scale_factor = 0.02`

### 11. Read Replica Routing & CQRS (F-11)

- Database connection manager provides primary vs replica engine factory:
  - `get_read_session()`: targets read replica with fallback to primary.
  - `get_write_session()`: targets primary engine.
- Web reader catalog & search endpoints consume `get_read_session()`.

### 12. Split-Service Connection Segregation (F-12)

- Architecture contract: `novelai.main_reader` must connect to `READER_DATABASE_URL` (defaulting to read-only replica or `novelai_reader` role), preventing any accidental write operations from the public surface.
- The `novelai.main_admin` and `novelaibook worker` services connect to `DATABASE_URL` using `novelai_app` and `novelai_worker` roles.

### 13. Generation Activation CAS & Row Locking (F-13)

- During R2 novel generation activation in `R2GenerationActivationService`:
  ```python
  # Atomically lock novel row to prevent concurrent crawl activations
  novel = session.scalar(
      select(Novel).where(Novel.id == novel_id).with_for_update()
  )
  if novel.active_generation_id != expected_generation_id:
      raise StaleGenerationActivationError()
  novel.active_generation_id = new_generation_id
  ```

### 14. Activity Worker Concurrency & Lock Contention (F-14)

- `ActivityDatabase.claim_pending` employs non-blocking concurrency:
  ```python
  pending = (
      select(ActivityRecord.activity_id)
      .where(ActivityRecord.status == "pending")
      .order_by(ActivityRecord.created_at)
      .limit(1)
      .with_for_update(skip_locked=True)
  )
  ```
- Sweeper jobs for expired leases process in discrete batches (`LIMIT 50`) inside short transaction windows to avoid long-lived row lock accumulation.

### 15. Write-Heavy Table Autovacuum Parameters (F-15)

- Tables with high turnover (`activity_records`, `scheduled_job_leases`, `analytics_events`, `reading_progress`) generate significant dead tuples from repeated updates.
- Storage parameters applied via Alembic DDL:
  ```sql
  ALTER TABLE activity_records SET (
      autovacuum_vacuum_scale_factor = 0.01,
      autovacuum_vacuum_threshold = 50,
      autovacuum_vacuum_cost_limit = 1000
  );
  ALTER TABLE scheduled_job_leases SET (
      autovacuum_vacuum_scale_factor = 0.01,
      autovacuum_vacuum_threshold = 20
  );
  ```

### 16. Hybrid RLS Portability & Session Isolation (F-16)

- In `session_scope()`:
  ```python
  @contextmanager
  def session_scope(user_id: int | None = None) -> Generator[Session]:
      with sessionmaker() as session:
          if user_id is not None:
              session.execute(text("SET LOCAL app.current_user_id = :uid"), {"uid": str(user_id)})
          yield session
  ```
- Because `SET LOCAL` is bound to the current transaction block, it automatically resets on `COMMIT` or `ROLLBACK`, eliminating cross-request session contamination in connection poolers.

### 17. Alembic Reversibility & Linear Head CI Gate (F-17)

- Strict CI check enforces:
  1. `alembic heads`: Exactly one head revision.
  2. `alembic check`: Schema model metadata matches migration DAG.
  3. Reversibility drill: Downgrades test migration cleanly without syntax or integrity error.

### 18. Admin GUI Isolation & Hardening (F-18)

- `CloudBeaver` bound exclusively to loopback: `${CLOUDBEAVER_BIND_ADDRESS:-127.0.0.1}:${CLOUDBEAVER_PORT:-8978}:8978`.
- Compose profiles keep `cloudbeaver` under `profiles: ["tools", "debug"]`, preventing execution in production container stacks.
- Enforce mandatory administrative credentials via environment configuration.
- **Anonymous access disabled**: Set `anonymousAccessEnabled: false` in `deploy/postgres/cloudbeaver/cloudbeaver.conf` to prevent unauthorized metadata discovery.
- **Transaction-mode pooler visibility**: Configure a connection template for port 6543 to inspect pooler routing and transaction behavior.

### 19. Schema Exposure Governance (F-19)

- Database navigator filters hide unpopulated or internal schemas (`auth`, `private`), exposing strictly `public` to reduce cognitive load and prevent accidental queries to staging schemas.

### 20. Query Result Set Ceiling (F-20)

- Enforce `sqlResultSetRowsLimit: 1000` in CloudBeaver resource quotas.
- Prevents browser UI thread freezing and heap exhaustion when developers inadvertently execute `SELECT * FROM chapters` with large raw HTML text blobs.

### 21. Idle Transaction Avoidance via Default Autocommit (F-21)

- CloudBeaver SQL editor defaults to autocommit enabled.
- Prevents developers from executing a `SELECT ... FOR UPDATE` or DML query in an uncommitted tab and leaving the workspace open, which would hold table locks and block application workers or migrations.

### 22. Container Disk Quota Hardening (F-22)

- CloudBeaver export limits enforce `dataExportFileSizeLimit: 10000000` (10MB).
- Prevents accidental runaway data dumps from consuming host Docker volume storage.

### 23. Dedicated Least-Privilege Analyst Profile (F-23)

- Pre-seed connection configuration `PostgreSQL@db-reader` using role `novelai_reader`.
- Analysts and developers use this profile for read-only inspection, guaranteeing zero risk of dropping tables or mutating rows during ad-hoc queries.

## Data Contracts & Schemas

### Role & Permission Matrix

| Role               | Connect | Tables (DML)                   | Sequences | Schemas (DDL)  | statement_timeout |
| ------------------ | ------- | ------------------------------ | --------- | -------------- | ----------------- |
| `novelai_migrator` | Yes     | ALL                            | ALL       | CREATE / ALTER | 120s              |
| `novelai_app`      | Yes     | SELECT, INSERT, UPDATE, DELETE | USAGE     | None           | 15s               |
| `novelai_reader`   | Yes     | SELECT (catalog only)          | None      | None           | 8s                |
| `novelai_worker`   | Yes     | SELECT, INSERT, UPDATE, DELETE | USAGE     | None           | 60s               |

## Failure Modes & System Invariants

- **Invariant 1**: No client application connection may ever run with `SUPERUSER` or schema ownership privileges.
- **Invariant 2**: Any DDL lock acquisition taking longer than 2 seconds must abort (`lock_timeout = '2s'`) to prevent production connection pileups.
- **Invariant 3**: Transaction poolers must never execute server-side prepared statements or session-pinned advisory locks.
- **Invariant 4**: Secrets in relational tables must never be stored in plaintext.
- **Invariant 5**: `SET LOCAL app.current_user_id` must never cross transaction boundaries.
- **Invariant 6**: Public reader processes must never possess write or DDL privileges on database relations.
- **Invariant 3**: Transaction poolers must never execute server-side prepared statements or session-pinned advisory locks.
- **Invariant 4**: Secrets in relational tables must never be stored in plaintext.

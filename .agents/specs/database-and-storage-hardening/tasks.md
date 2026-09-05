# Database and Storage Hardening Tasks

Spec ID: database-and-storage-hardening
Version: 1.0.0
Status: Active
Updated: 2026-09-05
Requester: Project owner
Owner: Project owner with implementation agent

## Prerequisites & Setup

- [x] 1. Verify clean worktree and existing checks pass
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1`
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/ruff.ps1 check .`

## Phase 1: Database Session & Engine Security (Findings 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 9.1, 9.5, 9.10)

- [x] 2. Update `engine.py` session context managers
  - Add parameterized `set_config` RLS injection in `session_scope` (Finding 1.2).
  - Add `session.in_transaction()` check before commit on exit (Finding 1.3).
  - Enforce `SET TRANSACTION READ ONLY` on checked out read connections (Finding 1.4).
  - Set tight `SET LOCAL statement_timeout = '3000'` in `read_session_scope` (Finding 9.5).
  - Partition `_ENGINE_CACHE` by `os.getpid()` (Finding 1.5).
  - Set `pool_recycle=1800` (Finding 1.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_db_engine.py`
- [x] 3. Fix nested session management in `r2_catalog.py` & streaming routers
  - Refactor `save_edited_translation` to use savepoints (`session.begin_nested()`) when outer session is passed (Finding 1.1).
  - Replace manual raw session creation with `session_scope` context manager (Finding 9.10).
  - Add bounded size checks during JSON parsing (Finding 1.8).
  - Finalize session and audit state before streaming response body release (Finding 1.9).
  - Verification: `tools/pytest.ps1 backend/tests/test_r2_catalog.py`
- [x] 4. Enforce PostgreSQL connection pool budget in configuration
  - Update `backend/src/novelai/config/settings.py` and `deploy/compose.yml` to reflect 5/5 split across services (Finding 9.1).
  - Verification: `tools/pytest.ps1 backend/tests/test_production_config.py`

## Phase 2: Concurrency, Locking & Queue Integrity (Findings 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 1.6)

- [x] 5. Implement non-blocking worker queue claiming & lock controls
  - Add `with_for_update(skip_locked=True)` to pending chapter queries in `jobs.py` (Finding 7.1).
  - Sort rows by primary key before bulk updates to prevent deadlocks (Finding 7.2).
  - Synchronize user role promotions with row lock and advisory lock (Finding 7.4).
  - Set `ISOLATION LEVEL REPEATABLE READ` on complex analytics rollups (Finding 7.6).
  - Deprecate single-node `fcntl` file locks in favor of distributed locking (Finding 7.7).
  - Set statement-level `lock_timeout = '3s'` on all lock operations (Finding 7.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_scheduled_job_lease_service.py`
- [x] 6. Enforce optimistic locking, counters & deterministic advisory locks
  - Configure `version_id_col` on `Chapter` model (Finding 1.6).
  - Buffer novel view increments in Redis to eliminate DB lock contention (Finding 7.5).
  - Refactor advisory lock integer generation to use deterministic SHA-256 (Finding 7.9).
  - Use `INSERT ... ON CONFLICT` for idempotent scraper inserts (Finding 7.8).
  - Verification: `tools/pytest.ps1 backend/tests/test_advisory_lock.py`

## Phase 3: R2 Gateway Worker & Storage Client Hardening (Findings 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 7.3, 10.5, 10.7)

- [x] 7. Harden R2 Gateway Worker (`workers/r2-gateway/`)
  - Implement cryptographic JWT verification against Cloudflare Access JWKS (Finding 10.7).
  - Add rate-limiting binding on object downloads (Finding 10.5).
  - Enforce streaming uploads directly to `R2Bucket.put` without in-memory buffering (Finding 2.1).
  - Lowercase header parsing for metadata (Finding 2.3).
  - Add batch delete endpoint for up to 1000 keys (Finding 2.9).
  - Sanitize key path traversal regex against dot-dot patterns (Finding 2.7).
  - Verification: `npm --prefix workers/r2-gateway test`
- [x] 8. Harden Python R2 Gateway Client (`r2_gateway.py`)
  - Add jittered exponential backoff for transient errors in `_request()` (Finding 2.2).
  - Enforce byte-matching and cleanup on stream length mismatch (Finding 2.4).
  - Refresh service tokens and validate expiry window before calls (Finding 2.5).
  - Add bounded pagination limits to `_iter_objects` (Finding 2.6).
  - Send SHA-256 checksum headers on non-immutable writes (Finding 2.8).
  - Tune HTTP connection pool limits (Finding 2.10).
  - Implement atomic compare-and-swap using `If-Match` headers (Finding 7.3).
  - Verification: `tools/pytest.ps1 backend/tests/test_r2_immutability.py`

## Phase 4: Content Addressing, Hashing & Immutability (Findings 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10)

- [x] 9. Refactor `content_addressing.py`
  - Strip provider execution telemetry from volatile fields (Finding 3.1).
  - Ensure canonical float formatting and normalize control characters (Finding 3.2, Finding 3.3).
  - Use native `gzip.compress(data, mtime=0)` for performance (Finding 3.4).
  - Emit structured diagnostic logs on `ArtifactConflictError` (Finding 3.5).
  - Enforce strict non-padded canonical integer IDs (Finding 3.6).
  - Introduce BLAKE3 secondary hash support for large streams (Finding 3.7).
  - Record uncompressed size metadata headers (Finding 3.8).
  - Match volatile dictionary keys case-insensitively (Finding 3.9).
  - Support approved media extensions in `artifact_key` (Finding 3.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_r2_content_addressing.py`

## Phase 5: Schema Migrations & DDL Integrity (Findings 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 1.7, 9.3, 9.4, 9.6, 9.8, 9.9)

- [x] 10. Create new migration for schema hardening and missing indexes
  - Convert `activity_records.id` to `BigInteger` (Finding 4.3).
  - Add missing index on `activity_records.user_id` (Finding 1.7).
  - Convert clamped string columns to `Text` (Finding 4.2).
  - Allow flexible/unknown third-party scraping statuses (Finding 4.4).
  - Add `ondelete="SET NULL"` on optional auditor/user foreign keys (Finding 4.5).
  - Add database-level server defaults for timestamps (Finding 4.6).
  - Add partial indexes on published novels `WHERE is_deleted = false` (Finding 4.7).
  - Add compound natural unique constraint `(novel_id, chapter_number)` (Finding 4.8).
  - Standardize Alembic file naming template (Finding 4.9).
  - Enforce `lock_timeout = '2s'` and `statement_timeout = '10s'` in migration runner (Finding 4.10).
  - Add composite index on `chapters (novel_id, chapter_number)` (Finding 9.3).
  - Add GIN trigram index on `novels.title` (Finding 9.4).
  - Add index on junction table foreign keys (Finding 9.6).
  - Use `pg_class.reltuples` for fast dashboard row counting (Finding 9.8).
  - Add expression index on `activity_records ((details->>'action'))` (Finding 9.9).
  - Provide full reversible `downgrade()` implementation (Finding 4.1).
  - Verification: `tools/pytest.ps1 backend/tests/test_security_migration.py`

## Phase 6: Backup Engine, Retention & Disaster Recovery (Findings 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10)

- [x] 11. Harden backup engine in `r2_backup.py`
  - Partition large manifests into chunked files (Finding 5.1).
  - Implement cryptographic manifest signing via ed25519 (Finding 5.2).
  - Enforce minimum retention count floor (`keep_minimum=7`) (Finding 5.3).
  - Store PostgreSQL LSN in backup metadata for PITR alignment (Finding 5.4).
  - Clean up copied objects on failed/aborted snapshot runs (Finding 5.5).
  - Perform 1% random sample byte integrity check during restore drills (Finding 5.6).
  - Support multi-region/secondary bucket configurations (Finding 5.7).
  - Add rate limiting to backup copy loop (Finding 5.8).
  - Acquire distributed advisory lock before running backup (Finding 5.9).
  - Dispatch structured failure alert webhooks on backup abort (Finding 5.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_r2_backup.py`

## Phase 7: Storage Garbage Collection, Retention & Orphan Pruning (Findings 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10)

- [x] 12. Harden storage cutover and garbage collection in `r2_cutover.py`
  - Enforce 48-hour age grace period before pruning unreferenced objects (Finding 8.1).
  - Use batch deletion endpoint for pruned objects (Finding 8.2).
  - Stream DB references to avoid in-memory set OOM (Finding 8.3).
  - Verify media asset reference counts before deleting illustrations (Finding 8.4).
  - Support 30-day soft-delete grace period on novels (Finding 8.5).
  - Prune superseded scraping generations older than 7 days (Finding 8.6).
  - Replace full-bucket scans for `total_size_bytes` with aggregate metrics (Finding 8.7).
  - Record audit log entry on GC completion (Finding 8.8).
  - Configure lifecycle rule to abort stale multipart uploads after 7 days (Finding 8.9).
  - Require `--confirm-delete` flag; default to `--dry-run` (Finding 8.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_r2_cutover.py`

## Phase 8: Caching, Projections & Query Optimization (Findings 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 9.2, 9.7)

- [x] 13. Optimize caching layers
  - Register cache invalidations on `session.after_commit()` (Finding 6.1).
  - Use bounded `TTLCache` for in-memory metadata projections (Finding 6.2).
  - Paginate novel chapter catalog retrieval responses (Finding 6.3).
  - Establish PostgreSQL as status authority and R2 as payload authority (Finding 6.4).
  - Add single-flight mutex for cold cache misses (Finding 6.5).
  - Rely on `logical_sha256` rather than multipart ETags for cache validation (Finding 6.6).
  - Add `stale-while-revalidate` response headers on public reader routes (Finding 6.7).
  - Batch cache deletion keys on scrape completions (Finding 6.8).
  - Standardize datetime serialization in cache payloads (Finding 6.9).
  - Compress Redis cache entries exceeding 1KB (Finding 6.10).
  - Add eager loading `selectinload(Novel.chapters)` to prevent N+1 queries (Finding 9.2).
  - Enforce pagination limits on notification list queries (Finding 9.7).
  - Verification: `tools/pytest.ps1 backend/tests/test_public_projection_cache.py`

## Phase 9: Row-Level Security, Encryption & Access Controls (Findings 10.1, 10.2, 10.3, 10.4, 10.6, 10.8, 10.9, 10.10)

- [x] 14. Apply database RLS & role hardening
  - Execute `FORCE ROW LEVEL SECURITY` on all multi-tenant tables (Finding 10.1).
  - Pin `SET search_path = pg_catalog, pg_temp` on all `SECURITY DEFINER` functions (Finding 10.2).
  - Sanitize database operational errors in API responses (Finding 10.3).
  - Encrypt LLM provider API keys at rest using application envelope encryption (Finding 10.4).
  - Record audit records for sensitive data export and deletions (Finding 10.6).
  - Implement Argon2id or password hash cost upgrading (Finding 10.8).
  - Revoke `TRUNCATE` and `DROP` privileges from `novelai_app` (Finding 10.9).
  - Verify reader R2 payload against database `logical_sha256` (Finding 10.10).
  - Verification: `tools/pytest.ps1 backend/tests/test_security_migration.py`
  - Verification: `tools/pytest.ps1 backend/tests/test_security.py`

## Phase 10: Verification & Quality Gates

- [x] 15. Run full test suite and validation scripts
  - Verification: `tools/pytest.ps1`
  - Verification: `tools/pyright.ps1`
  - Verification: `tools/ruff.ps1 check .`
  - Verification: `powershell -ExecutionPolicy Bypass -Command "rg -n '^from novelai\.(db\.models|storage\.service|sources\.)' backend/src/novelai/api/routers/ --glob '!dependencies.py'"`
  - Verification: `powershell -ExecutionPolicy Bypass -File tools/docs-check.ps1`

## Phase 11: Lifecycle & Cleanup

- [x] 16. Record audit evidence and finalize specification
  - Update `docs/STATUS.md` and `docs/EVIDENCE.md` with verified remediation results.
  - Delete temporary `DATABASE_STORAGE_AUDIT.md` from root after two full review passes.
  - Verification: `Test-Path DATABASE_STORAGE_AUDIT.md` returns False.

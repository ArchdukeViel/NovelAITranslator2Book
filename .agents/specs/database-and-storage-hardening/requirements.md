# Database and Storage Hardening Requirements

Spec ID: database-and-storage-hardening
Version: 1.0.0
Status: Complete
Updated: 2026-09-05
Requester: Project owner
Owner: Project owner with implementation agent

## Goal

Resolve and remediate all 100 architectural and implementation findings identified across PostgreSQL database management, SQLAlchemy session lifecycles, and Cloudflare R2 object storage integration in `DATABASE_STORAGE_AUDIT.md`.

## Scope & Boundaries

### In Scope

- Scope covers all 10 audit domains from `DATABASE_STORAGE_AUDIT.md`:
  - Domain 1: Database Session Lifecycle & Transaction Integrity (Findings 1.1 - 1.10).
  - Domain 2: R2 Gateway & Object Storage Boundary Protocols (Findings 2.1 - 2.10).
  - Domain 3: Content Addressing, Hashing & Immutability Guarantees (Findings 3.1 - 3.10).
  - Domain 4: Alembic Migrations, DDL Constraints & Schema Contracts (Findings 4.1 - 4.10).
  - Domain 5: Backup Engine, Restore Drills & Disaster Recovery (Findings 5.1 - 5.10).
  - Domain 6: Catalog Projections, Caching & Recomputation Boundaries (Findings 6.1 - 6.10).
  - Domain 7: Concurrency, Row Locking & Race Conditions (Findings 7.1 - 7.10).
  - Domain 8: Storage Garbage Collection, Retention & Orphan Pruning (Findings 8.1 - 8.10).
  - Domain 9: Query Efficiency, Index Coverage & Pool Budgeting (Findings 9.1 - 9.10).
  - Domain 10: Security, RLS Hardening & Audit Trails (Findings 10.1 - 10.10).
- Relevant codebases:
  - `backend/src/novelai/db/`
  - `backend/src/novelai/storage/`
  - `backend/src/novelai/services/`
  - `backend/src/novelai/api/`
  - `backend/alembic/`
  - `backend/sql/`
  - `workers/r2-gateway/`
  - `deploy/compose.yml` & `deploy/postgres/`

### Out of Scope

- Direct modifications or destructive operations against production database/R2 instances.
- Adding unapproved external database engines (e.g. MongoDB, Cassandra).
- Breaking existing public reader API response JSON structures.

## Requirements

### Domain 1: Database Session Lifecycle & Transaction Integrity (Findings 1.1 - 1.10)

1. **REQ-D1-01 (F1.1: Double-Session Nested Transaction)**: `save_edited_translation` in `r2_catalog.py` must accept optional caller session. When passed, it must utilize `session.begin_nested()` (savepoint) without committing the outer transaction.
2. **REQ-D1-02 (F1.2: Parameterized RLS Injection)**: `session_scope()` in `engine.py` must execute `SELECT set_config('app.current_user_id', :user_id, true)` using parameter bindings instead of f-string SQL interpolation.
3. **REQ-D1-03 (F1.3: Redundant Commit Handling)**: `session_scope()` must verify `session.in_transaction()` before issuing `commit()` on context block exit.
4. **REQ-D1-04 (F1.4: Read-Only Transaction Enforcement)**: `read_session_scope()` must issue `SET TRANSACTION READ ONLY` on checked out connections.
5. **REQ-D1-05 (F1.5: Multi-Process Engine Cache Isolation)**: `_ENGINE_CACHE` in `engine.py` must partition cache keys by `os.getpid()` to prevent cross-process socket sharing on worker fork.
6. **REQ-D1-06 (F1.6: Optimistic Locking on Chapter Revisions)**: `Chapter` model in `chapter.py` must declare `version_id_col=version` for SQLAlchemy-managed optimistic concurrency control.
7. **REQ-D1-07 (F1.7: Foreign Key Indexing on Activity Records)**: Foreign key `activity_records.user_id` must have an explicit B-tree index.
8. **REQ-D1-08 (F1.8: Bounded JSON Deserialization)**: In-transaction metadata JSON deserialization in `r2_catalog.py` must enforce maximum payload size limits.
9. **REQ-D1-09 (F1.9: Streaming Session Lifecycle Finalization)**: Chapter streaming endpoints must finalize session and audit state prior to client stream release.
10. **REQ-D1-10 (F1.10: Stale Connection Pool Eviction)**: Engine connection pool recycle (`pool_recycle`) must be tuned to `1800` seconds to avoid idle firewall drops.

### Domain 2: R2 Gateway & Object Storage Boundary Protocols (Findings 2.1 - 2.10)

11. **REQ-D2-01 (F2.1: Streaming Worker Uploads)**: Gateway worker in `workers/r2-gateway/src/index.ts` must stream `request.body` directly to `R2Bucket.put()` without in-memory buffering.
12. **REQ-D2-02 (F2.2: Gateway Client Backoff & Retries)**: `_request()` in `r2_gateway.py` must implement jittered exponential backoff (3 attempts) on 429, 502, 503, and 504 responses.
13. **REQ-D2-03 (F2.3: Header Normalization)**: Gateway worker must lowercase all header keys before metadata matching against `FIXED_METADATA`.
14. **REQ-D2-04 (F2.4: Stream Content-Length Enforcement)**: `save_stream()` in `r2_gateway.py` must track streamed bytes and issue immediate `delete(key)` if length does not match declared `content_length`.
15. **REQ-D2-05 (F2.5: Service Token Expiry Validation)**: Gateway client must validate service token validity windows and refresh credentials upon receiving 401/403.
16. **REQ-D2-06 (F2.6: Bounded Object Listing)**: `_iter_objects()` in `r2_gateway.py` must accept a `max_items` ceiling to prevent heap exhaustion during broad scans.
17. **REQ-D2-07 (F2.7: Key Path Traversal Sanitization)**: Gateway worker must reject keys containing dot-dot (`..`) or invalid character sequences via regex `^[a-zA-Z0-9_\-\.\/]+$`.
18. **REQ-D2-08 (F2.8: Transport Checksum Verification)**: Non-immutable `save()` operations must supply `X-R2-Checksum-Sha256` or `Digest` headers for payload verification.
19. **REQ-D2-09 (F2.9: Bulk Object Deletion Endpoint)**: Gateway worker and client must provide a batch deletion endpoint accepting up to 1000 keys per call.
20. **REQ-D2-10 (F2.10: Tuned HTTP Connection Pooling)**: `httpx.Client` limits in `r2_gateway.py` must configure `max_keepalive_connections=50` and `max_connections=100`.

### Domain 3: Content Addressing, Hashing & Immutability Guarantees (Findings 3.1 - 3.10)

21. **REQ-D3-01 (F3.1: Complete Volatile Field Stripping)**: `DEFAULT_VOLATILE_FIELDS` in `content_addressing.py` must strip provider execution metadata (`model_version`, `prompt_tokens`, `completion_tokens`, `latency_ms`).
22. **REQ-D3-02 (F3.2: Deterministic Floating Point Normalization)**: Floating point numbers in `_normalize()` must be formatted canonically to ensure reproducible SHA-256 hashes across architectures.
23. **REQ-D3-03 (F3.3: Control Character Stripping)**: `_normalize()` must sanitize ASCII control characters (`[\x00-\x08\x0B\x0C\x0E-\x1F]`) from text fields.
24. **REQ-D3-04 (F3.4: Optimized Deterministic Gzip)**: `deterministic_gzip()` must utilize native `gzip.compress(data, mtime=0)` to reduce allocation overhead.
25. **REQ-D3-05 (F3.5: Structured Conflict Alerting)**: `ArtifactConflictError` must emit structured diagnostic logs with SHA-256 digests, payload sizes, and novel IDs.
26. **REQ-D3-06 (F3.6: Strict Canonical ID Formatting)**: All novel storage ID parsers must enforce `str(int(val)) == val` to prevent zero-padding namespace collisions.
27. **REQ-D3-07 (F3.7: Dual-Hash Architecture)**: Content addressing must introduce BLAKE3 support for high-throughput streaming verification alongside SHA-256.
28. **REQ-D3-08 (F3.8: Uncompressed Size Metadata)**: `put_immutable()` must record `X-R2-Meta-Uncompressed-Size` in object headers.
29. **REQ-D3-09 (F3.9: Case-Insensitive Volatile Key Matching)**: `_normalize()` must match volatile fields case-insensitively.
30. **REQ-D3-10 (F3.10: Media Artifact Extension Support)**: `artifact_key()` must support approved binary media extensions (`webp`, `png`, `jpeg`).

### Domain 4: Alembic Migrations, DDL Constraints & Schema Contracts (Findings 4.1 - 4.10)

31. **REQ-D4-01 (F4.1: Migration Reversibility)**: All Alembic migrations must implement operational, tested `downgrade()` methods.
32. **REQ-D4-02 (F4.2: Unclamped Text Types)**: Novel author notes, chapter content, and source URLs must use SQLAlchemy `Text` rather than `String(255)` or `String(512)`.
33. **REQ-D4-03 (F4.3: 64-Bit Primary Keys on Ledger Tables)**: `activity_records` and `analytics_events` must migrate to `BigInteger` (`BIGSERIAL`).
34. **REQ-D4-04 (F4.4: Permissive Status Constraint)**: `publication_status` must allow unnormalized/unknown third-party scraping statuses without crashing.
35. **REQ-D4-05 (F4.5: Foreign Key On-Delete Cascades)**: Non-critical foreign key relationships (e.g. audit and takedown records) must declare `ondelete="SET NULL"`.
36. **REQ-D4-06 (F4.6: Database-Level Server Defaults)**: Timestamp columns (`created_at`, `updated_at`) must declare `nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")`.
37. **REQ-D4-07 (F4.7: Partial Indexing on Published Novels)**: Ranking and listing indexes must be partial indexes filtering out soft-deleted novels (`WHERE is_deleted = false`).
38. **REQ-D4-08 (F4.8: Natural Unique Constraints)**: Active chapters must enforce `UniqueConstraint("novel_id", "chapter_number")`.
39. **REQ-D4-09 (F4.9: Standardized Migration Naming)**: Alembic configuration must enforce `YYYY-MM-DD_<hash>_<description>.py`.
40. **REQ-D4-10 (F4.10: Zero-Downtime Migration Lock Timeouts)**: Migrations must execute `SET LOCAL lock_timeout = '2s'` and `statement_timeout = '10s'`.

### Domain 5: Backup Engine, Restore Drills & Disaster Recovery (Findings 5.1 - 5.10)

41. **REQ-D5-01 (F5.1: Chunked Backup Manifests)**: `R2IncrementalBackupTarget` must partition large manifests into chunked files with an index manifest.
42. **REQ-D5-02 (F5.2: Cryptographic Manifest Signing)**: Backup manifests must be cryptographically signed using ed25519 recovery keys.
43. **REQ-D5-03 (F5.3: Minimum Retention Floor)**: Backup retention must enforce a minimum retained snapshot count floor (`keep_minimum=7`) regardless of elapsed days.
44. **REQ-D5-04 (F5.4: PostgreSQL LSN Alignment)**: Backup manifests must record the current PostgreSQL Log Sequence Number (LSN) for PITR alignment.
45. **REQ-D5-05 (F5.5: Atomic Backup Abort Cleanup)**: Failed or aborted snapshot runs must delete copied orphan objects from the backup bucket.
46. **REQ-D5-06 (F5.6: Deep Byte Sampling in Restore Drills)**: Automated restore drills must decompress and verify SHA-256 integrity on a 1% random sample of objects.
47. **REQ-D5-07 (F5.7: Multi-Region Backup Bucket Configuration)**: Backup bucket targets must support cross-region or secondary cloud configurations.
48. **REQ-D5-08 (F5.8: Backup Copy Rate Limiting)**: `create_snapshot()` must throttle copy requests to prevent worker execution limits and egress spikes.
49. **REQ-D5-09 (F5.9: Distributed Concurrency Lock on Backups)**: Backup execution must acquire a PostgreSQL advisory lock (`pg_try_advisory_lock`) before initiating.
50. **REQ-D5-10 (F5.10: Operational Alerting on Backup Failure)**: Backup exceptions must dispatch structured alert webhooks.

### Domain 6: Catalog Projections, Caching & Recomputation Boundaries (Findings 6.1 - 6.10)

51. **REQ-D6-01 (F6.1: Post-Commit Cache Invalidation)**: Redis cache invalidations must hook into SQLAlchemy `session.after_commit()` to prevent stale cache repopulation.
52. **REQ-D6-02 (F6.2: Bounded In-Memory Metadata Cache)**: Local metadata caches in `r2_catalog.py` must use bounded LRU caches with TTL (`TTLCache`).
53. **REQ-D6-03 (F6.3: Paginated Chapter Catalog Responses)**: Novel chapter list queries must enforce pagination or lightweight navigation projection.
54. **REQ-D6-04 (F6.4: Clear Status Authority Boundary)**: PostgreSQL owns orchestration state (`chapters.status`); R2 owns payload existence.
55. **REQ-D6-05 (F6.5: Cache Stampede Protection)**: Reader cache misses on cold novel chapters must acquire a single-flight mutex lock during R2 fetch.
56. **REQ-D6-06 (F6.6: Canonical ETag Validation)**: Cache validators must compare `logical_sha256` metadata rather than multipart S3/R2 ETag formats.
57. **REQ-D6-07 (F6.7: Stale-While-Revalidate Headers)**: Public reader endpoints must emit `Cache-Control: public, max-age=60, stale-while-revalidate=300`.
58. **REQ-D6-08 (F6.8: Bulk Invalidation Batching)**: Scraper completions must batch cache deletion keys into a single `redis.delete(*keys)` call.
59. **REQ-D6-09 (F6.9: Standardized Datetime Serialization)**: Datetime fields in cache payloads must use uniform ISO 8601 UTC representation.
60. **REQ-D6-10 (F6.10: Compressed Redis Cache Entries)**: Payloads exceeding 1KB stored in Redis must be compressed with `zstandard` or `gzip`.

### Domain 7: Concurrency, Row Locking & Race Conditions (Findings 7.1 - 7.10)

61. **REQ-D7-01 (F7.1: Non-Blocking Translation Queue Claiming)**: Chapter translation polling must execute `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1`.
62. **REQ-D7-02 (F7.2: Ordered Locking on Batch Reordering)**: Reordering operations must sort target row IDs (`id ASC`) before acquiring row locks to prevent deadlocks.
63. **REQ-D7-03 (F7.3: Atomic Conditional Compare-and-Swap)**: R2 Gateway `compare_and_swap` must send `If-Match: <etag>` HTTP headers for atomic write validation.
64. **REQ-D7-04 (F7.4: Synchronized User Role Mutations)**: Role promotion/demotion must lock target user rows and acquire an advisory lock on role changes.
65. **REQ-D7-05 (F7.5: Buffered Novel View Increments)**: View counters must buffer increments in Redis and flush periodically to PostgreSQL via background worker.
66. **REQ-D7-06 (F7.6: Repeatable Read on Analytics Rollups)**: Financial and operational rollup transactions must set `ISOLATION LEVEL REPEATABLE READ`.
67. **REQ-D7-07 (F7.7: Distributed Lock Abstraction)**: Deprecate single-node `fcntl` locks in favor of Redis/PostgreSQL advisory locks for distributed workers.
68. **REQ-D7-08 (F7.8: Idempotent Chapter Upserts)**: Scraping inserts must use PostgreSQL `INSERT ... ON CONFLICT DO NOTHING / UPDATE`.
69. **REQ-D7-09 (F7.9: Deterministic Advisory Lock Keys)**: Advisory lock integer keys must be computed using deterministic SHA-256 hashing rather than Python `hash()`.
70. **REQ-D7-10 (F7.10: Fast-Failing Lock Timeouts)**: All row locks must specify `NOWAIT` or set `SET LOCAL lock_timeout = '3s'`.

### Domain 8: Storage Garbage Collection, Retention & Orphan Pruning (Findings 8.1 - 8.10)

71. **REQ-D8-01 (F8.1: Quarantine Grace Period on Pruning)**: GC pruner in `r2_cutover.py` must enforce a 48-hour age grace period before deleting unreferenced objects.
72. **REQ-D8-02 (F8.2: Batched Deletion Requests)**: Pruning operations must utilize batch deletion endpoints.
73. **REQ-D8-03 (F8.3: Streamed Set Difference for GC)**: Key reconciliation must stream database references or use temporary Postgres tables rather than monolithic in-memory Python sets.
74. **REQ-D8-04 (F8.4: Shared Media Reference Counting)**: Media assets must verify reference counts across all chapters and novels before R2 deletion.
75. **REQ-D8-05 (F8.5: Soft-Delete Retention Grace Period)**: Deleted novels must be retained for 30 days before background prefix purges.
76. **REQ-D8-06 (F8.6: Dead Generation Pruning)**: Superseded scraping generations older than 7 days must be tracked and pruned.
77. **REQ-D8-07 (F8.7: Aggregate Storage Metrics Ingestion)**: Replace full-bucket scans for `total_size_bytes()` with database metrics or Cloudflare GraphQL analytics.
78. **REQ-D8-08 (F8.8: Audit Logging on GC Executions)**: Every GC execution must record an immutable audit entry in `audit_records`.
79. **REQ-D8-09 (F8.9: R2 Multipart Abort Lifecycle Rules)**: Configure R2 bucket lifecycle policies to automatically abort incomplete multipart uploads after 7 days.
80. **REQ-D8-10 (F8.10: Mandatory Dry-Run and Confirmation Gate)**: Cutover and purge scripts must default to `--dry-run` and require `--confirm-delete` for mutation.

### Domain 9: Query Efficiency, Index Coverage & Pool Budgeting (Findings 9.1 - 9.10)

81. **REQ-D9-01 (F9.1: Strict Pool Budgeting Allocation)**: Enforce pool formula: Backend (5/5), Reader (5/5), Worker (5/5), Reserve (10) under `max_connections = 100`.
82. **REQ-D9-02 (F9.2: Eager Loading on Chapter Relations)**: Detail queries must use `selectinload(Novel.chapters)` to prevent N+1 query patterns.
83. **REQ-D9-03 (F9.3: Composite Chapter Index)**: Add composite index `Index("ix_chapters_novel_chapter", "novel_id", "chapter_number")`.
84. **REQ-D9-04 (F9.4: GIN Trigram Index on Novel Search)**: Add `pg_trgm` GIN index on `novels.title` for fast case-insensitive search.
85. **REQ-D9-05 (F9.5: Tight Statement Timeout on Public Reads)**: `read_session_scope()` must enforce `SET LOCAL statement_timeout = '3000'`.
86. **REQ-D9-06 (F9.7: Notification Query Pagination)**: User notification listing must enforce mandatory `LIMIT` (max 50).
87. **REQ-D9-07 (F9.6: Indexing Junction Tables)**: Novel-to-Tag junction tables must index both foreign keys.
88. **REQ-D9-08 (F9.8: Fast Approximate Row Counts)**: Administrative dashboard metrics must query `pg_class.reltuples` instead of `count(*)` for high-cardinality tables.
89. **REQ-D9-09 (F9.9: Expression Indexing on Activity JSONB)**: Activity queries filtering on `details->>'action'` must have an expression index.
90. **REQ-D9-10 (F9.10: Enforced Session Scope Context)**: Raw session instantiation in `r2_catalog.py` must be replaced with `session_scope()` context managers.

### Domain 10: Security, RLS Hardening & Audit Trails (Findings 10.1 - 10.10)

91. **REQ-D10-01 (F10.1: Force Row Level Security)**: Execute `ALTER TABLE <name> FORCE ROW LEVEL SECURITY` on all multi-tenant tables.
92. **REQ-D10-02 (F10.2: Search Path Pinning on Security Definers)**: All `SECURITY DEFINER` routines must pin `SET search_path = pg_catalog, pg_temp`.
93. **REQ-D10-03 (F10.3: Sanitized Database Error Responses)**: Intercept all database operational exceptions and return generic error payloads without internal schema details.
94. **REQ-D10-04 (F10.4: Application-Layer Encryption for Provider Keys)**: Encrypt third-party LLM API keys at rest using AES-256-GCM / Fernet envelopes.
95. **REQ-D10-05 (F10.5: Rate Limiting on Object Gateway)**: Configure Cloudflare Worker Rate Limiting (`env.RATE_LIMITER`) on `/objects/*` download routes.
96. **REQ-D10-06 (F10.6: Comprehensive Data Export Auditing)**: Admin export operations must write synchronous records to `audit_records`.
97. **REQ-D10-07 (F10.7: Cryptographic JWT Verification in Gateway)**: Gateway worker must cryptographically verify Cloudflare Access JWT signatures against JWKS certificates.
98. **REQ-D10-08 (F10.8: Modern Password Hashing & Upgrade Path)**: Implement Argon2id or automated passlib hash upgrades for user credentials.
99. **REQ-D10-09 (F10.9: Principle of Least Privilege for App Role)**: Revoke `TRUNCATE` and `DROP` privileges from `novelai_app` runtime role.
100.  **REQ-D10-10 (F10.10: Reader Download Integrity Verification)**: Public reader streaming must verify downloaded R2 payload against `logical_sha256` recorded in PostgreSQL.

## Acceptance Criteria

- [ ] AC-1: All 100 requirements mapped to findings F1.1 through F10.10 are implemented and validated.
- [ ] AC-2: Full test suite passes via `tools/pytest.ps1`.
- [ ] AC-3: Pyright type checks pass with 0 errors via `tools/pyright.ps1`.
- [ ] AC-4: Ruff linter & formatter passes with 0 violations via `tools/ruff.ps1`.
- [ ] AC-5: Documentation contracts pass with 0 violations via `tools/docs-check.ps1`.
- [ ] AC-6: Router import guard passes with 0 violations.
- [ ] AC-7: `DATABASE_STORAGE_AUDIT.md` is removed after all findings are incorporated into the active specification.

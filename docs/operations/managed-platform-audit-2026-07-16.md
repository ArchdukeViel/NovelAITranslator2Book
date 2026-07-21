# Managed Platform Audit — 2026-07-16

This report records a point-in-time Supabase audit and security remediation plus an explicitly authorized Cloudflare R2 backup operation. It is operational evidence, not a durable source of current provider state. Re-verify live settings before relying on it.

## Scope

- Supabase project health, PostgreSQL version, migrations, extensions, RLS posture, scheduled cleanup, and advisors.
- Cloudflare R2 production-bucket connectivity and control-plane settings.
- Independent R2 snapshot creation, integrity verification, retention protection, and restore drill.
- Repository implementation, configuration, migration, test, and recovery maturity.

No secrets, database URLs, access keys, service-role keys, or object keys are recorded here.

## Supabase Findings

- Project status: healthy.
- PostgreSQL server version: 17.6.
- Remote Alembic revision: `3da9f497264c`, matching the local migration head after remediation.
- Public schema: 29 tables, all with RLS enabled.
- `pg_cron`: installed and running the scheduler-state cleanup from the non-exposed `private` schema at `03:30 UTC` daily.
- `pg_net`: removed after live dependency inspection found no dependent object, HTTP cron command, or application use.
- Security advisor result after remediation: no warnings. One informational notice remains because `scheduled_cron_log` intentionally has RLS enabled with no policy; table privileges are also revoked from `anon` and `authenticated`.
- RLS helper functions are security-definer functions in the non-exposed `private` schema with an empty `search_path`; only the policy roles receive the minimum execute privileges required by RLS.
- Performance advisor findings were unused-index notices on a lightly populated database. They are not sufficient evidence for removing indexes.

### Supabase Maturity

**Rating after remediation: 4/5 for the intended managed-PostgreSQL use case.**

The project has a mature provider-neutral database integration: SQLAlchemy owns application persistence, Alembic owns schema evolution, deployment runs migrations before services, health checks are redacted, and production PostgreSQL migrations are exercised in CI. The project intentionally does not use Supabase as its application SDK, Auth SDK, or Storage layer, so it should not be described as a mature integration with the entire Supabase platform.

Phase 1 database-security remediation is complete: public-table RLS policy state is reproducible through Alembic, privileged helpers are outside the exposed schema, the internal cron log is fail-closed, and the unused public extension is removed.

Remaining limitations:

- Most repository tests use SQLite; full service behavior is not continuously exercised against hosted PostgreSQL.
- Pooling, connection modes, TLS, and per-connection timeouts are now explicit in the repository; live deployment verification remains required.
- Encrypted logical database backup automation is implemented. A scheduler-created backup and automated clean PostgreSQL 17 restore verification succeeded on 2026-07-18; alert delivery and hosted workflow evidence remain acceptance gates.

## Cloudflare R2 Findings

### Production Bucket

- Bucket connectivity and object listing were authorized.
- Bucket location: APAC; default storage class: Standard.
- Public development URL: disabled.
- Custom domains: none.
- Bucket CORS is absent. Browser clients do not access R2 directly; application access stays behind the backend storage abstraction.
- Lifecycle rules cover abandoned multipart uploads and disposable cache, health-check, and integration-test prefixes.
- No production-prefix bucket lock is configured, avoiding interference with mutable application objects.

### Independent Backup

- Backup bucket: `dokushodo-backup`.
- Location: APAC; storage class: Standard.
- Public development URL: disabled.
- Custom domains: none.
- Snapshot `2026-07-16T062027Z`: 21 objects and 414,040 source bytes copied with zero ETag or size mismatches; protected by a 30-day prefix lock.
- Snapshot `2026-07-16T063000Z-controlplane-safe`: 21 objects and 414,040 source bytes copied with zero ETag or size mismatches; includes an integrity manifest and is protected by a 30-day prefix lock.
- The second snapshot uses an opaque content type so the Cloudflare control-plane connector can read artifacts without interpreting JSON objects as API envelopes.
- Backup-bucket verification after the application snapshot: 61 objects and 1,222,144 total bytes, with no remaining restore-drill or failed-automation artifacts.
- The deployment environment files now contain the required backup settings and pass the repository's fatal production-configuration checks.
- Snapshot `backup-20260716T085825Z-c385157e` was created through `Container -> BackupService -> S3SnapshotTarget`: 16 source objects and 381,808 source bytes, with a manifest-last commit marker and successful SHA-256 verification.
- Independent control-plane verification found 17 stored objects including exactly one manifest, 386,760 total stored bytes, 30-day lock coverage, 90-day snapshot expiration, and 7-day incomplete-upload cleanup.

### Restore Drill

- Restored all 21 source artifacts from `2026-07-16T063000Z-controlplane-safe` into an isolated drill prefix.
- Verified object count, byte sizes, and ETags with zero mismatches.
- Deleted all 21 drill copies after verification.
- Confirmed the drill prefix was empty after cleanup.
- Re-read and checksum-verified all 16 data objects in `backup-20260716T085825Z-c385157e` after commit; object count, byte sizes, and SHA-256 hashes matched the manifest.

### R2 Maturity

**Rating after remediation: 4.5/5 for object storage and recovery.**

The application-side object-storage implementation is production-capable for CRUD and recovery: storage access is behind backend abstractions, production configuration validates independent R2 backup credentials, virtual-prefix behavior is implemented, and mocked plus opt-in real integration tests exist. Live application-driven snapshot creation, manifest commit, retention coverage, and post-commit checksum verification are proven for the current dataset.

Remediation completed after the initial audit:

- Added scheduled, manifest-last snapshots from canonical R2 novel objects to an independently configured S3-compatible bucket.
- Added conditional source-ETag copy checks and full SHA-256 verification of restored target bytes.
- Fixed S3 existence and deletion behavior so provider, authorization, and network failures propagate instead of appearing as missing objects or successful deletes.
- Reconciled the storage save contract with object-store last-write-wins semantics.
- Fixed scheduler result propagation so failed or locked runs are not recorded as successful.
- Configured the live backup prefix for 30-day retention locks and 90-day lifecycle deletion.
- Installed three distinct credential roles and verified their behavior through the S3-compatible API: application read/write/delete on the production bucket, snapshot-source read with write denied on the production bucket, and backup-target read/write/delete on the backup bucket. Cross-bucket access attempts were denied and all isolated test artifacts were removed.

Remaining limitations:

- Real R2 tests are opt-in rather than continuously exercised in CI.
- Storage usage health now uses the storage-backend contract rather than boto3 internals. It still requires a complete application-prefix listing, so a metrics-based capacity source may be preferable at larger scale.
- Cron/timezone evaluation and renewable database leases are implemented. Two consecutive accelerated scheduler runs on 2026-07-18 created committed live snapshots; each restored and checksum-verified all 16 objects and 381,808 bytes.
- Encrypted PostgreSQL backup and clean PostgreSQL 17 restore are implemented. On 2026-07-18 the scheduler created a committed encrypted backup and automatically restored it into a newly created PostgreSQL 17 target at Alembic head `8b7f3d1a2c4e`, with 30 public tables and zero invalid constraints.

## Verification Evidence

- Live Supabase metadata, schema, extension, migration, advisor, SQL, and cron queries completed successfully.
- Alembic revision `3da9f497264c` applied transactionally to the hosted database and advanced the live schema from `024fcb03c7d0` to head.
- Post-migration role checks confirmed public catalog reads evaluate RLS helpers successfully while `anon` receives `permission denied` for `scheduled_cron_log`.
- A real `pg_cron` execution using `SELECT private.cleanup_expired_scheduler_states();` completed successfully at 09:54 UTC, wrote a successful internal log entry, and the job was restored to its normal `30 3 * * *` schedule.
- Live Cloudflare R2 bucket metadata, public-access, CORS, lifecycle, lock, domain, and object-list queries completed successfully.
- Production configuration validation reported zero fatal findings for `.env`, `deploy/.env`, and `deploy/.env.production`; remaining warnings concern CORS, trusted hosts, and one CSRF-origin configuration.
- A live application-driven snapshot completed successfully with 16 source objects, 381,808 source bytes, a manifest-last commit marker, and successful post-commit SHA-256 verification.
- Independent Cloudflare verification confirmed the committed snapshot, expected retention and lifecycle coverage, and no incomplete automatic snapshot artifacts.
- Live S3 permission-boundary verification confirmed all three R2 credential roles, including intended writes, denied writes, denied cross-bucket access, and cleanup of the isolated verification prefix.
- Two scheduler-created R2 snapshots completed successfully on 2026-07-18 and were independently re-read through the application S3 client; all recorded object sizes and SHA-256 checksums matched.
- A scheduler-created encrypted logical backup completed on 2026-07-18, followed by successful automated restoration into a newly created PostgreSQL 17 target. Supabase records both scheduler jobs as succeeded, and Cloudflare independently confirms the new committed database manifest and encrypted artifact size.
- Google OAuth configuration is installed consistently in the three local environment files and passes structural validation. The end-to-end hosted callback remains unverified until a production domain is selected.
- Focused repository tests after remediation: 66 passed with boto3/moto enabled.
- Documentation whitespace validation: `git diff --check` passed.

## Follow-Up Priorities

1. Configure tested SMTP and an operator recipient, then prove scheduled-job-failure and stale-backup alert delivery, cooldown, and redaction.
2. Enable the managed-services GitHub workflow with isolated hosted PostgreSQL and R2 credentials, then retain successful run evidence.
3. Select the production frontend/backend topology and domain, replace the local OAuth callback in the production environment, and clear the remaining CORS, CSRF, and allowed-host warnings.

## Recovery Acceptance Update — 2026-07-18

- Supabase remains `ACTIVE_HEALTHY` on PostgreSQL 17.6. The live Alembic head is
  `8b7f3d1a2c4e`, all 30 public tables have RLS, and the security advisor has
  zero WARN findings. The daily private cleanup job succeeded on both July 17
  and July 18 in addition to the earlier runs.
- Two accelerated one-minute scheduler occurrences created distinct committed
  R2 snapshots. Supabase contains two `succeeded` scheduler log rows; Cloudflare
  independently shows both new manifests under the lifecycle- and lock-covered
  `snapshots/` prefix. Application restore verification re-read all content and
  matched every recorded SHA-256 checksum.
- A separate scheduler occurrence created a manifest-last encrypted PostgreSQL
  backup. The automated verifier restored it into a newly created PostgreSQL 17
  Docker volume, verified the current Alembic head, 30 public tables, and zero
  invalid constraints, and the isolated container and volumes were removed
  afterward.
- No credential, connection string, object key, or decrypted artifact was
  printed or recorded. SMTP alert delivery and hosted workflow acceptance remain
  open.
- The opt-in hosted PostgreSQL suite verified timeout settings, current Alembic
  head, denied Data API lease-table privileges, reconnect behavior, and lease
  contention. The real-R2 suite verified the application/source/target
  credential split through an isolated snapshot and removed all test artifacts.
  Three hosted integration tests passed. The GitHub-hosted managed-services
  workflow itself remains pending.

## Repository and CI Reconciliation — 2026-07-18

The storage and database evidence above remains valid, but it does not close the
repository launch gate. The latest clean-PostgreSQL GitHub Actions migration
fails because the vanilla CI service does not contain Supabase's `auth` schema.
DEBT-076 and DEBT-077 now track that regression and the misleading aggregate
build signal.

The selected free hosted preview is Vercel Hobby plus one Render Free monolith,
Supabase Free, and development-only R2. It is disposable: continuous worker and
scheduler jobs, scheduled recovery verification, maintenance, and SMTP are
disabled. Production still requires an always-on container backend, managed
Redis, tested SMTP, monitoring, and full hosted acceptance. DEBT-079 records the
remaining topology proof.

## Supabase Schema Reconciliation — 2026-07-22

- The committed `9c2e4a6b8d0f` migration was applied to the hosted Supabase
  project after confirming that all four `novels` rows had matching legacy and
  canonical publication states and that no database object depended on the
  legacy column.
- Post-migration verification found live Alembic head `9c2e4a6b8d0f`, all four
  novel rows preserved, `novels.status` absent, and
  `novels.publication_status` present.
- Every public application table remains protected by RLS. The Supabase
  security advisor reports zero WARN findings and one expected INFO finding for
  the deliberately policy-free `scheduled_cron_log` table.
- PostgreSQL reports one unvalidated constraint in Supabase-managed
  `realtime.messages`; no unvalidated constraint belongs to the public
  application schema. This provider-managed constraint is recorded as evidence,
  not application debt.
- The successful hosted schema migration closes the Supabase half of DEBT-076.
  A fresh clean-PostgreSQL GitHub Actions run is still required to prove the CI
  compatibility shim and close that debt.

# design.md

# Design: Scheduled Backups and Restore Drills

## Overview

`scheduled-backups-and-restore-drills` adds production-grade backup operations before V1 launch. The system will run scheduled backups, retain backup artifacts according to policy, optionally upload copies to an offsite/S3-compatible target, expose backup status through an admin endpoint, alert when backups are stale or failed, and verify that backups can actually be restored.

This is a V1 launch blocker because data recovery cannot depend on manual database access or untested scripts after launch.

## Goals

* Add scheduled backup execution.
* Back up database data and required persistent application storage.
* Support local and S3-compatible/offsite backup targets.
* Add retention cleanup for old backups.
* Add admin backup status endpoint.
* Track backup metadata, status, size, duration, artifact location, and failure reason.
* Detect stale or failed backups.
* Add restore verification/drill workflow.
* Add tests for backup scheduling, metadata, retention, status, alerts, and restore verification.

## Non-goals

* No full disaster recovery automation across infrastructure providers.
* No cross-region failover orchestration.
* No user-facing backup download feature.
* No permanent archive/compliance retention beyond configured backup retention.
* No encrypted key-management system beyond using existing deployment secrets.
* No restoring directly over production data from the admin UI in V1.

## Backup scope

The backup system should include all persistent data needed to recover the application.

Recommended backup sources:

```text id="sd9mpw"
database
uploaded/generated storage files
public reader/export artifacts if not reproducible
configuration metadata required for app recovery
```

Do not include:

```text id="mv0qid"
temporary files
cache-only files
worker scratch directories
runtime lock files
secrets or .env files
third-party dependency directories
```

If some artifacts are fully reproducible from database state and source content, they may be excluded only if this is documented.

## Backup types

V1 should support full backups.

Recommended V1 type:

```text id="gchhjx"
full
```

Future types:

```text id="w0io4x"
incremental
differential
database-only
storage-only
```

The metadata model should include a `backup_type` field even if only `full` is implemented.

## Backup targets

### Local target

Local backups are written to a configured directory.

Example:

```text id="onbwpf"
BACKUP_LOCAL_DIR=/var/lib/novelai/backups
```

Local backups are useful for quick recovery and restore drills but are not sufficient alone for production.

### S3-compatible/offsite target

The backup system should optionally upload backup artifacts to an S3-compatible target.

Recommended config:

```text id="czn0ox"
BACKUP_S3_ENABLED=true
BACKUP_S3_ENDPOINT_URL=
BACKUP_S3_REGION=
BACKUP_S3_BUCKET=
BACKUP_S3_PREFIX=novelai/backups
BACKUP_S3_ACCESS_KEY_ID=
BACKUP_S3_SECRET_ACCESS_KEY=
```

The design should support AWS S3, Cloudflare R2, MinIO, Backblaze B2 S3-compatible storage, or another S3-compatible provider.

## Backup artifact format

Each backup run should produce a backup bundle.

Recommended layout:

```text id="3oszp4"
backup-20260710T010000Z/
  manifest.json
  database/
    database.dump
  storage/
    ...
  checksums.sha256
```

The final artifact may be compressed:

```text id="c38gxf"
backup-20260710T010000Z.tar.gz
```

Recommended manifest fields:

```json id="otszql"
{
  "backup_id": "backup_20260710T010000Z",
  "backup_type": "full",
  "status": "succeeded",
  "started_at": "2026-07-10T01:00:00Z",
  "finished_at": "2026-07-10T01:02:30Z",
  "duration_ms": 150000,
  "app_version": "unknown",
  "database": {
    "included": true,
    "engine": "postgresql",
    "dump_file": "database/database.dump"
  },
  "storage": {
    "included": true,
    "root": "storage/",
    "file_count": 1200
  },
  "artifacts": [
    {
      "target": "local",
      "uri": "file:///var/lib/novelai/backups/backup-20260710T010000Z.tar.gz",
      "size_bytes": 123456789,
      "checksum_sha256": "..."
    },
    {
      "target": "s3",
      "uri": "s3://bucket/novelai/backups/backup-20260710T010000Z.tar.gz",
      "size_bytes": 123456789,
      "checksum_sha256": "..."
    }
  ],
  "restore_verification": {
    "status": "not_run",
    "verified_at": null
  }
}
```

## Backup metadata persistence

Backup metadata should be persisted in the application database or an existing durable operations store.

Recommended table/model: `backup_runs`

Recommended fields:

```text id="af32ee"
id
backup_type
status
started_at
finished_at
duration_ms
local_path
offsite_uri
size_bytes
checksum_sha256
error_category
error_message
manifest_json
restore_verification_status
restore_verified_at
restore_verification_error
created_at
updated_at
```

Recommended statuses:

```text id="00erxh"
queued
running
succeeded
failed
partially_succeeded
verification_running
verification_succeeded
verification_failed
```

A backup that succeeds locally but fails offsite upload should be `partially_succeeded` unless production policy requires offsite upload to succeed.

## Scheduler design

Use the existing scheduler/worker system if available.

Recommended config:

```text id="lpa450"
BACKUP_ENABLED=true
BACKUP_SCHEDULE_CRON=0 2 * * *
BACKUP_TIMEZONE=UTC
BACKUP_RETENTION_DAYS=30
BACKUP_MIN_SUCCESS_INTERVAL_HOURS=26
BACKUP_RESTORE_DRILL_ENABLED=true
BACKUP_RESTORE_DRILL_CRON=0 4 * * 0
```

Scheduler behavior:

1. Check whether scheduled backups are enabled.
2. Acquire a backup lock to prevent overlapping backup runs.
3. Create a `backup_runs` record with `running` status.
4. Run database backup.
5. Run storage backup.
6. Build manifest and checksums.
7. Write local artifact.
8. Upload to offsite target if enabled.
9. Mark run as succeeded, partially succeeded, or failed.
10. Run retention cleanup.
11. Emit stale/failed alert if needed.

## Locking and concurrency

Only one backup should run at a time.

Recommended lock options:

```text id="1zgs1j"
database advisory lock
database row lock
Redis lock
filesystem lock for single-node deployments
```

If a backup is already running, the scheduler should skip the new run and record a skipped/locked event in logs or metadata.

## Database backup strategy

Use the database engine’s native dump mechanism when possible.

Examples:

```text id="w404j8"
PostgreSQL: pg_dump
SQLite: safe file copy with write lock or online backup API
MySQL/MariaDB: mysqldump
```

The implementation should detect or use configured database type.

Recommended config:

```text id="80xi9d"
BACKUP_DATABASE_ENABLED=true
BACKUP_DATABASE_COMMAND=
```

If the project uses SQLite in development and PostgreSQL in production, support both if both are supported deployment modes.

## Storage backup strategy

Persistent storage should be backed up by copying required directories into the backup bundle.

Recommended config:

```text id="yz8vd3"
BACKUP_STORAGE_ENABLED=true
BACKUP_STORAGE_PATHS=storage,uploads,exports
BACKUP_STORAGE_EXCLUDE_PATTERNS=tmp/**,cache/**,*.lock
```

Storage backup should:

* Preserve relative paths.
* Exclude temporary/cache files.
* Count included files.
* Fail clearly on unreadable required files.
* Include checksums.

## Retention policy

Retention should remove old backup artifacts and metadata according to configured policy.

Recommended V1 policy:

```text id="jd6u2h"
keep successful backups for BACKUP_RETENTION_DAYS
keep failed backup metadata for BACKUP_FAILED_RETENTION_DAYS
never delete the newest successful backup
delete local and offsite artifacts together when possible
```

Recommended config:

```text id="7g5g8s"
BACKUP_RETENTION_DAYS=30
BACKUP_FAILED_RETENTION_DAYS=14
BACKUP_MIN_SUCCESSFUL_TO_KEEP=3
```

Retention cleanup should not delete all successful backups even if they are older than retention.

## Restore verification / drills

A backup is only useful if it can be restored. The system should support a restore verification workflow that runs against an isolated temporary location or test database, never directly over production.

V1 restore verification should:

1. Select the latest successful backup or a specified backup ID.
2. Download from offsite if local artifact is unavailable.
3. Verify checksum.
4. Extract the backup bundle.
5. Validate manifest.
6. Restore database into a temporary database or isolated restore location.
7. Restore storage into a temporary directory.
8. Run basic integrity checks.
9. Record verification status and timestamp.
10. Clean up temporary restore resources.

Recommended verification checks:

```text id="ld620t"
manifest exists and parses
checksum matches
database dump can be restored
expected core tables exist
user/novel/chapter/activity counts can be queried
storage files can be extracted
required storage directories exist
```

The restore drill must not mutate production database or production storage.

## Admin status endpoint

Add an admin-only backup status endpoint.

Recommended path:

```http id="a6xjoc"
GET /admin/backups/status
```

Recommended response:

```json id="vyo59v"
{
  "enabled": true,
  "schedule": "0 2 * * *",
  "last_successful_backup_at": "2026-07-10T02:00:00Z",
  "last_backup_status": "succeeded",
  "last_backup_id": "backup_20260710T020000Z",
  "last_restore_verification_status": "verification_succeeded",
  "last_restore_verified_at": "2026-07-10T04:05:00Z",
  "stale": false,
  "offsite_enabled": true,
  "retention_days": 30,
  "recent_runs": []
}
```

Optional admin endpoints:

```http id="fd9gna"
GET /admin/backups
GET /admin/backups/{backup_id}
POST /admin/backups/run
POST /admin/backups/{backup_id}/verify-restore
```

For V1, status endpoint is required. Manual run and manual restore verification endpoints are recommended if they fit the existing admin API pattern.

## Alerts

The system should detect:

```text id="6cslas"
backup_failed
backup_stale
offsite_upload_failed
restore_verification_failed
retention_cleanup_failed
```

Recommended alert channels for V1:

```text id="jb72tv"
application logs
admin health/status endpoint
optional email/webhook if notification infrastructure already exists
```

This spec should not build the full notification system. It should expose enough status for `deep-health-readiness-checks` and future `notification-system` to report backup problems.

## Health/readiness integration

The backup status should be available for health/readiness checks, but the full health endpoint work belongs to `deep-health-readiness-checks`.

This spec should provide a service method such as:

```text id="4wpib7"
BackupStatusService.get_backup_health()
```

Expected health signal:

```text id="qt58rd"
healthy: latest successful backup is within allowed interval
degraded: latest backup is stale or latest run partially succeeded
unhealthy: no successful backup exists or latest restore verification failed
```

## Error categories

Recommended backup error categories:

```text id="c69hjv"
database_dump_failed
storage_copy_failed
compression_failed
checksum_failed
local_write_failed
offsite_upload_failed
retention_cleanup_failed
restore_download_failed
restore_extract_failed
restore_database_failed
restore_storage_failed
restore_integrity_failed
lock_unavailable
unknown
```

## Security

Backup artifacts can contain sensitive application data.

Required security rules:

* Admin-only endpoints.
* Do not expose raw database contents through the API.
* Do not log secrets or full S3 credentials.
* Do not include `.env` files or secret files in backup bundles.
* Use deployment secrets for S3 credentials.
* Restrict local backup directory permissions.
* Prefer encryption at rest through the storage provider or deployment environment.
* Document backup artifact sensitivity.

Optional future hardening:

```text id="pbh2y3"
application-level backup encryption
KMS-managed encryption keys
signed manifests
immutable object storage retention
```

## Testing strategy

Backend tests should cover:

* Backup metadata creation.
* Successful local backup.
* Offsite upload success and failure handling.
* Failed backup status.
* Retention cleanup.
* Stale backup detection.
* Status endpoint authorization and response.
* Restore verification success.
* Restore verification failure.
* Locking behavior.
* Secret redaction.

Integration tests can use temporary directories and a fake S3 adapter.

## Rollout plan

1. Add backup configuration.
2. Add backup metadata model and migration.
3. Add backup artifact builder.
4. Add local backup target.
5. Add optional S3-compatible target.
6. Add scheduled worker job.
7. Add retention cleanup.
8. Add backup status service and admin endpoint.
9. Add restore verification workflow.
10. Add stale/failed backup detection.
11. Add tests.
12. Document first production backup and restore drill procedure.
13. Verify V1 launch checklist:

    * Backup job runs.
    * Backup artifact exists.
    * Offsite copy exists if enabled.
    * Status endpoint reports success.
    * Stale backup detection works.
    * Restore drill succeeds.

# design.md

# Design: Maintenance Cron

## Overview

`maintenance-cron` adds recurring operational cleanup jobs for data and files that should not live forever.

The application already has multiple runtime surfaces that can accumulate stale data:

```text id="ycfj6m"
temporary files
stale sessions
old activity records
expired scheduler runtime states
stale caches
old backup artifacts
orphaned export artifacts
worker scratch data
```

This spec adds a centralized maintenance cron framework and a first set of cleanup tasks. It is a should-have operations spec, not a V1 launch blocker, but it becomes important as usage grows.

## Goals

* Add a recurring maintenance job.
* Clean up temporary files and worker scratch files.
* Clean up expired/stale sessions if the app owns session storage.
* Clean up old activity records according to retention policy.
* Clean up expired scheduler runtime state.
* Clean up stale caches where safe.
* Trigger old backup retention cleanup if backup service exists.
* Clean up orphaned export artifacts where safe.
* Persist maintenance run metadata.
* Add admin/status visibility for recent maintenance runs.
* Add tests for cleanup behavior, retention safety, and failure isolation.

## Non-goals

* No full metrics dashboard.
* No alert notification delivery system.
* No backup implementation. That belongs to `scheduled-backups-and-restore-drills`.
* No scheduler runtime state design. That belongs to `scheduler-runtime-state-persistence`.
* No permanent deletion of user-owned source data unless separately specified.
* No destructive cleanup without explicit retention rules.
* No admin UI requirement unless an existing admin operations page exists.

## Maintenance job architecture

Recommended components:

```text id="k6o2mn"
MaintenanceScheduler
MaintenanceService
MaintenanceTaskRegistry
MaintenanceTask
MaintenanceRunRepository
CleanupResult
```

High-level flow:

```text id="0g4moo"
1. Scheduler triggers maintenance cron.
2. MaintenanceService acquires lock.
3. MaintenanceService creates maintenance run metadata.
4. Each enabled maintenance task runs in sequence.
5. Each task returns result counts and safe warnings.
6. Failures are isolated per task.
7. Maintenance run metadata is persisted.
8. Optional admin status endpoint exposes recent runs.
```

## Maintenance tasks

Recommended V1 tasks:

```text id="oeh6ov"
temp_file_cleanup
stale_session_cleanup
old_activity_cleanup
scheduler_runtime_state_cleanup
cache_cleanup
backup_retention_cleanup
export_artifact_cleanup
```

Each task should be independently enabled/disabled.

## Configuration

Recommended config:

```text id="v6mnns"
MAINTENANCE_ENABLED=true
MAINTENANCE_CRON=0 3 * * *
MAINTENANCE_TIMEZONE=UTC
MAINTENANCE_LOCK_TTL_SECONDS=3600
MAINTENANCE_TASK_TIMEOUT_SECONDS=300
MAINTENANCE_DRY_RUN=false
```

Task-specific config:

```text id="i4y5cb"
TEMP_FILE_RETENTION_HOURS=24
WORKER_SCRATCH_RETENTION_HOURS=24
SESSION_RETENTION_DAYS=30
ACTIVITY_RETENTION_DAYS=90
FAILED_ACTIVITY_RETENTION_DAYS=180
SCHEDULER_RUNTIME_STATE_RETENTION_DAYS=14
CACHE_RETENTION_HOURS=24
EXPORT_ARTIFACT_RETENTION_DAYS=30
ORPHANED_EXPORT_RETENTION_HOURS=24
BACKUP_RETENTION_DAYS=30
```

Use existing config names where already present.

## Maintenance run metadata

Persist maintenance run metadata so operators can confirm cleanup is running.

Recommended table/model: `maintenance_runs`

Recommended fields:

```text id="m8xqx5"
id
status
started_at
finished_at
duration_ms
trigger
locked_by
dry_run
tasks_total
tasks_succeeded
tasks_failed
items_deleted
bytes_deleted
error_message
metadata_json
created_at
updated_at
```

Recommended statuses:

```text id="bfrnpc"
running
succeeded
partially_succeeded
failed
skipped_locked
```

Recommended task result shape inside `metadata_json`:

```json id="gq5l5d"
{
  "tasks": [
    {
      "task_key": "temp_file_cleanup",
      "status": "succeeded",
      "items_scanned": 120,
      "items_deleted": 75,
      "bytes_deleted": 52428800,
      "duration_ms": 220,
      "warnings": []
    }
  ]
}
```

## Locking

Only one maintenance run should execute at a time.

Recommended lock options:

```text id="nv7glq"
database advisory lock
database row lock
Redis lock
filesystem lock for single-node deployment
```

If a run is already active:

```text id="xjp550"
skip new run
record skipped_locked status
do not run duplicate cleanup
```

## Failure isolation

A failure in one maintenance task should not automatically stop all other safe tasks.

Recommended behavior:

```text id="svvxag"
task succeeds -> record succeeded result
task fails -> record failed result and continue to next task if safe
critical setup failure -> maintenance run failed
lock unavailable -> skipped_locked
partial task failures -> run partially_succeeded
```

Examples:

```text id="cro5x7"
cache cleanup fails -> continue old activity cleanup
backup retention cleanup fails -> continue temp cleanup
database unavailable -> most database tasks fail; filesystem tasks may still run if safe
```

## Dry-run mode

Maintenance should support dry-run mode for staging and launch verification.

In dry-run mode:

```text id="w5dxss"
scan eligible items
calculate counts and bytes
do not delete files or records
record would_delete counts
return dry_run=true
```

Dry-run helps verify retention policies before destructive cleanup.

## Temp file cleanup

Clean configured temporary directories.

Recommended target paths:

```text id="5xmhkp"
storage/tmp
tmp
worker_scratch
export_tmp
download_tmp
```

Use actual project paths.

Rules:

```text id="e22n2t"
delete files older than TEMP_FILE_RETENTION_HOURS
delete empty directories after file cleanup
do not follow symlinks outside allowed roots
do not delete configured storage roots
do not delete user uploads or published artifacts
```

Safety checks:

```text id="9dn4b6"
path must be inside allowed cleanup root
path cannot be filesystem root
path cannot be project root unless explicitly allowed
path cannot be empty string
```

## Stale session cleanup

If sessions are server-side, delete expired sessions.

Possible stores:

```text id="bkcnsn"
database sessions
Redis sessions
token blacklist/revocation records
remember-me/session metadata table
```

Rules:

```text id="jy0kbl"
delete sessions expired by TTL
delete revoked sessions older than retention
delete disabled-user sessions if session store supports lookup
preserve active sessions
```

If sessions are stateless JWT-only, this task may only clean token revocation records or be disabled.

## Old activity cleanup

Activity records can grow quickly.

Recommended retention:

```text id="od6cjj"
completed succeeded activities: ACTIVITY_RETENTION_DAYS
failed activities: FAILED_ACTIVITY_RETENTION_DAYS
running activities: never delete unless stale cleanup policy exists
queued activities: never delete unless stale cleanup policy exists
```

Rules:

```text id="p5pt2b"
delete or archive old completed activity records
preserve active/running/queued activities
preserve activity records referenced by active jobs
preserve activity records needed for recent user-facing status
preserve audit/security records
```

If activity metadata contains large diagnostic data, cleanup may remove old records according to retention policy.

## Scheduler runtime state cleanup

Integrate with `scheduler-runtime-state-persistence`.

Rules:

```text id="fwzg74"
delete expired idle/recovered runtime states
preserve active failed/cooldown/running/disabled states
preserve configured scheduler scope states
do not delete active diagnostics
```

If the scheduler runtime state service exists, maintenance should call its cleanup method.

## Cache cleanup

Clean stale caches only where safe.

Possible caches:

```text id="bp37ne"
filesystem cache
public reader cache
export cache
source health cache
annotation cache
translation prompt cache
HTTP fetch cache
```

Rules:

```text id="037w2l"
delete expired cache entries
do not delete cache entries without expiration unless configured
do not delete durable source data
do not delete published reader snapshots unless they are explicitly cache-only
```

For in-memory caches, maintenance may call cache invalidation hooks if available.

## Backup retention cleanup

If `scheduled-backups-and-restore-drills` exists, maintenance should call backup retention cleanup.

Rules:

```text id="fh3zgp"
use backup service retention policy
never delete newest successful backup
preserve minimum successful backups
attempt local and offsite cleanup
record counts and warnings
```

Maintenance should not implement a separate conflicting backup retention algorithm if the backup service already owns it.

## Export artifact cleanup

Export artifacts can be cleaned if they are stale, orphaned, or reproducible.

Recommended categories:

```text id="n2oxrs"
temporary export working directories
failed export artifacts
orphaned artifacts not referenced by manifest
stale scheduled export artifacts according to retention
```

Rules:

```text id="xs7fwf"
preserve current manifest-referenced exports
preserve user-requested exports within retention window
delete failed/orphaned temp artifacts older than retention
do not delete advertised downloadable files prematurely
```

## Admin/status endpoint

Recommended admin-only endpoint:

```http id="75208h"
GET /admin/maintenance/status
```

Recommended response:

```json id="lv3j1j"
{
  "enabled": true,
  "schedule": "0 3 * * *",
  "last_run_status": "succeeded",
  "last_run_at": "2026-07-10T03:00:00Z",
  "last_success_at": "2026-07-10T03:00:00Z",
  "last_duration_ms": 8200,
  "recent_runs": []
}
```

Optional manual trigger:

```http id="fjhkpp"
POST /admin/maintenance/run
```

Request:

```json id="jcwlgo"
{
  "dry_run": true,
  "tasks": ["temp_file_cleanup", "cache_cleanup"]
}
```

Manual trigger is useful but optional. If implemented, admin-only authorization is required.

## Health integration

Maintenance status can feed deep health later.

Suggested health signal:

```text id="pui8kg"
healthy: recent maintenance run succeeded within expected interval
degraded: last run partially succeeded or stale
unhealthy: repeated failures or maintenance lock stuck
```

This spec should expose a service method:

```text id="a3fo1n"
MaintenanceStatusService.get_status()
```

## Security

Maintenance cleanup is destructive. Required safety:

```text id="3zf7go"
admin-only status/manual endpoints
path allowlist for filesystem cleanup
no following unsafe symlinks
dry-run support
safe logging
no secret exposure in status responses
no deletion of audit logs unless explicitly governed
no deletion of backups outside backup retention policy
```

## Observability

Structured logs:

```text id="u8x2kn"
maintenance.started
maintenance.task_started
maintenance.task_succeeded
maintenance.task_failed
maintenance.succeeded
maintenance.partially_succeeded
maintenance.failed
maintenance.skipped_locked
```

Safe fields:

```text id="j52b6r"
run_id
task_key
duration_ms
items_deleted
bytes_deleted
dry_run
error_category
```

Avoid logging full file paths if paths may expose private data. Log root-relative paths only if safe.

## Testing strategy

Tests should cover:

```text id="o6aqtl"
maintenance lock
run metadata persistence
task success and failure isolation
dry-run mode
temp file cleanup safety
stale session cleanup
old activity cleanup
scheduler runtime state cleanup
cache cleanup
backup retention delegation
export artifact cleanup
admin status authorization
manual trigger if implemented
path safety checks
symlink safety checks
```

## Rollout plan

1. Inspect scheduler and cleanup surfaces.
2. Add maintenance config.
3. Add maintenance run metadata model.
4. Add task registry and service.
5. Add lock.
6. Add temp cleanup task.
7. Add stale session cleanup task where applicable.
8. Add old activity cleanup task.
9. Add scheduler runtime state cleanup integration.
10. Add cache cleanup task.
11. Add backup retention delegation if backup service exists.
12. Add export artifact cleanup task.
13. Add status endpoint.
14. Add tests.
15. Verify dry-run in staging.
16. Enable scheduled maintenance.

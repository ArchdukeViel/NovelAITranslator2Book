# requirements.md

# Requirements: Maintenance Cron

## Introduction

The application needs a recurring maintenance cron to clean up stale operational data and temporary files. The system must safely remove expired temp files, stale sessions, old activity records, expired scheduler runtime states, stale caches, old backups, and orphaned export artifacts according to explicit retention policies.

## Requirement 1: Maintenance scheduling

### User story

As an operator, I want maintenance cleanup to run automatically so operational data does not grow forever.

### Acceptance criteria

1. WHEN maintenance is enabled THEN the system SHALL run maintenance according to configured schedule.
2. WHEN maintenance is disabled THEN the system SHALL not run scheduled maintenance.
3. WHEN maintenance starts THEN the system SHALL create a maintenance run record or equivalent metadata.
4. WHEN maintenance completes successfully THEN the system SHALL record success status.
5. WHEN maintenance partially fails THEN the system SHALL record partial success status.
6. WHEN maintenance fails before running tasks THEN the system SHALL record failed status.
7. WHEN maintenance schedule is invalid THEN the system SHALL surface a configuration error.
8. WHEN maintenance is running THEN another scheduled run SHALL not overlap it.

## Requirement 2: Maintenance locking

### User story

As an operator, I want maintenance runs to be non-overlapping so cleanup does not race with itself.

### Acceptance criteria

1. WHEN a maintenance run starts THEN the system SHALL acquire a maintenance lock.
2. WHEN another maintenance run already holds the lock THEN the new run SHALL be skipped.
3. WHEN a run is skipped due to lock THEN the system SHALL record or log `skipped_locked`.
4. WHEN a maintenance run completes THEN the system SHALL release the lock.
5. WHEN a maintenance run fails unexpectedly THEN the lock SHALL expire or become recoverable.
6. WHEN manual maintenance trigger exists THEN it SHALL use the same lock.
7. WHEN locking fails unexpectedly THEN the system SHALL not run destructive cleanup.

## Requirement 3: Maintenance run metadata

### User story

As an operator, I want metadata for maintenance runs so I can verify cleanup is happening.

### Acceptance criteria

1. WHEN maintenance starts THEN the system SHALL record start time.
2. WHEN maintenance finishes THEN the system SHALL record finish time and duration.
3. WHEN maintenance runs THEN the system SHALL record trigger type, such as scheduled or manual.
4. WHEN maintenance runs THEN the system SHALL record dry-run status.
5. WHEN maintenance tasks run THEN the system SHALL record per-task status.
6. WHEN cleanup deletes items THEN the system SHALL record item counts where practical.
7. WHEN cleanup deletes files THEN the system SHOULD record deleted bytes where practical.
8. WHEN a task fails THEN the system SHALL record safe error category or message.
9. WHEN recent maintenance status is requested THEN the system SHALL return recent run summaries.

## Requirement 4: Task registry and task isolation

### User story

As a maintainer, I want cleanup tasks to be modular so one failing task does not break all maintenance.

### Acceptance criteria

1. WHEN maintenance starts THEN it SHALL run enabled tasks from a registry or equivalent list.
2. WHEN a task succeeds THEN its result SHALL be recorded.
3. WHEN a task fails THEN its failure SHALL be recorded.
4. WHEN a non-critical task fails THEN remaining tasks SHALL continue where safe.
5. WHEN a critical task fails THEN the maintenance run MAY stop according to task configuration.
6. WHEN all tasks succeed THEN the run SHALL be marked succeeded.
7. WHEN some tasks fail and some succeed THEN the run SHALL be marked partially succeeded.
8. WHEN all runnable tasks fail THEN the run SHALL be marked failed.
9. WHEN a task is disabled THEN it SHALL not run.

## Requirement 5: Dry-run mode

### User story

As an operator, I want dry-run mode so I can verify cleanup behavior before deleting data.

### Acceptance criteria

1. WHEN dry-run mode is enabled THEN cleanup tasks SHALL scan eligible items without deleting them.
2. WHEN dry-run mode is enabled THEN task results SHALL report would-delete counts.
3. WHEN dry-run mode is enabled THEN file cleanup SHALL not delete files or directories.
4. WHEN dry-run mode is enabled THEN database cleanup SHALL not delete records.
5. WHEN dry-run mode is enabled THEN backup cleanup SHALL not delete local or offsite artifacts.
6. WHEN dry-run mode is enabled THEN the maintenance run metadata SHALL record `dry_run=true`.
7. WHEN manual trigger supports dry-run THEN admins SHALL be able to request dry-run mode.

## Requirement 6: Temporary file cleanup

### User story

As an operator, I want temporary files cleaned up so disk space is not consumed by stale scratch data.

### Acceptance criteria

1. WHEN temp file cleanup runs THEN it SHALL scan only configured allowlisted temp roots.
2. WHEN a temp file is older than configured retention THEN it SHALL be eligible for deletion.
3. WHEN a temp file is newer than configured retention THEN it SHALL be preserved.
4. WHEN an empty temp directory remains after cleanup THEN it MAY be deleted if inside an allowlisted root.
5. WHEN a path is outside allowlisted roots THEN it SHALL NOT be deleted.
6. WHEN a path is a filesystem root, project root, or empty path THEN cleanup SHALL refuse to run.
7. WHEN a symlink points outside an allowed cleanup root THEN cleanup SHALL NOT follow it for deletion.
8. WHEN temp cleanup succeeds THEN task result SHALL include scanned and deleted counts.
9. WHEN temp cleanup fails for a file THEN it SHALL record a warning and continue where safe.

## Requirement 7: Stale session cleanup

### User story

As an operator, I want expired sessions cleaned up so session storage does not grow forever.

### Acceptance criteria

1. WHEN server-side sessions exist THEN maintenance SHALL delete sessions expired by configured TTL.
2. WHEN revoked session records are older than configured retention THEN maintenance MAY delete them.
3. WHEN sessions are still active and unexpired THEN maintenance SHALL preserve them.
4. WHEN disabled-user sessions can be identified safely THEN maintenance SHOULD remove them.
5. WHEN the app uses stateless JWT-only sessions THEN this task SHALL be disabled or limited to revocation metadata cleanup.
6. WHEN session cleanup fails THEN the task SHALL record safe failure metadata.
7. WHEN session cleanup runs THEN it SHALL not reveal session tokens in logs or metadata.

## Requirement 8: Old activity record cleanup

### User story

As an operator, I want old activity records cleaned up so activity tables and metadata do not grow forever.

### Acceptance criteria

1. WHEN completed successful activity records are older than configured retention THEN they SHALL be eligible for cleanup.
2. WHEN failed activity records are older than configured failed-retention THEN they SHALL be eligible for cleanup.
3. WHEN activity records are running, queued, or active THEN they SHALL be preserved.
4. WHEN activity records are referenced by active jobs THEN they SHALL be preserved.
5. WHEN activity records are needed for recent user-facing status THEN they SHALL be preserved.
6. WHEN activity cleanup deletes records THEN it SHALL record deleted count.
7. WHEN activity cleanup runs THEN it SHALL not delete admin audit logs or security records.
8. WHEN activity cleanup fails THEN it SHALL record safe failure metadata and continue where safe.

## Requirement 9: Scheduler runtime state cleanup

### User story

As an operator, I want expired scheduler runtime state cleaned up while preserving active scheduler diagnostics.

### Acceptance criteria

1. WHEN scheduler runtime state cleanup runs THEN it SHALL call the scheduler runtime state cleanup service if available.
2. WHEN runtime states are idle or recovered and older than TTL THEN they MAY be deleted.
3. WHEN runtime states are active failed, cooldown, running, disabled, or stale THEN they SHALL be preserved.
4. WHEN runtime states represent configured scheduler scopes THEN they SHALL be preserved if needed for health output.
5. WHEN scheduler runtime cleanup service is unavailable THEN the task SHALL be skipped or marked unavailable safely.
6. WHEN cleanup succeeds THEN task result SHALL include deleted count where practical.
7. WHEN cleanup fails THEN task result SHALL include safe error metadata.

## Requirement 10: Cache cleanup

### User story

As an operator, I want stale caches cleaned up so cache storage does not grow forever.

### Acceptance criteria

1. WHEN cache cleanup runs THEN it SHALL delete only cache entries that are expired or safe to regenerate.
2. WHEN cache entries have no expiration and are not explicitly cache-only THEN they SHALL be preserved.
3. WHEN public reader snapshots are durable published artifacts THEN cache cleanup SHALL NOT delete them.
4. WHEN filesystem cache roots are cleaned THEN path safety rules SHALL apply.
5. WHEN in-memory cache invalidation hooks exist THEN maintenance MAY call them.
6. WHEN cache cleanup succeeds THEN task result SHALL include deleted/invalidated counts where practical.
7. WHEN cache cleanup fails THEN task result SHALL include safe error metadata and continue where safe.

## Requirement 11: Backup retention cleanup

### User story

As an operator, I want old backups cleaned up using the backup service’s retention policy.

### Acceptance criteria

1. WHEN backup retention cleanup runs and backup service exists THEN maintenance SHALL delegate to the backup retention service.
2. WHEN backup service does not exist THEN the task SHALL be disabled or skipped safely.
3. WHEN backup retention runs THEN it SHALL preserve the newest successful backup.
4. WHEN backup retention runs THEN it SHALL preserve the configured minimum number of successful backups.
5. WHEN offsite backup exists THEN retention cleanup SHALL use the backup service’s offsite deletion logic.
6. WHEN backup retention fails THEN maintenance SHALL record safe failure metadata.
7. WHEN backup retention is in dry-run mode THEN no local or offsite backup artifacts SHALL be deleted.

## Requirement 12: Export artifact cleanup

### User story

As an operator, I want stale and orphaned export artifacts cleaned up without deleting active downloadable exports.

### Acceptance criteria

1. WHEN export temp directories are older than configured retention THEN they SHALL be eligible for deletion.
2. WHEN failed export artifacts are older than configured retention THEN they SHALL be eligible for deletion.
3. WHEN export artifacts are referenced by a current manifest and within retention THEN they SHALL be preserved.
4. WHEN orphaned export artifacts are older than configured orphan retention THEN they MAY be deleted.
5. WHEN export artifacts are currently being generated THEN they SHALL be preserved.
6. WHEN export cleanup deletes files THEN it SHALL record file count and bytes where practical.
7. WHEN export cleanup fails THEN it SHALL record safe failure metadata and continue where safe.

## Requirement 13: Admin maintenance status

### User story

As an admin, I want to view maintenance status so I can confirm cleanup is running successfully.

### Acceptance criteria

1. WHEN an admin requests maintenance status THEN the system SHALL return schedule, enabled state, last run, and recent runs.
2. WHEN no maintenance run has occurred THEN the status response SHALL clearly indicate no runs.
3. WHEN the last run failed THEN the status response SHALL include safe failure summary.
4. WHEN the last run partially succeeded THEN the status response SHALL include failed task summaries.
5. WHEN a non-admin requests maintenance status THEN the system SHALL return `403 Forbidden`.
6. WHEN an unauthenticated user requests maintenance status THEN the system SHALL return `401 Unauthorized`.
7. WHEN status response includes task errors THEN it SHALL not expose secrets or unsafe paths.

## Requirement 14: Optional manual maintenance trigger

### User story

As an admin, I want to manually trigger maintenance so I can verify cleanup during staging or before release.

### Acceptance criteria

1. WHEN manual trigger is implemented THEN only admins SHALL be allowed to trigger it.
2. WHEN manual trigger is called with dry-run enabled THEN maintenance SHALL run in dry-run mode.
3. WHEN manual trigger specifies task keys THEN only those enabled/allowed tasks SHALL run.
4. WHEN manual trigger is called while maintenance lock is held THEN the request SHALL not start overlapping cleanup.
5. WHEN manual trigger succeeds THEN it SHALL return a run ID or run summary.
6. WHEN manual trigger fails validation THEN it SHALL return a clear validation error.
7. WHEN manual trigger is not implemented THEN scheduled maintenance and status endpoint SHALL still work.

## Requirement 15: Security and safety

### User story

As an operator, I want maintenance cleanup to be safe because it deletes data and files.

### Acceptance criteria

1. WHEN filesystem cleanup runs THEN it SHALL use path allowlists.
2. WHEN filesystem cleanup sees unsafe paths THEN it SHALL refuse deletion.
3. WHEN filesystem cleanup encounters symlinks THEN it SHALL not follow symlinks outside allowed roots.
4. WHEN maintenance logs results THEN it SHALL not log secrets, tokens, credentials, or private content.
5. WHEN maintenance status returns file information THEN it SHALL not expose sensitive absolute paths.
6. WHEN cleanup tasks delete records THEN they SHALL follow explicit retention rules.
7. WHEN cleanup tasks encounter audit/security records THEN they SHALL preserve them unless a separate explicit retention policy exists.
8. WHEN destructive cleanup behavior is changed THEN tests SHALL cover the safety rule.

## Requirement 16: Observability

### User story

As an operator, I want maintenance logs and summaries so cleanup behavior is diagnosable.

### Acceptance criteria

1. WHEN maintenance starts THEN the system SHALL log a safe start event.
2. WHEN each task starts THEN the system SHOULD log a safe task-start event.
3. WHEN each task succeeds THEN the system SHOULD log a safe task-success event with counts.
4. WHEN each task fails THEN the system SHALL log a safe task-failure event.
5. WHEN maintenance completes THEN the system SHALL log final status.
6. WHEN maintenance is skipped due to lock THEN the system SHALL log or record that skip.
7. WHEN logs include paths THEN they SHALL use safe root-relative or redacted paths.
8. WHEN logs include errors THEN they SHALL not expose secrets or stack traces in user-visible responses.

## Requirement 17: Test coverage

### User story

As a maintainer, I want automated tests for maintenance cleanup so retention and safety do not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover scheduled maintenance service execution.
2. WHEN tests run THEN they SHALL cover maintenance locking.
3. WHEN tests run THEN they SHALL cover maintenance run metadata persistence.
4. WHEN tests run THEN they SHALL cover task success and task failure isolation.
5. WHEN tests run THEN they SHALL cover dry-run mode.
6. WHEN tests run THEN they SHALL cover temp file cleanup and path safety.
7. WHEN tests run THEN they SHALL cover symlink safety where practical.
8. WHEN tests run THEN they SHALL cover stale session cleanup where applicable.
9. WHEN tests run THEN they SHALL cover old activity cleanup.
10. WHEN tests run THEN they SHALL cover scheduler runtime state cleanup if service exists.
11. WHEN tests run THEN they SHALL cover cache cleanup.
12. WHEN tests run THEN they SHALL cover backup retention delegation if backup service exists.
13. WHEN tests run THEN they SHALL cover export artifact cleanup.
14. WHEN tests run THEN they SHALL cover admin status authorization.
15. WHEN tests run THEN they SHALL cover manual trigger if implemented.
16. WHEN tests run THEN they SHALL cover safe error redaction.

## Requirement 18: Completion verification

### User story

As an operator, I want a clear verification path so maintenance cron is only considered complete when it runs safely.

### Acceptance criteria

1. WHEN maintenance runs in dry-run mode in staging THEN it SHALL report eligible cleanup counts without deleting data.
2. WHEN maintenance runs normally in staging THEN it SHALL delete only eligible temp/cache/runtime data.
3. WHEN active sessions, active activities, current exports, and newest backups exist THEN maintenance SHALL preserve them.
4. WHEN one task is forced to fail THEN maintenance SHALL record partial success and continue safe tasks.
5. WHEN maintenance status is requested by admin THEN recent run metadata SHALL be visible.
6. WHEN maintenance status is requested by non-admin THEN access SHALL be blocked.
7. WHEN maintenance is scheduled THEN it SHALL run according to configured cron.

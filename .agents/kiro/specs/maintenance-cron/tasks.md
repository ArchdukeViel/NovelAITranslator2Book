# tasks.md

# Tasks: Maintenance Cron

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing scheduler/cron/worker infrastructure.
  * [ ] 0.2 Inspect existing temp directories and worker scratch paths.
  * [ ] 0.3 Inspect session storage strategy: database, Redis, JWT-only, or hybrid.
  * [ ] 0.4 Inspect activity record model, statuses, and metadata usage.
  * [ ] 0.5 Inspect scheduler runtime state persistence service if implemented.
  * [ ] 0.6 Inspect cache storage locations and invalidation hooks.
  * [ ] 0.7 Inspect backup retention service if implemented.
  * [ ] 0.8 Inspect export artifact and manifest storage.
  * [ ] 0.9 Inspect existing admin auth/router patterns.
  * [ ] 0.10 Inspect existing tests for scheduler, activity, sessions, storage, and exports.

* [ ] 1. Define maintenance configuration

  * [ ] 1.1 Add `MAINTENANCE_ENABLED`. (REQ-1)
  * [ ] 1.2 Add `MAINTENANCE_CRON`. (REQ-1)
  * [ ] 1.3 Add `MAINTENANCE_TIMEZONE`. (REQ-1)
  * [ ] 1.4 Add `MAINTENANCE_LOCK_TTL_SECONDS`. (REQ-2)
  * [ ] 1.5 Add `MAINTENANCE_TASK_TIMEOUT_SECONDS`. (REQ-4)
  * [ ] 1.6 Add `MAINTENANCE_DRY_RUN`. (REQ-5)
  * [ ] 1.7 Add temp file retention config. (REQ-6)
  * [ ] 1.8 Add session retention config. (REQ-7)
  * [ ] 1.9 Add activity retention config. (REQ-8)
  * [ ] 1.10 Add scheduler runtime state retention config. (REQ-9)
  * [ ] 1.11 Add cache retention config. (REQ-10)
  * [ ] 1.12 Add export artifact retention config. (REQ-12)
  * [ ] 1.13 Validate maintenance config at startup or scheduler registration. (REQ-1)

* [ ] 2. Add maintenance run metadata model

  * [ ] 2.1 Create `maintenance_runs` table/model or equivalent metadata store. (REQ-3)
  * [ ] 2.2 Add status, started time, finished time, duration, trigger, and dry-run fields. (REQ-3)
  * [ ] 2.3 Add task total, task success count, task failure count, deleted item count, and deleted bytes fields. (REQ-3)
  * [ ] 2.4 Add safe error message/category fields. (REQ-3, REQ-16)
  * [ ] 2.5 Add metadata JSON for per-task results. (REQ-3)
  * [ ] 2.6 Add indexes for status, started time, and finished time. (REQ-13)
  * [ ] 2.7 Add migration tests or migration verification. (REQ-17)

* [ ] 3. Implement maintenance task result contract

  * [ ] 3.1 Define task result statuses: succeeded, failed, skipped, unavailable. (REQ-4)
  * [ ] 3.2 Define scanned count, deleted count, would-delete count, and bytes deleted fields. (REQ-3, REQ-5)
  * [ ] 3.3 Define safe warning list. (REQ-3, REQ-16)
  * [ ] 3.4 Define safe error category/message fields. (REQ-3, REQ-16)
  * [ ] 3.5 Define dry-run behavior in result object. (REQ-5)
  * [ ] 3.6 Add unit tests for result serialization. (REQ-3, REQ-17)

* [ ] 4. Implement maintenance task registry

  * [ ] 4.1 Add maintenance task interface. (REQ-4)
  * [ ] 4.2 Add task registry. (REQ-4)
  * [ ] 4.3 Register temp file cleanup task. (REQ-6)
  * [ ] 4.4 Register stale session cleanup task where applicable. (REQ-7)
  * [ ] 4.5 Register old activity cleanup task. (REQ-8)
  * [ ] 4.6 Register scheduler runtime state cleanup task if service exists. (REQ-9)
  * [ ] 4.7 Register cache cleanup task. (REQ-10)
  * [ ] 4.8 Register backup retention cleanup task if service exists. (REQ-11)
  * [ ] 4.9 Register export artifact cleanup task. (REQ-12)
  * [ ] 4.10 Add tests for enabled, disabled, missing, and unavailable tasks. (REQ-4, REQ-17)

* [ ] 5. Implement maintenance locking

  * [ ] 5.1 Choose lock strategy using existing database, Redis, or filesystem lock conventions. (REQ-2)
  * [ ] 5.2 Acquire lock before running tasks. (REQ-2)
  * [ ] 5.3 Release lock after completion. (REQ-2)
  * [ ] 5.4 Add lock TTL or stale lock recovery. (REQ-2)
  * [ ] 5.5 Record skipped run when lock is unavailable. (REQ-2)
  * [ ] 5.6 Ensure destructive cleanup does not run if lock acquisition fails unexpectedly. (REQ-2)
  * [ ] 5.7 Add tests for normal lock, skipped lock, and stale lock behavior. (REQ-2, REQ-17)

* [ ] 6. Implement maintenance service orchestration

  * [ ] 6.1 Add `run_maintenance()` service method. (REQ-1, REQ-4)
  * [ ] 6.2 Create maintenance run metadata at start. (REQ-3)
  * [ ] 6.3 Run enabled tasks in configured order. (REQ-4)
  * [ ] 6.4 Apply per-task timeout if supported. (REQ-4)
  * [ ] 6.5 Continue safe tasks after non-critical task failure. (REQ-4)
  * [ ] 6.6 Aggregate task results into run metadata. (REQ-3)
  * [ ] 6.7 Mark run succeeded, partially succeeded, failed, or skipped. (REQ-1, REQ-4)
  * [ ] 6.8 Persist final run metadata. (REQ-3)
  * [ ] 6.9 Add orchestration tests for all-success, partial-failure, all-failure, and skipped-lock runs. (REQ-1, REQ-4, REQ-17)

* [ ] 7. Implement dry-run support

  * [ ] 7.1 Add dry-run flag to maintenance context. (REQ-5)
  * [ ] 7.2 Ensure filesystem tasks do not delete in dry-run mode. (REQ-5)
  * [ ] 7.3 Ensure database tasks do not delete in dry-run mode. (REQ-5)
  * [ ] 7.4 Ensure backup/export cleanup does not delete in dry-run mode. (REQ-5)
  * [ ] 7.5 Record would-delete counts. (REQ-5)
  * [ ] 7.6 Add tests for dry-run behavior in each destructive task. (REQ-5, REQ-17)

* [ ] 8. Implement filesystem cleanup safety helpers

  * [ ] 8.1 Add allowlisted cleanup root validation. (REQ-6, REQ-15)
  * [ ] 8.2 Reject empty paths. (REQ-6, REQ-15)
  * [ ] 8.3 Reject filesystem root paths. (REQ-6, REQ-15)
  * [ ] 8.4 Reject project root unless explicitly configured. (REQ-6, REQ-15)
  * [ ] 8.5 Prevent following symlinks outside allowed roots. (REQ-6, REQ-15)
  * [ ] 8.6 Use safe root-relative path logging where needed. (REQ-15, REQ-16)
  * [ ] 8.7 Add tests for path allowlist, unsafe root, symlink escape, and safe path behavior. (REQ-6, REQ-15, REQ-17)

* [ ] 9. Implement temp file cleanup task

  * [ ] 9.1 Identify configured temp and scratch roots. (REQ-6)
  * [ ] 9.2 Scan files older than temp retention. (REQ-6)
  * [ ] 9.3 Delete eligible files in normal mode. (REQ-6)
  * [ ] 9.4 Report would-delete files in dry-run mode. (REQ-5, REQ-6)
  * [ ] 9.5 Delete empty directories inside allowlisted roots where safe. (REQ-6)
  * [ ] 9.6 Preserve newer files. (REQ-6)
  * [ ] 9.7 Continue after individual file deletion warnings where safe. (REQ-6)
  * [ ] 9.8 Add tests for eligible deletion, preservation, empty directory cleanup, dry-run, and file error handling. (REQ-6, REQ-17)

* [ ] 10. Implement stale session cleanup task

  * [ ] 10.1 Detect session storage mode. (REQ-7)
  * [ ] 10.2 For database sessions, delete expired sessions. (REQ-7)
  * [ ] 10.3 For Redis sessions, use existing session key expiration or cleanup stale metadata where applicable. (REQ-7)
  * [ ] 10.4 For JWT-only mode, cleanup token revocation records if present. (REQ-7)
  * [ ] 10.5 Preserve active/unexpired sessions. (REQ-7)
  * [ ] 10.6 Remove disabled-user sessions where supported. (REQ-7)
  * [ ] 10.7 Ensure tokens are not logged. (REQ-7, REQ-15)
  * [ ] 10.8 Add tests for expired, active, revoked, disabled-user, and JWT-only behavior where applicable. (REQ-7, REQ-17)

* [ ] 11. Implement old activity cleanup task

  * [ ] 11.1 Define cleanup-eligible terminal activity statuses. (REQ-8)
  * [ ] 11.2 Define statuses that must never be deleted while active. (REQ-8)
  * [ ] 11.3 Delete completed successful activities older than retention. (REQ-8)
  * [ ] 11.4 Delete failed activities older than failed-retention. (REQ-8)
  * [ ] 11.5 Preserve running/queued/active activities. (REQ-8)
  * [ ] 11.6 Preserve activities referenced by active jobs. (REQ-8)
  * [ ] 11.7 Preserve audit/security records. (REQ-8, REQ-15)
  * [ ] 11.8 Add dry-run support. (REQ-5, REQ-8)
  * [ ] 11.9 Add tests for eligible old activities, active preservation, failed retention, references, and dry-run. (REQ-8, REQ-17)

* [ ] 12. Implement scheduler runtime state cleanup task

  * [ ] 12.1 Detect scheduler runtime state cleanup service. (REQ-9)
  * [ ] 12.2 Call existing cleanup method if available. (REQ-9)
  * [ ] 12.3 Preserve active failed/cooldown/running/disabled/stale states. (REQ-9)
  * [ ] 12.4 Delete expired idle/recovered states. (REQ-9)
  * [ ] 12.5 Return unavailable/skipped result if service does not exist. (REQ-9)
  * [ ] 12.6 Add dry-run support if service supports it. (REQ-5, REQ-9)
  * [ ] 12.7 Add tests for preservation, deletion, unavailable service, and dry-run. (REQ-9, REQ-17)

* [ ] 13. Implement cache cleanup task

  * [ ] 13.1 Identify filesystem cache roots. (REQ-10)
  * [ ] 13.2 Identify database cache tables, if any. (REQ-10)
  * [ ] 13.3 Identify in-memory cache invalidation hooks, if any. (REQ-10)
  * [ ] 13.4 Delete expired cache entries only. (REQ-10)
  * [ ] 13.5 Preserve durable public snapshots and non-cache artifacts. (REQ-10)
  * [ ] 13.6 Apply filesystem path safety rules. (REQ-10, REQ-15)
  * [ ] 13.7 Add dry-run support. (REQ-5, REQ-10)
  * [ ] 13.8 Add tests for expired cache deletion, durable artifact preservation, invalidation hook, and dry-run. (REQ-10, REQ-17)

* [ ] 14. Implement backup retention delegation task

  * [ ] 14.1 Detect backup retention service. (REQ-11)
  * [ ] 14.2 Delegate retention cleanup to backup service when available. (REQ-11)
  * [ ] 14.3 Ensure newest successful backup is preserved by backup service. (REQ-11)
  * [ ] 14.4 Ensure minimum successful backup count is preserved by backup service. (REQ-11)
  * [ ] 14.5 Support local and offsite cleanup through backup service. (REQ-11)
  * [ ] 14.6 Return skipped/unavailable when backup service is absent. (REQ-11)
  * [ ] 14.7 Add dry-run support if backup service supports it. (REQ-5, REQ-11)
  * [ ] 14.8 Add tests using fake backup service for success, failure, unavailable, and dry-run. (REQ-11, REQ-17)

* [ ] 15. Implement export artifact cleanup task

  * [ ] 15.1 Identify export temporary directories. (REQ-12)
  * [ ] 15.2 Identify failed export artifact locations. (REQ-12)
  * [ ] 15.3 Identify manifest-referenced current artifacts. (REQ-12)
  * [ ] 15.4 Delete stale export temp directories. (REQ-12)
  * [ ] 15.5 Delete old failed export artifacts. (REQ-12)
  * [ ] 15.6 Delete orphaned artifacts older than orphan retention. (REQ-12)
  * [ ] 15.7 Preserve current manifest-referenced exports. (REQ-12)
  * [ ] 15.8 Preserve artifacts currently being generated. (REQ-12)
  * [ ] 15.9 Add dry-run support. (REQ-5, REQ-12)
  * [ ] 15.10 Add tests for temp deletion, failed artifact deletion, orphan deletion, manifest preservation, active generation preservation, and dry-run. (REQ-12, REQ-17)

* [ ] 16. Register scheduled maintenance job

  * [ ] 16.1 Register maintenance cron with existing scheduler. (REQ-1)
  * [ ] 16.2 Respect `MAINTENANCE_ENABLED`. (REQ-1)
  * [ ] 16.3 Use configured cron schedule and timezone. (REQ-1)
  * [ ] 16.4 Ensure scheduled runs use normal non-dry-run mode unless configured otherwise. (REQ-5)
  * [ ] 16.5 Ensure scheduler errors are logged safely. (REQ-16)
  * [ ] 16.6 Add tests or integration checks for job registration. (REQ-1, REQ-17)

* [ ] 17. Add admin maintenance status endpoint

  * [ ] 17.1 Add `GET /admin/maintenance/status`. (REQ-13)
  * [ ] 17.2 Protect endpoint with admin auth. (REQ-13)
  * [ ] 17.3 Return enabled state and schedule. (REQ-13)
  * [ ] 17.4 Return last run and last success timestamps. (REQ-13)
  * [ ] 17.5 Return recent run summaries. (REQ-13)
  * [ ] 17.6 Return safe task failure summaries. (REQ-13, REQ-15)
  * [ ] 17.7 Add API tests for admin, non-admin, unauthenticated, no-runs, success, failure, and partial success states. (REQ-13, REQ-17)

* [ ] 18. Add optional manual maintenance trigger

  * [ ] 18.1 Add `POST /admin/maintenance/run` if manual trigger is in scope. (REQ-14)
  * [ ] 18.2 Protect endpoint with admin auth. (REQ-14)
  * [ ] 18.3 Support dry-run request option. (REQ-14)
  * [ ] 18.4 Support optional task key subset. (REQ-14)
  * [ ] 18.5 Validate requested task keys. (REQ-14)
  * [ ] 18.6 Use same maintenance lock. (REQ-14)
  * [ ] 18.7 Return run ID or run summary. (REQ-14)
  * [ ] 18.8 Add tests for admin trigger, non-admin block, dry-run, task subset, invalid task, and lock conflict. (REQ-14, REQ-17)

* [ ] 19. Add observability logs

  * [ ] 19.1 Log `maintenance.started`. (REQ-16)
  * [ ] 19.2 Log `maintenance.task_started`. (REQ-16)
  * [ ] 19.3 Log `maintenance.task_succeeded`. (REQ-16)
  * [ ] 19.4 Log `maintenance.task_failed`. (REQ-16)
  * [ ] 19.5 Log final maintenance status. (REQ-16)
  * [ ] 19.6 Log skipped lock state. (REQ-16)
  * [ ] 19.7 Redact secrets and unsafe paths from logs. (REQ-15, REQ-16)
  * [ ] 19.8 Add log tests only where project conventions support them. (REQ-16, REQ-17)

* [ ] 20. Security and safety review

  * [ ] 20.1 Verify all destructive filesystem tasks use allowlisted roots. (REQ-15)
  * [ ] 20.2 Verify unsafe root/project paths are rejected. (REQ-15)
  * [ ] 20.3 Verify symlink escape behavior is safe. (REQ-15)
  * [ ] 20.4 Verify active records are preserved. (REQ-8, REQ-15)
  * [ ] 20.5 Verify newest/minimum backups are preserved through backup service. (REQ-11, REQ-15)
  * [ ] 20.6 Verify audit/security records are not deleted. (REQ-8, REQ-15)
  * [ ] 20.7 Verify admin endpoints do not expose secrets or sensitive paths. (REQ-13, REQ-15)
  * [ ] 20.8 Add missing safety tests before enabling scheduled cleanup. (REQ-15, REQ-17)

* [ ] 21. Documentation

  * [ ] 21.1 Document maintenance schedule configuration. (REQ-1)
  * [ ] 21.2 Document each maintenance task and retention policy. (REQ-4 through REQ-12)
  * [ ] 21.3 Document dry-run mode. (REQ-5)
  * [ ] 21.4 Document path safety and allowlisted cleanup roots. (REQ-6, REQ-15)
  * [ ] 21.5 Document admin maintenance status endpoint. (REQ-13)
  * [ ] 21.6 Document manual trigger if implemented. (REQ-14)
  * [ ] 21.7 Document staging verification procedure. (REQ-18)

* [ ] 22. Test coverage pass

  * [ ] 22.1 Add maintenance scheduling tests. (REQ-1, REQ-17)
  * [ ] 22.2 Add lock tests. (REQ-2, REQ-17)
  * [ ] 22.3 Add run metadata tests. (REQ-3, REQ-17)
  * [ ] 22.4 Add task registry/isolation tests. (REQ-4, REQ-17)
  * [ ] 22.5 Add dry-run tests. (REQ-5, REQ-17)
  * [ ] 22.6 Add temp cleanup and path safety tests. (REQ-6, REQ-15, REQ-17)
  * [ ] 22.7 Add stale session cleanup tests where applicable. (REQ-7, REQ-17)
  * [ ] 22.8 Add activity cleanup tests. (REQ-8, REQ-17)
  * [ ] 22.9 Add scheduler runtime state cleanup tests if applicable. (REQ-9, REQ-17)
  * [ ] 22.10 Add cache cleanup tests. (REQ-10, REQ-17)
  * [ ] 22.11 Add backup retention delegation tests if applicable. (REQ-11, REQ-17)
  * [ ] 22.12 Add export artifact cleanup tests. (REQ-12, REQ-17)
  * [ ] 22.13 Add admin status tests. (REQ-13, REQ-17)
  * [ ] 22.14 Add manual trigger tests if implemented. (REQ-14, REQ-17)
  * [ ] 22.15 Add redaction/safe error tests. (REQ-15, REQ-17)

* [ ] 23. Completion verification

  * [ ] 23.1 Run maintenance in dry-run mode in staging. (REQ-18)
  * [ ] 23.2 Verify dry-run reports eligible items without deleting them. (REQ-5, REQ-18)
  * [ ] 23.3 Run maintenance normally against controlled stale temp/cache data. (REQ-18)
  * [ ] 23.4 Verify eligible temp files are deleted. (REQ-6, REQ-18)
  * [ ] 23.5 Verify active sessions are preserved. (REQ-7, REQ-18)
  * [ ] 23.6 Verify active/running activities are preserved. (REQ-8, REQ-18)
  * [ ] 23.7 Verify active scheduler runtime states are preserved. (REQ-9, REQ-18)
  * [ ] 23.8 Verify current export manifest artifacts are preserved. (REQ-12, REQ-18)
  * [ ] 23.9 Verify newest successful backup is preserved if backup cleanup is enabled. (REQ-11, REQ-18)
  * [ ] 23.10 Force one task failure and verify partial success behavior. (REQ-4, REQ-18)
  * [ ] 23.11 Verify admin maintenance status shows recent run. (REQ-13, REQ-18)
  * [ ] 23.12 Verify non-admin cannot access maintenance status. (REQ-13, REQ-18)
  * [ ] 23.13 Enable scheduled maintenance and verify it runs according to cron. (REQ-1, REQ-18)
  * [ ] 23.14 Mark `maintenance-cron` complete only after dry-run and normal controlled cleanup verification pass.

# tasks.md

# Tasks: Scheduled Backups and Restore Drills

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing scheduler/worker system and recurring job registration pattern.
  * [ ] 0.2 Inspect existing database engine support, migration tooling, and database connection configuration.
  * [ ] 0.3 Inspect existing storage paths for uploads, generated files, public reader artifacts, exports, temp files, and caches.
  * [ ] 0.4 Inspect existing admin auth guard and admin router conventions.
  * [ ] 0.5 Inspect existing health/status endpoint patterns.
  * [ ] 0.6 Inspect existing settings/config pattern and environment variable loading.
  * [ ] 0.7 Inspect existing logging, structured errors, and alert/notification hooks if any.
  * [ ] 0.8 Inspect existing tests for scheduler jobs, storage services, and admin endpoints.

* [ ] 1. Define backup configuration

  * [ ] 1.1 Add `BACKUP_ENABLED`. (REQ-1)
  * [ ] 1.2 Add `BACKUP_SCHEDULE_CRON` and `BACKUP_TIMEZONE`. (REQ-1, REQ-2)
  * [ ] 1.3 Add `BACKUP_LOCAL_DIR`. (REQ-1)
  * [ ] 1.4 Add `BACKUP_RETENTION_DAYS`, `BACKUP_FAILED_RETENTION_DAYS`, and `BACKUP_MIN_SUCCESSFUL_TO_KEEP`. (REQ-1, REQ-7)
  * [ ] 1.5 Add `BACKUP_MIN_SUCCESS_INTERVAL_HOURS` for stale detection. (REQ-9)
  * [ ] 1.6 Add database backup enable/config options if needed. (REQ-3)
  * [ ] 1.7 Add storage backup paths and exclude patterns. (REQ-4, REQ-12)
  * [ ] 1.8 Add S3/offsite configuration keys. (REQ-6)
  * [ ] 1.9 Add restore drill configuration. (REQ-10)
  * [ ] 1.10 Validate required backup settings at startup or scheduler execution. (REQ-1)

* [ ] 2. Add backup metadata model and migration

  * [ ] 2.1 Create `backup_runs` table/model or equivalent durable metadata store. (REQ-2, REQ-8)
  * [ ] 2.2 Add fields for backup ID, type, status, timestamps, duration, artifact locations, size, checksum, and manifest. (REQ-2, REQ-5)
  * [ ] 2.3 Add fields for error category and safe error message. (REQ-2, REQ-9)
  * [ ] 2.4 Add fields for restore verification status, timestamp, and error. (REQ-10)
  * [ ] 2.5 Add indexes for status, started time, finished time, and backup ID. (REQ-8)
  * [ ] 2.6 Add migration tests or migration verification. (REQ-13)

* [ ] 3. Define backup status and error contracts

  * [ ] 3.1 Define backup run statuses: `queued`, `running`, `succeeded`, `failed`, `partially_succeeded`, `verification_running`, `verification_succeeded`, `verification_failed`. (REQ-2, REQ-10)
  * [ ] 3.2 Define error categories for database, storage, compression, checksum, local write, offsite upload, retention, restore, lock, and unknown failures. (REQ-2, REQ-9)
  * [ ] 3.3 Define admin backup status response model. (REQ-8)
  * [ ] 3.4 Define backup run summary response model. (REQ-8)
  * [ ] 3.5 Define manual backup trigger response model if implemented. (REQ-11)
  * [ ] 3.6 Define manual restore verification response model if implemented. (REQ-11)

* [ ] 4. Implement backup locking

  * [ ] 4.1 Choose lock strategy using database, Redis, or filesystem based on existing infrastructure. (REQ-2)
  * [ ] 4.2 Add lock acquisition before backup execution. (REQ-2)
  * [ ] 4.3 Add lock release on success, failure, and exception paths. (REQ-2)
  * [ ] 4.4 Prevent overlapping scheduled and manual backups. (REQ-2, REQ-11)
  * [ ] 4.5 Add tests for already-running backup behavior. (REQ-2, REQ-13)

* [ ] 5. Implement database backup service

  * [ ] 5.1 Detect or configure database engine. (REQ-3)
  * [ ] 5.2 Implement database dump for the supported production database. (REQ-3)
  * [ ] 5.3 Implement SQLite backup support if SQLite is a supported deployment mode. (REQ-3)
  * [ ] 5.4 Store database dump inside the backup working directory. (REQ-3, REQ-5)
  * [ ] 5.5 Capture safe error category and message on database backup failure. (REQ-3, REQ-9)
  * [ ] 5.6 Ensure database credentials are redacted from logs and metadata. (REQ-3, REQ-12)
  * [ ] 5.7 Add tests for successful database backup and database backup failure. (REQ-3, REQ-13)

* [ ] 6. Implement storage backup service

  * [ ] 6.1 Resolve configured persistent storage paths. (REQ-4)
  * [ ] 6.2 Apply exclude patterns for temp, cache, lock, and secret paths. (REQ-4, REQ-12)
  * [ ] 6.3 Copy storage files into the backup working directory while preserving relative paths. (REQ-4)
  * [ ] 6.4 Count included files and total bytes where practical. (REQ-4, REQ-5)
  * [ ] 6.5 Fail or warn on missing required storage paths according to config. (REQ-4)
  * [ ] 6.6 Capture safe error category and message on storage backup failure. (REQ-4, REQ-9)
  * [ ] 6.7 Add tests for successful storage backup, excluded files, missing paths, and unreadable file behavior. (REQ-4, REQ-13)

* [ ] 7. Implement manifest and checksum generation

  * [ ] 7.1 Generate `manifest.json` for each backup run. (REQ-5)
  * [ ] 7.2 Include backup ID, type, status, timestamps, app version when available, database metadata, storage metadata, and artifact metadata. (REQ-5)
  * [ ] 7.3 Generate SHA-256 checksum for the final backup artifact. (REQ-5)
  * [ ] 7.4 Store checksum in backup metadata. (REQ-5)
  * [ ] 7.5 Add checksum file or manifest checksum entry. (REQ-5)
  * [ ] 7.6 Add tests for manifest contents and checksum validation. (REQ-5, REQ-13)

* [ ] 8. Implement local backup artifact writer

  * [ ] 8.1 Create backup working directory per run. (REQ-2, REQ-5)
  * [ ] 8.2 Compress backup bundle into final artifact. (REQ-5)
  * [ ] 8.3 Write final artifact to configured local backup directory. (REQ-1, REQ-2)
  * [ ] 8.4 Record local path, size, and checksum in metadata. (REQ-2, REQ-5)
  * [ ] 8.5 Clean temporary working directory after success or failure where safe. (REQ-10)
  * [ ] 8.6 Add tests for local artifact creation and local write failure. (REQ-2, REQ-13)

* [ ] 9. Implement S3/offsite backup target

  * [ ] 9.1 Add S3-compatible client wrapper or adapter. (REQ-6)
  * [ ] 9.2 Upload final backup artifact to configured bucket/prefix. (REQ-6)
  * [ ] 9.3 Record offsite URI or object key in metadata. (REQ-6)
  * [ ] 9.4 Redact credentials from logs, metadata, and API responses. (REQ-6, REQ-12)
  * [ ] 9.5 Handle offsite upload failure without deleting successful local artifact. (REQ-6)
  * [ ] 9.6 Mark local-success/offsite-failure as `partially_succeeded` or failed according to policy. (REQ-2, REQ-6)
  * [ ] 9.7 Add tests using a fake S3 adapter for upload success and failure. (REQ-6, REQ-13)

* [ ] 10. Implement backup orchestration service

  * [ ] 10.1 Add high-level `run_backup()` service method. (REQ-2)
  * [ ] 10.2 Create metadata record at backup start. (REQ-2)
  * [ ] 10.3 Run database backup step. (REQ-3)
  * [ ] 10.4 Run storage backup step. (REQ-4)
  * [ ] 10.5 Generate manifest and checksum. (REQ-5)
  * [ ] 10.6 Write local artifact. (REQ-2)
  * [ ] 10.7 Upload offsite artifact when enabled. (REQ-6)
  * [ ] 10.8 Update metadata with final status. (REQ-2)
  * [ ] 10.9 Handle exceptions and mark run failed with safe error metadata. (REQ-2, REQ-9)
  * [ ] 10.10 Add orchestration tests for success, failure, and partial success. (REQ-13)

* [ ] 11. Register scheduled backup job

  * [ ] 11.1 Register recurring backup job with existing scheduler. (REQ-2)
  * [ ] 11.2 Respect `BACKUP_ENABLED`. (REQ-1, REQ-2)
  * [ ] 11.3 Use configured cron schedule and timezone. (REQ-1, REQ-2)
  * [ ] 11.4 Ensure scheduler errors are logged safely. (REQ-9, REQ-12)
  * [ ] 11.5 Ensure job does not overlap with manual backups. (REQ-2, REQ-11)
  * [ ] 11.6 Add tests or integration checks for scheduled job registration. (REQ-13)

* [ ] 12. Implement retention cleanup

  * [ ] 12.1 Add retention service for local backup artifacts. (REQ-7)
  * [ ] 12.2 Add retention service for offsite artifacts when enabled. (REQ-7)
  * [ ] 12.3 Preserve newest successful backup. (REQ-7)
  * [ ] 12.4 Preserve configured minimum number of successful backups. (REQ-7)
  * [ ] 12.5 Apply failed backup metadata retention. (REQ-7)
  * [ ] 12.6 Record retention cleanup failures without corrupting latest successful backup status. (REQ-7, REQ-9)
  * [ ] 12.7 Run retention cleanup after backup completion. (REQ-7)
  * [ ] 12.8 Add tests for retention deletion, minimum keep count, newest backup preservation, and deletion failure. (REQ-7, REQ-13)

* [ ] 13. Implement backup status service

  * [ ] 13.1 Query latest backup run. (REQ-8)
  * [ ] 13.2 Query latest successful backup. (REQ-8, REQ-9)
  * [ ] 13.3 Query latest restore verification status. (REQ-8, REQ-10)
  * [ ] 13.4 Compute stale state using configured maximum success interval. (REQ-9)
  * [ ] 13.5 Compute healthy/degraded/unhealthy backup state for health integration. (REQ-9)
  * [ ] 13.6 Return offsite enabled/upload status without secrets. (REQ-6, REQ-8, REQ-12)
  * [ ] 13.7 Add tests for no backup, fresh backup, stale backup, failed backup, partial backup, and failed verification. (REQ-8, REQ-9, REQ-13)

* [ ] 14. Add admin backup API endpoints

  * [ ] 14.1 Add `GET /admin/backups/status`. (REQ-8)
  * [ ] 14.2 Add `GET /admin/backups` for recent run list if needed. (REQ-8)
  * [ ] 14.3 Add `GET /admin/backups/{backup_id}` for run detail if needed. (REQ-8)
  * [ ] 14.4 Add `POST /admin/backups/run` for manual backup if implemented. (REQ-11)
  * [ ] 14.5 Add `POST /admin/backups/{backup_id}/verify-restore` for manual restore verification if implemented. (REQ-11)
  * [ ] 14.6 Protect all backup endpoints with admin auth. (REQ-8, REQ-11)
  * [ ] 14.7 Add API tests for admin, non-admin, and unauthenticated access. (REQ-8, REQ-13)

* [ ] 15. Implement stale/failed backup alerts

  * [ ] 15.1 Add stale backup detection helper. (REQ-9)
  * [ ] 15.2 Add failed backup detection helper. (REQ-9)
  * [ ] 15.3 Add offsite upload failure detection. (REQ-9)
  * [ ] 15.4 Add restore verification failure detection. (REQ-9)
  * [ ] 15.5 Emit structured logs for stale or failed backup states. (REQ-9)
  * [ ] 15.6 Add alert event hook if existing notification/alert infrastructure exists. (REQ-9)
  * [ ] 15.7 Expose alert state through status service for future health checks. (REQ-9)
  * [ ] 15.8 Add tests for stale, failed, partial, and verification-failed alert states. (REQ-9, REQ-13)

* [ ] 16. Implement restore verification service

  * [ ] 16.1 Select latest successful backup or requested backup ID. (REQ-10)
  * [ ] 16.2 Download from offsite target if local artifact is missing and offsite is available. (REQ-10)
  * [ ] 16.3 Verify checksum before extraction. (REQ-5, REQ-10)
  * [ ] 16.4 Extract backup artifact into isolated temporary directory. (REQ-10)
  * [ ] 16.5 Parse and validate manifest. (REQ-5, REQ-10)
  * [ ] 16.6 Restore database dump into isolated verification target. (REQ-3, REQ-10)
  * [ ] 16.7 Restore storage files into isolated verification directory. (REQ-4, REQ-10)
  * [ ] 16.8 Run integrity checks for required tables and basic counts. (REQ-10)
  * [ ] 16.9 Record verification success or failure in backup metadata. (REQ-10)
  * [ ] 16.10 Clean temporary restore resources where safe. (REQ-10)
  * [ ] 16.11 Add tests for verification success, checksum failure, manifest failure, database restore failure, storage restore failure, and cleanup. (REQ-10, REQ-13)

* [ ] 17. Register scheduled restore drill

  * [ ] 17.1 Add optional recurring restore drill job. (REQ-10)
  * [ ] 17.2 Respect restore drill enabled flag. (REQ-10)
  * [ ] 17.3 Use configured restore drill schedule. (REQ-10)
  * [ ] 17.4 Ensure restore drill never targets production database or production storage. (REQ-10)
  * [ ] 17.5 Add logs/status for restore drill result. (REQ-9, REQ-10)
  * [ ] 17.6 Add tests or integration checks for restore drill job registration. (REQ-10, REQ-13)

* [ ] 18. Security and redaction hardening

  * [ ] 18.1 Exclude `.env` and configured secret paths from storage backup. (REQ-12)
  * [ ] 18.2 Redact database credentials from command errors and logs. (REQ-12)
  * [ ] 18.3 Redact S3 credentials from config errors, logs, and API responses. (REQ-12)
  * [ ] 18.4 Ensure admin status endpoint does not expose local filesystem paths unless project convention allows admin-only paths. (REQ-8, REQ-12)
  * [ ] 18.5 Verify backup directory permission recommendation is documented. (REQ-12)
  * [ ] 18.6 Add tests for secret exclusion and response redaction where practical. (REQ-12, REQ-13)

* [ ] 19. Documentation

  * [ ] 19.1 Document backup configuration variables. (REQ-1, REQ-14)
  * [ ] 19.2 Document local backup setup. (REQ-1, REQ-14)
  * [ ] 19.3 Document S3-compatible/offsite setup. (REQ-6, REQ-14)
  * [ ] 19.4 Document retention policy. (REQ-7, REQ-14)
  * [ ] 19.5 Document manual backup procedure. (REQ-11, REQ-14)
  * [ ] 19.6 Document restore drill procedure. (REQ-10, REQ-14)
  * [ ] 19.7 Document backup artifact sensitivity and secret handling. (REQ-12, REQ-14)
  * [ ] 19.8 Add V1 launch checklist entries. (REQ-14)

* [ ] 20. Test coverage pass

  * [ ] 20.1 Add unit tests for backup config validation. (REQ-1, REQ-13)
  * [ ] 20.2 Add unit tests for database backup service. (REQ-3, REQ-13)
  * [ ] 20.3 Add unit tests for storage backup service. (REQ-4, REQ-13)
  * [ ] 20.4 Add unit tests for manifest/checksum generation. (REQ-5, REQ-13)
  * [ ] 20.5 Add unit tests for S3 adapter using fake client. (REQ-6, REQ-13)
  * [ ] 20.6 Add unit tests for retention cleanup. (REQ-7, REQ-13)
  * [ ] 20.7 Add API tests for backup status endpoint. (REQ-8, REQ-13)
  * [ ] 20.8 Add tests for stale/failed detection. (REQ-9, REQ-13)
  * [ ] 20.9 Add restore verification tests. (REQ-10, REQ-13)
  * [ ] 20.10 Add lock/concurrency tests. (REQ-2, REQ-13)
  * [ ] 20.11 Add redaction/security tests where practical. (REQ-12, REQ-13)

* [ ] 21. Release verification

  * [ ] 21.1 Run migrations from a clean database. (REQ-14)
  * [ ] 21.2 Configure local backup target in staging. (REQ-14)
  * [ ] 21.3 Configure S3/offsite target in staging or document launch exception. (REQ-6, REQ-14)
  * [ ] 21.4 Trigger a manual backup. (REQ-11, REQ-14)
  * [ ] 21.5 Verify backup metadata shows success. (REQ-8, REQ-14)
  * [ ] 21.6 Verify backup artifact exists locally. (REQ-2, REQ-14)
  * [ ] 21.7 Verify backup artifact exists offsite if enabled. (REQ-6, REQ-14)
  * [ ] 21.8 Run restore verification against the latest backup. (REQ-10, REQ-14)
  * [ ] 21.9 Verify restore verification status is successful. (REQ-10, REQ-14)
  * [ ] 21.10 Verify stale backup detection by using test configuration or controlled metadata. (REQ-9, REQ-14)
  * [ ] 21.11 Verify failed backup status using a controlled failure. (REQ-9, REQ-14)
  * [ ] 21.12 Verify retention cleanup does not delete the newest successful backup. (REQ-7, REQ-14)
  * [ ] 21.13 Mark `scheduled-backups-and-restore-drills` launch blocker complete only after successful backup and restore drill verification.

# requirements.md

# Requirements: Scheduled Backups and Restore Drills

## Introduction

The application needs scheduled backups and restore verification before V1 launch. Operators must be able to rely on automated backups, confirm that recent backups exist, retain them according to policy, store offsite copies, and verify that backups can be restored.

## Requirement 1: Backup configuration

### User story

As an operator, I want backup behavior to be configurable so that each deployment can choose schedule, retention, and storage targets safely.

### Acceptance criteria

1. WHEN backups are enabled THEN the system SHALL run backups according to configured schedule.
2. WHEN backups are disabled THEN the system SHALL not run scheduled backups.
3. WHEN local backup directory is configured THEN the system SHALL write backup artifacts to that directory.
4. WHEN S3/offsite backup is enabled THEN the system SHALL require bucket/target configuration.
5. WHEN required backup configuration is missing THEN the system SHALL fail safely and expose a configuration error.
6. WHEN backup credentials are configured THEN the system SHALL not expose them in API responses or logs.
7. WHEN retention settings are configured THEN the system SHALL apply them during cleanup.
8. WHEN configuration is invalid THEN the system SHALL surface a clear startup, scheduler, or status error.

## Requirement 2: Scheduled backup execution

### User story

As an operator, I want backups to run automatically so that recovery does not depend on manual intervention.

### Acceptance criteria

1. WHEN the configured backup schedule is reached THEN the system SHALL start a backup run.
2. WHEN a backup starts THEN the system SHALL create a backup metadata record with `running` status.
3. WHEN a backup succeeds THEN the system SHALL mark the backup metadata as `succeeded`.
4. WHEN a backup fails THEN the system SHALL mark the backup metadata as `failed` and store a safe failure reason.
5. WHEN local backup succeeds but offsite upload fails THEN the system SHALL mark the run as `partially_succeeded` or failed according to configured policy.
6. WHEN a backup is already running THEN the system SHALL prevent overlapping backup execution.
7. WHEN the scheduler skips a run due to an existing lock THEN the system SHALL log or record the skipped condition.
8. WHEN a backup completes THEN the system SHALL record start time, finish time, duration, size when available, and checksum when available.

## Requirement 3: Database backup

### User story

As an operator, I want database data included in backups so that core application state can be restored.

### Acceptance criteria

1. WHEN database backup is enabled THEN the system SHALL create a database dump or equivalent backup artifact.
2. WHEN the database backup succeeds THEN the backup manifest SHALL include database backup metadata.
3. WHEN the database backup fails THEN the backup run SHALL fail unless configured as a storage-only backup.
4. WHEN database backup fails THEN the system SHALL record an error category and safe error message.
5. WHEN database credentials are used for backup THEN they SHALL not be written to backup metadata, manifest, API responses, or logs.
6. WHEN multiple database engines are supported by the app THEN the backup implementation SHALL use the correct strategy for the configured engine.
7. WHEN restore verification runs THEN the database backup SHALL be restorable into an isolated verification target.

## Requirement 4: Storage backup

### User story

As an operator, I want persistent storage included in backups so that uploaded, generated, and required reader/export files can be recovered.

### Acceptance criteria

1. WHEN storage backup is enabled THEN the system SHALL include configured persistent storage paths in the backup artifact.
2. WHEN storage files are backed up THEN relative paths SHALL be preserved.
3. WHEN storage files are backed up THEN configured temporary/cache paths SHALL be excluded.
4. WHEN required storage paths are missing THEN the system SHALL fail or warn according to configuration.
5. WHEN unreadable required files are encountered THEN the system SHALL record a clear failure.
6. WHEN storage backup succeeds THEN the manifest SHALL include storage metadata such as included paths and file count.
7. WHEN restore verification runs THEN storage artifacts SHALL be extractable into an isolated verification directory.

## Requirement 5: Backup artifact manifest and checksums

### User story

As an operator, I want backup artifacts to include manifests and checksums so that backup contents can be inspected and validated.

### Acceptance criteria

1. WHEN a backup artifact is created THEN it SHALL include a manifest.
2. WHEN a backup artifact is created THEN it SHALL include or be associated with a checksum.
3. WHEN the manifest is created THEN it SHALL include backup ID, type, status, timestamps, included sources, artifact locations, and restore verification status.
4. WHEN checksum generation fails THEN the backup run SHALL fail or be marked with a clear error.
5. WHEN restore verification starts THEN the system SHALL verify artifact checksum before restore.
6. WHEN checksum verification fails THEN restore verification SHALL fail safely without restoring.
7. WHEN manifest parsing fails THEN restore verification SHALL fail safely.

## Requirement 6: Offsite/S3-compatible backup target

### User story

As an operator, I want backups copied to an offsite/S3-compatible target so that data can survive local disk loss.

### Acceptance criteria

1. WHEN offsite backup is enabled THEN the system SHALL upload backup artifacts to the configured S3-compatible target.
2. WHEN offsite upload succeeds THEN the backup metadata SHALL include the offsite URI or object key.
3. WHEN offsite upload fails THEN the system SHALL record `offsite_upload_failed` or equivalent error category.
4. WHEN offsite upload fails after local backup succeeds THEN the system SHALL not delete the successful local artifact.
5. WHEN offsite upload credentials are invalid THEN the system SHALL fail safely and expose a safe error.
6. WHEN offsite backup is disabled THEN the system SHALL not require S3 credentials.
7. WHEN backup status is requested THEN the system SHALL indicate whether offsite backup is enabled and whether the latest run uploaded successfully.

## Requirement 7: Retention cleanup

### User story

As an operator, I want old backups cleaned up automatically so that backup storage does not grow forever.

### Acceptance criteria

1. WHEN retention cleanup runs THEN the system SHALL delete backup artifacts older than configured retention policy.
2. WHEN retention cleanup runs THEN the system SHALL preserve at least the configured minimum number of successful backups.
3. WHEN retention cleanup runs THEN the system SHALL never delete the newest successful backup.
4. WHEN retention cleanup deletes local artifacts THEN it SHALL update or retain metadata according to project conventions.
5. WHEN offsite backup is enabled THEN retention cleanup SHALL attempt to delete expired offsite artifacts.
6. WHEN offsite deletion fails THEN the system SHALL record a retention cleanup warning or failure.
7. WHEN failed backup metadata is older than failed-retention policy THEN the system MAY delete or archive the metadata according to configuration.
8. WHEN retention cleanup fails THEN the latest successful backup SHALL not be marked as failed.

## Requirement 8: Backup status endpoint

### User story

As an admin, I want to view backup status so that I can confirm whether the system is protected.

### Acceptance criteria

1. WHEN an admin calls the backup status endpoint THEN the system SHALL return current backup configuration summary and recent backup state.
2. WHEN a non-admin calls the backup status endpoint THEN the system SHALL return `403 Forbidden`.
3. WHEN an unauthenticated user calls the backup status endpoint THEN the system SHALL return `401 Unauthorized`.
4. WHEN no successful backup exists THEN the status response SHALL clearly indicate that state.
5. WHEN the latest successful backup is older than the allowed interval THEN the status response SHALL mark backups as stale.
6. WHEN the latest backup failed THEN the status response SHALL include safe failure metadata.
7. WHEN restore verification has run THEN the status response SHALL include latest verification status and timestamp.
8. WHEN offsite backup is enabled THEN the status response SHALL include offsite status without exposing credentials.
9. WHEN recent runs exist THEN the status response SHALL include recent run summaries.

## Requirement 9: Stale and failed backup detection

### User story

As an operator, I want stale or failed backups to be detected so that I can fix recovery risk before an incident.

### Acceptance criteria

1. WHEN the latest successful backup is older than the configured maximum interval THEN the system SHALL mark backup status as stale.
2. WHEN the latest backup run failed THEN the system SHALL expose failed status.
3. WHEN offsite upload fails THEN the system SHALL expose degraded or partially successful status.
4. WHEN restore verification fails THEN the system SHALL expose unhealthy or degraded status.
5. WHEN stale or failed backup state is detected THEN the system SHALL log a warning or error.
6. WHEN alert integration exists THEN the system SHOULD emit an alert event for stale or failed backups.
7. WHEN health/readiness checks consume backup status THEN they SHALL be able to identify healthy, degraded, and unhealthy backup states.

## Requirement 10: Restore verification / restore drill

### User story

As an operator, I want restore drills so that backups are proven recoverable instead of merely created.

### Acceptance criteria

1. WHEN restore verification is run for a backup THEN the system SHALL verify the artifact checksum.
2. WHEN restore verification is run THEN the system SHALL extract the backup into an isolated temporary location.
3. WHEN restore verification is run THEN the system SHALL restore the database backup into an isolated verification database or equivalent safe target.
4. WHEN restore verification is run THEN the system SHALL restore storage files into an isolated verification directory.
5. WHEN restore verification is run THEN the system SHALL perform basic integrity checks.
6. WHEN restore verification succeeds THEN the system SHALL record verification success and timestamp.
7. WHEN restore verification fails THEN the system SHALL record verification failure and safe error reason.
8. WHEN restore verification runs THEN the system SHALL NOT overwrite or mutate production database data.
9. WHEN restore verification runs THEN the system SHALL NOT overwrite or mutate production storage.
10. WHEN temporary restore resources are created THEN the system SHALL clean them up after the drill where safe.

## Requirement 11: Manual backup and manual verification

### User story

As an admin, I want to manually trigger a backup or restore verification so that I can validate recovery before launch or maintenance.

### Acceptance criteria

1. WHEN manual backup endpoint is implemented THEN only admins SHALL be allowed to trigger it.
2. WHEN an admin triggers a manual backup THEN the system SHALL create a normal backup metadata record.
3. WHEN a backup is already running THEN manual trigger SHALL not start an overlapping backup.
4. WHEN manual restore verification endpoint is implemented THEN only admins SHALL be allowed to trigger it.
5. WHEN an admin triggers manual restore verification THEN the system SHALL run verification against the selected backup or latest successful backup.
6. WHEN manual trigger fails validation THEN the system SHALL return a clear error response.
7. WHEN manual trigger succeeds THEN the system SHALL return the created backup or verification run status.

## Requirement 12: Security and secret handling

### User story

As a security-conscious operator, I want backups to avoid leaking secrets so that backup operations do not create new vulnerabilities.

### Acceptance criteria

1. WHEN backup artifacts are created THEN the system SHALL exclude `.env` files and configured secret paths.
2. WHEN backup metadata is returned through APIs THEN the system SHALL not include S3 secrets, database passwords, tokens, or raw credentials.
3. WHEN backup operations are logged THEN logs SHALL not include secrets.
4. WHEN local backup artifacts are written THEN they SHOULD be written to a restricted directory.
5. WHEN offsite uploads are used THEN credentials SHALL come from deployment secrets or secure configuration.
6. WHEN backup artifact sensitivity is documented THEN operators SHALL be warned that artifacts may contain user/application data.
7. WHEN restore verification logs errors THEN logs SHALL redact secrets and avoid dumping sensitive data.

## Requirement 13: Test coverage

### User story

As a maintainer, I want automated tests for backups and restore drills so that recovery behavior does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover backup metadata lifecycle.
2. WHEN tests run THEN they SHALL cover successful local backup creation.
3. WHEN tests run THEN they SHALL cover database backup failure.
4. WHEN tests run THEN they SHALL cover storage backup failure.
5. WHEN tests run THEN they SHALL cover offsite upload success and failure.
6. WHEN tests run THEN they SHALL cover retention cleanup behavior.
7. WHEN tests run THEN they SHALL cover stale backup detection.
8. WHEN tests run THEN they SHALL cover admin-only status endpoint authorization.
9. WHEN tests run THEN they SHALL cover restore verification success.
10. WHEN tests run THEN they SHALL cover restore verification failure.
11. WHEN tests run THEN they SHALL cover non-overlapping backup lock behavior.
12. WHEN tests run THEN they SHALL cover secret redaction in API responses and logs where practical.

## Requirement 14: Launch readiness

### User story

As a deployer, I want backup launch verification so that V1 is not released without a tested recovery path.

### Acceptance criteria

1. WHEN production is prepared for V1 THEN scheduled backups SHALL be enabled or explicitly documented as disabled for a non-production environment.
2. WHEN production is prepared for V1 THEN at least one successful backup SHALL exist.
3. WHEN production is prepared for V1 THEN offsite backup SHALL be configured or an explicit risk exception SHALL be documented.
4. WHEN production is prepared for V1 THEN restore verification SHALL pass for a recent backup.
5. WHEN production is prepared for V1 THEN the admin backup status endpoint SHALL report non-stale backup state.
6. WHEN production is prepared for V1 THEN stale/failed backup behavior SHALL be manually verified.
7. WHEN release verification is complete THEN operators SHALL have documented backup and restore drill instructions.

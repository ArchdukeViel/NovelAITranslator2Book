# requirements.md

# Requirements: Scheduled Export Freshness Check

## Introduction

Export freshness should be detected in the background instead of only when an export API is called. The system must periodically check generated export artifacts, compare them against current source/export inputs, and persist freshness status such as fresh, stale, missing, unknown, or error.

## Requirement 1: Export freshness metadata

### User story

As an operator, I want export artifacts to store freshness metadata so the system can determine whether they are current.

### Acceptance criteria

1. WHEN an export artifact is generated THEN the system SHALL record freshness metadata.
2. WHEN freshness metadata is recorded THEN it SHALL include artifact format and generated timestamp.
3. WHEN source revision information is available THEN freshness metadata SHALL include source/content revision values.
4. WHEN translation revision information is available THEN freshness metadata SHALL include translation revision values.
5. WHEN glossary revision affects exported content THEN freshness metadata SHALL include glossary revision values.
6. WHEN export template/profile affects output THEN freshness metadata SHALL include template/profile version or hash.
7. WHEN chapter ordering affects output THEN freshness metadata SHALL include chapter set/order hash or revision.
8. WHEN metadata is stored THEN it SHALL use hashes or revisions, not full chapter text.
9. WHEN an export artifact has no freshness metadata THEN the system SHALL treat freshness as unknown until checked or regenerated.

## Requirement 2: Freshness status model

### User story

As a frontend or API consumer, I want a clear freshness status so I can distinguish current, stale, missing, and unknown exports.

### Acceptance criteria

1. WHEN an artifact is current and exists THEN its freshness status SHALL be `fresh`.
2. WHEN an artifact exists but inputs changed THEN its freshness status SHALL be `stale`.
3. WHEN an artifact record exists but the file/object is missing THEN its freshness status SHALL be `missing`.
4. WHEN freshness cannot be determined safely THEN its status SHALL be `unknown`.
5. WHEN checking fails for an artifact THEN its status SHALL be `error` or `unknown` according to error policy.
6. WHEN an artifact is stale THEN the system SHALL record a safe stale reason where possible.
7. WHEN an artifact is checked THEN the system SHALL record `freshness_checked_at`.
8. WHEN freshness status is returned through APIs THEN it SHALL be JSON-compatible and safe.

## Requirement 3: Freshness calculation

### User story

As an operator, I want the system to compare export-time inputs with current inputs so stale exports are detected reliably.

### Acceptance criteria

1. WHEN current translation revision differs from export metadata THEN the artifact SHALL be marked stale.
2. WHEN current source/chapter content fingerprint differs from export metadata THEN the artifact SHALL be marked stale.
3. WHEN current chapter set/order differs from export metadata THEN the artifact SHALL be marked stale.
4. WHEN current novel metadata used in export differs from export metadata THEN the artifact SHALL be marked stale.
5. WHEN current glossary revision differs and glossary affects export output THEN the artifact SHALL be marked stale.
6. WHEN current export template version differs from export metadata THEN the artifact SHALL be marked stale.
7. WHEN current export profile/settings hash differs from export metadata THEN the artifact SHALL be marked stale.
8. WHEN publication state changed in a way that affects the export THEN the artifact SHALL be marked stale.
9. WHEN all required values match and artifact exists THEN the artifact SHALL be marked fresh.
10. WHEN required current values cannot be computed due to dependency failure THEN the artifact SHALL NOT be marked fresh.

## Requirement 4: Missing artifact detection

### User story

As an operator, I want missing export files detected before a user tries to download them.

### Acceptance criteria

1. WHEN an export artifact record points to a file/object that exists THEN missing check SHALL pass.
2. WHEN an export artifact record points to a file/object that does not exist THEN the artifact SHALL be marked missing.
3. WHEN object storage returns not found THEN the artifact SHALL be marked missing.
4. WHEN storage check fails due to timeout or temporary error THEN the artifact SHALL be marked unknown or error, not missing.
5. WHEN an artifact is marked missing THEN APIs SHALL not claim it is downloadable/current.
6. WHEN missing artifact is detected THEN the system SHALL log a safe event.

## Requirement 5: Scheduled freshness checker

### User story

As an operator, I want export freshness checked on a schedule so stale exports are detected without user action.

### Acceptance criteria

1. WHEN scheduled freshness checking is enabled THEN the system SHALL run it according to configured schedule.
2. WHEN scheduled freshness checking is disabled THEN the scheduled job SHALL not run.
3. WHEN the job runs THEN it SHALL scan export artifacts in batches.
4. WHEN the job runs THEN it SHALL respect maximum artifacts per run.
5. WHEN the job runs THEN it SHALL skip artifacts currently being generated.
6. WHEN an artifact check fails THEN the job SHALL continue checking other artifacts where safe.
7. WHEN the job finishes THEN it SHALL record run summary or log summary.
8. WHEN the job runs successfully THEN stale/missing/unknown statuses SHALL be persisted before any API call requires them.

## Requirement 6: Freshness checker locking

### User story

As an operator, I want freshness checks to avoid overlapping runs so artifact status is not updated concurrently by duplicate jobs.

### Acceptance criteria

1. WHEN a freshness check run starts THEN it SHALL acquire a freshness-check lock.
2. WHEN another run already holds the lock THEN the new run SHALL skip safely.
3. WHEN a run is skipped due to lock THEN the system SHALL record or log `skipped_locked`.
4. WHEN a run completes THEN it SHALL release the lock.
5. WHEN a run crashes THEN the lock SHALL expire or become recoverable.
6. WHEN lock acquisition fails unexpectedly THEN the system SHALL not run the freshness scan.

## Requirement 7: Freshness run metadata

### User story

As an operator, I want freshness check run metadata so I can verify the scheduled checker is working.

### Acceptance criteria

1. WHEN a freshness check run starts THEN the system SHALL record start time.
2. WHEN a freshness check run finishes THEN the system SHALL record finish time and duration.
3. WHEN a freshness check run finishes THEN the system SHALL record scanned artifact count.
4. WHEN a freshness check run finishes THEN the system SHALL record fresh, stale, missing, unknown, and error counts.
5. WHEN a freshness check run partially fails THEN the system SHALL record partial success or equivalent.
6. WHEN a freshness check run is skipped due to lock THEN the system SHALL record skipped state.
7. WHEN run metadata is exposed through admin APIs THEN it SHALL not expose secrets or raw stack traces.

## Requirement 8: Export API freshness exposure

### User story

As a frontend or API consumer, I want export APIs to expose persisted freshness status so users know whether an artifact is current.

### Acceptance criteria

1. WHEN export artifact metadata is returned through an API THEN it SHALL include freshness status where available.
2. WHEN an artifact is stale THEN the API SHALL include a safe stale reason where available.
3. WHEN an artifact is missing THEN the API SHALL indicate missing/unavailable status.
4. WHEN freshness is unknown THEN the API SHALL indicate unknown status instead of claiming fresh.
5. WHEN old artifacts do not have freshness metadata THEN the API SHALL handle them without crashing.
6. WHEN existing clients ignore freshness metadata THEN existing export behavior SHALL remain compatible.
7. WHEN freshness metadata is returned THEN it SHALL not include private content, raw paths, signed URLs, or secrets.

## Requirement 9: Download behavior compatibility

### User story

As a user, I want export downloads to behave safely when exports are stale or missing.

### Acceptance criteria

1. WHEN a fresh artifact is downloaded THEN existing download behavior SHALL continue.
2. WHEN a stale artifact is downloaded THEN the system SHALL follow product policy: allow with stale marker, warn, or require regeneration.
3. WHEN a missing artifact is requested for download THEN the system SHALL return a controlled missing-artifact error.
4. WHEN an artifact freshness is unknown THEN the system SHALL not claim it is fresh.
5. WHEN a download fails due to storage error THEN the system SHALL return a controlled export/storage error.
6. WHEN download errors occur THEN raw storage paths, signed URLs, credentials, and stack traces SHALL not be returned.

## Requirement 10: Optional event-driven stale hints

### User story

As an operator, I want exports marked stale soon after source changes, even before the next scheduled scan.

### Acceptance criteria

1. WHEN translation content changes and event-driven hints are implemented THEN affected exports SHOULD be marked likely stale.
2. WHEN glossary revision changes and glossary affects exports THEN affected exports SHOULD be marked likely stale.
3. WHEN export template/profile changes THEN affected exports SHOULD be marked likely stale.
4. WHEN novel metadata or chapter order changes THEN affected exports SHOULD be marked likely stale.
5. WHEN event-driven stale marking fails THEN the scheduled checker SHALL still be able to detect staleness later.
6. WHEN event-driven hints are not implemented THEN scheduled freshness checking SHALL still satisfy this spec.

## Requirement 11: Dry-run/manual check support

### User story

As an admin, I want to manually or dry-run freshness checks so I can verify behavior safely in staging.

### Acceptance criteria

1. WHEN manual freshness check endpoint is implemented THEN it SHALL be admin-only.
2. WHEN manual check is called with dry-run enabled THEN it SHALL calculate statuses without persisting mutations.
3. WHEN manual check specifies a format or novel filter THEN only matching artifacts SHALL be checked.
4. WHEN manual check runs while lock is held THEN it SHALL not start an overlapping scan.
5. WHEN manual check is not implemented THEN scheduled job and tests SHALL still provide freshness checking.
6. WHEN dry-run result is returned THEN it SHALL include safe counts and not expose secrets.

## Requirement 12: Security and privacy

### User story

As an operator, I want freshness metadata to avoid storing private content or secrets.

### Acceptance criteria

1. WHEN freshness metadata is stored THEN it SHALL not include full source chapter text.
2. WHEN freshness metadata is stored THEN it SHALL not include full translated chapter text.
3. WHEN freshness metadata is stored THEN it SHALL not include raw prompts.
4. WHEN freshness metadata is stored THEN it SHALL not include provider API responses.
5. WHEN freshness metadata is stored THEN it SHALL not include API keys, credentials, tokens, or signed URLs.
6. WHEN freshness errors are exposed through APIs THEN they SHALL be redacted.
7. WHEN logs are emitted THEN they SHALL not include private content or unsafe artifact URLs.
8. WHEN admin status is exposed THEN it SHALL require admin authorization.

## Requirement 13: Admin freshness status

### User story

As an admin, I want to inspect export freshness checker status so I can confirm stale exports are being detected.

### Acceptance criteria

1. WHEN admin freshness status endpoint is implemented THEN it SHALL require admin authorization.
2. WHEN admin requests status THEN it SHALL return enabled state and schedule.
3. WHEN admin requests status THEN it SHALL return last run status and timestamp.
4. WHEN admin requests status THEN it SHALL return summary counts for fresh, stale, missing, unknown, and error artifacts.
5. WHEN no run has occurred THEN it SHALL clearly indicate no runs.
6. WHEN non-admin requests status THEN access SHALL be blocked.
7. WHEN status includes errors THEN they SHALL be safe and redacted.

## Requirement 14: Test coverage

### User story

As a maintainer, I want tests for scheduled export freshness so stale export detection does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover fresh artifact detection.
2. WHEN tests run THEN they SHALL cover stale detection from translation revision changes.
3. WHEN tests run THEN they SHALL cover stale detection from chapter order/content changes.
4. WHEN tests run THEN they SHALL cover stale detection from glossary revision changes where applicable.
5. WHEN tests run THEN they SHALL cover stale detection from template/profile changes.
6. WHEN tests run THEN they SHALL cover missing artifact detection.
7. WHEN tests run THEN they SHALL cover unknown/error behavior for dependency failures.
8. WHEN tests run THEN they SHALL cover scheduled batch scanning.
9. WHEN tests run THEN they SHALL cover locking/skipped run behavior.
10. WHEN tests run THEN they SHALL cover API freshness exposure.
11. WHEN tests run THEN they SHALL cover download behavior for missing/stale artifacts according to policy.
12. WHEN tests run THEN they SHALL cover redaction/security rules.
13. WHEN manual/dry-run endpoint is implemented THEN tests SHALL cover admin authorization and dry-run no-mutation behavior.

## Requirement 15: Completion verification

### User story

As an operator, I want a clear verification path so scheduled export freshness is complete only when stale exports are detected before API calls.

### Acceptance criteria

1. WHEN an export is generated and no inputs change THEN scheduled check SHALL keep it fresh.
2. WHEN translation content changes after export THEN scheduled check SHALL mark the export stale.
3. WHEN the artifact file is removed after export THEN scheduled check SHALL mark it missing.
4. WHEN export template/profile changes after export THEN scheduled check SHALL mark affected exports stale.
5. WHEN freshness check runs before any user export API call THEN stale/missing status SHALL already be persisted.
6. WHEN export API is later called THEN it SHALL return the persisted freshness status.
7. WHEN a dependency failure occurs during check THEN artifact SHALL not be incorrectly marked fresh.
8. WHEN freshness metadata is inspected THEN it SHALL contain hashes/revisions, not full content or secrets.

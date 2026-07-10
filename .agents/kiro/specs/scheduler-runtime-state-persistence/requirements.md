# requirements.md

# Requirements: Scheduler Runtime State Persistence

## Introduction

The scheduler needs durable runtime state so operational health reflects actual scheduler behavior. The system must persist cooldown, exhausted, failed, running, heartbeat, and recovery states so the scheduler health API can report live status instead of only static configuration.

## Requirement 1: Runtime state persistence model

### User story

As an operator, I want scheduler runtime states persisted so that failures and cooldowns survive process restarts and are visible in health diagnostics.

### Acceptance criteria

1. WHEN a scheduler runtime state is created THEN the system SHALL persist it durably.
2. WHEN a scheduler runtime state already exists for the same scheduler and scope THEN the system SHALL update the existing record instead of creating duplicates.
3. WHEN runtime state is persisted THEN it SHALL include scheduler key, scope type, scope key, state, timestamps, and safe metadata.
4. WHEN a state includes an error THEN it SHALL include a safe error category and safe error message.
5. WHEN a state includes cooldown or exhaustion THEN it SHALL include next eligible time when known.
6. WHEN runtime state is queried after process restart THEN the latest persisted state SHALL still be available.
7. WHEN runtime state metadata is stored THEN it SHALL not contain secrets, tokens, credentials, or private content.

## Requirement 2: Scheduler started and running state

### User story

As an operator, I want to know when a scheduler is actively running so that stuck or stale runs can be detected.

### Acceptance criteria

1. WHEN a scheduler loop starts a run THEN the system SHALL persist a `running` state or equivalent.
2. WHEN a scheduler run starts THEN the system SHALL record `last_started_at`.
3. WHEN a scheduler run starts THEN the system SHALL update `heartbeat_at`.
4. WHEN a scheduler run is associated with a run ID or worker ID THEN the system SHOULD persist safe run ownership metadata.
5. WHEN a scheduler is already marked running by another active owner THEN the system SHALL avoid unsafe overwrite.
6. WHEN a scheduler run finishes THEN the system SHALL record `last_finished_at`.
7. WHEN a scheduler crashes before finishing THEN stale detection SHALL be able to identify the old running state.

## Requirement 3: Successful run and recovery state

### User story

As an operator, I want successful scheduler runs to clear active failure/cooldown state so that health reflects recovery.

### Acceptance criteria

1. WHEN a scheduler or scoped job succeeds THEN the system SHALL record `last_success_at`.
2. WHEN a scheduler or scoped job succeeds THEN the system SHALL reset `consecutive_failures` to zero.
3. WHEN a scheduler or scoped job succeeds after failure THEN the system SHALL clear active error state or mark the scope recovered.
4. WHEN a scheduler or scoped job succeeds after cooldown THEN the system SHALL clear active cooldown state if no longer applicable.
5. WHEN success is recorded THEN previous historical failure counters MAY be retained in total failure count.
6. WHEN success is recorded THEN scheduler health SHALL no longer report the scope as actively failed.
7. WHEN recovery is represented explicitly THEN the system SHALL eventually transition recovered state to idle or expire it.

## Requirement 4: Failure state

### User story

As an operator, I want scheduler failures persisted so that repeated failures are visible and diagnosable.

### Acceptance criteria

1. WHEN a scheduler or scoped job fails THEN the system SHALL persist `failed` state or equivalent.
2. WHEN failure is persisted THEN the system SHALL record `last_failure_at`.
3. WHEN failure is persisted THEN the system SHALL increment total failure count.
4. WHEN failure is persisted THEN the system SHALL increment consecutive failure count.
5. WHEN failure is persisted THEN the system SHALL record safe error category.
6. WHEN failure is persisted THEN the system SHALL record safe error message.
7. WHEN retry or backoff applies THEN the system SHALL record `next_eligible_at`.
8. WHEN a required scheduler scope is failed THEN scheduler health SHALL reflect degraded or unhealthy status according to criticality.
9. WHEN failure details are exposed through admin APIs THEN secrets and stack traces SHALL be redacted.

## Requirement 5: Cooldown state

### User story

As an operator, I want scheduler cooldowns persisted so that rate limits and intentional backoffs are visible.

### Acceptance criteria

1. WHEN a scheduler scope enters cooldown THEN the system SHALL persist `cooldown` state.
2. WHEN cooldown is persisted THEN the system SHALL record `cooldown_until`.
3. WHEN cooldown is persisted THEN the system SHALL record `next_eligible_at`.
4. WHEN cooldown is caused by an error THEN the system SHALL record safe error category and reason.
5. WHEN cooldown expires THEN the scheduler SHALL treat the scope as eligible again.
6. WHEN cooldown expires and the next run succeeds THEN active cooldown state SHALL be cleared.
7. WHEN scheduler health is requested THEN active cooldowns SHALL be included in the runtime health summary.
8. WHEN all required scopes are in cooldown THEN scheduler health SHALL report degraded or unhealthy according to configured policy.

## Requirement 6: Exhausted state

### User story

As an operator, I want exhausted/no-work states persisted so that the scheduler can distinguish healthy no-work conditions from failures.

### Acceptance criteria

1. WHEN a scheduler scope has no eligible work THEN the system SHALL persist `exhausted` or equivalent state.
2. WHEN exhaustion has a known retry/recheck time THEN the system SHALL record `exhausted_until` or `next_eligible_at`.
3. WHEN exhaustion is expected and not an error THEN scheduler health SHALL not report it as failed.
4. WHEN all work is exhausted but the scheduler is functioning THEN scheduler health SHALL report healthy or degraded according to policy.
5. WHEN new eligible work appears THEN exhausted state SHALL be cleared or replaced.
6. WHEN exhausted state is exposed through admin health THEN the response SHALL include safe reason and next eligible time when known.

## Requirement 7: Heartbeat and stale detection

### User story

As an operator, I want stale scheduler state detected so that crashed or stuck scheduler loops do not appear healthy.

### Acceptance criteria

1. WHEN a scheduler loop is active THEN it SHALL update heartbeat at a configured interval.
2. WHEN heartbeat is older than the configured stale threshold THEN scheduler health SHALL mark the scheduler or scope as stale.
3. WHEN a running state becomes stale THEN scheduler health SHALL report degraded or unhealthy according to criticality.
4. WHEN the scheduler restarts and updates heartbeat THEN stale state SHALL clear.
5. WHEN no runtime state exists yet THEN scheduler health SHALL report unknown or not-yet-run state.
6. WHEN stale detection runs THEN it SHALL not require manual database edits.
7. WHEN stale state is returned through admin APIs THEN it SHALL include heartbeat age or last heartbeat time.

## Requirement 8: Scheduler health API integration

### User story

As an admin, I want scheduler health to show persisted runtime states so that I can see real scheduler behavior.

### Acceptance criteria

1. WHEN admin scheduler health is requested THEN the system SHALL read persisted runtime states.
2. WHEN active cooldowns exist THEN health response SHALL include active cooldown count and details.
3. WHEN active failures exist THEN health response SHALL include active failure count and details.
4. WHEN exhausted scopes exist THEN health response SHALL include exhausted count and details.
5. WHEN stale scheduler heartbeat exists THEN health response SHALL mark scheduler as stale.
6. WHEN no runtime state exists THEN health response SHALL clearly indicate unknown/not-yet-run status.
7. WHEN runtime state exists from before process restart THEN health response SHALL use it.
8. WHEN static scheduler config is included THEN it SHALL be combined with runtime state, not used as a replacement.
9. WHEN health response includes error messages THEN they SHALL be safe and redacted.

## Requirement 9: Runtime state API authorization

### User story

As a site operator, I want scheduler runtime state protected so that operational internals are not exposed publicly.

### Acceptance criteria

1. WHEN unauthenticated users request scheduler runtime health THEN the system SHALL return `401 Unauthorized`.
2. WHEN non-admin authenticated users request scheduler runtime health THEN the system SHALL return `403 Forbidden`.
3. WHEN admins request scheduler runtime health THEN the system SHALL return scheduler runtime status.
4. WHEN public health endpoints exist THEN they SHALL not expose detailed scheduler runtime states.
5. WHEN detailed runtime states are returned THEN they SHALL not include secrets, credentials, tokens, private user content, or stack traces.
6. WHEN disabled admins are rejected by existing auth rules THEN scheduler health SHALL follow the same behavior.

## Requirement 10: Runtime state cleanup

### User story

As an operator, I want old runtime states cleaned up so that the runtime state store does not grow forever.

### Acceptance criteria

1. WHEN runtime states are active THEN cleanup SHALL not delete them.
2. WHEN runtime states are idle/recovered and older than configured TTL THEN cleanup MAY delete them.
3. WHEN runtime states refer to disabled or removed scheduler scopes THEN cleanup MAY expire them after TTL.
4. WHEN cleanup runs THEN it SHALL preserve currently configured disabled states if needed for health output.
5. WHEN cleanup deletes expired states THEN it SHALL not affect scheduler job data.
6. WHEN cleanup fails THEN it SHALL log a safe warning and not crash the scheduler.
7. WHEN `maintenance-cron` is implemented later THEN this cleanup SHALL be callable from that job.

## Requirement 11: Safe error categorization and redaction

### User story

As an operator, I want useful scheduler error categories without leaking sensitive provider or infrastructure information.

### Acceptance criteria

1. WHEN runtime state records an error THEN it SHALL use a stable error category where possible.
2. WHEN an unknown error occurs THEN the system SHALL use `unknown` or equivalent.
3. WHEN an error message is stored THEN secrets SHALL be redacted.
4. WHEN provider errors include API keys or tokens THEN those values SHALL not be persisted.
5. WHEN stack traces are logged THEN they SHALL not be returned through admin health APIs.
6. WHEN public health endpoints summarize scheduler state THEN they SHALL not include detailed error messages.
7. WHEN admin health returns error metadata THEN it SHALL be safe for an admin operator to view.

## Requirement 12: Concurrency safety

### User story

As a maintainer, I want runtime state updates to be safe when multiple scheduler instances or workers are active.

### Acceptance criteria

1. WHEN two scheduler instances update the same scope THEN the system SHALL avoid duplicate state records.
2. WHEN state is upserted THEN unique scheduler/scope identity SHALL be enforced.
3. WHEN lock ownership exists THEN state updates SHOULD include safe owner or run ID.
4. WHEN one scheduler owns a running state THEN another scheduler SHALL not incorrectly clear it without ownership validation where practical.
5. WHEN concurrent updates occur THEN final state SHALL remain valid and queryable.
6. WHEN a state transition is tied to job claiming THEN updates SHOULD be atomic with the relevant scheduler decision where practical.

## Requirement 13: Test coverage

### User story

As a maintainer, I want automated tests for scheduler state persistence so runtime health does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover runtime state creation and update.
2. WHEN tests run THEN they SHALL cover started/running transition.
3. WHEN tests run THEN they SHALL cover success/recovery transition.
4. WHEN tests run THEN they SHALL cover failure transition.
5. WHEN tests run THEN they SHALL cover cooldown transition.
6. WHEN tests run THEN they SHALL cover exhausted transition.
7. WHEN tests run THEN they SHALL cover heartbeat update and stale detection.
8. WHEN tests run THEN they SHALL cover health API output from persisted state.
9. WHEN tests run THEN they SHALL cover admin-only authorization.
10. WHEN tests run THEN they SHALL cover redaction of error details.
11. WHEN tests run THEN they SHALL cover cleanup of expired states.
12. WHEN tests run THEN they SHALL cover process restart behavior by reading previously persisted state.
13. WHEN tests run THEN they SHOULD cover concurrent upsert behavior.

## Requirement 14: Launch readiness

### User story

As a deployer, I want scheduler health to reflect real runtime state before scaling so that production operations can detect stuck schedulers.

### Acceptance criteria

1. WHEN scheduler runtime state persistence is complete THEN scheduler health SHALL show persisted live states.
2. WHEN a scheduler enters cooldown in staging THEN health SHALL show the cooldown and next eligible time.
3. WHEN a scheduler failure is simulated in staging THEN health SHALL show failed state and safe error category.
4. WHEN a scheduler has no eligible work THEN health SHALL show exhausted/no-work state instead of failure.
5. WHEN scheduler heartbeat becomes stale THEN health SHALL mark stale state.
6. WHEN the app restarts THEN previous failed/cooldown state SHALL still be visible until cleared or expired.
7. WHEN a later success occurs THEN active failed/cooldown state SHALL clear.
8. WHEN public health endpoints are checked THEN they SHALL not leak detailed scheduler internals.

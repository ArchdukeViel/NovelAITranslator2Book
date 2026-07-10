# tasks.md

# Tasks: Scheduler Runtime State Persistence

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing scheduler implementation and scheduler loop entry points.
  * [ ] 0.2 Inspect existing scheduler health/status API response.
  * [ ] 0.3 Inspect existing job selection, cooldown, retry, exhausted, and failure handling.
  * [ ] 0.4 Inspect existing worker/queue heartbeat or activity runtime metadata.
  * [ ] 0.5 Inspect existing database model and migration conventions.
  * [ ] 0.6 Inspect existing admin auth guard and admin router conventions.
  * [ ] 0.7 Inspect existing structured error categories and redaction helpers.
  * [ ] 0.8 Inspect existing cleanup/maintenance patterns.
  * [ ] 0.9 Inspect existing scheduler and API tests.

* [ ] 1. Define scheduler runtime state contract

  * [ ] 1.1 Define scheduler keys used by existing schedulers. (REQ-1)
  * [ ] 1.2 Define supported scope types such as `scheduler`, `job_type`, and `source`. (REQ-1)
  * [ ] 1.3 Define stable state values: `idle`, `running`, `cooldown`, `exhausted`, `failed`, `disabled`, `stale`, and optional `recovered`. (REQ-1)
  * [ ] 1.4 Define state transition rules. (REQ-2 through REQ-7)
  * [ ] 1.5 Define stable error categories. (REQ-4, REQ-11)
  * [ ] 1.6 Define scheduler health summary response. (REQ-8)
  * [ ] 1.7 Define runtime state detail response. (REQ-8, REQ-9)
  * [ ] 1.8 Define redaction rules for stored and returned error data. (REQ-9, REQ-11)

* [ ] 2. Add runtime state configuration

  * [ ] 2.1 Add scheduler heartbeat interval config. (REQ-7)
  * [ ] 2.2 Add scheduler stale-after threshold config. (REQ-7)
  * [ ] 2.3 Add scheduler runtime state TTL config. (REQ-10)
  * [ ] 2.4 Add optional config for whether cooldown/exhausted states are degraded or healthy. (REQ-5, REQ-6, REQ-8)
  * [ ] 2.5 Add optional config for required scheduler scopes/job types. (REQ-8)
  * [ ] 2.6 Validate configuration at startup or scheduler initialization. (REQ-14)

* [ ] 3. Add database model and migration

  * [ ] 3.1 Create `scheduler_runtime_states` table/model or equivalent. (REQ-1)
  * [ ] 3.2 Add scheduler key, scope type, scope key, state, reason, error category, and safe error message fields. (REQ-1, REQ-11)
  * [ ] 3.3 Add failure count and consecutive failure count fields. (REQ-4)
  * [ ] 3.4 Add last attempt, last success, last failure, last started, and last finished timestamps. (REQ-2, REQ-3, REQ-4)
  * [ ] 3.5 Add cooldown, exhausted, and next eligible timestamp fields. (REQ-5, REQ-6)
  * [ ] 3.6 Add heartbeat timestamp. (REQ-7)
  * [ ] 3.7 Add safe owner/run metadata fields if needed. (REQ-12)
  * [ ] 3.8 Add metadata JSON and expiry timestamp fields. (REQ-1, REQ-10)
  * [ ] 3.9 Add unique constraint on scheduler key, scope type, and scope key. (REQ-1, REQ-12)
  * [ ] 3.10 Add indexes for scheduler key, state, next eligible time, heartbeat, and updated time. (REQ-8, REQ-10)
  * [ ] 3.11 Add migration tests or migration verification. (REQ-13)

* [ ] 4. Implement runtime state repository

  * [ ] 4.1 Add atomic upsert method for runtime state. (REQ-1, REQ-12)
  * [ ] 4.2 Add method to get state by scheduler/scope. (REQ-1)
  * [ ] 4.3 Add method to list states by scheduler key. (REQ-8)
  * [ ] 4.4 Add method to list active cooldown states. (REQ-5, REQ-8)
  * [ ] 4.5 Add method to list active failure states. (REQ-4, REQ-8)
  * [ ] 4.6 Add method to list exhausted states. (REQ-6, REQ-8)
  * [ ] 4.7 Add method to update heartbeat. (REQ-7)
  * [ ] 4.8 Add method to delete expired states. (REQ-10)
  * [ ] 4.9 Add repository tests for create, update, unique key behavior, list filters, and delete expired. (REQ-1, REQ-10, REQ-13)

* [ ] 5. Implement state transition service

  * [ ] 5.1 Add `mark_started()` transition. (REQ-2)
  * [ ] 5.2 Add `mark_success()` transition. (REQ-3)
  * [ ] 5.3 Add `mark_failure()` transition. (REQ-4)
  * [ ] 5.4 Add `mark_cooldown()` transition. (REQ-5)
  * [ ] 5.5 Add `mark_exhausted()` transition. (REQ-6)
  * [ ] 5.6 Add `mark_disabled()` transition if scheduler config supports disabled scopes. (REQ-1)
  * [ ] 5.7 Add `mark_recovered()` or direct recovery-to-idle behavior. (REQ-3)
  * [ ] 5.8 Add `clear_state()` or `mark_idle()` helper. (REQ-3, REQ-6)
  * [ ] 5.9 Add transition tests for all supported states. (REQ-2 through REQ-7, REQ-13)

* [ ] 6. Add error categorization and redaction

  * [ ] 6.1 Reuse existing structured error categorization if available. (REQ-11)
  * [ ] 6.2 Add scheduler-specific error category mapping where missing. (REQ-11)
  * [ ] 6.3 Add safe error message extraction. (REQ-4, REQ-11)
  * [ ] 6.4 Redact provider API keys, tokens, credentials, URLs with secrets, and stack traces. (REQ-9, REQ-11)
  * [ ] 6.5 Ensure metadata JSON does not include private user content. (REQ-1, REQ-11)
  * [ ] 6.6 Add tests for known categories, unknown categories, and redaction. (REQ-11, REQ-13)

* [ ] 7. Wire scheduler loop lifecycle

  * [ ] 7.1 Call `mark_started()` when scheduler pass begins. (REQ-2)
  * [ ] 7.2 Update heartbeat during long scheduler passes. (REQ-7)
  * [ ] 7.3 Call `mark_success()` when scheduler pass completes successfully. (REQ-3)
  * [ ] 7.4 Call `mark_failure()` when scheduler pass fails. (REQ-4)
  * [ ] 7.5 Record `last_finished_at` on both success and failure. (REQ-2, REQ-4)
  * [ ] 7.6 Avoid crashing the scheduler if best-effort runtime state update fails, except where persistence is required for a scheduling decision. (REQ-1)
  * [ ] 7.7 Add scheduler lifecycle tests. (REQ-2, REQ-3, REQ-4, REQ-13)

* [ ] 8. Wire cooldown decisions

  * [ ] 8.1 Find existing cooldown/backoff decision points. (REQ-5)
  * [ ] 8.2 Persist source-level cooldown state. (REQ-5)
  * [ ] 8.3 Persist job-type-level cooldown state if applicable. (REQ-5)
  * [ ] 8.4 Record cooldown reason and safe error category. (REQ-5, REQ-11)
  * [ ] 8.5 Record cooldown until and next eligible time. (REQ-5)
  * [ ] 8.6 Ensure scheduler uses persisted cooldown after restart if applicable. (REQ-5, REQ-14)
  * [ ] 8.7 Clear cooldown when expired and work succeeds. (REQ-5, REQ-3)
  * [ ] 8.8 Add tests for cooldown persistence, restart visibility, expiry, and recovery. (REQ-5, REQ-13, REQ-14)

* [ ] 9. Wire exhausted/no-work decisions

  * [ ] 9.1 Find existing no-work/exhausted scheduler paths. (REQ-6)
  * [ ] 9.2 Persist exhausted state when no eligible work exists. (REQ-6)
  * [ ] 9.3 Record exhausted reason. (REQ-6)
  * [ ] 9.4 Record next eligible/recheck time when known. (REQ-6)
  * [ ] 9.5 Clear exhausted state when new work appears or next run starts. (REQ-6)
  * [ ] 9.6 Ensure exhausted state does not appear as failure by default. (REQ-6, REQ-8)
  * [ ] 9.7 Add tests for exhausted, recheck time, new work recovery, and health classification. (REQ-6, REQ-13)

* [ ] 10. Wire scoped failure tracking

  * [ ] 10.1 Find source-level failure handling. (REQ-4)
  * [ ] 10.2 Find job-type-level failure handling. (REQ-4)
  * [ ] 10.3 Persist failed state for failed source/job scope. (REQ-4)
  * [ ] 10.4 Increment total and consecutive failure counts. (REQ-4)
  * [ ] 10.5 Record last failure timestamp. (REQ-4)
  * [ ] 10.6 Record retry or next eligible time when applicable. (REQ-4)
  * [ ] 10.7 Clear active failure state after later success. (REQ-3, REQ-4)
  * [ ] 10.8 Add tests for failure count, consecutive failure reset, retry time, and recovery. (REQ-4, REQ-13)

* [ ] 11. Implement heartbeat and stale detection

  * [ ] 11.1 Update scheduler heartbeat at configured interval. (REQ-7)
  * [ ] 11.2 Add stale detection helper based on heartbeat age. (REQ-7)
  * [ ] 11.3 Mark stale in health calculation without necessarily mutating persisted state. (REQ-7, REQ-8)
  * [ ] 11.4 Optionally persist stale state when cleanup/health job runs. (REQ-7)
  * [ ] 11.5 Clear stale state when scheduler heartbeat resumes. (REQ-7)
  * [ ] 11.6 Add tests for fresh heartbeat, stale heartbeat, restart recovery, and missing state. (REQ-7, REQ-13)

* [ ] 12. Implement scheduler health aggregation

  * [ ] 12.1 Read persisted runtime states. (REQ-8)
  * [ ] 12.2 Read static scheduler configuration. (REQ-8)
  * [ ] 12.3 Combine static config with runtime state. (REQ-8)
  * [ ] 12.4 Compute active cooldown count. (REQ-5, REQ-8)
  * [ ] 12.5 Compute active failure count. (REQ-4, REQ-8)
  * [ ] 12.6 Compute exhausted scope count. (REQ-6, REQ-8)
  * [ ] 12.7 Compute stale scheduler state. (REQ-7, REQ-8)
  * [ ] 12.8 Compute overall scheduler status: healthy, degraded, unhealthy, or unknown. (REQ-8)
  * [ ] 12.9 Redact unsafe error details from health output. (REQ-8, REQ-9, REQ-11)
  * [ ] 12.10 Add aggregation tests for healthy, degraded, unhealthy, unknown, cooldown, failure, exhausted, stale, and recovered states. (REQ-8, REQ-13)

* [ ] 13. Update admin scheduler health API

  * [ ] 13.1 Locate existing scheduler health endpoint or add project-standard admin endpoint. (REQ-8)
  * [ ] 13.2 Protect endpoint with admin auth. (REQ-9)
  * [ ] 13.3 Return runtime-aware scheduler summary. (REQ-8)
  * [ ] 13.4 Return active runtime state details. (REQ-8)
  * [ ] 13.5 Return safe next eligible timestamps for cooldown/exhausted states. (REQ-5, REQ-6, REQ-8)
  * [ ] 13.6 Return safe error categories/messages for failure states. (REQ-4, REQ-8, REQ-11)
  * [ ] 13.7 Ensure public health endpoints do not expose detailed runtime states. (REQ-9)
  * [ ] 13.8 Add API tests for admin, non-admin, unauthenticated, and redacted responses. (REQ-8, REQ-9, REQ-13)

* [ ] 14. Add runtime state cleanup

  * [ ] 14.1 Implement cleanup method for expired idle/recovered states. (REQ-10)
  * [ ] 14.2 Ensure active cooldown, failed, running, disabled, and stale states are preserved. (REQ-10)
  * [ ] 14.3 Expire states for removed/unknown scopes after TTL. (REQ-10)
  * [ ] 14.4 Make cleanup callable from future `maintenance-cron`. (REQ-10)
  * [ ] 14.5 Optionally call cleanup from scheduler startup or existing cleanup path. (REQ-10)
  * [ ] 14.6 Add tests for cleanup preserving active states and deleting expired inactive states. (REQ-10, REQ-13)

* [ ] 15. Add concurrency safety

  * [ ] 15.1 Enforce unique scheduler/scope identity in database. (REQ-12)
  * [ ] 15.2 Use atomic upsert for state updates. (REQ-12)
  * [ ] 15.3 Preserve owner/run ID where scheduler uses locks. (REQ-12)
  * [ ] 15.4 Avoid clearing another owner’s active running state where practical. (REQ-12)
  * [ ] 15.5 Add transaction boundaries around state updates tied to job claiming where practical. (REQ-12)
  * [ ] 15.6 Add tests for duplicate prevention and concurrent update behavior. (REQ-12, REQ-13)

* [ ] 16. Optional admin UI integration

  * [ ] 16.1 Inspect existing admin scheduler/status UI if any. (REQ-8)
  * [ ] 16.2 Add runtime state summary if UI exists. (REQ-8)
  * [ ] 16.3 Display heartbeat age. (REQ-7, REQ-8)
  * [ ] 16.4 Display active cooldowns and next eligible times. (REQ-5, REQ-8)
  * [ ] 16.5 Display active failures and safe error categories. (REQ-4, REQ-8, REQ-11)
  * [ ] 16.6 Display exhausted/no-work scopes. (REQ-6, REQ-8)
  * [ ] 16.7 Add frontend tests if UI is implemented. (REQ-13)

* [ ] 17. Documentation

  * [ ] 17.1 Document scheduler runtime states and meanings. (REQ-1)
  * [ ] 17.2 Document cooldown, exhausted, failed, stale, and recovered behavior. (REQ-3 through REQ-7)
  * [ ] 17.3 Document scheduler health status calculation. (REQ-8)
  * [ ] 17.4 Document runtime state cleanup behavior. (REQ-10)
  * [ ] 17.5 Document operational troubleshooting examples. (REQ-14)
  * [ ] 17.6 Document how this feeds future health, metrics, and notification specs. (REQ-8)

* [ ] 18. Backend test coverage pass

  * [ ] 18.1 Add model/repository tests. (REQ-1, REQ-13)
  * [ ] 18.2 Add started/running transition tests. (REQ-2, REQ-13)
  * [ ] 18.3 Add success/recovery transition tests. (REQ-3, REQ-13)
  * [ ] 18.4 Add failure transition tests. (REQ-4, REQ-13)
  * [ ] 18.5 Add cooldown transition tests. (REQ-5, REQ-13)
  * [ ] 18.6 Add exhausted transition tests. (REQ-6, REQ-13)
  * [ ] 18.7 Add heartbeat/stale tests. (REQ-7, REQ-13)
  * [ ] 18.8 Add scheduler health aggregation tests. (REQ-8, REQ-13)
  * [ ] 18.9 Add admin API authorization tests. (REQ-9, REQ-13)
  * [ ] 18.10 Add cleanup tests. (REQ-10, REQ-13)
  * [ ] 18.11 Add redaction/error category tests. (REQ-11, REQ-13)
  * [ ] 18.12 Add concurrency/upsert tests. (REQ-12, REQ-13)
  * [ ] 18.13 Add process restart persistence test by reading state after service/repository reinitialization. (REQ-1, REQ-13, REQ-14)

* [ ] 19. Release verification

  * [ ] 19.1 Run migrations from a clean database. (REQ-14)
  * [ ] 19.2 Start scheduler and verify runtime state is created. (REQ-1, REQ-14)
  * [ ] 19.3 Verify running/heartbeat state updates during scheduler activity. (REQ-2, REQ-7, REQ-14)
  * [ ] 19.4 Simulate successful scheduler pass and verify last success is recorded. (REQ-3, REQ-14)
  * [ ] 19.5 Simulate scheduler failure and verify failed state appears in admin health. (REQ-4, REQ-14)
  * [ ] 19.6 Simulate cooldown and verify cooldown until/next eligible time appears. (REQ-5, REQ-14)
  * [ ] 19.7 Simulate no eligible work and verify exhausted/no-work state appears without false failure. (REQ-6, REQ-14)
  * [ ] 19.8 Stop scheduler heartbeat and verify stale state appears after threshold. (REQ-7, REQ-14)
  * [ ] 19.9 Restart app and verify persisted failed/cooldown state remains visible. (REQ-1, REQ-14)
  * [ ] 19.10 Run successful recovery and verify active failure/cooldown clears. (REQ-3, REQ-14)
  * [ ] 19.11 Verify non-admin cannot access detailed scheduler runtime health. (REQ-9, REQ-14)
  * [ ] 19.12 Verify public health endpoints do not expose scheduler internals. (REQ-9, REQ-14)
  * [ ] 19.13 Mark `scheduler-runtime-state-persistence` complete only after runtime state survives restart and scheduler health uses persisted state.

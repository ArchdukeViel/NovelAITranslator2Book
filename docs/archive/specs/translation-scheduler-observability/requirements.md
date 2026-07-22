# Requirements: Translation Scheduler Observability

## Introduction

The translation backend already has scheduler-aware provider/model routing, runtime provider state, request IDs, checkpoint/resume, chapter parallelization, quota/cooldown handling, and memory safeguards. The remaining gap is visibility.

Admins need to understand why a model was selected, why other candidates were skipped, when fallback happened, when no capacity was available, and what provider/model health looked like at selection time. This spec makes scheduler decisions observable without changing scheduling behavior.

This work is instrumentation-first. It must not change model ordering, provider routing, quota policy, cooldown behavior, checkpoint/resume behavior, chapter parallelization, memory guards, or translation output.

## Requirements

### REQ-1: Record Scheduler Selection Decisions

Every provider/model selection attempt should produce a compact scheduler decision record.

- REQ-1.1: Record selected provider and model when selection succeeds.
- REQ-1.2: Record `selected: null` when no provider/model is available.
- REQ-1.3: Record the scheduler policy used for selection.
- REQ-1.4: Record whether fallback was used.
- REQ-1.5: Record selection timestamp.
- REQ-1.6: Record candidate provider/model entries considered by the scheduler.
- REQ-1.7: Candidate lists must be bounded to avoid oversized metadata.
- REQ-1.8: If the candidate list is truncated, record total candidate count, recorded candidate count, and truncation flag.
- REQ-1.9: Decision recording must observe scheduler behavior only and must not influence selection.

### REQ-2: Include Request, Job, Chapter, and Checkpoint Identity

Scheduler decisions must be traceable across activity/job dashboards and per-chapter translation records.

- REQ-2.1: Decision records should include `request_id` when available.
- REQ-2.2: Decision records should include `activity_id` when available.
- REQ-2.3: Decision records should include `job_id` when available.
- REQ-2.4: Decision records should include `chapter_id` when available.
- REQ-2.5: Decision records should include attempt number when available.
- REQ-2.6: Decision records should include checkpoint ID or checkpoint reference when available.
- REQ-2.7: Missing identity fields must not break translation execution.
- REQ-2.8: Existing request ID propagation must be reused rather than replaced.

### REQ-3: Standardize Skip and Failure Reason Codes

Scheduler skip, fallback, and failure reasons must use stable machine-readable codes.

- REQ-3.1: Include `cooldown_active` when a candidate is cooling down.
- REQ-3.2: Include `quota_exhausted` when provider/model quota is exhausted.
- REQ-3.3: Include `rpm_limited` when requests-per-minute limits prevent selection.
- REQ-3.4: Include `rpd_limited` when requests-per-day limits prevent selection.
- REQ-3.5: Include `memory_pressure` when existing memory guards prevent safe scheduling or execution.
- REQ-3.6: Include `parallelism_limit` when chapter parallelization limits prevent immediate execution.
- REQ-3.7: Include `disabled` when a provider/model is disabled by config.
- REQ-3.8: Include `previously_attempted` when a candidate is skipped because it was already attempted for the same unit of work.
- REQ-3.9: Include `unhealthy` when runtime health marks a candidate unavailable.
- REQ-3.10: Include `checkpoint_blocked` when existing checkpoint/resume state blocks execution.
- REQ-3.11: Include `no_capacity` when no candidate can be selected.
- REQ-3.12: Include `unknown` for unexpected cases.
- REQ-3.13: Reason codes must not contain raw exception traces or secrets.

### REQ-4: Record Candidate Runtime State Safely

Each recorded scheduler candidate must include safe runtime state.

- REQ-4.1: Candidate records must include provider and model.
- REQ-4.2: Candidate records must include runtime status when available.
- REQ-4.3: Candidate records must include whether the candidate was selected.
- REQ-4.4: Skipped candidate records must include `skip_reason`.
- REQ-4.5: Candidate records should include `cooldown_until` when available.
- REQ-4.6: Candidate records should include `exhausted_until` when available.
- REQ-4.7: Candidate records should include `failed_at` when available.
- REQ-4.8: Candidate records should include safe `last_error_code` when available.
- REQ-4.9: Candidate records must not include API keys, credentials, account identifiers, prompts, source text, translated text, raw provider responses, or full exception traces.

### REQ-5: Persist Per-Chapter Scheduler Metadata

Scheduler decisions must survive beyond logs.

- REQ-5.1: Per-chapter translation output metadata should include the scheduler decision when available.
- REQ-5.2: Translation version metadata may store the scheduler decision where provider/model metadata is already stored.
- REQ-5.3: Scheduler metadata must be additive to existing translation metadata.
- REQ-5.4: Existing translation versions without scheduler metadata must remain loadable.
- REQ-5.5: Scheduler metadata must not duplicate prompt text, source text, or translated text.
- REQ-5.6: Scheduler metadata must remain compact enough for existing metadata storage.

### REQ-6: Aggregate Scheduler Summary in Activity Metadata

Translation activities must expose a compact scheduler summary.

- REQ-6.1: Activity metadata should include `scheduler_summary` when translation scheduler decisions are recorded.
- REQ-6.2: Summary must include `chapters_with_decisions`.
- REQ-6.3: Summary must include `fallback_count`.
- REQ-6.4: Summary must include `no_capacity_count`.
- REQ-6.5: Summary must include `skip_reason_counts`.
- REQ-6.6: Summary must include `selected_model_counts`.
- REQ-6.7: Summary should include `provider_counts`.
- REQ-6.8: Summary should include quota/cooldown-related counts.
- REQ-6.9: Summary should include checkpoint/resume counts when available.
- REQ-6.10: Summary should include memory-pressure counts when available.
- REQ-6.11: Summary updates must be safe under chapter parallelization.
- REQ-6.12: Legacy activity records without scheduler summaries must remain loadable.

### REQ-7: Preserve Checkpoint and Resume Semantics

Scheduler observability must align with existing checkpoint/resume behavior.

- REQ-7.1: Observability must not change checkpoint write timing.
- REQ-7.2: Observability must not change resume eligibility.
- REQ-7.3: A resumed chapter should preserve prior scheduler decision metadata when already recorded.
- REQ-7.4: A new provider/model selection after resume must create a new decision record.
- REQ-7.5: Decision records should include checkpoint references when available.
- REQ-7.6: Activity summaries should count resumed work when existing metadata supports it.
- REQ-7.7: Checkpoint-blocked states should use `checkpoint_blocked`.

### REQ-8: Support Chapter Parallelization Safely

Scheduler metadata must be safe when chapters are translated concurrently.

- REQ-8.1: Each decision record must be tied to a stable chapter identity where available.
- REQ-8.2: Parallel workers must not overwrite each other’s scheduler metadata.
- REQ-8.3: Aggregation must be concurrency-safe.
- REQ-8.4: Duplicate attempts for the same chapter must be distinguishable by attempt number, request ID, or job ID when available.
- REQ-8.5: Activity summaries must aggregate by decision/attempt rather than using lossy chapter-only keys when retries or resumes occur.
- REQ-8.6: Observability must not change chapter parallelization limits or scheduling behavior.

### REQ-9: Surface Exact Memory State When Available

Scheduler observability should reuse existing memory tracking.

- REQ-9.1: If exact memory tracking already exists, decision records should include current exact memory values when available.
- REQ-9.2: Memory metadata may include `exact_memory_bytes`.
- REQ-9.3: Memory metadata may include `memory_limit_bytes`.
- REQ-9.4: Memory metadata may include `memory_pressure`.
- REQ-9.5: Activity summary should include `peak_exact_memory_bytes` when available.
- REQ-9.6: Activity summary should include `memory_pressure_count` when available.
- REQ-9.7: Activity summary should include `memory_blocked_count` when available.
- REQ-9.8: Do not add a second memory accounting system.
- REQ-9.9: Do not change memory guard behavior.

### REQ-10: Expose Scheduler Health in Admin APIs

Admins must be able to inspect provider/model runtime health.

- REQ-10.1: Scheduler health must be exposed through an existing admin operations route when practical.
- REQ-10.2: If no suitable admin route exists, add a narrowly scoped admin-only scheduler health route.
- REQ-10.3: Health response must include provider and model.
- REQ-10.4: Health response must include status.
- REQ-10.5: Health response should include RPM limit and requests this minute when available.
- REQ-10.6: Health response should include RPD limit and requests today when available.
- REQ-10.7: Health response should include cooldown until when available.
- REQ-10.8: Health response should include exhausted until when available.
- REQ-10.9: Health response should include failed at when available.
- REQ-10.10: Health response should include safe last error code when available.
- REQ-10.11: Health response must not expose secrets.
- REQ-10.12: Public APIs must not expose scheduler health.

### REQ-11: Expose Scheduler Metadata in Admin Translation APIs

Admin APIs must make scheduler routing decisions visible in translation activity and chapter/version review.

- REQ-11.1: Translation activity detail response must include scheduler summary when available.
- REQ-11.2: Translation job dashboard response should include scheduler summary when available.
- REQ-11.3: Chapter/version translation detail must include selected provider/model when available.
- REQ-11.4: Chapter/version translation detail should include fallback state when available.
- REQ-11.5: Chapter/version translation detail should include compact skipped candidate summary when available.
- REQ-11.6: Chapter/version translation detail should include request ID/job ID when available.
- REQ-11.7: Novel translation summary may include fallback, cooldown, quota, memory, and no-capacity counts.
- REQ-11.8: Response changes must be additive.
- REQ-11.9: Strict response models must be updated if they would otherwise drop new fields.
- REQ-11.10: Legacy records without scheduler metadata must show `null`, omitted fields, or `not_available` according to existing API style.

### REQ-12: Admin UI Visibility

Admin UI must show scheduler routing outcomes and provider health.

- REQ-12.1: Translation activity UI must show selected model counts.
- REQ-12.2: Translation activity UI must show provider counts.
- REQ-12.3: Translation activity UI must show fallback count.
- REQ-12.4: Translation activity UI must show skip reason counts.
- REQ-12.5: Translation activity UI should show cooldown and quota counts.
- REQ-12.6: Translation activity UI should show memory pressure counts when available.
- REQ-12.7: Translation activity UI should show checkpoint/resume counts when available.
- REQ-12.8: Chapter/version UI should show selected provider/model.
- REQ-12.9: Chapter/version UI should show fallback state and skipped candidate reasons.
- REQ-12.10: Chapter/version UI should show request ID/job ID where useful.
- REQ-12.11: Provider/model health UI should show cooldown, exhausted, failed, quota, and healthy states.
- REQ-12.12: UI must not expose secrets.

### REQ-13: Failure and Fallback Visibility

Scheduler failures must be visible and diagnosable.

- REQ-13.1: When no provider/model is available, record `selected: null`.
- REQ-13.2: No-capacity decisions must include `failure_reason: "no_capacity"`.
- REQ-13.3: When fallback happens, record candidates skipped before final selection.
- REQ-13.4: When provider failure marks a model failed, cooling down, or exhausted, expose the safe resulting state where scheduler code already records it.
- REQ-13.5: Translation activity errors related to model availability should include a safe scheduler summary.
- REQ-13.6: Scheduler observability must not swallow, mask, or replace existing translation errors.
- REQ-13.7: Scheduler observability must not retry or reroute independently of existing scheduler policy.

### REQ-14: Bounded and Safe Metadata

Scheduler metadata must be safe and reasonably small.

- REQ-14.1: Candidate decision lists must be bounded by a constant such as `MAX_SCHEDULER_DECISION_CANDIDATES`.
- REQ-14.2: Candidate truncation must be explicit in metadata.
- REQ-14.3: Use machine-readable reason codes instead of long free-form error strings.
- REQ-14.4: Redact provider secrets.
- REQ-14.5: Redact account identifiers.
- REQ-14.6: Do not store prompts.
- REQ-14.7: Do not store source text.
- REQ-14.8: Do not store translated text inside scheduler metadata.
- REQ-14.9: Store safe `last_error_code`, not full exception traces.
- REQ-14.10: Keep activity summaries compact.

### REQ-15: Backward Compatibility

Existing scheduler and translation behavior must remain compatible.

- REQ-15.1: Model selection order must not change.
- REQ-15.2: Provider routing policy must not change.
- REQ-15.3: Quota and cooldown behavior must not change.
- REQ-15.4: Checkpoint/resume behavior must not change.
- REQ-15.5: Chapter parallelization behavior must not change.
- REQ-15.6: Memory guard behavior must not change.
- REQ-15.7: Existing translation flows must work when observability metadata is absent.
- REQ-15.8: Existing translation versions must remain loadable.
- REQ-15.9: Existing activity records must remain loadable.
- REQ-15.10: Existing provider/model config formats must remain supported.
- REQ-15.11: Public reader behavior must not change.

### REQ-16: Tests

Create `backend/tests/test_translation_scheduler_observability.py`.

- REQ-16.1: Test selected model decision is recorded.
- REQ-16.2: Test decision includes request ID, job ID, and chapter ID when available.
- REQ-16.3: Test cooldown candidate skip reason is recorded.
- REQ-16.4: Test RPM limit skip reason is recorded.
- REQ-16.5: Test RPD limit skip reason is recorded.
- REQ-16.6: Test quota/exhausted skip reason is recorded.
- REQ-16.7: Test memory pressure skip reason is recorded when memory guard state exists.
- REQ-16.8: Test checkpoint blocked skip reason is recorded when checkpoint state blocks execution.
- REQ-16.9: Test fallback selection records skipped candidates.
- REQ-16.10: Test no-capacity failure records `selected=null` and `failure_reason="no_capacity"`.
- REQ-16.11: Test candidate list is bounded and truncation metadata is recorded.
- REQ-16.12: Test parallel chapter decisions do not overwrite each other.
- REQ-16.13: Test resumed translation preserves or records scheduler decision metadata.
- REQ-16.14: Test per-chapter translation metadata includes scheduler decision.
- REQ-16.15: Test activity metadata includes aggregate scheduler summary.
- REQ-16.16: Test scheduler summary counts selected models.
- REQ-16.17: Test scheduler summary counts skip reasons.
- REQ-16.18: Test scheduler health API excludes secrets.
- REQ-16.19: Test legacy translations without scheduler metadata still load.
- REQ-16.20: Add frontend tests for UI rendering if frontend code changes.
- REQ-16.21: Tests must not call live translation providers.

## Non-Goals

- This spec does not redesign the scheduling algorithm.
- This spec does not change model priority or provider routing.
- This spec does not change provider quota policy.
- This spec does not change cooldown behavior.
- This spec does not change checkpoint/resume behavior.
- This spec does not change chapter parallelization behavior.
- This spec does not change memory guard behavior.
- This spec does not add provider billing integration.
- This spec does not expose scheduler health publicly.
- This spec does not implement distributed metrics storage.
- This spec does not change prompt construction.
- This spec does not change glossary behavior.
- This spec does not change public reader behavior.
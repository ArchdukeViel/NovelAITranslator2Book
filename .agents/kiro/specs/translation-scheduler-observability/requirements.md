# Requirements: Translation Scheduler Observability

## Introduction

The translation backend has scheduler-aware provider/model routing. The deep research reports found that scheduler state includes runtime limits and health fields such as RPM/RPD limits, requests this minute/day, cooldown, exhausted state, failed timestamp, last error code, and status. However, those decisions are not clearly surfaced to admins or captured in translation activity metadata.

This spec makes translation scheduler decisions observable. The goal is to explain which model was selected, which candidates were skipped, why fallback happened, and what provider/model health looked like at selection time.

## Requirements

### REQ-1: Record Scheduler Selection Decisions

Every translation model selection should produce a compact decision record.

- REQ-1.1: Record the selected provider and model.
- REQ-1.2: Record the scheduler policy used for selection.
- REQ-1.3: Record all candidate provider/model configs considered, or a bounded summary if the list is large.
- REQ-1.4: For each skipped candidate, record a machine-readable skip reason.
- REQ-1.5: Record whether the selected model is a fallback after one or more candidates were skipped.
- REQ-1.6: Record selection timestamp.
- REQ-1.7: Do not record provider API keys or sensitive configuration.

### REQ-2: Standardize Skip Reasons

Scheduler skip/fallback reasons must use stable codes.

- REQ-2.1: Include `cooldown_active` when a model is cooling down.
- REQ-2.2: Include `quota_exhausted` when daily or provider quota is exhausted.
- REQ-2.3: Include `rpm_limited` when minute rate limit prevents selection.
- REQ-2.4: Include `rpd_limited` when daily request limit prevents selection.
- REQ-2.5: Include `disabled` when a model/provider is disabled by config.
- REQ-2.6: Include `previously_attempted` when excluded by attempted model history.
- REQ-2.7: Include `unhealthy` when model status prevents selection.
- REQ-2.8: Include `no_capacity` when no known candidate is currently available.
- REQ-2.9: Include `unknown` for unexpected cases.

### REQ-3: Persist Decision Records in Translation Metadata

Scheduler decisions must survive beyond logs.

- REQ-3.1: Persist per-chapter scheduler decision metadata when translation runs.
- REQ-3.2: Persist aggregate scheduler summary in translation activity metadata when practical.
- REQ-3.3: Persist decision metadata in a bounded form to avoid oversized activity records.
- REQ-3.4: Decision metadata must be additive to existing translation version/activity metadata.
- REQ-3.5: Existing translation records without scheduler metadata must remain loadable.

### REQ-4: Expose Scheduler Health in Admin APIs

Admins must be able to inspect provider/model runtime health.

- REQ-4.1: Expose provider/model scheduler health through an existing admin route or a new narrowly scoped admin route.
- REQ-4.2: Health response must include provider, model, status, RPM limit, RPD limit, requests this minute, requests today, cooldown until, exhausted until, failed at, and last error code when available.
- REQ-4.3: Health response must not expose secrets.
- REQ-4.4: If strict response models are used, update them so new fields are not dropped.
- REQ-4.5: Public APIs must not expose scheduler health.

### REQ-5: Expose Scheduler Decisions in Admin Activity/Translation APIs

Admin APIs must make routing decisions visible in translation activity and chapter/version review.

- REQ-5.1: Translation activity detail response must include scheduler summary when available.
- REQ-5.2: Chapter/version translation metadata must include selected provider/model and skip/fallback summary when available.
- REQ-5.3: Novel translation summary may include counts of fallback selections, cooldown skips, quota skips, and failed selections.
- REQ-5.4: Response changes must be additive.
- REQ-5.5: Legacy translation records without scheduler metadata must show "not available" rather than failing.

### REQ-6: Admin UI Visibility

Admin UI must show scheduler routing outcomes and provider health.

- REQ-6.1: Translation activity UI must show selected provider/model summary.
- REQ-6.2: Translation activity UI must show fallback count.
- REQ-6.3: Translation activity UI must show skip reason counts.
- REQ-6.4: Chapter/version UI should show selected provider/model for that translation.
- REQ-6.5: Provider/model health UI should show cooldown, exhausted, failed, and healthy states.
- REQ-6.6: UI must not expose secrets.

### REQ-7: Failure and Fallback Visibility

Scheduler failures must be visible and diagnosable.

- REQ-7.1: When no provider/model is available, record a decision record with `selected=null` and reason `no_capacity`.
- REQ-7.2: When fallback happens, record the candidates skipped before the final selection.
- REQ-7.3: When provider call failure marks a model failed/cooling down/exhausted, record the state transition where current scheduler code already handles it.
- REQ-7.4: Translation activity errors should include a safe scheduler summary when failure is related to model availability.
- REQ-7.5: Scheduler observability must not swallow or mask existing translation errors.

### REQ-8: Bounded and Safe Metadata

Scheduler metadata must be safe and reasonably small.

- REQ-8.1: Bound candidate decision lists to a safe maximum.
- REQ-8.2: Use machine-readable reason codes instead of long free-form error strings where possible.
- REQ-8.3: Redact provider secrets and account identifiers.
- REQ-8.4: Avoid storing full prompts or translated content in scheduler metadata.
- REQ-8.5: Store only safe `last_error_code`, not full provider exception traces, unless existing admin error handling already redacts them.

### REQ-9: Backward Compatibility

Existing scheduler and translation behavior must remain compatible.

- REQ-9.1: Model selection order and policy must not change except for instrumentation.
- REQ-9.2: Existing translation flows must work when observability metadata is absent.
- REQ-9.3: Existing activity records must remain loadable.
- REQ-9.4: Existing provider/model config formats must remain supported.
- REQ-9.5: No public reader behavior changes are allowed.

### REQ-10: Tests

Focused tests must prove decision recording and health exposure.

- REQ-10.1: Test selected model decision is recorded.
- REQ-10.2: Test cooldown candidate skip reason is recorded.
- REQ-10.3: Test RPM/RPD limit skip reasons are recorded.
- REQ-10.4: Test quota/exhausted skip reason is recorded.
- REQ-10.5: Test fallback selection records skipped candidates.
- REQ-10.6: Test no-capacity failure records `selected=null` and `no_capacity`.
- REQ-10.7: Test activity metadata includes aggregate scheduler summary.
- REQ-10.8: Test admin scheduler health API excludes secrets.
- REQ-10.9: Test legacy translations without scheduler metadata still load.
- REQ-10.10: Test UI rendering if frontend is changed.

## Non-Goals

- This spec does not redesign the scheduling algorithm.
- This spec does not change provider quota policy.
- This spec does not add provider billing integration.
- This spec does not expose scheduler health publicly.
- This spec does not implement distributed metrics storage.
- This spec does not change prompt construction or glossary behavior.


# Requirements: Translation Integration Regression Suite

## Introduction

The backend translation pipeline crosses several high-risk boundaries: onboarding/readiness state, crawl/raw chapter storage, glossary gating, prompt construction, scheduler/provider selection, translation execution, cache identity, versioned storage, activity metadata, admin review, public reader availability, and failure handling.

A basic integration suite may already exist, so this spec should not duplicate broad end-to-end coverage. Instead, it defines an expanded deterministic regression suite for the translation backend and related specs. The suite must exercise real orchestration and storage seams where practical while replacing external systems with fakes.

No test may call live LLM providers, real source websites, real object storage services, or public network services.

## Requirements

### REQ-1: Core Translation Storage Regression

The suite must verify the happy path from synthetic raw chapter storage to saved translated version.

- REQ-1.1: Create a synthetic novel fixture with metadata and at least two chapters.
- REQ-1.2: Include at least one raw chapter bundle.
- REQ-1.3: Run the normal translation orchestration path, not only isolated stage functions.
- REQ-1.4: Use a deterministic fake provider/model response.
- REQ-1.5: Assert translated chapter text is saved.
- REQ-1.6: Assert a translation version is created.
- REQ-1.7: Assert version list includes the new version.
- REQ-1.8: Assert active version selection follows existing storage behavior.
- REQ-1.9: Assert provider/model metadata is saved where existing behavior supports it.
- REQ-1.10: Assert existing translation versions remain loadable after the test setup writes new versions.

### REQ-2: Glossary Gate and Prompt Injection Regression

The suite must prove glossary behavior works across the full translation path.

- REQ-2.1: Test translation is blocked when glossary gate is pending and bypass is not enabled.
- REQ-2.2: Test translation proceeds when glossary is ready.
- REQ-2.3: Test `skip_glossary_gate` preserves existing bypass behavior where supported.
- REQ-2.4: Test approved glossary terms are included in fake provider request prompts.
- REQ-2.5: Test pending glossary terms are not injected as approved terms.
- REQ-2.6: Test prompt glossary block and chunk glossary entries do not cause duplicated conflicting prompt sections.
- REQ-2.7: Test glossary revision/hash metadata reaches translation context or version metadata when implemented.
- REQ-2.8: Tests must not change glossary review workflow or glossary approval rules.

### REQ-3: JP-EN Prompt Policy Regression

The suite must protect Japanese-to-English prompt quality behavior through prompt/request assertions.

- REQ-3.1: Test JP-EN prompt includes the quality policy when source language is Japanese and target language is English.
- REQ-3.2: Test non-JP-EN prompt does not include JP-EN-specific policy by default.
- REQ-3.3: Test glossary compliance instructions remain present.
- REQ-3.4: Test honorific policy instructions render for supported modes.
- REQ-3.5: Test ambiguity and omitted-subject instructions remain present.
- REQ-3.6: Test dialogue/register instructions remain present.
- REQ-3.7: Test chapter title/body separation instructions remain present.
- REQ-3.8: Test JSON-mode prompt/request shape supports optional review metadata when parser support exists.
- REQ-3.9: Tests must assert prompt/request shape only, not live translation quality.

### REQ-4: Scheduler Selection and Observability Regression

The suite must verify scheduler-aware model selection inside translation orchestration.

- REQ-4.1: Test scheduler selects the primary available model.
- REQ-4.2: Test scheduler falls back when the primary model is cooling down.
- REQ-4.3: Test scheduler falls back when the primary model is quota-exhausted.
- REQ-4.4: Test RPM-limited and RPD-limited candidates produce stable skip reasons when supported.
- REQ-4.5: Test all-unavailable/no-capacity state records a safe failure.
- REQ-4.6: Test selected provider/model metadata reaches translation result or activity metadata.
- REQ-4.7: Test scheduler decision metadata includes stable skip reason codes when implemented.
- REQ-4.8: Test scheduler summary is written to activity metadata when implemented.
- REQ-4.9: Test request ID, job ID, and chapter ID are preserved where available.
- REQ-4.10: Test candidate lists are bounded and secrets are redacted when scheduler observability is implemented.
- REQ-4.11: Tests must not change scheduler policy, model order, quota behavior, or cooldown behavior.

### REQ-5: Translation Cache Identity Regression

The suite must validate cache behavior at integration seams.

- REQ-5.1: Test repeated translation can reuse cache when source text, model, prompt policy, and glossary state are unchanged.
- REQ-5.2: Test force/retranslate mode bypasses cache where existing behavior specifies it.
- REQ-5.3: Test cache key changes when model changes.
- REQ-5.4: Test cache key changes when provider changes.
- REQ-5.5: Test cache key changes when prompt policy/template identity changes, if prompt policy versioning exists.
- REQ-5.6: Test cache key changes when glossary revision/hash changes, if glossary revision invalidation exists.
- REQ-5.7: Test legacy cache entries without glossary identity are not reused for non-zero glossary revision when glossary-aware cache identity exists.

### REQ-6: Versioning and Retranslation Regression

The suite must validate translated version storage behavior.

- REQ-6.1: Test first translation creates an initial version.
- REQ-6.2: Test retranslation creates a new version rather than overwriting the old version.
- REQ-6.3: Test historical versions remain listable after retranslation.
- REQ-6.4: Test active version selection follows existing behavior.
- REQ-6.5: Test version metadata includes provider, model, timestamps, and policy metadata where storage supports them.
- REQ-6.6: Test failed retranslation does not overwrite or delete the active version.
- REQ-6.7: Test old versions remain available for admin comparison.

### REQ-7: Glossary Revision Invalidation Regression

The suite must cover stale glossary translation behavior when the invalidation spec is implemented.

- REQ-7.1: Test translation version stores glossary revision when available.
- REQ-7.2: Test translation version stores glossary hash when available.
- REQ-7.3: Test active version becomes stale after glossary revision increments.
- REQ-7.4: Test historical versions compute freshness independently.
- REQ-7.5: Test legacy versions without glossary metadata remain loadable.
- REQ-7.6: Test retranslate-stale creates a new fresh version.
- REQ-7.7: Test stale detection does not deactivate active version.
- REQ-7.8: Test old stale versions remain available for comparison.
- REQ-7.9: These assertions may be conditional until glossary revision invalidation has landed.

### REQ-8: Crawl/Fetch Observability Regression

The suite must verify crawl/fetch observability behavior without real HTTP.

- REQ-8.1: Use a fake source adapter or fake fetch service.
- REQ-8.2: Test successful fake crawl writes raw chapter data needed by translation.
- REQ-8.3: Test crawl activity persists `metadata.crawl_result` when implemented.
- REQ-8.4: Test per-chapter crawl failures include safe error category, HTTP status, and retry attempt fields when implemented.
- REQ-8.5: Test running crawl progress updates `metadata.progress` when implemented.
- REQ-8.6: Test source health aggregates stored crawl results when implemented.
- REQ-8.7: Test image download failures are counted by affected chapter count when implemented.
- REQ-8.8: Test crawl observability metadata does not break onboarding or translation readiness state.

### REQ-9: Public Reader Availability Regression

The suite must verify public reader behavior for translated and untranslated chapters.

- REQ-9.1: Test default `hard_404` returns HTTP 404 for missing active translation.
- REQ-9.2: Test `chapter_shell` returns HTTP 200 with `text: null` and `availability_status: "not_translated"` when configured.
- REQ-9.3: Test `latest_version` returns newest saved version when active version is missing and policy is configured.
- REQ-9.4: Test active version is always preferred when present.
- REQ-9.5: Test owner can preview a specific `version_id` when authenticated.
- REQ-9.6: Test public unauthenticated `version_id` is ignored.
- REQ-9.7: Test public chapter list includes additive `availability_status`.
- REQ-9.8: Test public reader responses do not expose admin-only glossary, scheduler, or QA metadata.

### REQ-10: Editor QA and Glossary Resolution Regression

The suite should cover editor QA glossary behavior when implemented.

- REQ-10.1: Test editor QA resolves approved glossary terms against the current glossary revision.
- REQ-10.2: Test stale translation version is flagged when glossary revision changes.
- REQ-10.3: Test pending terms are not treated as approved.
- REQ-10.4: Test approved-term suggestions preserve configured casing and spelling.
- REQ-10.5: Test QA metadata remains admin/editor-only.
- REQ-10.6: Test public reader output is unaffected.
- REQ-10.7: These assertions may be conditional until glossary-aware editor QA has landed.

### REQ-11: Failure and Partial Success Regression

The suite must cover important failure paths.

- REQ-11.1: Test missing raw chapter produces a clear per-chapter failure or preflight issue.
- REQ-11.2: Test provider failure is recorded.
- REQ-11.3: Test provider failure does not corrupt existing translation versions.
- REQ-11.4: Test provider failure does not create an active partial version.
- REQ-11.5: Test one failed chapter does not erase successful chapter translations when partial success is supported.
- REQ-11.6: Test fatal translation activity records top-level error metadata.
- REQ-11.7: Test scheduler no-capacity failure does not corrupt activity metadata.
- REQ-11.8: Test failed retranslation preserves active version state.

### REQ-12: Activity Metadata Regression

The suite must assert useful activity-level output.

- REQ-12.1: Test translation activity metadata includes translated, skipped, and failed counts if existing activity flow records them.
- REQ-12.2: Test activity metadata includes per-chapter failures or summary where supported.
- REQ-12.3: Test glossary diagnostics summary is included when glossary diagnostics is implemented.
- REQ-12.4: Test scheduler summary is included when scheduler observability is implemented.
- REQ-12.5: Test crawl/fetch activity metadata is not overwritten by later translation metadata.
- REQ-12.6: Optional metadata assertions must be gated until the related specs have landed.
- REQ-12.7: Once a related spec has landed, its assertions must become strict regression tests.

### REQ-13: Fixture and Fake Infrastructure

The suite must include reusable deterministic fixtures.

- REQ-13.1: Add fixture for synthetic novel metadata.
- REQ-13.2: Add fixture for raw chapter bundles.
- REQ-13.3: Add fixture for approved and pending glossary entries.
- REQ-13.4: Add deterministic fake translation provider.
- REQ-13.5: Add fake provider failure modes for rate-limit, quota, timeout, and generic errors where scheduler/orchestration supports them.
- REQ-13.6: Add fake scheduler state fixtures for primary available, fallback, cooldown, quota-exhausted, RPM/RPD-limited, all-unavailable, memory-pressure, and checkpoint-blocked states where supported.
- REQ-13.7: Add fake crawl adapter or fake fetch service fixtures.
- REQ-13.8: Add public reader fixtures for active, untranslated, latest-version, owner-auth, and public requests.
- REQ-13.9: Add helper to inspect saved translation versions.
- REQ-13.10: Add helper to inspect fake provider requests.
- REQ-13.11: Fixtures must be reusable by future translation specs.

### REQ-14: Test Isolation and Determinism

Integration tests must be reliable and fast.

- REQ-14.1: Tests must use temporary storage directories.
- REQ-14.2: Tests must use isolated test database/session fixtures.
- REQ-14.3: Tests must use fake provider/model clients.
- REQ-14.4: Tests must not perform network calls.
- REQ-14.5: Tests must not call real source websites.
- REQ-14.6: Tests must not call real object storage services.
- REQ-14.7: Tests must not depend on wall-clock timing except controlled or frozen timestamps.
- REQ-14.8: Tests must reset scheduler runtime state between cases.
- REQ-14.9: Tests must reset glossary revision/cache state between cases.
- REQ-14.10: Tests must use synthetic content only.
- REQ-14.11: Tests must not depend on test execution order.

### REQ-15: Dependency Injection and Production Compatibility

The suite must not require functional production behavior changes beyond making seams testable.

- REQ-15.1: Use existing provider factory override or provider registry injection where available.
- REQ-15.2: Use existing source adapter registry injection where available.
- REQ-15.3: Use existing storage backend test fixtures where available.
- REQ-15.4: Use dependency overrides for admin/owner auth where available.
- REQ-15.5: If dependency injection seams are missing, add minimal optional parameters that default to current production behavior.
- REQ-15.6: Production defaults must not change.
- REQ-15.7: Existing translation APIs must remain unchanged.
- REQ-15.8: Existing storage behavior must remain unchanged.
- REQ-15.9: Existing unit tests must continue to pass.

### REQ-16: Conditional Assertions

The suite must support specs landing in stages without hiding completed regressions.

- REQ-16.1: Core translation storage assertions must be mandatory.
- REQ-16.2: Already-landed spec assertions must be strict.
- REQ-16.3: Not-yet-landed observability or metadata fields may use conditional assertions temporarily.
- REQ-16.4: Conditional assertion helpers must explicitly document why a field is optional.
- REQ-16.5: Once a related spec lands, conditional assertions for that spec must be converted to strict assertions.
- REQ-16.6: Optional fields must not silently disappear after completion.

### REQ-17: Test Commands

The suite must be runnable independently and with related regression tests.

- REQ-17.1: Add focused test command documentation:
  - `pytest backend/tests/test_translation_integration_regression.py --tb=short -q`
- REQ-17.2: Document related backend commands:
  - `pytest backend/tests/test_translation*.py --tb=short -q`
  - `pytest backend/tests/test_public_reader_availability.py --tb=short -q`
  - `pytest backend/tests/test_glossary_revision_translation_invalidation.py --tb=short -q`
  - `pytest backend/tests/test_translation_scheduler_observability.py --tb=short -q`
  - `pytest backend/tests/test_crawl_fetch_observability.py --tb=short -q`
- REQ-17.3: Run lint and type checks on changed test helpers and production injection seams.

## Non-Goals

- This spec does not call live LLM providers.
- This spec does not call real crawler websites.
- This spec does not call real object storage services.
- This spec does not evaluate literary translation quality with an LLM judge.
- This spec does not replace unit tests for individual stages.
- This spec does not replace existing broad E2E tests.
- This spec does not change scheduler policy, prompt policy, glossary behavior, or storage schemas.
- This spec does not change public reader rendering behavior.
- This spec does not require browser/UI tests.
- This spec does not add production behavior except minimal dependency-injection seams required for deterministic tests.
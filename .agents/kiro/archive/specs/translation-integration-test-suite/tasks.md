# Tasks: Translation Integration Regression Suite

## Overview

Add an expanded deterministic backend regression suite for the translation pipeline and related translation-facing specs.

This suite should exercise real orchestration and storage seams where practical, while replacing external systems with deterministic fakes. It must not duplicate broad E2E coverage or change production behavior beyond minimal dependency-injection seams needed for tests.

Scope boundaries:

- No live LLM/provider calls.
- No real crawler website calls.
- No real object storage calls.
- No browser/UI tests required.
- No scheduler policy changes.
- No glossary workflow changes.
- No prompt policy changes.
- No storage schema changes.
- No public reader rendering changes.
- Production defaults must remain unchanged.

## Task List

- [x] 1. Preflight Translation Regression Coverage
  - [x] 1.1 Inspect `OperationsService.translate_novel`.
  - [x] 1.2 Inspect `NovelOrchestrationService.translate_chapters`.
  - [x] 1.3 Inspect `TranslationService` stage pipeline.
  - [x] 1.4 Inspect provider/model factory or registry injection seams.
  - [x] 1.5 Inspect scheduler fixtures and existing scheduler tests.
  - [x] 1.6 Inspect translation cache helpers and cache-key dimensions.
  - [x] 1.7 Inspect translation storage version helpers.
  - [x] 1.8 Inspect glossary gate/preflight tests.
  - [x] 1.9 Inspect JP-EN prompt tests and prompt builder fixtures.
  - [x] 1.10 Inspect crawl/fetch test fixtures and source adapter seams.
  - [x] 1.11 Inspect public reader availability tests and auth overrides.
  - [x] 1.12 Inspect glossary revision invalidation tests if implemented.
  - [x] 1.13 Inspect editor QA/glossary resolution tests if implemented.
  - [x] 1.14 Inspect existing `conftest.py`, storage fixtures, DB fixtures, and activity fixtures.
  - [x] 1.15 Identify which related specs have already landed and must use strict assertions.

- [x] 2. Add Integration Regression Test Module
  - [x] 2.1 Create `backend/tests/test_translation_integration_regression.py`.
  - [x] 2.2 Mark tests as integration/regression tests if the repository uses pytest markers.
  - [x] 2.3 Ensure focused command works:
    - `pytest backend/tests/test_translation_integration_regression.py --tb=short -q`
  - [x] 2.4 Keep the suite deterministic and independent from test order.
  - [x] 2.5 Keep existing integration tests intact.

- [x] 3. Add Synthetic Novel and Storage Fixtures
  - [x] 3.1 Add or reuse fixture for temporary storage root.
  - [x] 3.2 Add or reuse fixture for isolated test DB/session.
  - [x] 3.3 Add fixture for synthetic novel metadata.
  - [x] 3.4 Include source language `ja`.
  - [x] 3.5 Include target language `en`.
  - [x] 3.6 Include public slug.
  - [x] 3.7 Include at least two chapters.
  - [x] 3.8 Add fixture for one raw chapter bundle.
  - [x] 3.9 Add fixture for multiple raw chapters.
  - [x] 3.10 Add helper to inspect saved translation versions.
  - [x] 3.11 Add helper to inspect active translated chapter output.
  - [x] 3.12 Use synthetic content only.

- [x] 4. Add Glossary Fixtures
  - [x] 4.1 Add approved glossary entries fixture.
  - [x] 4.2 Add pending glossary entries fixture.
  - [x] 4.3 Add helper for glossary-ready novel state.
  - [x] 4.4 Add helper for glossary-pending novel state.
  - [x] 4.5 Add helper to increment glossary revision where existing behavior supports it.
  - [x] 4.6 Add helper for legacy translation versions without glossary metadata.
  - [x] 4.7 Add helper to inspect prompt glossary block in fake provider requests.
  - [x] 4.8 Ensure pending terms are distinguishable from approved terms.

- [x] 5. Add Deterministic Fake Translation Provider
  - [x] 5.1 Add fake provider that returns configured translated text.
  - [x] 5.2 Ensure fake provider records every request.
  - [x] 5.3 Record prompt text/request payload for assertions.
  - [x] 5.4 Record provider/model identity.
  - [x] 5.5 Record JSON mode request shape where available.
  - [x] 5.6 Add fake rate-limit failure mode.
  - [x] 5.7 Add fake quota failure mode.
  - [x] 5.8 Add fake timeout failure mode where orchestration supports it.
  - [x] 5.9 Add fake generic provider failure mode.
  - [x] 5.10 Ensure fake provider never performs network calls.

- [x] 6. Add Provider and Scheduler Injection Fixtures
  - [x] 6.1 Use existing provider factory override if available.
  - [x] 6.2 Use existing provider registry override if available.
  - [x] 6.3 If needed, add a minimal optional provider factory parameter with production default unchanged.
  - [x] 6.4 Add scheduler state fixture for primary available model.
  - [x] 6.5 Add scheduler state fixture for primary cooldown state.
  - [x] 6.6 Add scheduler state fixture for primary quota-exhausted state.
  - [x] 6.7 Add scheduler state fixture for RPM-limited state where supported.
  - [x] 6.8 Add scheduler state fixture for RPD-limited state where supported.
  - [x] 6.9 Add scheduler state fixture for fallback available model.
  - [x] 6.10 Add scheduler state fixture for all-unavailable/no-capacity state.
  - [x] 6.11 Add scheduler state fixture for memory-pressure state where supported.
  - [x] 6.12 Add scheduler state fixture for checkpoint-blocked state where supported.
  - [x] 6.13 Reset scheduler runtime state between tests.

- [x] 7. Add Fake Crawl and Reader Fixtures
  - [x] 7.1 Add fake source adapter or fake fetch service fixture.
  - [x] 7.2 Fake successful metadata discovery.
  - [x] 7.3 Fake successful raw chapter fetch.
  - [x] 7.4 Fake partial chapter fetch failure.
  - [x] 7.5 Fake retryable fetch failure.
  - [x] 7.6 Fake image download failure metadata where supported.
  - [x] 7.7 Add public reader fixture for published novel.
  - [x] 7.8 Add public reader fixture for active translated chapter.
  - [x] 7.9 Add public reader fixture for untranslated chapter.
  - [x] 7.10 Add public reader fixture for saved non-active translation version.
  - [x] 7.11 Add owner-authenticated request override.
  - [x] 7.12 Add public unauthenticated request helper.

- [x] 8. Add Conditional Assertion Helpers
  - [x] 8.1 Add helper for optional field assertions.
  - [x] 8.2 Require strict assertions for completed specs.
  - [x] 8.3 Allow temporary conditional assertions only for not-yet-landed metadata fields.
  - [x] 8.4 Document why each conditional assertion is optional.
  - [x] 8.5 Add TODO markers or comments identifying when conditional assertions must become strict.
  - [x] 8.6 Ensure completed optional fields cannot silently disappear.

- [x] 9. Write Core Translation Storage Regression Tests
  - [x] 9.1 Run normal translation orchestration path.
  - [x] 9.2 Assert fake provider was called.
  - [x] 9.3 Assert translated chapter text is saved.
  - [x] 9.4 Assert translation version is created.
  - [x] 9.5 Assert version list includes the new version.
  - [x] 9.6 Assert active version loads expected text.
  - [x] 9.7 Assert active-version behavior follows existing storage rules.
  - [x] 9.8 Assert provider/model metadata is saved where supported.
  - [x] 9.9 Assert existing versions remain loadable after new version writes.

- [x] 10. Write Glossary Gate and Prompt Injection Tests
  - [x] 10.1 Test pending glossary blocks translation without bypass.
  - [x] 10.2 Test glossary-ready state allows translation.
  - [x] 10.3 Test `skip_glossary_gate` preserves existing bypass behavior where supported.
  - [x] 10.4 Assert approved glossary terms appear in fake provider prompt/request.
  - [x] 10.5 Assert pending terms are not injected as approved terms.
  - [x] 10.6 Assert prompt glossary block and chunk glossary entries do not duplicate conflicting sections.
  - [x] 10.7 Assert glossary revision/hash metadata reaches context or version metadata when implemented.
  - [x] 10.8 Confirm tests do not alter glossary approval rules.

- [x] 11. Write JP-EN Prompt Policy Regression Tests
  - [x] 11.1 Test JP-EN prompt includes quality policy instructions.
  - [x] 11.2 Test non-JP-EN prompt does not include JP-EN-specific policy by default.
  - [x] 11.3 Test glossary compliance instructions remain present.
  - [x] 11.4 Test honorific policy instructions render for supported modes.
  - [x] 11.5 Test ambiguity and omitted-subject instructions remain present.
  - [x] 11.6 Test dialogue/register instructions remain present.
  - [x] 11.7 Test chapter title/body separation instructions remain present.
  - [x] 11.8 Test JSON-mode prompt/request shape supports optional review metadata when parser support exists.
  - [x] 11.9 Assert prompt/request shape only, not live translation quality.

- [x] 12. Write Scheduler Selection and Observability Tests
  - [x] 12.1 Test primary available model is selected.
  - [x] 12.2 Test fallback when primary model is cooling down.
  - [x] 12.3 Test fallback when primary model is quota-exhausted.
  - [x] 12.4 Test RPM-limited candidate produces stable skip reason where supported.
  - [x] 12.5 Test RPD-limited candidate produces stable skip reason where supported.
  - [x] 12.6 Test no available model produces clear no-capacity failure.
  - [x] 12.7 Assert selected provider/model metadata reaches result or activity metadata.
  - [x] 12.8 Assert scheduler decision metadata includes stable skip reason codes when implemented.
  - [x] 12.9 Assert scheduler summary is written to activity metadata when implemented.
  - [x] 12.10 Assert request ID, job ID, and chapter ID are preserved where available.
  - [x] 12.11 Assert candidate lists are bounded and redacted when scheduler observability is implemented.
  - [x] 12.12 Confirm tests do not require scheduler policy changes.

- [x] 13. Write Cache Identity Regression Tests
  - [x] 13.1 Test repeated translation can reuse cache with unchanged dimensions.
  - [x] 13.2 Test force/retranslate bypasses cache where specified.
  - [x] 13.3 Test model change changes cache key.
  - [x] 13.4 Test provider change changes cache key.
  - [x] 13.5 Test prompt policy/template version changes cache key when implemented.
  - [x] 13.6 Test glossary revision/hash changes cache key when implemented.
  - [x] 13.7 Test legacy cache entries without glossary identity are not reused for non-zero glossary revision when implemented.
  - [x] 13.8 Gate only not-yet-landed cache dimensions.

- [x] 14. Write Versioning and Retranslation Tests
  - [x] 14.1 Test first translation creates initial version.
  - [x] 14.2 Test retranslation creates a new version.
  - [x] 14.3 Test retranslation does not overwrite old version.
  - [x] 14.4 Test old versions remain listable.
  - [x] 14.5 Test active version behavior matches current storage rules.
  - [x] 14.6 Test version metadata includes provider, model, timestamps, and policy metadata where supported.
  - [x] 14.7 Test failed retranslation does not overwrite or delete active version.
  - [x] 14.8 Test old versions remain available for admin comparison.

- [x] 15. Write Glossary Revision Invalidation Tests
  - [x] 15.1 Test translation version stores glossary revision when available.
  - [x] 15.2 Test translation version stores glossary hash when available.
  - [x] 15.3 Test active version becomes stale after glossary revision increment.
  - [x] 15.4 Test historical versions compute freshness independently.
  - [x] 15.5 Test legacy versions without glossary metadata remain loadable.
  - [x] 15.6 Test retranslate-stale creates a new fresh version.
  - [x] 15.7 Test stale detection does not deactivate active version.
  - [x] 15.8 Test old stale versions remain available for comparison.
  - [x] 15.9 Keep assertions conditional only until glossary revision invalidation has landed.

- [x] 16. Write Crawl/Fetch Observability Regression Tests
  - [x] 16.1 Test fake crawl writes raw chapter data needed by translation.
  - [x] 16.2 Test successful fake crawl persists `metadata.crawl_result` when implemented.
  - [x] 16.3 Test per-chapter crawl failure includes safe error category when implemented.
  - [x] 16.4 Test per-chapter crawl failure includes HTTP status when implemented.
  - [x] 16.5 Test per-chapter crawl failure includes retry attempts when implemented.
  - [x] 16.6 Test running crawl progress updates `metadata.progress` when implemented.
  - [x] 16.7 Test source health aggregates stored crawl results when implemented.
  - [x] 16.8 Test image download failures are counted by affected chapter count when implemented.
  - [x] 16.9 Test crawl observability metadata does not break onboarding or translation readiness state.
  - [x] 16.10 Ensure no real HTTP calls occur.

- [x] 17. Write Public Reader Availability Regression Tests
  - [x] 17.1 Test default `hard_404` returns HTTP 404 for missing active translation.
  - [x] 17.2 Test `chapter_shell` returns HTTP 200 with `text: null`.
  - [x] 17.3 Assert `chapter_shell` returns `availability_status: "not_translated"`.
  - [x] 17.4 Test `latest_version` returns newest saved version when active version is missing.
  - [x] 17.5 Test active version is always preferred when present.
  - [x] 17.6 Test authenticated owner can preview specific `version_id`.
  - [x] 17.7 Test public unauthenticated `version_id` is ignored.
  - [x] 17.8 Test public chapter list includes additive `availability_status`.
  - [x] 17.9 Test public reader responses do not expose admin-only glossary metadata.
  - [x] 17.10 Test public reader responses do not expose admin-only scheduler metadata.
  - [x] 17.11 Test public reader responses do not expose editor QA metadata.

- [x] 18. Write Editor QA and Glossary Resolution Tests
  - [x] 18.1 Test editor QA resolves approved glossary terms against current revision when implemented.
  - [x] 18.2 Test stale translation version is flagged when glossary revision changes when implemented.
  - [x] 18.3 Test pending terms are not treated as approved.
  - [x] 18.4 Test approved-term suggestions preserve configured casing and spelling.
  - [x] 18.5 Test QA metadata remains admin/editor-only.
  - [x] 18.6 Test public reader output is unaffected.
  - [x] 18.7 Keep assertions conditional only until glossary-aware editor QA has landed.

- [x] 19. Write Failure and Partial Success Tests
  - [x] 19.1 Test missing raw chapter produces clear per-chapter failure or preflight issue.
  - [x] 19.2 Test provider failure is recorded.
  - [x] 19.3 Test provider failure does not corrupt existing translation versions.
  - [x] 19.4 Test provider failure does not create active partial version.
  - [x] 19.5 Test one failed chapter does not erase successful chapter translations when partial success is supported.
  - [x] 19.6 Test fatal translation activity records top-level error metadata.
  - [x] 19.7 Test scheduler no-capacity failure does not corrupt activity metadata.
  - [x] 19.8 Test failed retranslation preserves active version state.

- [x] 20. Write Activity Metadata Regression Tests
  - [x] 20.1 Test translation activity metadata includes translated count when supported.
  - [x] 20.2 Test translation activity metadata includes skipped count when supported.
  - [x] 20.3 Test translation activity metadata includes failed count when supported.
  - [x] 20.4 Test activity metadata includes per-chapter failures or summary where supported.
  - [x] 20.5 Test glossary diagnostics summary when implemented.
  - [x] 20.6 Test scheduler summary when implemented.
  - [x] 20.7 Test crawl/fetch activity metadata is not overwritten by later translation metadata.
  - [x] 20.8 Gate optional metadata assertions until related specs have landed.
  - [x] 20.9 Convert landed-spec metadata assertions to strict regression tests.

- [x] 21. Isolation and Determinism Checks
  - [x] 21.1 Confirm tests use temporary storage directories.
  - [x] 21.2 Confirm tests use isolated DB/session fixtures.
  - [x] 21.3 Confirm fake provider/model clients are used.
  - [x] 21.4 Confirm no network calls occur.
  - [x] 21.5 Confirm no real source websites are called.
  - [x] 21.6 Confirm no real object storage services are called.
  - [x] 21.7 Confirm timestamps are controlled, frozen, or asserted tolerantly.
  - [x] 21.8 Confirm scheduler runtime state resets between tests.
  - [x] 21.9 Confirm glossary revision/cache state resets between tests.
  - [x] 21.10 Confirm all content is synthetic.
  - [x] 21.11 Confirm tests do not depend on execution order.

- [x] 22. Backward Compatibility Checks
  - [x] 22.1 Confirm production provider factory defaults are unchanged.
  - [x] 22.2 Confirm production source adapter defaults are unchanged.
  - [x] 22.3 Confirm translation APIs behave as before.
  - [x] 22.4 Confirm storage behavior is unchanged.
  - [x] 22.5 Confirm scheduler policy and model order are unchanged.
  - [x] 22.6 Confirm glossary workflow behavior is unchanged.
  - [x] 22.7 Confirm public reader behavior is unchanged unless an opt-in availability policy is configured in the test.
  - [x] 22.8 Confirm existing unit tests touched by fixtures/injection changes still pass.

- [x] 23. Run Verification
  - [x] 23.1 Run `pytest backend/tests/test_translation_integration_regression.py --tb=short -q`.
  - [x] 23.2 Run `pytest backend/tests/test_translation*.py --tb=short -q`.
  - [x] 23.3 Run `pytest backend/tests/test_public_reader_availability.py --tb=short -q` if present.
  - [x] 23.4 Run `pytest backend/tests/test_glossary_revision_translation_invalidation.py --tb=short -q` if present.
  - [x] 23.5 Run `pytest backend/tests/test_translation_scheduler_observability.py --tb=short -q` if present.
  - [x] 23.6 Run `pytest backend/tests/test_crawl_fetch_observability.py --tb=short -q` if present.
  - [x] 23.7 Run existing glossary gate tests.
  - [x] 23.8 Run existing scheduler tests.
  - [x] 23.9 Run existing translation storage tests.
  - [x] 23.10 Run `ruff check` on changed backend test/helper files.
  - [x] 23.11 Run configured backend type checker if helpers or injection seams were added outside tests.
  - [x] 23.12 Fix test, lint, and type failures caused by this work.

- [x] 24. Final Acceptance Review
  - [x] 24.1 Verify synthetic raw chapter translates into saved versioned storage.
  - [x] 24.2 Verify glossary gate and approved-term prompt injection are covered.
  - [x] 24.3 Verify JP-EN prompt policy behavior is covered by prompt/request assertions.
  - [x] 24.4 Verify scheduler primary/fallback/no-capacity behavior is covered.
  - [x] 24.5 Verify scheduler observability metadata is asserted where implemented.
  - [x] 24.6 Verify cache reuse and invalidation dimensions are covered.
  - [x] 24.7 Verify glossary stale-version detection and stale retranslation are covered where implemented.
  - [x] 24.8 Verify crawl/fetch observability metadata is covered without real HTTP.
  - [x] 24.9 Verify public reader availability policies are covered.
  - [x] 24.10 Verify editor QA glossary-resolution behavior is covered where implemented.
  - [x] 24.11 Verify failure tests prove active translations are not corrupted.
  - [x] 24.12 Verify tests are deterministic, isolated, synthetic, and do not call live providers.
  - [x] 24.13 Verify focused regression command passes.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Core Translation Storage Regression | 3, 5, 6, 9, 21, 24 |
| REQ-2 Glossary Gate and Prompt Injection Regression | 4, 10, 20, 24 |
| REQ-3 JP-EN Prompt Policy Regression | 5, 11, 24 |
| REQ-4 Scheduler Selection and Observability Regression | 6, 12, 20, 24 |
| REQ-5 Translation Cache Identity Regression | 13, 21, 24 |
| REQ-6 Versioning and Retranslation Regression | 14, 19, 24 |
| REQ-7 Glossary Revision Invalidation Regression | 4, 15, 20, 24 |
| REQ-8 Crawl/Fetch Observability Regression | 7, 16, 20, 24 |
| REQ-9 Public Reader Availability Regression | 7, 17, 22, 24 |
| REQ-10 Editor QA and Glossary Resolution Regression | 18, 24 |
| REQ-11 Failure and Partial Success Regression | 19, 20, 24 |
| REQ-12 Activity Metadata Regression | 20, 24 |
| REQ-13 Fixture and Fake Infrastructure | 3, 4, 5, 6, 7, 8 |
| REQ-14 Test Isolation and Determinism | 21, 23, 24 |
| REQ-15 Dependency Injection and Production Compatibility | 6, 7, 22, 23 |
| REQ-16 Conditional Assertions | 8, 13, 15, 18, 20 |
| REQ-17 Test Commands | 2, 23 |

## Definition of Done

- [x] `backend/tests/test_translation_integration_regression.py` exists.
- [x] Synthetic novel, raw chapter, glossary, scheduler, crawl, reader, and auth fixtures exist or are reused.
- [x] Fake provider supports deterministic success and failure paths.
- [x] Normal orchestration translates synthetic raw chapters into saved versioned output.
- [x] Glossary gate and approved-term prompt injection are covered.
- [x] JP-EN prompt policy request shape is covered.
- [x] Scheduler primary, fallback, limited, and no-capacity paths are covered.
- [x] Cache identity and force/retranslate behavior are covered where supported.
- [x] Versioning and retranslation behavior are covered.
- [x] Glossary stale-version behavior is covered where implemented.
- [x] Crawl/fetch observability behavior is covered without real HTTP.
- [x] Public reader availability behavior is covered.
- [x] Editor QA glossary behavior is covered where implemented.
- [x] Failure paths do not corrupt active translation state.
- [x] Conditional assertions are documented and converted to strict assertions for landed specs.
- [x] Tests are isolated, deterministic, synthetic, and make no network calls.
- [x] Production defaults remain unchanged.
- [x] Focused and related regression commands pass.
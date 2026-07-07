# Tasks: Translation Integration Test Suite

## Task List

- [ ] 1. Preflight Translation Testability Review
  - [ ] 1.1 Inspect `OperationsService.translate_novel`.
  - [ ] 1.2 Inspect `NovelOrchestrationService.translate_chapters`.
  - [ ] 1.3 Inspect `TranslationService` stage pipeline.
  - [ ] 1.4 Inspect provider/model factory injection seams.
  - [ ] 1.5 Inspect scheduler test fixtures or existing scheduler unit tests.
  - [ ] 1.6 Inspect translation cache helpers.
  - [ ] 1.7 Inspect translation storage version helpers.
  - [ ] 1.8 Inspect glossary gate/preflight tests.
  - [ ] 1.9 Inspect existing `conftest.py` and storage/db fixtures.

- [ ] 2. Add Integration Test Module
  - [ ] 2.1 Create `backend/tests/test_translation_integration.py`. (REQ-10.4)
  - [ ] 2.2 Mark tests clearly as integration tests if the repository uses pytest markers.
  - [ ] 2.3 Ensure tests can run with `pytest backend/tests/test_translation_integration.py --tb=short -q`.

- [ ] 3. Add Synthetic Novel Fixtures
  - [ ] 3.1 Add fixture for temporary storage root. (REQ-8.1)
  - [ ] 3.2 Add fixture for isolated test DB/session or reuse existing one. (REQ-8.2)
  - [ ] 3.3 Add fixture for synthetic novel metadata. (REQ-9.1)
  - [ ] 3.4 Add fixture for one raw chapter. (REQ-1.1, REQ-9.2)
  - [ ] 3.5 Add fixture for multiple raw chapters for partial success/failure tests.
  - [ ] 3.6 Ensure all fixture text is synthetic. (REQ-8.7)

- [ ] 4. Add Glossary Fixtures
  - [ ] 4.1 Add approved glossary entries fixture. (REQ-9.3)
  - [ ] 4.2 Add pending glossary entries fixture. (REQ-9.3)
  - [ ] 4.3 Add helper for glossary-ready novel state. (REQ-2.2)
  - [ ] 4.4 Add helper for glossary-pending novel state. (REQ-2.1)
  - [ ] 4.5 Add helper to inspect prompt glossary block in fake provider request. (REQ-2.4)

- [ ] 5. Add Fake Translation Provider
  - [ ] 5.1 Add deterministic fake provider. (REQ-1.3, REQ-8.3)
  - [ ] 5.2 Fake provider returns configured translated text. (REQ-9.4)
  - [ ] 5.3 Fake provider records requests for assertions. (REQ-2.4)
  - [ ] 5.4 Add fake rate-limit failure mode. (REQ-9.5)
  - [ ] 5.5 Add fake quota failure mode. (REQ-9.5)
  - [ ] 5.6 Add fake timeout/generic failure modes if current orchestration handles them. (REQ-9.5)
  - [ ] 5.7 Ensure fake provider never makes network calls. (REQ-8.4)

- [ ] 6. Add Provider/Scheduler Injection
  - [ ] 6.1 Use existing provider factory override if available. (REQ-10.1)
  - [ ] 6.2 If needed, add minimal optional provider factory parameter with production default unchanged. (REQ-10.1)
  - [ ] 6.3 Add scheduler config fixture for primary available model. (REQ-3.1)
  - [ ] 6.4 Add scheduler config fixture for primary cooldown state. (REQ-3.2)
  - [ ] 6.5 Add scheduler config fixture for primary quota/exhausted state. (REQ-3.3)
  - [ ] 6.6 Add scheduler config fixture for no available models. (REQ-3.4)
  - [ ] 6.7 Reset scheduler runtime state between tests. (REQ-8.6)

- [ ] 7. Write Happy Path Integration Test
  - [ ] 7.1 Run normal translation orchestration path. (REQ-1.2)
  - [ ] 7.2 Assert fake provider was called. (REQ-1.3)
  - [ ] 7.3 Assert translated chapter text is saved. (REQ-1.4)
  - [ ] 7.4 Assert translation version is created. (REQ-1.5)
  - [ ] 7.5 Assert active version loads expected text. (REQ-1.6)
  - [ ] 7.6 Assert provider/model metadata is saved where supported. (REQ-1.7)

- [ ] 8. Write Glossary Gate and Prompt Injection Tests
  - [ ] 8.1 Test pending glossary blocks translation without bypass. (REQ-2.1)
  - [ ] 8.2 Test glossary-ready state allows translation. (REQ-2.2)
  - [ ] 8.3 Test `skip_glossary_gate` bypasses according to existing behavior. (REQ-2.3)
  - [ ] 8.4 Assert approved glossary terms appear in fake provider prompt/request. (REQ-2.4)
  - [ ] 8.5 Assert prompt glossary block and chunk glossary do not duplicate conflicting sections. (REQ-2.5)
  - [ ] 8.6 Assert glossary metadata reaches context/version metadata when available. (REQ-2.6)

- [ ] 9. Write Scheduler Integration Tests
  - [ ] 9.1 Test primary available model is selected. (REQ-3.1)
  - [ ] 9.2 Test fallback when primary model is cooling down. (REQ-3.2)
  - [ ] 9.3 Test fallback when primary model is quota-exhausted. (REQ-3.3)
  - [ ] 9.4 Test no available model produces clear failure. (REQ-3.4)
  - [ ] 9.5 Assert selected provider/model metadata reaches result/activity where supported. (REQ-3.5)
  - [ ] 9.6 Confirm tests do not require policy changes. (REQ-3.6)

- [ ] 10. Write Cache Behavior Tests
  - [ ] 10.1 Test repeated translation can reuse cache with unchanged dimensions. (REQ-4.1)
  - [ ] 10.2 Test force/retranslate bypasses cache where specified. (REQ-4.2)
  - [ ] 10.3 Test provider/model change changes cache key. (REQ-4.3)
  - [ ] 10.4 Test prompt policy version changes cache key if implemented. (REQ-4.4)
  - [ ] 10.5 Test glossary revision/hash changes cache key if implemented. (REQ-4.5)
  - [ ] 10.6 Gate optional cache assertions so suite works before dependent specs land. (REQ-7.5)

- [ ] 11. Write Versioning and Retranslation Tests
  - [ ] 11.1 Test first translation creates initial version. (REQ-5.1)
  - [ ] 11.2 Test retranslation creates a new version. (REQ-5.2)
  - [ ] 11.3 Test old version remains listable. (REQ-5.3)
  - [ ] 11.4 Test active version behavior matches current storage rules. (REQ-5.4)
  - [ ] 11.5 Test version metadata includes expected provider/model/timestamps where supported. (REQ-5.5)

- [ ] 12. Write Failure and Partial Success Tests
  - [ ] 12.1 Test missing raw chapter produces clear failure/preflight issue. (REQ-6.1)
  - [ ] 12.2 Test provider failure does not corrupt existing versions. (REQ-6.2)
  - [ ] 12.3 Test partial chapter failure does not erase successful translations when partial success is supported. (REQ-6.3)
  - [ ] 12.4 Test activity status/error metadata for fatal failure. (REQ-6.4)
  - [ ] 12.5 Test failed provider response does not create active partial version. (REQ-6.5)

- [ ] 13. Write Activity Metadata Tests
  - [ ] 13.1 Test translated/skipped/failed counts when supported. (REQ-7.1)
  - [ ] 13.2 Test per-chapter failures or summary when supported. (REQ-7.2)
  - [ ] 13.3 Test glossary diagnostics summary if implemented. (REQ-7.3)
  - [ ] 13.4 Test scheduler summary if implemented. (REQ-7.4)
  - [ ] 13.5 Gate optional metadata assertions based on field presence. (REQ-7.5)

- [ ] 14. Isolation and Determinism Checks
  - [ ] 14.1 Confirm tests use temporary storage directories. (REQ-8.1)
  - [ ] 14.2 Confirm tests use isolated DB/session fixtures. (REQ-8.2)
  - [ ] 14.3 Confirm no network calls occur. (REQ-8.4)
  - [ ] 14.4 Confirm timestamps are controlled or assertions are time-tolerant. (REQ-8.5)
  - [ ] 14.5 Confirm scheduler state resets between tests. (REQ-8.6)

- [ ] 15. Backward Compatibility Checks
  - [ ] 15.1 Confirm production provider factory defaults are unchanged. (REQ-10.1)
  - [ ] 15.2 Confirm translation APIs behave as before. (REQ-10.2)
  - [ ] 15.3 Confirm storage behavior is unchanged. (REQ-10.2)
  - [ ] 15.4 Run existing unit tests touched by fixtures/injection changes. (REQ-10.3)

- [ ] 16. Run Verification
  - [ ] 16.1 Run `pytest backend/tests/test_translation_integration.py --tb=short -q`.
  - [ ] 16.2 Run existing translation tests.
  - [ ] 16.3 Run existing glossary gate tests.
  - [ ] 16.4 Run existing scheduler tests.
  - [ ] 16.5 Run existing translation storage tests.
  - [ ] 16.6 Run `ruff check` on changed backend test/helper files.
  - [ ] 16.7 Run configured backend type checker if helpers were added outside tests.
  - [ ] 16.8 Fix test, lint, and type failures caused by this work.

- [ ] 17. Final Acceptance Review
  - [ ] 17.1 Verify synthetic raw chapter translates into saved translated version storage.
  - [ ] 17.2 Verify glossary gate blocks pending glossary and allows ready/bypassed flows.
  - [ ] 17.3 Verify fake provider request proves glossary terms are injected.
  - [ ] 17.4 Verify scheduler primary/fallback/no-capacity behavior.
  - [ ] 17.5 Verify cache reuse/invalidation dimensions that exist in codebase.
  - [ ] 17.6 Verify retranslation creates a new version and preserves historical versions.
  - [ ] 17.7 Verify provider failure does not corrupt active translation state.
  - [ ] 17.8 Verify tests are deterministic, isolated, synthetic, and do not call live providers.
  - [ ] 17.9 Verify focused test command passes.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 End-to-End Workflow | 3, 5, 6, 7, 17 |
| REQ-2 Glossary Gate/Prompt Injection | 4, 8, 17 |
| REQ-3 Scheduler/Fallback | 6, 9, 17 |
| REQ-4 Cache Behavior | 10, 17 |
| REQ-5 Versioning/Retranslation | 11, 17 |
| REQ-6 Failure/Partial Success | 12, 17 |
| REQ-7 Activity Metadata | 13, 17 |
| REQ-8 Isolation/Determinism | 3, 5, 6, 14 |
| REQ-9 Fixtures/Fake Provider | 3, 4, 5, 6 |
| REQ-10 Backward Compatibility | 2, 6, 15, 16 |

## Definition of Done

- [ ] Focused translation integration test module exists.
- [ ] Synthetic novel/chapter/glossary fixtures exist.
- [ ] Fake provider supports success and failure paths.
- [ ] Happy path translates and saves versioned output.
- [ ] Glossary gate and prompt injection are covered.
- [ ] Scheduler primary/fallback/no-capacity paths are covered.
- [ ] Cache and retranslation behavior are covered where supported.
- [ ] Failure paths do not corrupt active translation state.
- [ ] Tests are isolated and make no network calls.
- [ ] Focused and related existing tests pass.


# Requirements: Translation Integration Test Suite

## Introduction

The backend translation pipeline is stage-oriented and crosses several important boundaries: storage, glossary gating, prompt construction, scheduler/provider selection, translation execution, QA/post-processing, cache flushing, versioned storage, and activity metadata. Existing unit tests can validate individual pieces, but the deep research reports recommend integration-level tests that prove the full translation workflow behaves correctly without live provider calls.

This spec adds a focused translation integration test suite. The suite must exercise the real orchestration and storage seams while replacing external model/provider calls with deterministic fakes.

## Requirements

### REQ-1: End-to-End Translation Workflow Test

The suite must verify the happy path from raw chapter storage to saved translated version.

- REQ-1.1: Create a synthetic novel fixture with metadata and at least one raw chapter.
- REQ-1.2: Run the normal translation orchestration path, not only isolated stage functions.
- REQ-1.3: Use a fake provider/model response instead of a live LLM call.
- REQ-1.4: Assert translated chapter text is saved.
- REQ-1.5: Assert a translation version is created.
- REQ-1.6: Assert active version selection follows existing storage behavior.
- REQ-1.7: Assert provider/model metadata is saved on the translation version where existing behavior supports it.

### REQ-2: Glossary Gate and Prompt Injection Coverage

The suite must prove glossary behavior works across the full translation path.

- REQ-2.1: Test translation is blocked when glossary gate is pending and bypass is not enabled.
- REQ-2.2: Test translation proceeds when glossary is ready.
- REQ-2.3: Test `skip_glossary_gate` preserves existing bypass behavior.
- REQ-2.4: Test approved glossary terms are included in prompt construction.
- REQ-2.5: Test prompt glossary block and chunk glossary entries do not cause duplicate conflicting prompt sections.
- REQ-2.6: Test glossary metadata is attached to translation context or version metadata when available.

### REQ-3: Scheduler and Fallback Coverage

The suite must verify scheduler-aware model selection inside translation orchestration.

- REQ-3.1: Test scheduler selects the primary available model.
- REQ-3.2: Test scheduler falls back when the primary model is cooling down.
- REQ-3.3: Test scheduler falls back when the primary model is quota-exhausted.
- REQ-3.4: Test translation fails with a clear error when no model is available.
- REQ-3.5: Test selected provider/model metadata reaches the translation result or activity metadata.
- REQ-3.6: Tests must not change scheduler policy; they only verify current behavior.

### REQ-4: Translation Cache Behavior

The suite must validate cache behavior at integration seams.

- REQ-4.1: Test repeated translation can reuse cache when source text, model, prompt policy, and glossary state are unchanged.
- REQ-4.2: Test force/retranslate mode bypasses cache where existing behavior specifies it.
- REQ-4.3: Test cache key changes when model/provider changes.
- REQ-4.4: Test cache key changes when prompt policy/template identity changes, if prompt policy versioning exists.
- REQ-4.5: Test cache key changes when glossary revision/hash changes, if glossary revision invalidation exists.

### REQ-5: Versioning and Retranslation Coverage

The suite must validate translated version storage behavior.

- REQ-5.1: Test first translation creates an initial version.
- REQ-5.2: Test retranslation creates a new version rather than overwriting old version.
- REQ-5.3: Test historical versions remain listable after retranslation.
- REQ-5.4: Test active version selection follows existing behavior.
- REQ-5.5: Test version metadata includes provider/model/timestamps where existing storage supports them.

### REQ-6: Failure and Partial Success Coverage

The suite must cover important failure paths.

- REQ-6.1: Test missing raw chapter produces a clear per-chapter failure or preflight issue.
- REQ-6.2: Test provider failure is recorded and does not corrupt existing translation versions.
- REQ-6.3: Test one failed chapter does not erase successful chapter translations when partial success is supported.
- REQ-6.4: Test activity status/error metadata reflects fatal translation failures.
- REQ-6.5: Test no partially written translation version becomes active after a failed provider response.

### REQ-7: Activity Metadata Coverage

The suite must assert useful activity-level output.

- REQ-7.1: Test translation activity metadata includes translated/skipped/failed counts if existing activity flow records them.
- REQ-7.2: Test activity metadata includes per-chapter failures or summary where supported.
- REQ-7.3: Test glossary diagnostics summary is included when the diagnostics spec is implemented.
- REQ-7.4: Test scheduler summary is included when the scheduler observability spec is implemented.
- REQ-7.5: Optional metadata assertions must be gated so the suite can run before later specs are implemented.

### REQ-8: Test Isolation and Determinism

Integration tests must be reliable and fast.

- REQ-8.1: Tests must use temporary storage directories.
- REQ-8.2: Tests must use an isolated test database/session or existing DB fixtures.
- REQ-8.3: Tests must use fake provider/model clients.
- REQ-8.4: Tests must not perform network calls.
- REQ-8.5: Tests must not depend on wall-clock timing except controlled/frozen timestamps.
- REQ-8.6: Tests must clean up provider scheduler state between cases.
- REQ-8.7: Tests must use synthetic content only.

### REQ-9: Fixture and Fake Provider Infrastructure

The suite must include reusable fixtures for translation integration tests.

- REQ-9.1: Add fixture for synthetic novel metadata.
- REQ-9.2: Add fixture for raw chapter bundles.
- REQ-9.3: Add fixture for approved/pending glossary entries.
- REQ-9.4: Add fake translation provider that returns deterministic text.
- REQ-9.5: Add fake provider failure modes for rate-limit, quota, timeout, and generic errors where scheduler/orchestration supports them.
- REQ-9.6: Add helper to inspect saved translation versions.
- REQ-9.7: Fixtures must be reusable by future translation specs.

### REQ-10: Backward Compatibility

The test suite must not require functional changes to production behavior beyond making seams testable.

- REQ-10.1: If dependency injection seams are missing, add minimal test-friendly injection without changing production defaults.
- REQ-10.2: Existing translation APIs and storage behavior must remain unchanged.
- REQ-10.3: Existing unit tests must continue to pass.
- REQ-10.4: The suite must be runnable independently with one focused pytest command.

## Non-Goals

- This spec does not call live LLM providers.
- This spec does not evaluate literary translation quality with an LLM judge.
- This spec does not replace unit tests for individual stages.
- This spec does not change scheduler policy, prompt policy, glossary behavior, or storage schemas.
- This spec does not require browser/UI tests.


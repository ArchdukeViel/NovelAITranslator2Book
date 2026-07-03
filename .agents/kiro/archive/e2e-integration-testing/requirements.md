# Requirements: End-to-End Integration Testing

## Introduction

The codebase has unit tests for individual components but lacks full pipeline integration tests covering the complete owner-to-public-reader flow. There is no single test that validates: create novel -> scrape metadata -> translate chapter -> publish -> public catalog -> public chapter read. This creates a high risk of silent failures and regressions when changes are made to any component.

This spec adds a reusable end-to-end integration test suite that exercises the full pipeline using a dummy novel source and mocked provider responses. The tests run in CI and catch regressions across the entire system.

## Requirements

### REQ-1: Dummy Novel Source Fixture

A reproducible test fixture must simulate a complete novel for ingestion.

- REQ-1.1: Create a static test novel fixture in `backend/tests/fixtures/e2e/` containing:
  - A minimal HTML file at `fixtures/e2e/test_novel/index.html` with a simple chapter structure (title, 3 chapters with 2-3 paragraphs each, all in Japanese).
  - A source adapter `DummySource` in `fixtures/e2e/dummy_source.py` that reads the fixture HTML and returns metadata and chapter content conforming to the `SourceAdapter` interface.
- REQ-1.2: The dummy source must be self-contained (no HTTP requests, no external dependencies).
- REQ-1.3: The dummy source must register with the `AdapterRegistry` so `NovelOrchestrationService` can discover it.

### REQ-2: Mocked Translation Provider

The translation provider must be mocked to avoid real API calls and costs.

- REQ-2.1: Create a `MockGeminiProvider` in `backend/tests/fixtures/e2e/mock_provider.py` that implements the provider interface.
- REQ-2.2: The mock provider must return deterministic "translations" for any input (e.g. prepend `[EN]` to the source text, or return a fixed mapping for known test phrases).
- REQ-2.3: The mock provider must support configurable failure injection: `fail_on_chapter(chapter_id: str)` to simulate provider errors for testing error paths.
- REQ-2.4: The mock provider must track call count per chapter for assertion: `get_call_count(chapter_id: str) -> int`.

### REQ-3: End-to-End Test Cases

The test suite must cover the full lifecycle and key error paths.

- REQ-3.1: `test_full_pipeline_create_to_public_read` — tests the happy path:
  1. `POST /api/admin/novels` — create novel with dummy source URL
  2. `POST /{novel_id}/scrape` — scrape metadata and chapters
  3. `POST /{novel_id}/refresh-catalog-projection` — sync DB
  4. `POST /{novel_id}/translate` — translate all chapters
  5. Publish the novel (set `is_published=True`)
  6. `GET /api/public/catalog` — assert novel appears
  7. `GET /api/public/novels/{slug}/chapters/{chapter_id}` — assert translated text present
  8. Assert correct chapter count, DB rows, and storage files exist.
- REQ-3.2: `test_pipeline_handles_provider_failure` — uses `fail_on_chapter` to make one chapter fail, asserts the translation job reports the failure for that chapter but others succeed.
- REQ-3.3: `test_pipeline_idempotent_retranslate` — run translate twice on the same novel, assert the second run is a no-op (checks translation status and skips).
- REQ-3.4: `test_pipeline_with_glossary` — create a glossary, apply it, translate, and assert glossary terms appear in the translated output.
- REQ-3.5: `test_pipeline_empty_novel` — create a novel with zero chapters, assert catalog shows it with `chapter_count=0` and translate succeeds trivially.

### REQ-4: Test Infrastructure and CI Integration

Tests must be reliable, fast, and runnable in CI.

- REQ-4.1: All e2e tests must use `tmp_path` for storage and an in-memory SQLite database. No persistent state.
- REQ-4.2: The test module must be marked `@pytest.mark.e2e` so it can be run separately from unit tests.
- REQ-4.3: The full e2e suite must complete in under 60 seconds.
- REQ-4.4: E2e tests must be included in the CI workflow (`.github/workflows/ci.yml`).

### REQ-5: Test Documentation

- REQ-5.1: The test module must include module-level docstrings explaining the test setup, fixture lifecycle, and how to add new scenarios.
- REQ-5.2: Each test function must have a docstring explaining what it verifies and which pipeline stages are covered.

## Non-Goals

- This spec does not add performance or load testing.
- This spec does not add UI-level end-to-end tests (Playwright/Selenium).
- This spec does not change the production code or pipeline behavior.
- This spec does not add VCR/cassette recording of real provider calls.
- This spec does not test multi-novel concurrent translation scenarios.

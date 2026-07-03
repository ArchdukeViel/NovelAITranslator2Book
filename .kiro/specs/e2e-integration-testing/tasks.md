# Tasks: End-to-End Integration Testing

## Task List

- [x] 1. Create dummy novel test fixture
  - [x] 1.1 Create `backend/tests/fixtures/e2e/test_novel/index.html` with 3-chapter Japanese novel (REQ-1.1)
  - [x] 1.2 Create `backend/tests/fixtures/e2e/dummy_source.py` with `DummySource` adapter (REQ-1.1)
  - [x] 1.3 Register `DummySource` with `AdapterRegistry` at test setup (REQ-1.3)

- [x] 2. Create mock Gemini provider
  - [x] 2.1 Create `backend/tests/fixtures/e2e/mock_provider.py` with `MockGeminiProvider` (REQ-2.1)
  - [x] 2.2 Implement deterministic translation (`[EN]` prefix) (REQ-2.2)
  - [x] 2.3 Implement `fail_on_chapter` for error injection (REQ-2.3)
  - [x] 2.4 Implement `get_call_count` tracking (REQ-2.4)

- [x] 3. Create e2e conftest
  - [x] 3.1 Create `backend/tests/e2e/__init__.py` (REQ-4)
  - [x] 3.2 Create `backend/tests/e2e/conftest.py` with FastAPI TestClient, in-memory SQLite, mock provider injection (REQ-4.1)
  - [x] 3.3 Implement `owner_auth` fixture for auth header (REQ-4)

- [x] 4. Write e2e test cases
  - [x] 4.1 Write `test_full_pipeline_create_to_public_read` — 8-step happy path (REQ-3.1)
  - [x] 4.2 Write `test_pipeline_handles_provider_failure` — partial failure test (REQ-3.2)
  - [x] 4.3 Write `test_pipeline_idempotent_retranslate` — double-translate no-op (REQ-3.3)
  - [x] 4.4 Write `test_pipeline_with_glossary` — glossary injection test (REQ-3.4)
  - [x] 4.5 Write `test_pipeline_empty_novel` — zero-chapter novel (REQ-3.5)

- [x] 5. Configure test runner
  - [x] 5.1 Add `e2e` marker to `pyproject.toml` `[tool.pytest.ini_options]` (REQ-4.2)
  - [x] 5.2 Mark all e2e test functions with `@pytest.mark.e2e` (REQ-4.2)

- [x] 6. Add CI integration
  - [x] 6.1 Add `pytest -m e2e --tb=short -q` step in CI workflow (REQ-4.4)

- [x] 7. Document tests
  - [x] 7.1 Add module-level docstring to `test_full_pipeline.py` (REQ-5.1)
  - [x] 7.2 Add function docstrings to each test (REQ-5.2)

- [x] 8. Verify
  - [x] 8.1 Run `pytest -m e2e --tb=short -q` and confirm all pass
  - [x] 8.2 Confirm suite completes in under 60 seconds (REQ-4.3)
  - [x] 8.3 Run `ruff check backend/tests/e2e/` and fix issues

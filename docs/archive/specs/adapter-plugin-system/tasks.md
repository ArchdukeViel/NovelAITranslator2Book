# Tasks: Adapter Plugin System

## Task List

- [ ] 1. Define `SourceAdapter` abstract base class
  - [ ] 1.1 Create `backend/src/novelai/sources/base.py` with `SourceAdapter` ABC (REQ-1.1)
  - [ ] 1.2 Define abstract methods: `can_handle`, `fetch_metadata`, `fetch_chapter` (REQ-1.1)
  - [ ] 1.3 Add `source_key` class attribute requirement (REQ-1.2)

- [ ] 2. Create `AdapterRegistry`
  - [ ] 2.1 Create `backend/src/novelai/sources/registry.py` with singleton pattern (REQ-2.1)
  - [ ] 2.2 Implement `register(adapter_class)` (REQ-2.2)
  - [ ] 2.3 Implement `discover()` with `pkgutil` auto-discovery (REQ-2.3)
  - [ ] 2.4 Implement `get_adapter(source)` that delegates to `can_handle` (REQ-2.4)
  - [ ] 2.5 Implement `list_adapters()` (REQ-2.5)
  - [ ] 2.6 Implement `get_by_key(source_key)` (REQ-2.6)

- [ ] 3. Refactor existing adapters to implement `SourceAdapter`
  - [ ] 3.1 Refactor `KakuyomuSource` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)
  - [ ] 3.2 Refactor `Novel18Source` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)
  - [ ] 3.3 Refactor `GenericSource` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)

- [ ] 4. Refactor `NovelOrchestrationService` to use registry
  - [ ] 4.1 Replace hard-coded adapter selection with `AdapterRegistry.get_adapter(source)` (REQ-3.1)
  - [ ] 4.2 Add no-match error: `OperationError(400, "No adapter found for source: ...")` (REQ-3.2)
  - [ ] 4.3 Preserve explicit `source_key` override via `get_by_key` (REQ-3.3)

- [ ] 5. Add startup initialization
  - [ ] 5.1 Call `registry.discover()` in FastAPI lifespan handler (REQ-4.1)
  - [ ] 5.2 Explicitly register built-in adapters as fallback (REQ-4.2)
  - [ ] 5.3 Add startup log line with adapter count (REQ-4.3)

- [ ] 6. Write tests
  - [ ] 6.1 Test `AdapterRegistry` discovery and registration
  - [ ] 6.2 Test auto-detection via `get_adapter` with known and unknown sources
  - [ ] 6.3 Test explicit key selection via `get_by_key`
  - [ ] 6.4 Test no-match error in `NovelOrchestrationService`
  - [ ] 6.5 Verify existing adapter tests still pass (REQ-5.2)

- [ ] 7. Verify, lint, and type-check
  - [ ] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [ ] 7.2 Run `ruff check backend/src/novelai/sources/` and fix issues
  - [ ] 7.3 Run `pyright backend/src/novelai/sources/` and fix type errors

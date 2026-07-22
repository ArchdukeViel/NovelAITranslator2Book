# Tasks: Adapter Plugin System

## Task List

- [x] 1. Define `SourceAdapter` abstract base class
  - [x] 1.1 Create `backend/src/novelai/sources/base.py` with `SourceAdapter` ABC (REQ-1.1)
  - [x] 1.2 Define abstract methods: `can_handle`, `fetch_metadata`, `fetch_chapter` (REQ-1.1)
  - [x] 1.3 Add `source_key` class attribute requirement (REQ-1.2)

- [x] 2. Create `AdapterRegistry`
  - [x] 2.1 Create `backend/src/novelai/sources/registry.py` with singleton pattern (REQ-2.1)
  - [x] 2.2 Implement `register(adapter_class)` (REQ-2.2)
  - [x] 2.3 Implement `discover()` with `pkgutil` auto-discovery (REQ-2.3)
  - [x] 2.4 Implement `get_adapter(source)` that delegates to `can_handle` (REQ-2.4)
  - [x] 2.5 Implement `list_adapters()` (REQ-2.5)
  - [x] 2.6 Implement `get_by_key(source_key)` (REQ-2.6)

- [x] 3. Refactor existing adapters to implement `SourceAdapter`
  - [x] 3.1 Refactor `KakuyomuSource` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)
  - [x] 3.2 Refactor `Novel18Source` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)
  - [x] 3.3 Refactor `GenericSource` to inherit `SourceAdapter`, add `can_handle` and `source_key` (REQ-1.3)

- [x] 4. Refactor `NovelOrchestrationService` to use registry
  - [x] 4.1 Replace hard-coded adapter selection with `AdapterRegistry.get_adapter(source)` (REQ-3.1)
  - [x] 4.2 Add no-match error: `OperationError(400, "No adapter found for source: ...")` (REQ-3.2)
  - [x] 4.3 Preserve explicit `source_key` override via `get_by_key` (REQ-3.3)

- [x] 5. Add startup initialization
  - [x] 5.1 Call `registry.discover()` in FastAPI lifespan handler (REQ-4.1)
  - [x] 5.2 Explicitly register built-in adapters as fallback (REQ-4.2)
  - [x] 5.3 Add startup log line with adapter count (REQ-4.3)

- [x] 6. Write tests
  - [x] 6.1 Test `AdapterRegistry` discovery and registration
  - [x] 6.2 Test auto-detection via `get_adapter` with known and unknown sources
  - [x] 6.3 Test explicit key selection via `get_by_key`
  - [x] 6.4 Test no-match error in `NovelOrchestrationService`
  - [x] 6.5 Verify existing adapter tests still pass (REQ-5.2)

- [x] 7. Verify, lint, and type-check
  - [x] 7.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 7.2 Run `ruff check backend/src/novelai/sources/` and fix issues
  - [x] 7.3 Run `pyright backend/src/novelai/sources/` and fix type errors

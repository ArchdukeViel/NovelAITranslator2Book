# Requirements: Adapter Plugin System

## Introduction

Source adapters are currently hard-coded into the orchestration layer. Adding a new source type requires modifying core code, registering the adapter in the orchestrator, and redeploying. There is no formal adapter interface contract, no plugin registry, and no runtime discovery mechanism. This makes the system brittle and makes it difficult for external contributors or future development to extend supported source types.

This spec introduces a plugin-based adapter architecture: a formal `SourceAdapter` interface, a registry that discovers and loads adapters at startup, and auto-detection logic that selects the correct adapter based on input. Existing adapters are refactored to conform to the interface without breaking backward compatibility.

## Requirements

### REQ-1: Formal SourceAdapter Interface

A canonical interface must be defined that all source adapters implement.

- REQ-1.1: Define an abstract base class `SourceAdapter` in `backend/src/novelai/sources/base.py` with the following methods:
  - `can_handle(source: str) -> bool` — returns `True` if this adapter can handle the given source URL or identifier.
  - `fetch_metadata(source: str) -> dict` — returns novel metadata (title, chapter list, etc.).
  - `fetch_chapter(source: str, chapter_id: str) -> dict` — returns the raw chapter content bundle.
- REQ-1.2: The interface must include a `source_key: str` class attribute that uniquely identifies the adapter type (e.g. `"kakuyomu"`, `"novel18"`, `"generic"`).
- REQ-1.3: All existing adapters (`KakuyomuSource`, `Novel18Source`, `GenericSource`, etc.) must be refactored to inherit from `SourceAdapter` and implement all required methods.
- REQ-1.4: The interface must be backward-compatible: existing callers of adapter methods must continue to work without change after the refactor.

### REQ-2: Adapter Plugin Registry

A central registry must manage adapter lifecycle and discovery.

- REQ-2.1: Create `AdapterRegistry` in `backend/src/novelai/sources/registry.py` as a singleton.
- REQ-2.2: The registry must expose `register(adapter_class: type[SourceAdapter])` for explicit registration.
- REQ-2.3: The registry must expose `discover()` that auto-discovers adapter classes from the `backend/src/novelai/sources/` package using Python's `importlib` or `pkgutil` module.
- REQ-2.4: The registry must expose `get_adapter(source: str) -> SourceAdapter | None` that returns the first adapter whose `can_handle(source)` returns `True`.
- REQ-2.5: The registry must expose `list_adapters() -> list[str]` returning all registered `source_key` values.
- REQ-2.6: The registry must expose `get_by_key(source_key: str) -> SourceAdapter | None` for direct access by key.

### REQ-3: Auto-Detection in NovelOrchestrationService

The orchestration layer must use the registry instead of hard-coded adapter selection.

- REQ-3.1: `NovelOrchestrationService` must use `AdapterRegistry.get_adapter(source)` instead of the current if/else or switch-based adapter selection.
- REQ-3.2: If no adapter matches, raise a clear `OperationError(400, "No adapter found for source: {source}")`.
- REQ-3.3: The explicit `source_key` override (when provided by the caller) must still work via `AdapterRegistry.get_by_key(source_key)`.
- REQ-3.4: Auto-detection and explicit key selection must be tested in integration tests.

### REQ-4: Startup Initialization

Adapter registration must happen at application startup.

- REQ-4.1: The registry must call `discover()` once during FastAPI application startup (lifespan event) in `backend/src/novelai/main.py`.
- REQ-4.2: Adapters in the known built-in list must also be explicitly registered to ensure they are available even if auto-discovery fails.
- REQ-4.3: A startup log line must report how many adapters were registered: `"Adapter registry initialized: {count} adapters registered"`.

### REQ-5: Backward Compatibility

- REQ-5.1: All existing `source_key` values must remain unchanged.
- REQ-5.2: All existing source adapter test fixtures must continue to pass without modification.
- REQ-5.3: The `POST /{novel_id}/scrape` and `POST /{novel_id}/import` endpoints must behave identically before and after the refactor.

## Non-Goals

- This spec does not add new source adapters.
- This spec does not change how fetched content is stored or processed.
- This spec does not introduce a hot-reload mechanism for adapters at runtime.
- This spec does not add a frontend UI for managing adapters.
- This spec does not change the crawl, scrape, or translation pipeline logic.

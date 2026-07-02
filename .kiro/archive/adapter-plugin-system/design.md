# Design: Adapter Plugin System

## Overview

Three targeted changes: (1) define a `SourceAdapter` abstract base class, (2) create an `AdapterRegistry` with auto-discovery, (3) refactor `NovelOrchestrationService` to use the registry. No changes to storage, translation pipeline, or API router shapes.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/sources/base.py` | New — `SourceAdapter` abstract base class |
| `backend/src/novelai/sources/registry.py` | New — `AdapterRegistry` with discovery and registration |
| `backend/src/novelai/sources/kakuyomu_source.py` | Refactor — inherit `SourceAdapter`, implement interface |
| `backend/src/novelai/sources/novel18_source.py` | Refactor — inherit `SourceAdapter`, implement interface |
| `backend/src/novelai/sources/generic_source.py` | Refactor — inherit `SourceAdapter`, implement interface |
| `backend/src/novelai/services/orchestration/operations.py` | Refactor — use `AdapterRegistry` instead of hard-coded selection |
| `backend/src/novelai/main.py` | Add startup adapter discovery |
| `backend/tests/test_source_adapters.py` | New or update — plugin registry tests |

### Files Not Touched

- Storage layer — no change
- Translation pipeline — no change
- API routers — no change
- DB models — no change
- Provider modules — no change

## Component Design

### 1. `SourceAdapter` Abstract Base Class (`sources/base.py`)

```python
from abc import ABC, abstractmethod

class SourceAdapter(ABC):
    """Interface that all source adapters must implement."""

    source_key: str = ""

    @classmethod
    @abstractmethod
    def can_handle(cls, source: str) -> bool:
        """Return True if this adapter can handle the given source URL or identifier."""
        ...

    @abstractmethod
    def fetch_metadata(self, source: str) -> dict:
        """Fetch and return novel metadata as a dict."""
        ...

    @abstractmethod
    def fetch_chapter(self, source: str, chapter_id: str) -> dict:
        """Fetch and return a single raw chapter bundle."""
        ...
```

### 2. `AdapterRegistry` (`sources/registry.py`)

```python
from novelai.sources.base import SourceAdapter

class AdapterRegistry:
    """Singleton registry for source adapter plugins."""

    def __init__(self):
        self._adapters: dict[str, type[SourceAdapter]] = {}
        self._instances: dict[str, SourceAdapter] = {}

    def register(self, adapter_class: type[SourceAdapter]) -> None:
        key = adapter_class.source_key
        if key in self._adapters:
            return  # idempotent
        self._adapters[key] = adapter_class
        self._instances[key] = adapter_class()

    def discover(self) -> None:
        """Auto-discover adapters in the sources package."""
        import pkgutil
        import importlib
        import novelai.sources
        for importer, modname, ispkg in pkgutil.iter_modules(novelai.sources.__path__):
            if modname.endswith("_source") and modname != "base":
                module = importlib.import_module(f"novelai.sources.{modname}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, SourceAdapter)
                            and attr is not SourceAdapter):
                        self.register(attr)

    def get_adapter(self, source: str) -> SourceAdapter | None:
        for instance in self._instances.values():
            if instance.can_handle(source):
                return instance
        return None

    def get_by_key(self, source_key: str) -> SourceAdapter | None:
        return self._instances.get(source_key)

    def list_adapters(self) -> list[str]:
        return list(self._adapters.keys())

# Module-level singleton
_registry: AdapterRegistry | None = None

def get_registry() -> AdapterRegistry:
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
    return _registry
```

### 3. Startup Initialization (`main.py`)

In the FastAPI lifespan handler:

```python
from novelai.sources.registry import get_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = get_registry()
    registry.discover()
    count = len(registry.list_adapters())
    logger.info("Adapter registry initialized: %d adapters registered", count)
    yield
```

### 4. Refactor Existing Adapters

Each existing adapter (`KakuyomuSource`, `Novel18Source`, `GenericSource`) must:

- Set `source_key` as a class attribute matching the current key string.
- Ensure `can_handle` returns `True` for URLs/identifiers it currently handles.
- Ensure existing `fetch_metadata` and `fetch_chapter` signatures and return types remain compatible.

Example refactor for `KakuyomuSource`:

```python
from novelai.sources.base import SourceAdapter

class KakuyomuSource(SourceAdapter):
    source_key = "kakuyomu"

    @classmethod
    def can_handle(cls, source: str) -> bool:
        return "kakuyomu.jp" in source

    # existing fetch_metadata and fetch_chapter remain unchanged
```

### 5. Refactor `NovelOrchestrationService` (`operations.py`)

Replace the current adapter selection logic:

```python
# BEFORE: hard-coded if/else
if "kakuyomu" in source_url:
    adapter = KakuyomuSource(...)
elif "novel18" in source_url:
    adapter = Novel18Source(...)
else:
    adapter = GenericSource(...)

# AFTER: registry-based selection
from novelai.sources.registry import get_registry
adapter = get_registry().get_adapter(source_url)
if adapter is None:
    raise OperationError(400, f"No adapter found for source: {source_url}")
```

When `source_key` is explicitly provided:

```python
adapter = get_registry().get_by_key(source_key)
if adapter is None:
    raise OperationError(400, f"No adapter found for source_key: {source_key}")
```

## Migration and Backward Compatibility

- All existing adapters are refactored in-place (same file, same class names, same method signatures).
- The `source_key` values remain identical to current values.
- Tests that instantiate adapters directly continue to work (the abstract base class does not change constructor requirements).
- The registry adds behavior; it does not remove any existing code paths until they are fully replaced and tested.

## Acceptance Criteria

1. `SourceAdapter` ABC is defined in `sources/base.py` and all existing adapters inherit from it.
2. `AdapterRegistry` discovers, registers, and resolves adapters correctly.
3. `NovelOrchestrationService` uses the registry and falls back to a clear error when no adapter is found.
4. Explicit `source_key` override continues to work via `get_by_key`.
5. Startup logs the adapter count.
6. All existing source adapter tests pass without modification.
7. Integration tests confirm auto-detection, explicit key selection, and no-match error paths.

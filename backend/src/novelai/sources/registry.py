from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable

from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)

_SOURCE_REGISTRY: dict[str, Callable[[], SourceAdapter]] = {}


def register_source(key: str, factory: Callable[[], SourceAdapter]) -> None:
    """Register a source adapter factory by key."""
    _SOURCE_REGISTRY[key] = factory


def get_source(key: str) -> SourceAdapter:
    factory = _SOURCE_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No source registered for key: {key}")
    return factory()


def detect_source(identifier_or_url: str) -> str | None:
    for key, factory in _SOURCE_REGISTRY.items():
        try:
            if factory().matches_url(identifier_or_url):
                return key
        except Exception:
            logger.debug("Source adapter %s failed during URL detection.", key)
            continue
    return None


def available_sources() -> list[str]:
    return list(_SOURCE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Spec-conforming aliases / extensions  (adapter-plugin-system spec)
# ---------------------------------------------------------------------------


def get_by_key(source_key: str) -> SourceAdapter:
    """Alias for :func:`get_source` -- return adapter by explicit key."""
    return get_source(source_key)


def get_adapter(identifier_or_url: str) -> SourceAdapter:
    """Return the best matching adapter for *identifier_or_url*.

    Tries each registered adapter's ``can_handle`` in registration order.
    """
    for _key, factory in _SOURCE_REGISTRY.items():
        try:
            instance = factory()
            if instance.can_handle(identifier_or_url):
                return instance
        except Exception:
            logger.debug("Source adapter %s failed during can_handle check.", _key)
            continue
    raise KeyError(f"No adapter found for source: {identifier_or_url}")


def list_adapters() -> list[str]:
    """Return sorted list of registered adapter keys."""
    return sorted(_SOURCE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Plugin discovery via pkgutil
# ---------------------------------------------------------------------------

_discovered = False


def discover() -> int:
    """Auto-discover source adapter modules under ``novelai.sources``.

    Imports every submodule so adapters using ``register_source`` at module
    level get registered.  Returns total adapter count after discovery.

    Idempotent -- safe to call multiple times.
    """
    global _discovered
    if _discovered:
        return len(_SOURCE_REGISTRY)
    _discovered = True

    import novelai.sources as pkg

    before = len(_SOURCE_REGISTRY)
    prefix = pkg.__name__ + "."
    for _importer, modname, _ispkg in pkgutil.iter_modules(pkg.__path__, prefix):
        try:
            importlib.import_module(modname)
        except Exception:
            logger.warning("Failed to import source adapter module %s", modname, exc_info=True)
    after = len(_SOURCE_REGISTRY)
    logger.info("Source adapter discovery complete: %d adapters registered (%d new).", after, after - before)
    return after

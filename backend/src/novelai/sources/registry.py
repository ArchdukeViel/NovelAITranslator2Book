from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil

from novelai.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for source-adapter factories and discovered plugins."""

    def __init__(self) -> None:
        self._adapter_classes: dict[str, type[SourceAdapter]] = {}
        self._instances: dict[str, SourceAdapter] = {}
        self._discovered = False

    def register(self, adapter_class: type[SourceAdapter]) -> None:
        normalized_source_key = adapter_class.source_key.strip()
        if not normalized_source_key:
            raise ValueError("source_key must not be blank")
        if normalized_source_key in self._adapter_classes:
            return
        self._adapter_classes[normalized_source_key] = adapter_class
        self._instances[normalized_source_key] = adapter_class()

    def get_by_key(self, source_key: str) -> SourceAdapter | None:
        return self._instances.get(source_key)

    def get_adapter(self, source: str) -> SourceAdapter | None:
        for source_key, adapter in self._instances.items():
            try:
                if adapter.can_handle(source):
                    return adapter
            except Exception:
                logger.debug("Source adapter %s failed during detection.", source_key)
        return None

    def list_adapters(self) -> list[str]:
        return sorted(self._adapter_classes)

    def discover(self) -> int:
        if self._discovered:
            return len(self._adapter_classes)
        self._discovered = True

        import novelai.sources as sources_package

        for module_info in pkgutil.iter_modules(sources_package.__path__):
            if module_info.name in {"base", "registry"}:
                continue
            module = importlib.import_module(f"novelai.sources.{module_info.name}")
            for _, candidate in inspect.getmembers(module, inspect.isclass):
                if candidate is SourceAdapter or not issubclass(candidate, SourceAdapter):
                    continue
                source_key = candidate.source_key.strip()
                if source_key and source_key not in self._adapter_classes:
                    self.register(candidate)
        return len(self._adapter_classes)


_registry = AdapterRegistry()


def get_registry() -> AdapterRegistry:
    return _registry

from __future__ import annotations

from typing import Callable, Dict

from novelai.export.base_exporter import BaseExporter

_EXPORTER_REGISTRY: Dict[str, Callable[[], BaseExporter]] = {}


def register_exporter(key: str, factory: Callable[[], BaseExporter]) -> None:
    """Register an exporter factory by key.
    
    Args:
        key: Unique identifier (e.g., 'epub', 'pdf', 'html')
        factory: Callable that returns a BaseExporter instance
    """
    _EXPORTER_REGISTRY[key] = factory


def get_exporter(key: str) -> BaseExporter:
    """Retrieve an exporter instance by key.
    
    Args:
        key: Exporter key (e.g., 'epub', 'pdf')
        
    Returns:
        BaseExporter instance
        
    Raises:
        KeyError: If exporter not registered
    """
    factory = _EXPORTER_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No exporter registered for key: {key}")
    return factory()


def available_exporters() -> list[str]:
    """Get list of registered exporter keys."""
    return list(_EXPORTER_REGISTRY.keys())

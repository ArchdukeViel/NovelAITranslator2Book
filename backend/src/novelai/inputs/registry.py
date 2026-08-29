from __future__ import annotations

from collections.abc import Callable

from novelai.inputs.base import DocumentAdapter

_INPUT_ADAPTER_REGISTRY: dict[str, Callable[[], DocumentAdapter]] = {}


def register_input_adapter(key: str, factory: Callable[[], DocumentAdapter]) -> None:
    _INPUT_ADAPTER_REGISTRY[key] = factory


def get_input_adapter(key: str) -> DocumentAdapter:
    factory = _INPUT_ADAPTER_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No input adapter registered for key: {key}")
    return factory()

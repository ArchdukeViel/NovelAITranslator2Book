from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from novelai.inputs.base import DocumentAdapter

logger = logging.getLogger(__name__)

_INPUT_ADAPTER_REGISTRY: dict[str, Callable[[], DocumentAdapter]] = {}


def register_input_adapter(key: str, factory: Callable[[], DocumentAdapter]) -> None:
    _INPUT_ADAPTER_REGISTRY[key] = factory


def get_input_adapter(key: str) -> DocumentAdapter:
    factory = _INPUT_ADAPTER_REGISTRY.get(key)
    if factory is None:
        raise KeyError(f"No input adapter registered for key: {key}")
    return factory()


def detect_input_adapter(source: str | Path) -> str | None:
    for key, factory in _INPUT_ADAPTER_REGISTRY.items():
        try:
            if factory().probe(source):
                return key
        except Exception:
            logger.debug("Input adapter %s failed during probe.", key, exc_info=True)
    return None


def available_input_adapters() -> list[str]:
    return list(_INPUT_ADAPTER_REGISTRY.keys())

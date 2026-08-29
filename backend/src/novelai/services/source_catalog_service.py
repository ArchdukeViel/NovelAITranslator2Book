"""Read-only catalog of available web source adapters.

Thin wrapper so routers don't import ``sources.*`` directly.
"""

from __future__ import annotations

from novelai.sources.registry import get_registry


def list_available_sources() -> list[str]:
    """Return the list of registered source adapter keys."""
    return get_registry().list_adapters()

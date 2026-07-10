"""Read-only catalog of available source adapters and input adapters.

Thin wrapper so routers don't import ``sources.*`` or ``inputs.*`` directly.
"""

from __future__ import annotations

from novelai.inputs.registry import available_input_adapters
from novelai.sources.registry import available_sources


def list_available_sources() -> list[str]:
    """Return the list of registered source adapter keys."""
    return available_sources()


def list_available_input_adapters() -> list[str]:
    """Return the list of registered input adapter keys."""
    return available_input_adapters()

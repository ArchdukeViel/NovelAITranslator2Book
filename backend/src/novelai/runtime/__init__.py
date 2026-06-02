"""Shared backend runtime wiring for Novel AI."""

from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import Container, container

__all__ = ["Container", "bootstrap", "container"]

"""Shared runtime wiring for Novel AI interfaces."""

from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import Container, container

__all__ = ["Container", "bootstrap", "container"]

"""Compatibility wrapper for the settings screen."""

import sys as _sys
from importlib import import_module

_impl = import_module("novelai.interfaces.tui.screens.settings")
_sys.modules[__name__] = _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in dir(_impl) if not name.startswith("__")]

"""Screen modules for the TUI dashboard."""

from novelai.tui.screens.diagnostics import DiagnosticsScreenMixin
from novelai.tui.screens.library import LibraryScreenMixin
from novelai.tui.screens.pipeline import PipelineScreenMixin
from novelai.tui.screens.settings import SettingsScreenMixin

__all__ = [
    "DiagnosticsScreenMixin",
    "LibraryScreenMixin",
    "PipelineScreenMixin",
    "SettingsScreenMixin",
]

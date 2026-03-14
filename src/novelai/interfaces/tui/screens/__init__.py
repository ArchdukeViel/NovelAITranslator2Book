"""Screen modules for the TUI dashboard."""

from novelai.interfaces.tui.screens.diagnostics import DiagnosticsScreenMixin
from novelai.interfaces.tui.screens.glossary import GlossaryScreenMixin
from novelai.interfaces.tui.screens.library import LibraryScreenMixin
from novelai.interfaces.tui.screens.pipeline import PipelineScreenMixin
from novelai.interfaces.tui.screens.settings import SettingsScreenMixin

__all__ = [
    "DiagnosticsScreenMixin",
    "GlossaryScreenMixin",
    "LibraryScreenMixin",
    "PipelineScreenMixin",
    "SettingsScreenMixin",
]

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from novelai.interfaces.desktop.pages.profiles import ProfilesView
from novelai.interfaces.desktop.pages.settings import SettingsView


class LLMOpsView(QWidget):
    """Unified LLM operations configuration page.

    Merges runtime settings (provider keys/defaults) with per-step profile routing.
    """

    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        self.settings_view = SettingsView(refresh_callback)
        self.profiles_view = ProfilesView(refresh_callback)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        layout.addWidget(self.settings_view)
        layout.addWidget(divider)
        layout.addWidget(self.profiles_view)

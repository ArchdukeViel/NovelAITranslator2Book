from __future__ import annotations

import contextlib
from pathlib import Path
from collections.abc import Callable

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novelai.config.settings import settings
from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.shared import build_stylesheet, resolve_theme_preference
from novelai.providers.registry import available_models, available_providers


UI_LANGUAGE_OPTIONS = [
    ("English", "en"),
    ("Indonesian", "id"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Chinese", "zh"),
]


class SettingsView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.refresh_callback = refresh_callback
        self._selected_library_path = str(settings.NOVEL_LIBRARY_DIR)
        layout = QVBoxLayout(self)
        eyebrow = QLabel("SETTINGS")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Control runtime defaults, provider access, and desktop preferences.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        body = QLabel(
            "Configure fallback defaults used when a workflow step is set to Inherit on the Profiles page."
        )
        body.setObjectName("HeroBody")
        body.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)

        defaults_group = QGroupBox("General Translation Defaults")
        defaults_form = QFormLayout(defaults_group)
        self.provider_input = QComboBox()
        provider_choices = sorted(available_providers())
        if "openai" in provider_choices:
            provider_choices.remove("openai")
            provider_choices.insert(0, "openai")
        if "gemini" in provider_choices:
            provider_choices.remove("gemini")
            provider_choices.insert(1 if provider_choices and provider_choices[0] == "openai" else 0, "gemini")
        for provider in provider_choices:
            self.provider_input.addItem(provider)
        self.model_input = QComboBox()
        self.model_input.setEditable(False)
        defaults_note = QLabel(
            "Provider and model are used as the fallback when a workflow step is set to Inherit on the Profiles page."
        )
        defaults_note.setObjectName("HeroBody")
        defaults_note.setWordWrap(True)
        defaults_form.addRow("Default Provider", self.provider_input)
        defaults_form.addRow("Default Model", self.model_input)
        defaults_form.addRow("", defaults_note)
        layout.addWidget(defaults_group)

        ui_group = QGroupBox("UI Preferences")
        ui_form = QFormLayout(ui_group)
        self.theme_input = QComboBox()
        self.theme_input.addItems(["auto", "light", "dark"])
        self.language_input = QComboBox()
        for label, code in UI_LANGUAGE_OPTIONS:
            self.language_input.addItem(label, code)
        ui_form.addRow("Theme", self.theme_input)
        ui_form.addRow("UI Language", self.language_input)
        layout.addWidget(ui_group)

        info_group = QGroupBox("System Info")
        info_form = QFormLayout(info_group)
        library_row = QHBoxLayout()
        self.library_path_input = QLineEdit(str(settings.NOVEL_LIBRARY_DIR))
        self.library_path_input.setReadOnly(True)
        self.library_browse_button = QPushButton("Browse")
        library_row.addWidget(self.library_path_input, 1)
        library_row.addWidget(self.library_browse_button)
        library_note = QLabel("Changing library path applies to new sessions. Restart the desktop app after saving.")
        library_note.setObjectName("HeroBody")
        library_note.setWordWrap(True)
        info_form.addRow("Library Path", library_row)
        info_form.addRow("", library_note)
        layout.addWidget(info_group)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save Settings")
        self.reload_button = QPushButton("Reload")
        self.save_button.clicked.connect(self.save)
        self.reload_button.clicked.connect(self.reload)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()

        self.provider_input.currentIndexChanged.connect(self._refresh_model_choices)
        self.library_browse_button.clicked.connect(self._select_library_path)
        self.reload()

    def _refresh_model_choices(self) -> None:
        provider = self.provider_input.currentText().strip()
        current_model = self.model_input.currentData() if isinstance(self.model_input.currentData(), str) else self.model_input.currentText().strip()
        self.model_input.clear()
        models: list[str] = []
        if provider:
            with contextlib.suppress(Exception):
                models = available_models(provider)
        for model in models:
            self.model_input.addItem(model, model)
        if current_model and self.model_input.findText(current_model) < 0:
            self.model_input.addItem(current_model, current_model)
        model_index = self.model_input.findData(current_model)
        self.model_input.setCurrentIndex(model_index if model_index >= 0 else 0)

    def _select_library_path(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Novel Library Folder", self._selected_library_path)
        if selected:
            self._selected_library_path = selected
            self.library_path_input.setText(selected)

    def _apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        app.setStyleSheet(build_stylesheet(theme=resolve_theme_preference(theme, app)))

    @staticmethod
    def _persist_library_path(path: Path) -> None:
        env_path = Path(".env")
        key = "NOVEL_LIBRARY_DIR"
        value = str(path)
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        for index, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[index] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def reload(self) -> None:
        prefs = desktop_shared.container.preferences
        provider = prefs.get_preferred_provider()
        provider_index = self.provider_input.findText(provider)
        self.provider_input.setCurrentIndex(provider_index if provider_index >= 0 else 0)
        self._refresh_model_choices()
        model = prefs.get_preferred_model()
        model_index = self.model_input.findData(model)
        self.model_input.setCurrentIndex(model_index if model_index >= 0 else 0)
        self.theme_input.setCurrentText(prefs.get_theme())
        language = prefs.get_language()
        language_index = self.language_input.findData(language)
        self.language_input.setCurrentIndex(language_index if language_index >= 0 else 0)
        self._selected_library_path = str(settings.NOVEL_LIBRARY_DIR)
        self.library_path_input.setText(self._selected_library_path)

    def save(self) -> None:
        prefs = desktop_shared.container.preferences
        prefs.set_preferred_provider(self.provider_input.currentText().strip())
        selected_model = self.model_input.currentData()
        prefs.set_preferred_model(selected_model if isinstance(selected_model, str) else self.model_input.currentText().strip())
        selected_theme = self.theme_input.currentText().strip()
        prefs.set_theme(selected_theme)
        selected_language = self.language_input.currentData()
        prefs.set_language(selected_language if isinstance(selected_language, str) else "en")
        selected_library_path = Path(self.library_path_input.text().strip() or str(settings.NOVEL_LIBRARY_DIR)).expanduser()
        settings.NOVEL_LIBRARY_DIR = selected_library_path
        self._persist_library_path(selected_library_path)
        self._apply_theme(selected_theme)
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Settings Saved", "Desktop settings were updated.")

from __future__ import annotations

import contextlib
from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novelai.config.settings import settings
from novelai.providers.registry import available_models, available_providers
from novelai.runtime.container import container
from novelai.sources.registry import available_sources


class SettingsView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.preferences = container.preferences
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        eyebrow = QLabel("SETTINGS")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Control runtime defaults, provider access, and desktop preferences.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        body = QLabel(
            "Secrets remain environment-backed. The desktop page updates the runtime key without persisting it to disk."
        )
        body.setObjectName("HeroBody")
        body.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)
        form = QFormLayout()

        self.provider_input = QComboBox()
        for provider in sorted(available_providers()):
            self.provider_input.addItem(provider)

        self.model_input = QComboBox()
        self.model_input.setEditable(True)

        self.source_input = QComboBox()
        self.source_input.addItem("Auto", None)
        for source in sorted(available_sources()):
            self.source_input.addItem(source, source)

        self.theme_input = QComboBox()
        self.theme_input.addItems(["auto", "light", "dark"])
        self.language_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.target_language_label = QLabel(settings.TRANSLATION_TARGET_LANGUAGE)
        self.library_path_label = QLabel(str(settings.NOVEL_LIBRARY_DIR))

        form.addRow("Default Provider", self.provider_input)
        form.addRow("Default Model", self.model_input)
        form.addRow("Preferred Source", self.source_input)
        form.addRow("Theme", self.theme_input)
        form.addRow("UI Language", self.language_input)
        form.addRow("Runtime API Key", self.api_key_input)
        form.addRow("Library Path", self.library_path_label)
        form.addRow("Target Language", self.target_language_label)
        layout.addLayout(form)

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
        self.reload()

    def _refresh_model_choices(self) -> None:
        provider = self.provider_input.currentText().strip()
        current_model = self.model_input.currentText().strip()
        self.model_input.clear()
        models: list[str] = []
        if provider:
            with contextlib.suppress(Exception):
                models = available_models(provider)
        for model in models:
            self.model_input.addItem(model)
        if current_model and self.model_input.findText(current_model) < 0:
            self.model_input.addItem(current_model)
        self.model_input.setCurrentText(current_model)

    def reload(self) -> None:
        provider = self.preferences.get_preferred_provider()
        provider_index = self.provider_input.findText(provider)
        self.provider_input.setCurrentIndex(provider_index if provider_index >= 0 else 0)
        self._refresh_model_choices()
        self.model_input.setCurrentText(self.preferences.get_preferred_model())
        source = self.preferences.get_preferred_source()
        self.source_input.setCurrentIndex(max(self.source_input.findData(source), 0))
        self.theme_input.setCurrentText(self.preferences.get_theme())
        self.language_input.setText(self.preferences.get_language())
        self.api_key_input.setText(self.preferences.get_api_key() or "")

    def save(self) -> None:
        self.preferences.set_preferred_provider(self.provider_input.currentText().strip())
        self.preferences.set_preferred_model(self.model_input.currentText().strip())
        source = self.source_input.currentData()
        self.preferences.set("preferred_source", source if isinstance(source, str) else None)
        self.preferences.set_theme(self.theme_input.currentText().strip())
        self.preferences.set_language(self.language_input.text().strip() or "en")
        api_key = self.api_key_input.text().strip()
        if api_key:
            self.preferences.set_api_key(api_key)
        else:
            self.preferences.clear_api_key()
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Settings Saved", "Desktop settings were updated.")

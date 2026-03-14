from __future__ import annotations

import contextlib
from collections.abc import Callable

from PySide6.QtWidgets import QComboBox, QGridLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.providers.registry import available_models, available_providers
from novelai.runtime.container import container


class ProfilesView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.preferences = container.preferences
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        eyebrow = QLabel("PROFILES")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Assign provider and model preferences to each workflow stage.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        description = QLabel(
            "These settings let OCR, term extraction, glossary work, and body translation use different models when needed."
        )
        description.setObjectName("HeroBody")
        description.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)

        grid = QGridLayout()
        grid.addWidget(QLabel("Step"), 0, 0)
        grid.addWidget(QLabel("Provider"), 0, 1)
        grid.addWidget(QLabel("Model"), 0, 2)
        self.inputs: dict[str, tuple[QComboBox, QComboBox]] = {}
        for row, step in enumerate(WORKFLOW_PROFILE_STEPS, start=1):
            profile = self.preferences.get_workflow_profile(step)
            provider_input = QComboBox()
            provider_input.addItem("Inherit", None)
            for provider in sorted(available_providers()):
                provider_input.addItem(provider, provider)
            provider_input.setCurrentIndex(max(provider_input.findData(profile["provider"]), 0))
            model_input = QComboBox()
            model_input.setEditable(True)
            self._populate_models(model_input, profile["provider"], profile["model"])
            provider_input.currentIndexChanged.connect(lambda _index, current_step=step: self._refresh_models(current_step))
            grid.addWidget(QLabel(step.replace("_", " ").title()), row, 0)
            grid.addWidget(provider_input, row, 1)
            grid.addWidget(model_input, row, 2)
            self.inputs[step] = (provider_input, model_input)
        layout.addLayout(grid)
        save_button = QPushButton("Save Profiles")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()

    def _populate_models(self, combo: QComboBox, provider: str | None, model: str | None) -> None:
        combo.clear()
        combo.addItem("")
        if isinstance(provider, str) and provider.strip():
            with contextlib.suppress(Exception):
                for current_model in available_models(provider):
                    combo.addItem(current_model)
        if isinstance(model, str) and model.strip() and combo.findText(model) < 0:
            combo.addItem(model)
        combo.setCurrentText(model or "")

    def _refresh_models(self, step: str) -> None:
        provider_input, model_input = self.inputs[step]
        provider = provider_input.currentData()
        if not isinstance(provider, str):
            provider = None
        self._populate_models(model_input, provider, model_input.currentText().strip() or None)

    def save(self) -> None:
        for step, (provider_input, model_input) in self.inputs.items():
            provider = provider_input.currentData()
            if not isinstance(provider, str):
                provider = None
            self.preferences.set_workflow_profile(
                step,
                provider=provider,
                model=model_input.currentText().strip() or None,
            )
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Profiles Saved", "Workflow profiles were updated.")

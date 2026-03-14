from __future__ import annotations

import ast
import asyncio
import contextlib
import json
from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.interfaces.desktop.shared import AsyncTaskThread
from novelai.providers.registry import available_models, available_providers, get_provider
from novelai.runtime.container import container


PROFILE_STEP_HINTS: dict[str, str] = {
    "glossary_extraction": "Extract candidate terms from source chapters before translation.",
    "glossary_translation": "Translate extracted glossary terms with a low-cost model.",
    "glossary_review": "Review pending glossary entries with rule-based or future LLM checks.",
    "body_translation": "Translate full chapter text with glossary and style guidance.",
    "polish": "Refine low-confidence output without reprocessing high-confidence chapters.",
    "ocr": "Review OCR text for image-heavy chapters before translation.",
}


class ProfilesView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.preferences = container.preferences
        self.refresh_callback = refresh_callback
        self._endpoint_validate_worker: AsyncTaskThread | None = None
        self._last_endpoint_validation_at: str | None = None
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

        endpoint_group = QGroupBox("Endpoint Profiles")
        endpoint_form = QFormLayout(endpoint_group)

        self.endpoint_select = QComboBox()
        self.endpoint_name_input = QLineEdit()
        self.endpoint_provider_input = QComboBox()
        self.endpoint_provider_input.addItem("", None)
        for provider in sorted(available_providers()):
            self.endpoint_provider_input.addItem(provider, provider)
        self.endpoint_model_input = QLineEdit()
        self.endpoint_temperature_input = QLineEdit()
        self.endpoint_timeout_input = QLineEdit()
        self.endpoint_retries_input = QLineEdit()
        self.endpoint_concurrency_input = QLineEdit()
        self.endpoint_base_url_input = QLineEdit()
        self.endpoint_api_version_input = QLineEdit()
        self.endpoint_api_key_env_input = QLineEdit()
        self.endpoint_kwargs_input = QPlainTextEdit()
        self.endpoint_kwargs_input.setPlaceholderText('{"top_p": 0.95}')
        self.endpoint_kwargs_input.setFixedHeight(80)

        endpoint_buttons = QHBoxLayout()
        self.endpoint_save_button = QPushButton("Save Endpoint Profile")
        self.endpoint_remove_button = QPushButton("Remove Endpoint Profile")
        self.endpoint_validate_button = QPushButton("Validate Endpoint")
        endpoint_buttons.addWidget(self.endpoint_save_button)
        endpoint_buttons.addWidget(self.endpoint_remove_button)
        endpoint_buttons.addWidget(self.endpoint_validate_button)
        endpoint_buttons.addStretch()
        self.endpoint_validation_status = QLabel("")
        self.endpoint_validation_status.setObjectName("HeroBody")
        self.endpoint_validation_status.setWordWrap(True)

        endpoint_form.addRow("Profile", self.endpoint_select)
        endpoint_form.addRow("Name", self.endpoint_name_input)
        endpoint_form.addRow("Provider", self.endpoint_provider_input)
        endpoint_form.addRow("Model", self.endpoint_model_input)
        endpoint_form.addRow("Temperature", self.endpoint_temperature_input)
        endpoint_form.addRow("Timeout", self.endpoint_timeout_input)
        endpoint_form.addRow("Max Retries", self.endpoint_retries_input)
        endpoint_form.addRow("Concurrency", self.endpoint_concurrency_input)
        endpoint_form.addRow("Base URL", self.endpoint_base_url_input)
        endpoint_form.addRow("API Version", self.endpoint_api_version_input)
        endpoint_form.addRow("API Key Env", self.endpoint_api_key_env_input)
        endpoint_form.addRow("Extra kwargs (JSON)", self.endpoint_kwargs_input)
        endpoint_form.addRow("", endpoint_buttons)
        endpoint_form.addRow("Validation", self.endpoint_validation_status)
        layout.addWidget(endpoint_group)

        grid = QGridLayout()
        grid.addWidget(QLabel("Step"), 0, 0)
        grid.addWidget(QLabel("Intent"), 0, 1)
        grid.addWidget(QLabel("Endpoint"), 0, 2)
        grid.addWidget(QLabel("Provider"), 0, 3)
        grid.addWidget(QLabel("Model"), 0, 4)
        grid.addWidget(QLabel("Temp"), 0, 5)
        grid.addWidget(QLabel("Timeout"), 0, 6)
        grid.addWidget(QLabel("Retries"), 0, 7)
        grid.addWidget(QLabel("Conc"), 0, 8)
        grid.addWidget(QLabel("Prompt"), 0, 9)
        grid.addWidget(QLabel("kwargs"), 0, 10)
        self.inputs: dict[str, tuple[QComboBox, QComboBox, QComboBox, QLineEdit, QLineEdit, QLineEdit, QLineEdit, QLineEdit, QPlainTextEdit]] = {}
        for row, step in enumerate(WORKFLOW_PROFILE_STEPS, start=1):
            profile = self.preferences.get_workflow_profile(step)
            step_config = self.preferences.get_llm_step_config(step)

            endpoint_input = QComboBox()
            endpoint_input.addItem("Inherit", None)

            provider_input = QComboBox()
            provider_input.addItem("Inherit", None)
            for provider in sorted(available_providers()):
                provider_input.addItem(provider, provider)
            provider_input.setCurrentIndex(max(provider_input.findData(profile["provider"]), 0))

            model_input = QComboBox()
            model_input.setEditable(True)
            self._populate_models(model_input, profile["provider"], profile["model"])
            provider_input.currentIndexChanged.connect(lambda _index, current_step=step: self._refresh_models(current_step))
            temperature_input = QLineEdit(str(step_config.get("temperature") or ""))
            timeout_input = QLineEdit(str(step_config.get("timeout") or ""))
            retries_input = QLineEdit(str(step_config.get("max_retries") or ""))
            concurrency_input = QLineEdit(str(step_config.get("concurrency") or ""))
            prompt_template_input = QLineEdit(str(step_config.get("prompt_template") or ""))
            kwargs_input = QPlainTextEdit()
            kwargs_input.setFixedHeight(56)
            kwargs_payload = step_config.get("kwargs") if isinstance(step_config.get("kwargs"), dict) else {}
            kwargs_input.setPlainText(str(kwargs_payload) if kwargs_payload else "")

            grid.addWidget(QLabel(step.replace("_", " ").title()), row, 0)
            hint_label = QLabel(PROFILE_STEP_HINTS.get(step, ""))
            hint_label.setWordWrap(True)
            hint_label.setObjectName("HeroBody")
            grid.addWidget(hint_label, row, 1)

            grid.addWidget(endpoint_input, row, 2)
            grid.addWidget(provider_input, row, 3)
            grid.addWidget(model_input, row, 4)
            grid.addWidget(temperature_input, row, 5)
            grid.addWidget(timeout_input, row, 6)
            grid.addWidget(retries_input, row, 7)
            grid.addWidget(concurrency_input, row, 8)
            grid.addWidget(prompt_template_input, row, 9)
            grid.addWidget(kwargs_input, row, 10)
            self.inputs[step] = (
                endpoint_input,
                provider_input,
                model_input,
                temperature_input,
                timeout_input,
                retries_input,
                concurrency_input,
                prompt_template_input,
                kwargs_input,
            )

            endpoint_name = step_config.get("endpoint_profile")
            if isinstance(endpoint_name, str) and endpoint_name.strip():
                endpoint_input.setCurrentText(endpoint_name)

        layout.addLayout(grid)

        extraction_group = QGroupBox("Glossary Extraction")
        extraction_form = QFormLayout(extraction_group)
        self.glossary_mode_input = QComboBox()
        self.glossary_mode_input.addItems(["heuristic", "llm", "hybrid"])
        self.glossary_prompt_input = QPlainTextEdit()
        self.glossary_prompt_input.setPlaceholderText(
            "Optional prompt template. Placeholders: {text}, {max_terms}, {source_language}"
        )
        self.glossary_prompt_input.setFixedHeight(120)
        extraction_form.addRow("Mode", self.glossary_mode_input)
        extraction_form.addRow("Prompt Template", self.glossary_prompt_input)
        layout.addWidget(extraction_group)

        save_button = QPushButton("Save Profiles")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()

        self.endpoint_select.currentIndexChanged.connect(self._on_endpoint_selected)
        self.endpoint_save_button.clicked.connect(self._save_endpoint_profile)
        self.endpoint_remove_button.clicked.connect(self._remove_endpoint_profile)
        self.endpoint_validate_button.clicked.connect(self._validate_endpoint_profile)

        self._reload_endpoint_profiles()
        for step, (endpoint_input, _provider_input, _model_input, _temperature_input, _timeout_input, _retries_input, _concurrency_input, _prompt_template_input, _kwargs_input) in self.inputs.items():
            endpoint_name = self.preferences.get_llm_step_config(step).get("endpoint_profile")
            if isinstance(endpoint_name, str) and endpoint_input.findData(endpoint_name) >= 0:
                endpoint_input.setCurrentIndex(endpoint_input.findData(endpoint_name))
        self.glossary_mode_input.setCurrentText(self.preferences.get_glossary_extraction_mode())
        self.glossary_prompt_input.setPlainText(self.preferences.get_glossary_extraction_prompt_template() or "")

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
        _endpoint_input, provider_input, model_input, _temperature_input, _timeout_input, _retries_input, _concurrency_input, _prompt_template_input, _kwargs_input = self.inputs[step]
        provider = provider_input.currentData()
        if not isinstance(provider, str):
            provider = None
        self._populate_models(model_input, provider, model_input.currentText().strip() or None)

    def _reload_endpoint_profiles(self) -> None:
        profiles = self.preferences.get_llm_endpoint_profiles()

        self.endpoint_select.blockSignals(True)
        self.endpoint_select.clear()
        self.endpoint_select.addItem("", None)
        for name in sorted(profiles.keys()):
            self.endpoint_select.addItem(name, name)
        self.endpoint_select.blockSignals(False)

        for endpoint_input, _provider_input, _model_input, _temperature_input, _timeout_input, _retries_input, _concurrency_input, _prompt_template_input, _kwargs_input in self.inputs.values():
            current_text = endpoint_input.currentText()
            endpoint_input.clear()
            endpoint_input.addItem("Inherit", None)
            for name in sorted(profiles.keys()):
                endpoint_input.addItem(name, name)
            if current_text and endpoint_input.findText(current_text) >= 0:
                endpoint_input.setCurrentText(current_text)

    def _on_endpoint_selected(self) -> None:
        selected = self.endpoint_select.currentData()
        if not isinstance(selected, str):
            self.endpoint_name_input.setText("")
            self.endpoint_provider_input.setCurrentIndex(0)
            self.endpoint_model_input.clear()
            return

        profiles = self.preferences.get_llm_endpoint_profiles()
        payload = profiles.get(selected, {})
        provider = payload.get("provider")
        model = payload.get("model")
        self.endpoint_name_input.setText(selected)
        self.endpoint_provider_input.setCurrentIndex(max(self.endpoint_provider_input.findData(provider), 0))
        self.endpoint_model_input.setText(model if isinstance(model, str) else "")
        self.endpoint_temperature_input.setText(str(payload.get("temperature") or ""))
        self.endpoint_timeout_input.setText(str(payload.get("timeout") or ""))
        self.endpoint_retries_input.setText(str(payload.get("max_retries") or ""))
        self.endpoint_concurrency_input.setText(str(payload.get("concurrency") or ""))
        self.endpoint_base_url_input.setText(str(payload.get("base_url") or ""))
        self.endpoint_api_version_input.setText(str(payload.get("api_version") or ""))
        self.endpoint_api_key_env_input.setText(str(payload.get("api_key_env") or ""))
        kwargs_payload = payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {}
        self.endpoint_kwargs_input.setPlainText(str(kwargs_payload) if kwargs_payload else "")

    @staticmethod
    def _parse_float(value: str) -> float | None:
        stripped = value.strip()
        if not stripped:
            return None
        with contextlib.suppress(ValueError):
            return float(stripped)
        return None

    @staticmethod
    def _parse_int(value: str) -> int | None:
        stripped = value.strip()
        if not stripped:
            return None
        with contextlib.suppress(ValueError):
            return int(stripped)
        return None

    @staticmethod
    def _parse_mapping_text(value: str) -> dict[str, object]:
        stripped = value.strip()
        if not stripped:
            return {}
        with contextlib.suppress(Exception):
            parsed_json = json.loads(stripped)
            if isinstance(parsed_json, dict):
                return {str(key): value for key, value in parsed_json.items()}
        with contextlib.suppress(Exception):
            parsed_literal = ast.literal_eval(stripped)
            if isinstance(parsed_literal, dict):
                return {str(key): value for key, value in parsed_literal.items()}
        return {}

    def _save_endpoint_profile(self) -> None:
        name = self.endpoint_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Provide an endpoint profile name.")
            return
        provider_data = self.endpoint_provider_input.currentData()
        provider = provider_data if isinstance(provider_data, str) else None
        model = self.endpoint_model_input.text().strip() or None
        self.preferences.set_llm_endpoint_profile(
            name,
            provider=provider,
            model=model,
            temperature=self._parse_float(self.endpoint_temperature_input.text()),
            timeout=self._parse_float(self.endpoint_timeout_input.text()),
            max_retries=self._parse_int(self.endpoint_retries_input.text()),
            concurrency=self._parse_int(self.endpoint_concurrency_input.text()),
            base_url=self.endpoint_base_url_input.text().strip() or None,
            api_version=self.endpoint_api_version_input.text().strip() or None,
            api_key_env=self.endpoint_api_key_env_input.text().strip() or None,
            kwargs=self._parse_mapping_text(self.endpoint_kwargs_input.toPlainText()),
        )
        self._reload_endpoint_profiles()
        self.endpoint_select.setCurrentIndex(max(self.endpoint_select.findData(name), 0))

    def _remove_endpoint_profile(self) -> None:
        selected = self.endpoint_select.currentData()
        if not isinstance(selected, str):
            return
        self.preferences.remove_llm_endpoint_profile(selected)
        self._reload_endpoint_profiles()
        self.endpoint_select.setCurrentIndex(0)

    def _set_endpoint_action_busy(self, busy: bool) -> None:
        self.endpoint_save_button.setEnabled(not busy)
        self.endpoint_remove_button.setEnabled(not busy)
        self.endpoint_validate_button.setEnabled(not busy)

    @staticmethod
    def _validation_timestamp() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ")

    def _set_validation_status(self, text: str, color_hex: str) -> None:
        self.endpoint_validation_status.setText(text)
        self.endpoint_validation_status.setStyleSheet(f"color: {color_hex};")

    def _validate_endpoint_profile(self) -> None:
        provider_data = self.endpoint_provider_input.currentData()
        provider = provider_data if isinstance(provider_data, str) and provider_data.strip() else None
        model = self.endpoint_model_input.text().strip() or None
        if provider is None:
            QMessageBox.warning(self, "Missing Provider", "Select a provider before validating the endpoint.")
            return

        self._set_validation_status("Validating endpoint...", "#ff9800")
        self._set_endpoint_action_busy(True)

        def _run() -> tuple[bool, str]:
            backend = get_provider(provider)
            return asyncio.run(backend.validate_connection(model=model))

        self._endpoint_validate_worker = AsyncTaskThread(_run, self)
        self._endpoint_validate_worker.succeeded.connect(self._on_endpoint_validation_succeeded)
        self._endpoint_validate_worker.failed.connect(self._on_endpoint_validation_failed)
        self._endpoint_validate_worker.finished.connect(lambda: self._set_endpoint_action_busy(False))
        self._endpoint_validate_worker.start()

    def _on_endpoint_validation_succeeded(self, payload: object) -> None:
        if not (isinstance(payload, tuple) and len(payload) == 2):
            self._set_validation_status("Validation failed: unexpected result payload.", "#f44336")
            return
        ok_raw, message_raw = payload
        ok = bool(ok_raw)
        message = str(message_raw)
        prefix = "Validation passed" if ok else "Validation failed"
        self._last_endpoint_validation_at = self._validation_timestamp()
        color = "#4caf50" if ok else "#f44336"
        self._set_validation_status(
            f"{prefix}: {message}\nLast validated: {self._last_endpoint_validation_at}",
            color,
        )

    def _on_endpoint_validation_failed(self, message: str) -> None:
        self._last_endpoint_validation_at = self._validation_timestamp()
        self._set_validation_status(
            f"Validation failed: {message}\nLast validated: {self._last_endpoint_validation_at}",
            "#f44336",
        )

    def save(self) -> None:
        for step, (endpoint_input, provider_input, model_input, temperature_input, timeout_input, retries_input, concurrency_input, prompt_template_input, kwargs_input) in self.inputs.items():
            endpoint = endpoint_input.currentData()
            if not isinstance(endpoint, str):
                endpoint = None
            provider = provider_input.currentData()
            if not isinstance(provider, str):
                provider = None

            model = model_input.currentText().strip() or None

            self.preferences.set_workflow_profile(
                step,
                provider=provider,
                model=model,
            )
            self.preferences.set_llm_step_config(
                step,
                endpoint_profile=endpoint,
                provider=provider,
                model=model,
                temperature=self._parse_float(temperature_input.text()),
                timeout=self._parse_float(timeout_input.text()),
                max_retries=self._parse_int(retries_input.text()),
                concurrency=self._parse_int(concurrency_input.text()),
                prompt_template=prompt_template_input.text().strip() or None,
                kwargs=self._parse_mapping_text(kwargs_input.toPlainText()),
            )

        self.preferences.set_glossary_extraction_mode(self.glossary_mode_input.currentText().strip())
        self.preferences.set_glossary_extraction_prompt_template(self.glossary_prompt_input.toPlainText().strip() or None)

        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Profiles Saved", "Workflow profiles were updated.")

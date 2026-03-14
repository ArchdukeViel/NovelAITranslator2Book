from __future__ import annotations

import ast
import asyncio
import contextlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.shared import AsyncTaskThread
from novelai.providers.registry import available_models, available_providers, get_provider


STEP_DISPLAY_NAMES: dict[str, str] = {
    "glossary_extraction": "Glossary Extraction",
    "glossary_translation": "Glossary Translation",
    "glossary_review": "Glossary Review",
    "body_translation": "Body Translation",
    "polish": "Polish",
    "ocr": "OCR",
}

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
        self.refresh_callback = refresh_callback
        self._endpoint_validate_worker: AsyncTaskThread | None = None
        self._last_endpoint_validation_at: str | None = None
        self._step_order = list(WORKFLOW_PROFILE_STEPS)

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

        # ── Endpoint Library ───────────────────────────────────────────────────
        endpoint_group = QGroupBox("Endpoint Library")
        endpoint_outer = QVBoxLayout(endpoint_group)
        endpoint_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.endpoint_list = QListWidget()
        self.endpoint_list.setMinimumWidth(180)
        self.endpoint_list.setMaximumWidth(260)
        endpoint_splitter.addWidget(self.endpoint_list)

        endpoint_form_widget = QWidget()
        endpoint_form = QFormLayout(endpoint_form_widget)
        endpoint_form.setContentsMargins(8, 4, 4, 4)
        self.endpoint_name_input = QLineEdit()
        self.endpoint_provider_input = QComboBox()
        self.endpoint_provider_input.addItem("", None)
        for provider in sorted(available_providers()):
            self.endpoint_provider_input.addItem(provider, provider)
        self.endpoint_model_input = QComboBox()
        self.endpoint_model_input.setEditable(True)
        self.endpoint_temperature_input = QLineEdit()
        self.endpoint_timeout_input = QLineEdit()
        self.endpoint_retries_input = QLineEdit()
        self.endpoint_concurrency_input = QLineEdit()
        self.endpoint_base_url_input = QLineEdit()
        self.endpoint_api_version_input = QLineEdit()
        env_key_row = QHBoxLayout()
        self.endpoint_api_key_env_input = QLineEdit()
        self.endpoint_api_key_env_status = QLabel()
        self.endpoint_api_key_env_status.setMinimumWidth(80)
        env_key_row.addWidget(self.endpoint_api_key_env_input, 1)
        env_key_row.addWidget(self.endpoint_api_key_env_status)
        self.endpoint_kwargs_input = QPlainTextEdit()
        self.endpoint_kwargs_input.setPlaceholderText('{"top_p": 0.95}')
        self.endpoint_kwargs_input.setFixedHeight(80)
        endpoint_form.addRow("Name", self.endpoint_name_input)
        endpoint_form.addRow("Provider", self.endpoint_provider_input)
        endpoint_form.addRow("Model", self.endpoint_model_input)
        endpoint_form.addRow("Temperature", self.endpoint_temperature_input)
        endpoint_form.addRow("Timeout", self.endpoint_timeout_input)
        endpoint_form.addRow("Max Retries", self.endpoint_retries_input)
        endpoint_form.addRow("Concurrency", self.endpoint_concurrency_input)
        endpoint_form.addRow("Base URL", self.endpoint_base_url_input)
        endpoint_form.addRow("API Version", self.endpoint_api_version_input)
        endpoint_form.addRow("API Key Env", env_key_row)
        endpoint_form.addRow("Extra kwargs (JSON)", self.endpoint_kwargs_input)
        endpoint_splitter.addWidget(endpoint_form_widget)
        endpoint_splitter.setStretchFactor(0, 0)
        endpoint_splitter.setStretchFactor(1, 1)
        endpoint_outer.addWidget(endpoint_splitter)

        endpoint_buttons = QHBoxLayout()
        self.endpoint_save_button = QPushButton("Save Endpoint Profile")
        self.endpoint_duplicate_button = QPushButton("Duplicate")
        self.endpoint_remove_button = QPushButton("Remove Endpoint Profile")
        self.endpoint_validate_button = QPushButton("Validate Endpoint")
        endpoint_buttons.addWidget(self.endpoint_save_button)
        endpoint_buttons.addWidget(self.endpoint_duplicate_button)
        endpoint_buttons.addWidget(self.endpoint_remove_button)
        endpoint_buttons.addWidget(self.endpoint_validate_button)
        endpoint_buttons.addStretch()
        self.endpoint_validation_status = QLabel("")
        self.endpoint_validation_status.setObjectName("HeroBody")
        self.endpoint_validation_status.setWordWrap(True)
        endpoint_outer.addLayout(endpoint_buttons)
        endpoint_outer.addWidget(self.endpoint_validation_status)
        layout.addWidget(endpoint_group)

        # ── Resolution order info ──────────────────────────────────────────────
        resolution_info = QLabel(
            "Resolution order: Step override → Endpoint profile → Global defaults (Settings page)"
        )
        resolution_info.setObjectName("HeroBody")
        layout.addWidget(resolution_info)

        # ── Workflow Step Routing ──────────────────────────────────────────────
        routing_group = QGroupBox("Workflow Step Routing")
        routing_layout = QVBoxLayout(routing_group)

        self.step_table = QTableWidget(len(self._step_order), 5)
        self.step_table.setHorizontalHeaderLabels(["Step", "Intent", "Endpoint", "Provider", "Model"])
        self.step_table.verticalHeader().setVisible(False)
        self.step_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.step_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.step_table.setColumnWidth(0, 160)
        self.step_table.setColumnWidth(1, 260)
        self.step_table.setColumnWidth(2, 160)
        self.step_table.setColumnWidth(3, 140)
        self.step_table.setColumnWidth(4, 180)
        self.step_table.verticalHeader().setDefaultSectionSize(44)

        prefs = desktop_shared.container.preferences
        self.summary_inputs: dict[str, tuple[QComboBox, QComboBox, QComboBox]] = {}
        for row, step in enumerate(self._step_order):
            profile = prefs.get_workflow_profile(step)
            step_config = prefs.get_llm_step_config(step)

            step_item = QTableWidgetItem(STEP_DISPLAY_NAMES.get(step, step.replace("_", " ").title()))
            self.step_table.setItem(row, 0, step_item)
            hint_text = PROFILE_STEP_HINTS.get(step, "")
            intent_item = QTableWidgetItem(hint_text[:50] + ("…" if len(hint_text) > 50 else ""))
            intent_item.setToolTip(hint_text)
            self.step_table.setItem(row, 1, intent_item)

            endpoint_combo = QComboBox()
            endpoint_combo.addItem("Inherit", None)
            provider_combo = QComboBox()
            provider_combo.addItem("Inherit", None)
            for p in sorted(available_providers()):
                provider_combo.addItem(p, p)
            provider_combo.setCurrentIndex(max(provider_combo.findData(profile["provider"]), 0))
            model_combo = QComboBox()
            model_combo.setEditable(True)
            self._populate_models(model_combo, profile["provider"], profile["model"])
            provider_combo.currentIndexChanged.connect(
                lambda _index, s=step: self._refresh_step_models(s)
            )
            self.step_table.setCellWidget(row, 2, endpoint_combo)
            self.step_table.setCellWidget(row, 3, provider_combo)
            self.step_table.setCellWidget(row, 4, model_combo)
            self.summary_inputs[step] = (endpoint_combo, provider_combo, model_combo)

            endpoint_name = step_config.get("endpoint_profile")
            if isinstance(endpoint_name, str) and endpoint_name.strip():
                endpoint_combo.setCurrentText(endpoint_name)

        routing_layout.addWidget(self.step_table)

        self.detail_group = QGroupBox("Step Parameters — select a step above")
        detail_layout = QVBoxLayout(self.detail_group)
        self.detail_stack = QStackedWidget()
        self.detail_inputs: dict[str, tuple[QLineEdit, QLineEdit, QLineEdit, QLineEdit, QPlainTextEdit, QPlainTextEdit]] = {}
        for step in self._step_order:
            step_config = prefs.get_llm_step_config(step)
            page = QWidget()
            page_form = QFormLayout(page)
            temp_input = QLineEdit(str(step_config.get("temperature") or ""))
            timeout_input = QLineEdit(str(step_config.get("timeout") or ""))
            retries_input = QLineEdit(str(step_config.get("max_retries") or ""))
            conc_input = QLineEdit(str(step_config.get("concurrency") or ""))
            prompt_input = QPlainTextEdit()
            prompt_input.setPlaceholderText("Optional prompt template override for this step.")
            prompt_input.setFixedHeight(80)
            prompt_input.setPlainText(str(step_config.get("prompt_template") or ""))
            kwargs_input = QPlainTextEdit()
            kwargs_input.setFixedHeight(68)
            kwargs_payload = step_config.get("kwargs") if isinstance(step_config.get("kwargs"), dict) else {}
            kwargs_input.setPlainText(self._format_mapping_text(kwargs_payload))
            page_form.addRow("Temperature", temp_input)
            page_form.addRow("Timeout", timeout_input)
            page_form.addRow("Max Retries", retries_input)
            page_form.addRow("Concurrency", conc_input)
            page_form.addRow("Prompt Template", prompt_input)
            page_form.addRow("Extra kwargs (JSON)", kwargs_input)
            self.detail_stack.addWidget(page)
            self.detail_inputs[step] = (temp_input, timeout_input, retries_input, conc_input, prompt_input, kwargs_input)

        detail_layout.addWidget(self.detail_stack)
        routing_layout.addWidget(self.detail_group)
        layout.addWidget(routing_group)

        # ── Glossary Extraction ────────────────────────────────────────────────
        extraction_group = QGroupBox("Glossary Extraction")
        extraction_form = QFormLayout(extraction_group)
        self.glossary_mode_input = QComboBox()
        self.glossary_mode_input.addItems(["heuristic", "llm", "hybrid"])
        self.glossary_max_terms_input = QSpinBox()
        self.glossary_max_terms_input.setMinimum(1)
        self.glossary_max_terms_input.setMaximum(500)
        self.glossary_max_terms_input.setValue(50)
        self.glossary_prompt_input = QPlainTextEdit()
        self.glossary_prompt_input.setPlaceholderText(
            "Optional prompt template. Placeholders: {text}, {max_terms}, {source_language}"
        )
        self.glossary_prompt_input.setFixedHeight(120)
        extraction_form.addRow("Mode", self.glossary_mode_input)
        extraction_form.addRow("Max Terms per Extraction", self.glossary_max_terms_input)
        extraction_form.addRow("Prompt Template", self.glossary_prompt_input)
        layout.addWidget(extraction_group)

        save_button = QPushButton("Save Profiles")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()

        # ── Wire signals ───────────────────────────────────────────────────────
        self.endpoint_list.currentItemChanged.connect(self._on_endpoint_list_item_changed)
        self.endpoint_save_button.clicked.connect(self._save_endpoint_profile)
        self.endpoint_duplicate_button.clicked.connect(self._duplicate_endpoint_profile)
        self.endpoint_remove_button.clicked.connect(self._remove_endpoint_profile)
        self.endpoint_validate_button.clicked.connect(self._validate_endpoint_profile)
        self.endpoint_provider_input.currentIndexChanged.connect(self._refresh_endpoint_model_choices)
        self.endpoint_api_key_env_input.textChanged.connect(self._update_env_key_status)
        self.step_table.currentCellChanged.connect(self._on_step_table_row_changed)

        self._reload_endpoint_profiles()
        self.glossary_mode_input.setCurrentText(prefs.get_glossary_extraction_mode())
        self.glossary_max_terms_input.setValue(prefs.get_glossary_extraction_max_terms())
        self.glossary_prompt_input.setPlainText(prefs.get_glossary_extraction_prompt_template() or "")
        if self._step_order:
            self.step_table.selectRow(0)

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

    def _refresh_step_models(self, step: str) -> None:
        _endpoint_combo, provider_combo, model_combo = self.summary_inputs[step]
        provider = provider_combo.currentData()
        if not isinstance(provider, str):
            provider = None
        self._populate_models(model_combo, provider, model_combo.currentText().strip() or None)

    def _refresh_endpoint_model_choices(self) -> None:
        provider_data = self.endpoint_provider_input.currentData()
        provider = provider_data if isinstance(provider_data, str) else None
        current = self.endpoint_model_input.currentText().strip()
        self.endpoint_model_input.clear()
        self.endpoint_model_input.addItem("")
        if isinstance(provider, str) and provider.strip():
            with contextlib.suppress(Exception):
                for model in available_models(provider):
                    self.endpoint_model_input.addItem(model)
        if current and self.endpoint_model_input.findText(current) < 0:
            self.endpoint_model_input.addItem(current)
        self.endpoint_model_input.setCurrentText(current)

    def _update_env_key_status(self) -> None:
        env_var_name = self.endpoint_api_key_env_input.text().strip()
        if not env_var_name:
            self.endpoint_api_key_env_status.setText("")
            return
        if os.environ.get(env_var_name):
            self.endpoint_api_key_env_status.setText("● set")
            self.endpoint_api_key_env_status.setStyleSheet("color: #4caf50;")
        else:
            self.endpoint_api_key_env_status.setText("○ not set")
            self.endpoint_api_key_env_status.setStyleSheet("color: #888;")

    def _on_step_table_row_changed(
        self, current_row: int, _current_col: int, _previous_row: int, _previous_col: int
    ) -> None:
        if 0 <= current_row < len(self._step_order):
            step = self._step_order[current_row]
            self.detail_group.setTitle(
                f"Step Parameters — {STEP_DISPLAY_NAMES.get(step, step)}"
            )
            self.detail_stack.setCurrentIndex(current_row)

    def _reload_endpoint_profiles(self) -> None:
        profiles = desktop_shared.container.preferences.get_llm_endpoint_profiles()
        current_name: str | None = None
        current_item = self.endpoint_list.currentItem()
        if current_item is not None:
            current_name = current_item.data(Qt.ItemDataRole.UserRole)
        self.endpoint_list.blockSignals(True)
        self.endpoint_list.clear()
        for name in sorted(profiles.keys()):
            payload = profiles[name]
            provider_badge = payload.get("provider") or "—"
            item = QListWidgetItem(f"{name}  [{provider_badge}]")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.endpoint_list.addItem(item)
        self.endpoint_list.blockSignals(False)
        if current_name:
            for i in range(self.endpoint_list.count()):
                item = self.endpoint_list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == current_name:
                    self.endpoint_list.setCurrentItem(item)
                    break

        for step, (endpoint_combo, _provider_combo, _model_combo) in self.summary_inputs.items():
            current_endpoint = endpoint_combo.currentData()
            endpoint_combo.blockSignals(True)
            endpoint_combo.clear()
            endpoint_combo.addItem("Inherit", None)
            for name in sorted(profiles.keys()):
                endpoint_combo.addItem(name, name)
            if isinstance(current_endpoint, str) and endpoint_combo.findData(current_endpoint) >= 0:
                endpoint_combo.setCurrentIndex(endpoint_combo.findData(current_endpoint))
            endpoint_combo.blockSignals(False)

    def _on_endpoint_list_item_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.endpoint_name_input.clear()
            self.endpoint_provider_input.setCurrentIndex(0)
            self.endpoint_model_input.clear()
            self.endpoint_temperature_input.clear()
            self.endpoint_timeout_input.clear()
            self.endpoint_retries_input.clear()
            self.endpoint_concurrency_input.clear()
            self.endpoint_base_url_input.clear()
            self.endpoint_api_version_input.clear()
            self.endpoint_api_key_env_input.clear()
            self.endpoint_kwargs_input.clear()
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str):
            return
        profiles = desktop_shared.container.preferences.get_llm_endpoint_profiles()
        payload = profiles.get(name, {})
        provider = payload.get("provider")
        self.endpoint_name_input.setText(name)
        self.endpoint_provider_input.setCurrentIndex(max(self.endpoint_provider_input.findData(provider), 0))
        self._refresh_endpoint_model_choices()
        model = payload.get("model")
        self.endpoint_model_input.setCurrentText(model if isinstance(model, str) else "")
        self.endpoint_temperature_input.setText(str(payload.get("temperature") or ""))
        self.endpoint_timeout_input.setText(str(payload.get("timeout") or ""))
        self.endpoint_retries_input.setText(str(payload.get("max_retries") or ""))
        self.endpoint_concurrency_input.setText(str(payload.get("concurrency") or ""))
        self.endpoint_base_url_input.setText(str(payload.get("base_url") or ""))
        self.endpoint_api_version_input.setText(str(payload.get("api_version") or ""))
        self.endpoint_api_key_env_input.setText(str(payload.get("api_key_env") or ""))
        kwargs_payload = payload.get("kwargs") if isinstance(payload.get("kwargs"), dict) else {}
        self.endpoint_kwargs_input.setPlainText(self._format_mapping_text(kwargs_payload))

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
                return {str(key): val for key, val in parsed_json.items()}
        with contextlib.suppress(Exception):
            parsed_literal = ast.literal_eval(stripped)
            if isinstance(parsed_literal, dict):
                return {str(key): val for key, val in parsed_literal.items()}
        return {}

    @staticmethod
    def _format_mapping_text(value: object) -> str:
        if not isinstance(value, dict) or not value:
            return ""
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

    def _save_endpoint_profile(self) -> None:
        name = self.endpoint_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Provide an endpoint profile name.")
            return
        provider_data = self.endpoint_provider_input.currentData()
        provider = provider_data if isinstance(provider_data, str) else None
        model = self.endpoint_model_input.currentText().strip() or None
        desktop_shared.container.preferences.set_llm_endpoint_profile(
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
        for i in range(self.endpoint_list.count()):
            item = self.endpoint_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == name:
                self.endpoint_list.setCurrentItem(item)
                break

    def _duplicate_endpoint_profile(self) -> None:
        current = self.endpoint_list.currentItem()
        if current is None:
            return
        source_name = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(source_name, str):
            return
        prefs = desktop_shared.container.preferences
        profiles = prefs.get_llm_endpoint_profiles()
        source = profiles.get(source_name, {})
        new_name = f"{source_name} (copy)"
        counter = 2
        while new_name in profiles:
            new_name = f"{source_name} (copy {counter})"
            counter += 1
        prefs.set_llm_endpoint_profile(new_name, **source)
        self._reload_endpoint_profiles()
        for i in range(self.endpoint_list.count()):
            item = self.endpoint_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == new_name:
                self.endpoint_list.setCurrentItem(item)
                break

    def _remove_endpoint_profile(self) -> None:
        current = self.endpoint_list.currentItem()
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str):
            return
        desktop_shared.container.preferences.remove_llm_endpoint_profile(name)
        self._reload_endpoint_profiles()
        if self.endpoint_list.count() > 0:
            self.endpoint_list.setCurrentRow(0)

    def _set_endpoint_action_busy(self, busy: bool) -> None:
        self.endpoint_save_button.setEnabled(not busy)
        self.endpoint_duplicate_button.setEnabled(not busy)
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
        model = self.endpoint_model_input.currentText().strip() or None
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
        prefs = desktop_shared.container.preferences
        for step, (endpoint_combo, provider_combo, model_combo) in self.summary_inputs.items():
            endpoint = endpoint_combo.currentData()
            if not isinstance(endpoint, str):
                endpoint = None
            provider = provider_combo.currentData()
            if not isinstance(provider, str):
                provider = None
            model = model_combo.currentText().strip() or None
            temp_input, timeout_input, retries_input, conc_input, prompt_input, kwargs_input = self.detail_inputs[step]
            prefs.set_workflow_profile(step, provider=provider, model=model)
            prefs.set_llm_step_config(
                step,
                endpoint_profile=endpoint,
                provider=provider,
                model=model,
                temperature=self._parse_float(temp_input.text()),
                timeout=self._parse_float(timeout_input.text()),
                max_retries=self._parse_int(retries_input.text()),
                concurrency=self._parse_int(conc_input.text()),
                prompt_template=prompt_input.toPlainText().strip() or None,
                kwargs=self._parse_mapping_text(kwargs_input.toPlainText()),
            )
        prefs.set_glossary_extraction_mode(self.glossary_mode_input.currentText().strip())
        prefs.set_glossary_extraction_prompt_template(self.glossary_prompt_input.toPlainText().strip() or None)
        prefs.set_glossary_extraction_max_terms(self.glossary_max_terms_input.value())
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Profiles Saved", "Workflow profiles were updated.")

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.config.settings import settings
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions
from novelai.cost_estimator.pricing import list_supported_models
from novelai.inputs.registry import available_input_adapters
from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.shared import AsyncTaskThread, DesktopActivityModel, library_snapshots, safe_str
from novelai.providers.registry import available_models, available_providers
from novelai.sources.registry import available_sources
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection


def _selected_numbers(chapter_selection: str) -> set[int] | None:
    if is_full_chapter_selection(chapter_selection):
        return None
    return {spec.chapter for spec in parse_chapter_selection(chapter_selection)}


def _estimate_translation_budget(novel_id: str, chapter_selection: str, provider_key: str | None, model: str | None) -> str:
    storage = desktop_shared.container.storage
    meta = storage.load_metadata(novel_id)
    if not meta:
        raise ValueError("Metadata not found; import or scrape a project first.")

    selected_numbers = _selected_numbers(chapter_selection)
    chapter_count = 0
    japanese_characters = 0
    for chapter in meta.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id"))
        if selected_numbers is not None:
            if not chapter_id.isdigit() or int(chapter_id) not in selected_numbers:
                continue
        raw_data = storage.load_chapter(novel_id, chapter_id) or {}
        media_state = storage.load_chapter_media_state(novel_id, chapter_id) or {}
        text = None
        reviewed_ocr = media_state.get("ocr_text")
        if (
            bool(media_state.get("ocr_required"))
            and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
            and isinstance(reviewed_ocr, str)
            and reviewed_ocr.strip()
        ):
            text = reviewed_ocr
        elif isinstance(raw_data.get("text"), str):
            text = raw_data.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        chapter_count += 1
        japanese_characters += len("".join(text.split()))

    if japanese_characters <= 0:
        raise ValueError("Budget estimate unavailable because no source text was available.")

    if provider_key == "openai" and isinstance(model, str) and model in list_supported_models():
        estimate_models = [model]
        note = ""
    else:
        estimate_models = list(list_supported_models())
        note = "Reference estimate shown for supported priced models."

    comparison = compare_models(
        estimate_models,
        EstimationOptions(japanese_characters=japanese_characters),
    )

    lines = [
        f"Estimated source size: {japanese_characters} non-whitespace characters across {chapter_count} chapter(s).",
    ]
    if len(comparison.estimates) == 1:
        estimate = comparison.estimates[0]
        lines.append(
            f"Estimated tokens ({estimate.model_name}): {estimate.estimated_input_tokens} input / "
            f"{estimate.estimated_output_tokens} output."
        )
        lines.append(f"Estimated cost ({estimate.model_name}): ${estimate.estimated_total_cost_usd:.4f}.")
    else:
        lines.append("Estimated translation budget:")
        for estimate in comparison.estimates:
            lines.append(
                f"- {estimate.model_name}: {estimate.estimated_input_tokens} in / "
                f"{estimate.estimated_output_tokens} out / ${estimate.estimated_total_cost_usd:.4f}"
            )
        lines.append(
            f"Cheapest estimate: {comparison.cheapest_model} "
            f"(${comparison.cost_difference_usd:.4f} spread, {comparison.percentage_difference:.2f}%)."
        )
    if note:
        lines.append(note)
    return "\n".join(lines)


class TranslateTab(QWidget):
    activity = Signal(str)

    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = desktop_shared.container.orchestrator
        self._active_job_id: str | None = None
        self._runtime_busy = False
        self._preflight_block_reason: str | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.preflight_label = QLabel()
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setObjectName("HeroBody")
        layout.addWidget(self.preflight_label)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        progress_page = QWidget()
        progress_layout = QVBoxLayout(progress_page)
        form = QFormLayout()
        self.source_key_input = QComboBox()
        self.source_key_input.addItems(sorted(set(available_sources() + available_input_adapters() + ["imported"])))
        self.chapter_selection_input = QLineEdit("all")
        self.provider_input = QComboBox()
        self.provider_input.addItem("Inherit", None)
        for provider in sorted(available_providers()):
            self.provider_input.addItem(provider, provider)
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.source_language_input = QLineEdit()
        self.source_language_input.setPlaceholderText("auto")
        self.target_language_input = QLineEdit(settings.TRANSLATION_TARGET_LANGUAGE)
        self.style_input = QComboBox()
        self.style_input.addItem("")
        self.style_input.addItems(["fantasy", "romance", "action", "comedy"])
        self.confidence_threshold_input = QComboBox()
        self.confidence_threshold_input.setEditable(True)
        for option in ["0.35", "0.45", "0.55", "0.65", "0.75"]:
            self.confidence_threshold_input.addItem(option)
        self.confidence_threshold_input.setCurrentText("0.55")
        self.polish_low_confidence_only_input = QCheckBox("Polish low-confidence only")
        self.polish_low_confidence_only_input.setChecked(True)
        self.consistency_input = QCheckBox("Consistency mode")
        self.json_input = QCheckBox("JSON output mode")
        self.force_input = QCheckBox("Force retranslate")
        form.addRow("Source/Input Key", self.source_key_input)
        form.addRow("Chapter Selection", self.chapter_selection_input)
        form.addRow("Provider Override", self.provider_input)
        form.addRow("Model Override", self.model_input)
        form.addRow("Source Language Override", self.source_language_input)
        form.addRow("Target Language", self.target_language_input)
        form.addRow("Style Preset", self.style_input)
        form.addRow("Confidence Threshold", self.confidence_threshold_input)
        form.addRow("", self.polish_low_confidence_only_input)
        form.addRow("", self.consistency_input)
        form.addRow("", self.json_input)
        form.addRow("", self.force_input)
        progress_layout.addLayout(form)

        button_row = QHBoxLayout()
        self.estimate_button = QPushButton("Estimate Budget")
        self.translate_button = QPushButton("Translate")
        self.retranslate_button = QPushButton("Retranslate One")
        self.review_mode_button = QPushButton("Review Translations")
        button_row.addWidget(self.estimate_button)
        button_row.addWidget(self.translate_button)
        button_row.addWidget(self.retranslate_button)
        button_row.addWidget(self.review_mode_button)
        button_row.addStretch()
        self.translate_button.clicked.connect(self.start_translation)
        self.estimate_button.clicked.connect(self.estimate_budget)
        self.retranslate_button.clicked.connect(self.retranslate_one)
        self.review_mode_button.clicked.connect(self._switch_to_review)
        progress_layout.addLayout(button_row)

        phase_box = QGroupBox("Phased Workflow")
        phase_layout = QHBoxLayout(phase_box)
        self.phase1_button = QPushButton("Run Phase 1")
        self.phase1b_button = QPushButton("Run Phase 1b")
        self.phase2_button = QPushButton("Run Phase 2")
        self.phase_full_button = QPushButton("Run Full Pipeline")
        self.phase3_button = QPushButton("Optional Run Phase 3")
        phase_layout.addWidget(self.phase1_button)
        phase_layout.addWidget(self.phase1b_button)
        phase_layout.addWidget(self.phase2_button)
        phase_layout.addWidget(self.phase_full_button)
        phase_layout.addWidget(self.phase3_button)
        self.phase1_button.clicked.connect(self.run_phase1)
        self.phase1b_button.clicked.connect(self.run_phase1b)
        self.phase2_button.clicked.connect(self.run_phase2)
        self.phase_full_button.clicked.connect(self.run_full_pipeline)
        self.phase3_button.clicked.connect(self.run_phase3)
        progress_layout.addWidget(phase_box)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        progress_layout.addWidget(self.output)

        review_page = QWidget()
        review_layout = QVBoxLayout(review_page)
        review_toolbar = QHBoxLayout()
        self.back_to_progress_button = QPushButton("Back to Progress")
        self.refresh_review_button = QPushButton("Refresh Review")
        self.retranslate_selected_button = QPushButton("Retranslate Selected")
        review_toolbar.addWidget(self.back_to_progress_button)
        review_toolbar.addWidget(self.refresh_review_button)
        review_toolbar.addWidget(self.retranslate_selected_button)
        review_toolbar.addStretch()
        review_layout.addLayout(review_toolbar)
        self.back_to_progress_button.clicked.connect(self._switch_to_progress)
        self.refresh_review_button.clicked.connect(self._refresh_review_list)
        self.retranslate_selected_button.clicked.connect(self._retranslate_selected)

        review_splitter = QSplitter()
        self.review_chapter_list = QListWidget()
        self.review_chapter_list.currentItemChanged.connect(self._load_review_selection)
        review_splitter.addWidget(self.review_chapter_list)

        editor_group = QGroupBox("Translation Review")
        editor_layout = QVBoxLayout(editor_group)
        self.review_status_label = QLabel("Select a chapter to inspect translations.")
        self.review_status_label.setWordWrap(True)
        editor_layout.addWidget(self.review_status_label)
        editor_layout.addWidget(QLabel("Source Text"))
        self.review_source_text = QPlainTextEdit()
        self.review_source_text.setReadOnly(True)
        editor_layout.addWidget(self.review_source_text)
        editor_layout.addWidget(QLabel("Translated Text"))
        self.review_translated_text = QPlainTextEdit()
        editor_layout.addWidget(self.review_translated_text)
        edit_buttons = QHBoxLayout()
        self.save_review_button = QPushButton("Save Edited Translation")
        edit_buttons.addWidget(self.save_review_button)
        edit_buttons.addStretch()
        editor_layout.addLayout(edit_buttons)
        self.save_review_button.clicked.connect(self._save_review_translation)

        review_splitter.addWidget(editor_group)
        review_splitter.setStretchFactor(0, 1)
        review_splitter.setStretchFactor(1, 2)
        review_layout.addWidget(review_splitter)

        self.stack.addWidget(progress_page)
        self.stack.addWidget(review_page)
        self.stack.setCurrentWidget(progress_page)

        self.provider_input.currentIndexChanged.connect(self._refresh_model_choices)
        self.refresh()

    def _refresh_model_choices(self) -> None:
        provider = self.provider_input.currentData()
        current_model = self.model_input.currentText().strip()
        self.model_input.clear()
        self.model_input.addItem("")
        if isinstance(provider, str) and provider.strip():
            with contextlib.suppress(Exception):
                for model in available_models(provider):
                    self.model_input.addItem(model)
        if current_model and self.model_input.findText(current_model) < 0:
            self.model_input.addItem(current_model)
        self.model_input.setCurrentText(current_model)

    def refresh(self) -> None:
        snapshot = next((item for item in library_snapshots() if item["novel_id"] == self.novel_id), None)
        if snapshot is None:
            self.summary_label.setText("Project metadata not found.")
            self._preflight_block_reason = "Project metadata not found."
            self.preflight_label.setText(self._preflight_block_reason)
            self._sync_translation_controls()
            return
        self.summary_label.setText(
            f"Translated: {snapshot['translated_units']}/{snapshot['total_units']} | "
            f"OCR Pending: {snapshot['ocr_pending']} | Glossary Pending: {snapshot['glossary_pending']}"
        )
        default_source = safe_str(
            (desktop_shared.container.storage.load_metadata(self.novel_id) or {}).get("input_adapter_key"),
            "imported",
        )
        source_index = self.source_key_input.findText(default_source)
        if source_index >= 0:
            self.source_key_input.setCurrentIndex(source_index)
        self._preflight_block_reason = self._translation_preflight_reason(snapshot)
        self.preflight_label.setText(self._preflight_block_reason or "")
        self._sync_translation_controls()
        self._refresh_review_list()

    def _translation_preflight_reason(self, snapshot: dict[str, Any]) -> str | None:
        total_units = int(snapshot.get("total_units", 0))
        if total_units <= 0:
            return "Import or scrape chapters before starting translation."
        ocr_pending = int(snapshot.get("ocr_pending", 0))
        if ocr_pending > 0:
            return f"Resolve OCR pending items ({ocr_pending}) before translation."
        glossary_pending = int(snapshot.get("glossary_pending", 0))
        if glossary_pending > 0:
            return f"Review pending glossary terms ({glossary_pending}) before translation."
        return None

    def _switch_to_review(self) -> None:
        self._refresh_review_list()
        self.stack.setCurrentIndex(1)

    def _switch_to_progress(self) -> None:
        self.stack.setCurrentIndex(0)

    def _selected_review_chapter_id(self) -> str | None:
        item = self.review_chapter_list.currentItem()
        if item is None:
            return None
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        return chapter_id if isinstance(chapter_id, str) and chapter_id.isdigit() else None

    def _refresh_review_list(self) -> None:
        selected = self._selected_review_chapter_id()
        meta = desktop_shared.container.storage.load_metadata(self.novel_id) or {}
        chapter_rows = [row for row in meta.get("chapters", []) if isinstance(row, dict)]
        chapter_title_map = {
            str(row.get("id")): safe_str(row.get("translated_title") or row.get("title"), "")
            for row in chapter_rows
            if row.get("id") is not None
        }
        chapter_ids = [str(row.get("id")) for row in chapter_rows if row.get("id") is not None]
        if not chapter_ids:
            chapter_ids = desktop_shared.container.storage.list_stored_chapters(self.novel_id)

        self.review_chapter_list.clear()
        for chapter_id in chapter_ids:
            if not chapter_id.isdigit():
                continue
            translated = desktop_shared.container.storage.load_translated_chapter(self.novel_id, chapter_id)
            status = "translated" if translated and isinstance(translated.get("text"), str) and translated.get("text") else "pending"
            title = chapter_title_map.get(chapter_id, "")
            label = f"{chapter_id}"
            if title:
                label = f"{chapter_id} - {title}"
            item = QListWidgetItem(f"{label} [{status}]")
            item.setData(Qt.ItemDataRole.UserRole, chapter_id)
            self.review_chapter_list.addItem(item)
            if selected == chapter_id:
                self.review_chapter_list.setCurrentItem(item)

        if self.review_chapter_list.count() == 0:
            self.review_status_label.setText("No chapters available for review.")
            self.review_source_text.clear()
            self.review_translated_text.clear()
            return
        if self.review_chapter_list.currentItem() is None:
            self.review_chapter_list.setCurrentRow(0)

    def _load_review_selection(
        self,
        current: QListWidgetItem | None = None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        item = current or self.review_chapter_list.currentItem()
        if item is None:
            self.review_status_label.setText("Select a chapter to inspect translations.")
            self.review_source_text.clear()
            self.review_translated_text.clear()
            return
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(chapter_id, str):
            return

        raw_data = desktop_shared.container.storage.load_chapter(self.novel_id, chapter_id) or {}
        media_state = desktop_shared.container.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
        source_text: str = ""
        reviewed_ocr = media_state.get("ocr_text")
        if (
            bool(media_state.get("ocr_required"))
            and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
            and isinstance(reviewed_ocr, str)
            and reviewed_ocr.strip()
        ):
            source_text = reviewed_ocr
        else:
            raw_text = raw_data.get("text")
            if isinstance(raw_text, str):
                source_text = raw_text

        translated = desktop_shared.container.storage.load_translated_chapter(self.novel_id, chapter_id) or {}
        translated_value = translated.get("text")
        translated_text = translated_value if isinstance(translated_value, str) else ""
        translated_status = "translated" if translated_text.strip() else "pending"
        self.review_status_label.setText(f"Chapter {chapter_id} | Status: {translated_status}")
        self.review_source_text.setPlainText(source_text)
        self.review_translated_text.setPlainText(translated_text)

    def _save_review_translation(self) -> None:
        chapter_id = self._selected_review_chapter_id()
        if chapter_id is None:
            return
        text = self.review_translated_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Missing Translation", "Translated text cannot be empty.")
            return
        existing = desktop_shared.container.storage.load_translated_chapter(self.novel_id, chapter_id) or {}
        provider = existing.get("provider") if isinstance(existing.get("provider"), str) else None
        model = existing.get("model") if isinstance(existing.get("model"), str) else None
        desktop_shared.container.storage.save_translated_chapter(
            self.novel_id,
            chapter_id,
            text,
            provider=provider,
            model=model,
        )
        self.activity.emit(f"Saved reviewed translation for chapter {chapter_id}.")
        if self.refresh_callback is not None:
            self.refresh_callback()
        self._refresh_review_list()

    def _set_translation_controls_enabled(self, enabled: bool) -> None:
        self._runtime_busy = not enabled
        self._sync_translation_controls()

    def _sync_translation_controls(self) -> None:
        blocked_reason = self._preflight_block_reason
        allow_translate = (not self._runtime_busy) and blocked_reason is None
        allow_unblocked_busy = not self._runtime_busy
        self.translate_button.setEnabled(allow_translate)
        self.retranslate_button.setEnabled(allow_translate)
        self.retranslate_selected_button.setEnabled(allow_translate)
        self.phase1_button.setEnabled(allow_unblocked_busy)
        self.phase1b_button.setEnabled(allow_unblocked_busy)
        self.phase2_button.setEnabled(allow_unblocked_busy)
        self.phase_full_button.setEnabled(allow_unblocked_busy)
        self.phase3_button.setEnabled(allow_unblocked_busy)
        self.save_review_button.setEnabled(not self._runtime_busy)
        if blocked_reason and not self._runtime_busy:
            self.translate_button.setToolTip(blocked_reason)
            self.retranslate_button.setToolTip(blocked_reason)
            self.retranslate_selected_button.setToolTip(blocked_reason)
            self.phase2_button.setToolTip(blocked_reason)
        else:
            self.translate_button.setToolTip("")
            self.retranslate_button.setToolTip("")
            self.retranslate_selected_button.setToolTip("")
            self.phase2_button.setToolTip("")

    def _translation_runtime_options(self) -> dict[str, Any]:
        provider_key = self.provider_input.currentData()
        if not isinstance(provider_key, str):
            provider_key = None
        threshold_raw = self.confidence_threshold_input.currentText().strip()
        try:
            threshold = float(threshold_raw)
        except ValueError:
            threshold = 0.55
        threshold = max(0.0, min(1.0, threshold))
        return {
            "source_key": self.source_key_input.currentText(),
            "chapters": self.chapter_selection_input.text().strip() or "all",
            "provider_key": provider_key,
            "provider_model": self.model_input.currentText().strip() or None,
            "source_language": self.source_language_input.text().strip() or None,
            "target_language": self.target_language_input.text().strip() or None,
            "confidence_threshold": threshold,
            "polish_low_confidence_only": self.polish_low_confidence_only_input.isChecked(),
            "consistency_mode": self.consistency_input.isChecked(),
            "json_output": self.json_input.isChecked(),
        }

    def _start_translate_worker(self, *, job_label: str, runner: Callable[[], Any]) -> None:
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(job_label)
        self._set_translation_controls_enabled(False)

        worker = AsyncTaskThread(runner, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self._set_translation_controls_enabled(True))
        worker.start()
        self._worker = worker

    def estimate_budget(self) -> None:
        provider_key = self.provider_input.currentData()
        if not isinstance(provider_key, str):
            provider_key = desktop_shared.container.preferences.get_preferred_provider()
        model = self.model_input.currentText().strip() or desktop_shared.container.preferences.get_preferred_model()
        chapters = self.chapter_selection_input.text().strip() or "all"
        try:
            summary = _estimate_translation_budget(self.novel_id, chapters, provider_key, model)
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(str(exc))
            return
        self.output.setPlainText(summary)

    def start_translation(self) -> None:
        options = self._translation_runtime_options()
        source_key = str(options["source_key"])
        chapters = str(options["chapters"])
        style_preset = self.style_input.currentText().strip() or None
        consistency_mode = bool(options["consistency_mode"])
        json_output = bool(options["json_output"])
        force = self.force_input.isChecked()

        def _run() -> Any:
            asyncio.run(
                self.orchestrator.translate_chapters(
                    source_key,
                    self.novel_id,
                    chapters,
                    provider_key=options["provider_key"],
                    provider_model=options["provider_model"],
                    force=force,
                    source_language=options["source_language"],
                    target_language=options["target_language"],
                    style_preset=style_preset,
                    confidence_threshold=float(options["confidence_threshold"]),
                    mark_polish_needed=True,
                    consistency_mode=consistency_mode,
                    json_output=json_output,
                )
            )
            return "Translation completed."

        self._start_translate_worker(job_label=f"Translate {self.novel_id} ({chapters})", runner=_run)

    def translate_glossary_terms(self) -> None:
        options = self._translation_runtime_options()

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.translate_glossary_terms(
                    self.novel_id,
                    provider_key=options["provider_key"],
                    provider_model=options["provider_model"],
                    only_pending=True,
                )
            )

        self._start_translate_worker(job_label=f"Translate glossary {self.novel_id}", runner=_run)

    def run_phased_pipeline(self) -> None:
        self.run_full_pipeline()

    def polish_low_confidence(self) -> None:
        self.run_phase3()

    def _run_pipeline_phase(self, phase: str, *, run_polish_phase: bool) -> None:
        options = self._translation_runtime_options()

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.run_phased_translation_pipeline(
                    source_key=str(options["source_key"]),
                    novel_id=self.novel_id,
                    chapters=str(options["chapters"]),
                    phase=phase,
                    glossary_provider_key=options["provider_key"],
                    glossary_provider_model=options["provider_model"],
                    body_provider_key=options["provider_key"],
                    body_provider_model=options["provider_model"],
                    source_language=options["source_language"],
                    target_language=options["target_language"],
                    confidence_threshold=float(options["confidence_threshold"]),
                    polish_low_confidence_only=bool(options["polish_low_confidence_only"]),
                    consistency_mode=bool(options["consistency_mode"]),
                    json_output=bool(options["json_output"]),
                    run_polish_phase=run_polish_phase,
                )
            )

        self._start_translate_worker(job_label=f"Pipeline {phase} {self.novel_id}", runner=_run)

    def run_phase1(self) -> None:
        self._run_pipeline_phase("1", run_polish_phase=False)

    def run_phase1b(self) -> None:
        self._run_pipeline_phase("1b", run_polish_phase=False)

    def run_phase2(self) -> None:
        self._run_pipeline_phase("2", run_polish_phase=False)

    def run_full_pipeline(self) -> None:
        self._run_pipeline_phase("full", run_polish_phase=False)

    def run_phase3(self) -> None:
        self._run_pipeline_phase("3", run_polish_phase=True)

    def _retranslate_selected(self) -> None:
        chapter_id = self._selected_review_chapter_id()
        if chapter_id is None:
            self.output.setPlainText("Select a chapter in review mode to retranslate.")
            return
        self.chapter_selection_input.setText(chapter_id)
        self.retranslate_one()

    def retranslate_one(self) -> None:
        options = self._translation_runtime_options()
        source_key = str(options["source_key"])
        chapter_id = self.chapter_selection_input.text().strip()
        if not chapter_id.isdigit():
            selected = self._selected_review_chapter_id()
            if selected is not None:
                chapter_id = selected
                self.chapter_selection_input.setText(chapter_id)
        if not chapter_id.isdigit():
            self.output.setPlainText("Retranslate One requires a single numeric chapter ID in Chapter Selection.")
            return
        style_preset = self.style_input.currentText().strip() or None
        consistency_mode = bool(options["consistency_mode"])
        json_output = bool(options["json_output"])

        def _run() -> Any:
            asyncio.run(
                self.orchestrator.retranslate_chapter(
                    source_key=source_key,
                    novel_id=self.novel_id,
                    chapter_id=chapter_id,
                    provider_key=options["provider_key"],
                    provider_model=options["provider_model"],
                    source_language=options["source_language"],
                    target_language=options["target_language"],
                    style_preset=style_preset,
                    consistency_mode=consistency_mode,
                    json_output=json_output,
                )
            )
            return f"Retranslated chapter {chapter_id}."

        self._start_translate_worker(job_label=f"Retranslate {self.novel_id}/{chapter_id}", runner=_run)

    def _on_success(self, payload: object) -> None:
        formatted = self._format_runtime_payload(payload)
        self.output.setPlainText(formatted)
        finished_message = formatted if isinstance(payload, (dict, str)) else f"Translation completed for {self.novel_id}."
        if self.activity_model is not None and isinstance(payload, dict) and isinstance(payload.get("phase"), str):
            self.activity_model.add_phase_event(self.novel_id, payload)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, finished_message)
        self._active_job_id = None
        self.activity.emit(formatted)
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.refresh()
        self._refresh_review_list()
        self._extract_new_terms_background()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.fail_job(self._active_job_id, f"Translation failed for {self.novel_id}: {message}")
        self._active_job_id = None
        self.activity.emit(f"Translation failed: {message}")

    def _extract_new_terms_background(self) -> None:
        def _run() -> Any:
            return asyncio.run(self.orchestrator.extract_glossary_terms(self.novel_id, max_terms=50))

        self._bg_extract_worker = AsyncTaskThread(_run, self)
        self._bg_extract_worker.succeeded.connect(self._on_background_extract_success)
        self._bg_extract_worker.failed.connect(lambda _msg: None)
        self._bg_extract_worker.start()

    def _on_background_extract_success(self, payload: object) -> None:
        summary = payload if isinstance(payload, dict) else {}
        added = int(summary.get("added", 0))
        if added > 0:
            self.activity.emit(f"Auto-extracted {added} new glossary term(s) for {self.novel_id}.")
            if self.refresh_callback is not None:
                self.refresh_callback()

    @staticmethod
    def _format_runtime_payload(payload: object) -> str:
        if isinstance(payload, str):
            return payload
        if not isinstance(payload, dict):
            return str(payload)

        phase = str(payload.get("phase") or "")
        status = str(payload.get("status") or "")
        message = str(payload.get("message") or "")
        lines = []
        if phase:
            lines.append(f"{phase} [{status}]")
        if message:
            lines.append(message)
        blocked_reason = payload.get("blocked_reason")
        if isinstance(blocked_reason, str) and blocked_reason.strip():
            lines.append(f"Blocked: {blocked_reason}")

        results = payload.get("results")
        if isinstance(results, dict):
            for key, value in results.items():
                if isinstance(value, dict):
                    summary = value.get("message") or value.get("status") or "completed"
                    lines.append(f"- {key}: {summary}")
                else:
                    lines.append(f"- {key}: {value}")

        if not lines:
            lines.append(str(payload))
        return "\n".join(lines)

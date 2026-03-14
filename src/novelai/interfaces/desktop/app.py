from __future__ import annotations

import asyncio
import contextlib
import hashlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QInputDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QFileDialog,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QListView,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container
from novelai.config.settings import settings
from novelai.core.chapter_state import ChapterState
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions
from novelai.cost_estimator.pricing import list_supported_models
from novelai.glossary import glossary_status_counts
from novelai.inputs.registry import available_input_adapters, detect_input_adapter
from novelai.interfaces.desktop.pages import (
    ActivityView,
    DiagnosticsView,
    HomeView,
    LLMOpsView,
    LibraryView,
)
from novelai.interfaces.desktop.export_helpers import build_export_output_path, build_export_plan
from novelai.interfaces.desktop.shared import (
    AsyncTaskThread,
    DesktopActivityModel,
    StatCard,
    build_stylesheet,
    library_snapshots,
    profiles_snapshot_text,
    recent_export_paths,
    safe_str,
    timestamp_label,
)
from novelai.providers.registry import available_models, available_providers
from novelai.sources.registry import available_sources, detect_source
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection


def _selected_numbers(chapter_selection: str) -> set[int] | None:
    if is_full_chapter_selection(chapter_selection):
        return None
    return {spec.chapter for spec in parse_chapter_selection(chapter_selection)}


def _estimate_translation_budget(novel_id: str, chapter_selection: str, provider_key: str | None, model: str | None) -> str:
    storage = container.storage
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



class ImportTab(QWidget):
    activity = Signal(str)
    completed = Signal()

    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.fixed_novel_id = novel_id or None
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = container.orchestrator
        self._active_job_id: str | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit(self.fixed_novel_id or "")
        self.title_input.setReadOnly(self.fixed_novel_id is not None)
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        browse_button = QPushButton("Select Item")
        browse_button.clicked.connect(self.browse_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_input)
        source_row.addWidget(browse_button)
        format_note = QLabel(
            "Allowed formats: URL, .txt/.md/.html, .epub, .pdf, .cbz, or an image folder."
        )
        format_note.setObjectName("HeroBody")
        format_note.setWordWrap(True)
        form.addRow("Novel Title", self.title_input)
        form.addRow("Select Item", source_row)
        form.addRow("", format_note)
        layout.addLayout(form)
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.start_import)
        layout.addWidget(self.import_button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.output)

    def _build_novel_id_from_title(self, title: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
        if not normalized:
            normalized = "novel"
        token = hashlib.sha1(title.encode("utf-8", errors="ignore")).hexdigest()[:6]
        return f"{normalized[:24]}-{token}"

    def browse_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Source File",
            "",
            "Supported Files (*.txt *.md *.html *.htm *.epub *.pdf *.cbz);;All Files (*)",
        )
        if not path:
            return
        self.source_input.setText(path)

    def _detect_adapter(self, source: str) -> str | None:
        return detect_input_adapter(source)

    def start_import(self) -> None:
        title = (self.fixed_novel_id or self.title_input.text()).strip()
        source = self.source_input.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing Novel Title", "Provide a novel title before importing.")
            return
        if not source:
            QMessageBox.warning(self, "Missing Item", "Choose a file or folder to import.")
            return
        adapter_key = self._detect_adapter(source)
        if adapter_key is None:
            QMessageBox.warning(
                self,
                "Unsupported Format",
                "Could not detect an adapter for this item. Allowed: URL, text/html, epub, pdf, cbz, or image folder.",
            )
            return
        novel_id = self._build_novel_id_from_title(title)
        self.novel_id = novel_id
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(f"Import {novel_id} via {adapter_key}")
        self.import_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.import_document(
                    adapter_key,
                    novel_id,
                    source,
                )
            )

        worker = AsyncTaskThread(_run, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self.import_button.setEnabled(True))
        worker.start()
        self._worker = worker

    def _on_success(self, payload: object) -> None:
        self.output.setPlainText(str(payload))
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, f"Completed import for {self.novel_id}.")
        self._active_job_id = None
        self.activity.emit("Import completed.")
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.completed.emit()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.fail_job(self._active_job_id, f"Import failed for {self.novel_id}: {message}")
        self._active_job_id = None
        self.activity.emit(f"Import failed: {message}")


class ImportPage(QWidget):
    open_workspace_requested = Signal(str)

    def __init__(
        self,
        activity_model: DesktopActivityModel,
        refresh_callback: Callable[[], None],
    ) -> None:
        super().__init__()
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("IMPORT AND SCRAPE")
        title.setObjectName("HeroTitle")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.import_panel = ImportTab(
            "",
            activity_model=self.activity_model,
            refresh_callback=self.refresh_callback,
        )
        self.import_panel.novel_id = ""
        self.source_panel = SourceScrapePanel(
            activity_model=self.activity_model,
            refresh_callback=self.refresh_callback,
        )
        self.tabs.addTab(self.import_panel, "Import")
        self.tabs.addTab(self.source_panel, "Scrape")
        layout.addWidget(self.tabs)

        self.import_panel.completed.connect(self._open_imported_workspace)
        self.source_panel.completed.connect(self._open_scraped_workspace)

    def _open_imported_workspace(self) -> None:
        novel_id = self.import_panel.novel_id.strip() if hasattr(self.import_panel, "novel_id") else ""
        if not novel_id:
            return
        self.open_workspace_requested.emit(novel_id)

    def _open_scraped_workspace(self) -> None:
        novel_id = self.source_panel._resolved_novel_id()
        if not novel_id:
            return
        self.open_workspace_requested.emit(novel_id)

    def refresh(self) -> None:
        return


class SourceScrapePanel(QWidget):
    activity = Signal(str)
    completed = Signal()

    def __init__(
        self,
        *,
        fixed_novel_id: str | None = None,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.fixed_novel_id = fixed_novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        self._active_job_id: str | None = None
        self._progress_emit: Callable[[str], None] | None = None
        self._source_detected = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.novel_input = QLineEdit(fixed_novel_id or "")
        self.novel_input.setReadOnly(fixed_novel_id is not None)
        self.source_input = QLineEdit()
        self.source_input.setReadOnly(True)
        self.source_input.setPlaceholderText("Auto-detected from novel URL")
        self.chapter_selection_input = QLineEdit()
        self.chapter_selection_input.setPlaceholderText("all or range like 1-10, 12")
        form.addRow("Novel URL", self.novel_input)
        form.addRow("Source Adapter", self.source_input)
        form.addRow("Chapter", self.chapter_selection_input)
        layout.addLayout(form)

        controls = QHBoxLayout()
        self.scrape_button = QPushButton("Scrape")
        controls.addWidget(self.scrape_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.output)

        self.novel_input.textChanged.connect(self._auto_detect_source_adapter)
        self.scrape_button.clicked.connect(self.start_scrape)
        self._auto_detect_source_adapter(self._resolved_novel_id())

    def _resolved_novel_id(self) -> str:
        return (self.fixed_novel_id or self.novel_input.text()).strip()

    def _auto_detect_source_adapter(self, candidate: str) -> None:
        normalized = candidate.strip()
        if not normalized:
            self._source_detected = False
            self.source_input.clear()
            return
        detected = detect_source(normalized)
        if detected is None:
            self._source_detected = False
            self.source_input.clear()
            return
        self._source_detected = True
        self.source_input.setText(detected)

    def _resolved_source_key(self) -> str | None:
        self._auto_detect_source_adapter(self._resolved_novel_id())
        if not self._source_detected:
            return None
        source_key = self.source_input.text().strip()
        return source_key if source_key else None

    def _select_scrape_mode(self) -> str | None:
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Scrape Mode")
        dialog.setLabelText("Select scrape mode:")
        dialog.setComboBoxItems(["Scrape Metadata", "Scrape Chapters", "Full"])
        dialog.setComboBoxEditable(False)
        dialog.setTextValue("Full")
        if not dialog.exec():
            return None
        mode = dialog.textValue().strip().lower()
        if mode == "scrape metadata":
            return "metadata"
        if mode == "scrape chapters":
            return "chapters"
        return "full"

    def _set_busy(self, busy: bool) -> None:
        self.scrape_button.setEnabled(not busy)

    def start_scrape(self) -> None:
        mode = self._select_scrape_mode()
        if mode is None:
            return

        novel_id = self._resolved_novel_id()
        if not novel_id:
            QMessageBox.warning(self, "Missing URL", "Provide a novel URL or source identifier.")
            return
        source_key = self._resolved_source_key()
        if source_key is None:
            QMessageBox.warning(
                self,
                "Source Not Detected",
                "Could not auto-detect source adapter from the provided URL/identifier.",
            )
            return
        selection = self.chapter_selection_input.text().strip() or "all"

        if mode == "metadata":
            self.start_metadata_scrape(novel_id, source_key)
            return
        if mode == "chapters":
            self.start_chapter_scrape(novel_id, source_key, selection)
            return
        self.start_full_sync(novel_id, source_key, selection)

    def detect_source_adapter(self) -> None:
        candidate = self._resolved_novel_id()
        detected = detect_source(candidate)
        if detected is None:
            self._source_detected = False
            self.output.setPlainText("Could not auto-detect a source adapter from the current identifier/URL.")
            return
        self._source_detected = True
        self.source_input.setText(detected)
        self.output.setPlainText(f"Detected source adapter: {detected}")

    def _start_task(self, label: str, fn: Callable[[], Any], success_message: str) -> None:
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(label)
        self._set_busy(True)
        self.output.clear()
        self.output.appendPlainText(f"Starting: {label}")
        self._worker = AsyncTaskThread(fn, self)
        self._progress_emit = self._worker.progress.emit
        self._worker.progress.connect(self.output.appendPlainText)
        self._worker.succeeded.connect(lambda payload: self._on_success(payload, success_message))
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def start_metadata_scrape(self, novel_id: str, source_key: str) -> None:

        def _run() -> Any:
            def _prog(msg: str) -> None:
                if self._progress_emit:
                    self._progress_emit(msg)

            return asyncio.run(
                self.orchestrator.scrape_metadata(
                    source_key,
                    novel_id,
                    mode="update",
                    max_chapter=None,
                    progress_callback=_prog,
                )
            )

        self._start_task(
            f"Scrape metadata for {novel_id} via {source_key}",
            _run,
            f"Metadata scraped for {novel_id}.",
        )

    def start_chapter_scrape(self, novel_id: str, source_key: str, selection: str) -> None:

        def _run() -> Any:
            def _prog(msg: str) -> None:
                if self._progress_emit:
                    self._progress_emit(msg)

            asyncio.run(
                self.orchestrator.scrape_chapters(
                    source_key,
                    novel_id,
                    selection,
                    mode="update",
                    progress_callback=_prog,
                )
            )
            return {"novel_id": novel_id, "selection": selection}

        self._start_task(
            f"Scrape chapters for {novel_id} ({selection})",
            _run,
            f"Chapters scraped for {novel_id} ({selection}).",
        )

    def start_full_sync(self, novel_id: str, source_key: str, selection: str) -> None:

        def _run() -> Any:
            def _prog(msg: str) -> None:
                if self._progress_emit:
                    self._progress_emit(msg)

            metadata = asyncio.run(
                self.orchestrator.scrape_metadata(
                    source_key,
                    novel_id,
                    mode="update",
                    max_chapter=None,
                    progress_callback=_prog,
                )
            )
            asyncio.run(
                self.orchestrator.scrape_chapters(
                    source_key,
                    novel_id,
                    selection,
                    mode="update",
                    progress_callback=_prog,
                )
            )
            return metadata

        self._start_task(
            f"Sync source novel {novel_id}",
            _run,
            f"Source sync completed for {novel_id}.",
        )

    def _on_success(self, payload: object, message: str) -> None:
        self.output.appendPlainText(f"\n[Done] {message}")
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, message)
        self._active_job_id = None
        self.activity.emit(message)
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.completed.emit()

    def _on_error(self, message: str) -> None:
        self.output.appendPlainText(f"\n[Error] {message}")
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.fail_job(self._active_job_id, f"Source scrape failed: {message}")
        self._active_job_id = None
        self.activity.emit(f"Source scrape failed: {message}")


class OCRReviewTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        self._current_chapter_id: str | None = None
        self._pages: list[dict[str, Any]] = []
        self._page_index = 0
        self._ocr_block_reason: str | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.preflight_label = QLabel()
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setObjectName("HeroBody")
        layout.addWidget(self.preflight_label)

        ingest_group = QGroupBox("OCR Candidate Ingest")
        ingest_layout = QFormLayout(ingest_group)
        self.ingest_selection_input = QLineEdit("all")
        self.overwrite_input = QCheckBox("Overwrite reviewed text")
        self.required_input = QCheckBox("Require OCR review before translation")
        self.required_input.setChecked(True)
        ingest_buttons = QHBoxLayout()
        self.ingest_button = QPushButton("Ingest OCR Candidates")
        self.list_pending_button = QPushButton("List Pending")
        ingest_buttons.addWidget(self.ingest_button)
        ingest_buttons.addWidget(self.list_pending_button)
        ingest_layout.addRow("Chapter Selection", self.ingest_selection_input)
        ingest_layout.addRow("", self.required_input)
        ingest_layout.addRow("", self.overwrite_input)
        ingest_layout.addRow("", ingest_buttons)
        layout.addWidget(ingest_group)

        self.chapter_list = QListWidget()
        self.chapter_list.currentItemChanged.connect(self._load_current)
        self.chapter_list.setMinimumWidth(240)
        self.ocr_text = QPlainTextEdit()
        self.status_input = QComboBox()
        self.status_input.addItems(["pending", "reviewed", "skipped", "failed"])
        editor_group = QGroupBox("OCR Review")
        editor_layout = QVBoxLayout(editor_group)
        nav_layout = QHBoxLayout()
        self.first_button = QPushButton("|<")
        self.prev_button = QPushButton("<")
        self.page_label = QLabel("Page 0 of 0")
        self.page_input = QSpinBox()
        self.page_input.setMinimum(1)
        self.page_input.setMaximum(1)
        self.go_button = QPushButton("Go")
        self.next_button = QPushButton(">")
        self.last_button = QPushButton(">|")
        nav_layout.addWidget(self.first_button)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.page_label)
        nav_layout.addStretch()
        nav_layout.addWidget(QLabel("Go to"))
        nav_layout.addWidget(self.page_input)
        nav_layout.addWidget(self.go_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.last_button)
        editor_layout.addLayout(nav_layout)
        editor_form = QFormLayout()
        editor_form.addRow("Status", self.status_input)
        editor_layout.addLayout(editor_form)
        editor_layout.addWidget(self.ocr_text)
        editor_buttons = QHBoxLayout()
        self.review_button = QPushButton("Mark Reviewed")
        self.save_button = QPushButton("Save Status")
        editor_buttons.addWidget(self.review_button)
        editor_buttons.addWidget(self.save_button)
        editor_buttons.addStretch()
        editor_layout.addLayout(editor_buttons)

        splitter = QSplitter()
        splitter.addWidget(self.chapter_list)
        splitter.addWidget(editor_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        self.ingest_button.clicked.connect(self.ingest_candidates)
        self.list_pending_button.clicked.connect(self._show_pending_summary)
        self.review_button.clicked.connect(self.mark_reviewed)
        self.save_button.clicked.connect(self.save_status)
        self.first_button.clicked.connect(lambda: self._go_to_page(0))
        self.prev_button.clicked.connect(lambda: self._go_to_page(self._page_index - 1))
        self.next_button.clicked.connect(lambda: self._go_to_page(self._page_index + 1))
        self.last_button.clicked.connect(lambda: self._go_to_page(len(self._pages) - 1))
        self.go_button.clicked.connect(self._go_to_entered_page)
        self.refresh()

    def _apply_ocr_preflight(self) -> None:
        has_items = self.chapter_list.count() > 0
        self.ingest_button.setEnabled(has_items)
        self.list_pending_button.setEnabled(has_items)
        self.review_button.setEnabled(has_items)
        self.save_button.setEnabled(has_items)
        if has_items:
            self._ocr_block_reason = None
            self.preflight_label.setText("")
            for button in (self.ingest_button, self.list_pending_button, self.review_button, self.save_button):
                button.setToolTip("")
            return

        self._ocr_block_reason = "Import or scrape chapters before running OCR review."
        self.preflight_label.setText(self._ocr_block_reason)
        for button in (self.ingest_button, self.list_pending_button, self.review_button, self.save_button):
            button.setToolTip(self._ocr_block_reason)

    def refresh(self) -> None:
        pending = 0
        total_required = 0
        self.chapter_list.clear()
        for chapter_id in self.storage.list_stored_chapters(self.novel_id):
            media = self.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
            if not bool(media.get("ocr_required", False)):
                continue
            total_required += 1
            status = str(media.get("ocr_status") or "pending").strip().lower()
            if status != "reviewed":
                pending += 1
            item = QListWidgetItem(f"Chapter {chapter_id} [{status}]")
            item.setData(Qt.ItemDataRole.UserRole, chapter_id)
            self.chapter_list.addItem(item)
        self.summary_label.setText(
            f"OCR-required chapters: {total_required} | Pending review: {pending}"
        )
        if self.chapter_list.count() == 0:
            self.ocr_text.setPlainText("No OCR review items for this project.")
            self._current_chapter_id = None
            self._pages = []
            self._page_index = 0
            self._update_navigation()
        elif self.chapter_list.currentItem() is None:
            self.chapter_list.setCurrentRow(0)
        self._apply_ocr_preflight()

    def _build_pages(self, media: dict[str, Any]) -> list[dict[str, Any]]:
        pages = media.get("ocr_pages")
        normalized: list[dict[str, Any]] = []
        if isinstance(pages, list):
            for index, page in enumerate(pages, start=1):
                if not isinstance(page, dict):
                    continue
                text = page.get("text") if isinstance(page.get("text"), str) else ""
                status = str(page.get("status") or "pending").strip().lower()
                if status not in {"pending", "reviewed", "skipped", "failed"}:
                    status = "pending"
                normalized.append({"page": index, "text": text, "status": status})
        if normalized:
            return normalized

        fallback_text = media.get("ocr_text") if isinstance(media.get("ocr_text"), str) else ""
        fallback_status = str(media.get("ocr_status") or "pending").strip().lower()
        if fallback_status not in {"pending", "reviewed", "skipped", "failed"}:
            fallback_status = "pending"
        return [{"page": 1, "text": fallback_text, "status": fallback_status}]

    def _aggregate_status(self, pages: list[dict[str, Any]]) -> str:
        statuses = {str(page.get("status") or "pending") for page in pages}
        if statuses == {"reviewed"}:
            return "reviewed"
        if "failed" in statuses:
            return "failed"
        if "pending" in statuses:
            return "pending"
        if "reviewed" in statuses:
            return "pending"
        if "skipped" in statuses and len(statuses) == 1:
            return "skipped"
        return "pending"

    def _compose_ocr_text(self, pages: list[dict[str, Any]]) -> str:
        chunks = [str(page.get("text") or "").strip() for page in pages]
        return "\n\n".join(chunk for chunk in chunks if chunk)

    def _persist_pages(self, *, override_status: str | None = None) -> None:
        if not self._current_chapter_id:
            return
        status = override_status or self._aggregate_status(self._pages)
        payload: dict[str, Any] = {
            "ocr_required": self.required_input.isChecked(),
            "ocr_pages": self._pages,
            "ocr_text": self._compose_ocr_text(self._pages),
            "ocr_status": status,
        }
        if status == "reviewed":
            payload["reembed_status"] = "pending"
        self.storage.save_chapter_media_state(self.novel_id, self._current_chapter_id, **payload)

    def _update_navigation(self) -> None:
        total = len(self._pages)
        current = self._page_index + 1 if total else 0
        self.page_label.setText(f"Page {current} of {total}")
        self.page_input.blockSignals(True)
        self.page_input.setMaximum(max(total, 1))
        self.page_input.setValue(max(current, 1))
        self.page_input.blockSignals(False)
        has_pages = total > 0
        self.first_button.setEnabled(has_pages and self._page_index > 0)
        self.prev_button.setEnabled(has_pages and self._page_index > 0)
        self.next_button.setEnabled(has_pages and self._page_index < total - 1)
        self.last_button.setEnabled(has_pages and self._page_index < total - 1)
        self.go_button.setEnabled(has_pages)

    def _show_current_page(self) -> None:
        if not self._pages:
            self.ocr_text.clear()
            self.status_input.setCurrentText("pending")
            self._update_navigation()
            return
        page = self._pages[self._page_index]
        self.ocr_text.setPlainText(str(page.get("text") or ""))
        status = str(page.get("status") or "pending")
        self.status_input.setCurrentText(status if status in {"pending", "reviewed", "skipped", "failed"} else "pending")
        self._update_navigation()

    def _go_to_page(self, index: int) -> None:
        if not self._pages:
            return
        index = max(0, min(index, len(self._pages) - 1))
        if index == self._page_index:
            return
        # Save current edits before switching pages.
        self._pages[self._page_index]["text"] = self.ocr_text.toPlainText()
        self._pages[self._page_index]["status"] = self.status_input.currentText().strip()
        self._page_index = index
        self._show_current_page()

    def _go_to_entered_page(self) -> None:
        self._go_to_page(self.page_input.value() - 1)

    def _load_current(self, current: QListWidgetItem | None = None, _previous: QListWidgetItem | None = None) -> None:
        item = current or self.chapter_list.currentItem()
        if item is None:
            self.ocr_text.clear()
            self._current_chapter_id = None
            self._pages = []
            self._page_index = 0
            self._update_navigation()
            return
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        self._current_chapter_id = str(chapter_id)
        media = self.storage.load_chapter_media_state(self.novel_id, self._current_chapter_id) or {}
        self._pages = self._build_pages(media)
        self._page_index = 0
        self.required_input.setChecked(bool(media.get("ocr_required", False)))
        self._show_current_page()

    def ingest_candidates(self) -> None:
        selection = self.ingest_selection_input.text().strip() or "all"
        self.ingest_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.ingest_ocr_candidates(
                    novel_id=self.novel_id,
                    chapters=selection,
                    mark_required=self.required_input.isChecked(),
                    overwrite=self.overwrite_input.isChecked(),
                )
            )

        self._worker = AsyncTaskThread(_run, self)
        self._worker.succeeded.connect(self._on_ingest_success)
        self._worker.failed.connect(self._on_ingest_error)
        self._worker.finished.connect(lambda: self.ingest_button.setEnabled(True))
        self._worker.start()

    def _on_ingest_success(self, payload: object) -> None:
        self.activity.emit(f"OCR ingest completed for {self.novel_id}.")
        self.ocr_text.setPlainText(str(payload))
        self.refresh()

    def _on_ingest_error(self, message: str) -> None:
        self.activity.emit(f"OCR ingest failed: {message}")
        self.ocr_text.setPlainText(message)

    def _show_pending_summary(self) -> None:
        pending_lines: list[str] = []
        for chapter_id in self.storage.list_stored_chapters(self.novel_id):
            media = self.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
            if not bool(media.get("ocr_required", False)):
                continue
            status = str(media.get("ocr_status") or "pending").strip().lower()
            if status != "reviewed":
                pending_lines.append(f"[{status}] chapter {chapter_id}")
        self.ocr_text.setPlainText("\n".join(pending_lines) if pending_lines else "No chapters pending OCR review.")

    def mark_reviewed(self) -> None:
        if not self._current_chapter_id or not self._pages:
            return
        self._pages[self._page_index]["text"] = self.ocr_text.toPlainText()
        self._pages[self._page_index]["status"] = "reviewed"
        all_reviewed = all(str(page.get("status") or "pending") == "reviewed" for page in self._pages)
        self._persist_pages(override_status="reviewed" if all_reviewed else None)
        self.activity.emit(
            f"OCR reviewed for chapter {self._current_chapter_id}, page {self._page_index + 1}."
        )
        self.refresh()

    def save_status(self) -> None:
        if not self._current_chapter_id or not self._pages:
            return
        self._pages[self._page_index]["text"] = self.ocr_text.toPlainText()
        self._pages[self._page_index]["status"] = self.status_input.currentText().strip()
        self._persist_pages()
        self.activity.emit(
            f"OCR status updated for chapter {self._current_chapter_id}, page {self._page_index + 1}."
        )
        self.refresh()


class GlossaryTab(QWidget):
    activity = Signal(str)

    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel | None = None,
    ) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.storage = container.storage
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        toolbar = QHBoxLayout()
        self.extract_button = QPushButton("Extract Candidates")
        self.translate_glossary_button = QPushButton("Translate Glossary")
        self.review_pending_button = QPushButton("Review Pending")
        self.new_button = QPushButton("New Term")
        self.clear_button = QPushButton("Clear Glossary")
        toolbar.addWidget(self.extract_button)
        toolbar.addWidget(self.translate_glossary_button)
        toolbar.addWidget(self.review_pending_button)
        toolbar.addWidget(self.new_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        mid_layout = QHBoxLayout()
        term_list_group = QGroupBox("Terms")
        term_list_inner = QVBoxLayout(term_list_group)
        self.term_list = QListWidget()
        self.term_list.setObjectName("GlossaryTermList")
        self.term_list.currentItemChanged.connect(self._load_current)
        self.term_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        term_list_inner.addWidget(self.term_list)
        mid_layout.addWidget(term_list_group, stretch=1)

        editor_group = QGroupBox("Term Editor")
        editor_layout = QVBoxLayout(editor_group)
        form = QFormLayout()
        self.source_input = QLineEdit()
        self.target_input = QLineEdit()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("e.g. names, places, titles")
        self.notes_input = QLineEdit()
        self.status_input = QComboBox()
        self.status_input.addItems(["pending", "approved", "ignored"])
        form.addRow("Source", self.source_input)
        form.addRow("Target", self.target_input)
        form.addRow("Folder", self.folder_input)
        form.addRow("Notes", self.notes_input)
        form.addRow("Status", self.status_input)
        editor_layout.addLayout(form)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save Term")
        self.remove_button = QPushButton("Remove Term")
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch()
        editor_layout.addLayout(buttons)
        mid_layout.addWidget(editor_group, stretch=1)
        layout.addLayout(mid_layout)

        table_group = QGroupBox("Term List")
        table_group_layout = QVBoxLayout(table_group)
        self.terms_table = QTableWidget(0, 5)
        self.terms_table.setObjectName("GlossaryTermsTable")
        self.terms_table.setHorizontalHeaderLabels(["Folder", "Source", "Target", "Status", "Notes"])
        self.terms_table.horizontalHeader().setStretchLastSection(True)
        self.terms_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.terms_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.terms_table.verticalHeader().setVisible(False)
        self.terms_table.itemSelectionChanged.connect(self._on_table_selection)
        table_group_layout.addWidget(self.terms_table)
        layout.addWidget(table_group, stretch=1)

        self.extract_button.clicked.connect(self.extract_terms)
        self.translate_glossary_button.clicked.connect(self.translate_glossary_terms)
        self.review_pending_button.clicked.connect(self.review_pending_terms)
        self.new_button.clicked.connect(self.new_term)
        self.clear_button.clicked.connect(self.clear_glossary)
        self.save_button.clicked.connect(self.save_term)
        self.remove_button.clicked.connect(self.remove_term)
        self.refresh()

    def refresh(self) -> None:
        entries = self.storage.load_glossary(self.novel_id)
        counts = glossary_status_counts(entries)
        self.summary_label.setText(
            f"Terms: {len(entries)} | Approved: {counts.get('approved', 0)} | "
            f"Pending: {counts.get('pending', 0)} | Ignored: {counts.get('ignored', 0)}"
        )
        current_source = self.source_input.text().strip()
        self.term_list.clear()
        sorted_list_entries = sorted(
            entries,
            key=lambda e: (safe_str(e.get("folder"), "").casefold(), safe_str(e.get("source"), "").casefold()),
        )
        for entry in sorted_list_entries:
            item = QListWidgetItem(
                f"[{entry.get('status', 'pending')}] {safe_str(entry.get('source'))} -> {safe_str(entry.get('target'))}"
            )
            item.setData(Qt.ItemDataRole.UserRole, dict(entry))
            self.term_list.addItem(item)
            if current_source and entry.get("source") == current_source:
                self.term_list.setCurrentItem(item)
        if self.term_list.count() > 0 and self.term_list.currentItem() is None:
            self.term_list.setCurrentRow(0)

        sorted_entries = sorted(
            entries,
            key=lambda e: (safe_str(e.get("folder"), "").casefold(), safe_str(e.get("source"), "").casefold()),
        )
        self.terms_table.setRowCount(len(sorted_entries))
        for row, entry in enumerate(sorted_entries):
            for col, val in enumerate([
                safe_str(entry.get("folder"), ""),
                safe_str(entry.get("source"), ""),
                safe_str(entry.get("target"), ""),
                safe_str(entry.get("status"), "pending"),
                safe_str(entry.get("notes"), ""),
            ]):
                cell = QTableWidgetItem(val)
                cell.setData(Qt.ItemDataRole.UserRole, entry.get("source"))
                self.terms_table.setItem(row, col, cell)
        for col in range(4):
            self.terms_table.resizeColumnToContents(col)

    def _load_current(self, current: QListWidgetItem | None = None, _previous: QListWidgetItem | None = None) -> None:
        item = current or self.term_list.currentItem()
        if item is None:
            self.new_term()
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, dict):
            self.new_term()
            return
        self.source_input.setText(safe_str(entry.get("source"), ""))
        self.target_input.setText(safe_str(entry.get("target"), ""))
        self.folder_input.setText(safe_str(entry.get("folder"), ""))
        self.notes_input.setText(safe_str(entry.get("notes"), ""))
        self.status_input.setCurrentText(safe_str(entry.get("status"), "pending"))

    def _on_table_selection(self) -> None:
        row = self.terms_table.currentRow()
        if row < 0:
            return
        source_item = self.terms_table.item(row, 1)
        if source_item is None:
            return
        source_val = source_item.text()
        for i in range(self.term_list.count()):
            list_item = self.term_list.item(i)
            entry = list_item.data(Qt.ItemDataRole.UserRole) if list_item else None
            if isinstance(entry, dict) and entry.get("source") == source_val:
                self.term_list.blockSignals(True)
                self.term_list.setCurrentItem(list_item)
                self.term_list.blockSignals(False)
                self._load_current(list_item)
                break

    def new_term(self) -> None:
        self.source_input.clear()
        self.target_input.clear()
        self.folder_input.clear()
        self.notes_input.clear()
        self.status_input.setCurrentText("pending")

    def extract_terms(self) -> None:
        self.extract_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(self.orchestrator.extract_glossary_terms(self.novel_id, max_terms=50))

        self._worker = AsyncTaskThread(_run, self)
        self._worker.succeeded.connect(self._on_extract_success)
        self._worker.failed.connect(self._on_extract_error)
        self._worker.finished.connect(lambda: self.extract_button.setEnabled(True))
        self._worker.start()

    def _on_extract_success(self, payload: object) -> None:
        summary = payload if isinstance(payload, dict) else {}
        if self.activity_model is not None and isinstance(payload, dict) and isinstance(payload.get("phase"), str):
            self.activity_model.add_phase_event(self.novel_id, payload)
        self.activity.emit(
            f"Glossary extraction added {summary.get('added', 0)} term(s) for {self.novel_id}."
        )
        self.refresh()

    def _on_extract_error(self, message: str) -> None:
        self.activity.emit(f"Glossary extraction failed: {message}")

    def translate_glossary_terms(self) -> None:
        self.translate_glossary_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(self.orchestrator.translate_glossary_terms(self.novel_id, only_pending=True))

        self._worker = AsyncTaskThread(_run, self)
        self._worker.succeeded.connect(self._on_translate_glossary_success)
        self._worker.failed.connect(self._on_translate_glossary_error)
        self._worker.finished.connect(lambda: self.translate_glossary_button.setEnabled(True))
        self._worker.start()

    def _on_translate_glossary_success(self, payload: object) -> None:
        summary = payload if isinstance(payload, dict) else {}
        if self.activity_model is not None and isinstance(payload, dict) and isinstance(payload.get("phase"), str):
            self.activity_model.add_phase_event(self.novel_id, payload)
        self.activity.emit(
            "Glossary translation completed: "
            f"translated={summary.get('translated', 0)}, skipped={summary.get('skipped', 0)}."
        )
        self.refresh()

    def _on_translate_glossary_error(self, message: str) -> None:
        self.activity.emit(f"Glossary translation failed: {message}")

    def review_pending_terms(self) -> None:
        self.review_pending_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(self.orchestrator.review_glossary_terms(self.novel_id))

        self._worker = AsyncTaskThread(_run, self)
        self._worker.succeeded.connect(self._on_review_glossary_success)
        self._worker.failed.connect(self._on_review_glossary_error)
        self._worker.finished.connect(lambda: self.review_pending_button.setEnabled(True))
        self._worker.start()

    def _on_review_glossary_success(self, payload: object) -> None:
        summary = payload if isinstance(payload, dict) else {}
        if self.activity_model is not None and isinstance(payload, dict) and isinstance(payload.get("phase"), str):
            self.activity_model.add_phase_event(self.novel_id, payload)
        self.activity.emit(
            "Glossary review completed: "
            f"approved={summary.get('approved', 0)}, pending={summary.get('pending', 0)}."
        )
        self.refresh()

    def _on_review_glossary_error(self, message: str) -> None:
        self.activity.emit(f"Glossary review failed: {message}")

    def save_term(self) -> None:
        source = self.source_input.text().strip()
        target = self.target_input.text().strip()
        if not source or not target:
            QMessageBox.warning(self, "Missing Term Data", "Source and target terms are required.")
            return
        entries = self.storage.load_glossary(self.novel_id)
        entries = [entry for entry in entries if entry.get("source") != source]
        entries.append(
            {
                "source": source,
                "target": target,
                "folder": self.folder_input.text().strip() or None,
                "locked": True,
                "notes": self.notes_input.text().strip() or None,
                "status": "approved",
            }
        )
        self.storage.save_glossary(self.novel_id, entries)
        self.activity.emit(f"Saved glossary term '{source}'.")
        self.refresh()
        for i in range(self.term_list.count()):
            item = self.term_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(entry, dict) and entry.get("source") == source:
                if i != 0:
                    self.term_list.blockSignals(True)
                    taken = self.term_list.takeItem(i)
                    self.term_list.insertItem(0, taken)
                    self.term_list.blockSignals(False)
                self.term_list.setCurrentRow(0)
                break

    def remove_term(self) -> None:
        source = self.source_input.text().strip()
        if not source:
            return
        entries = self.storage.load_glossary(self.novel_id)
        filtered = [entry for entry in entries if entry.get("source") != source]
        self.storage.save_glossary(self.novel_id, filtered)
        self.activity.emit(f"Removed glossary term '{source}'.")
        self.new_term()
        self.refresh()

    def clear_glossary(self) -> None:
        if QMessageBox.question(self, "Clear Glossary", "Remove all glossary entries for this project?") != QMessageBox.StandardButton.Yes:
            return
        self.storage.save_glossary(self.novel_id, [])
        self.activity.emit(f"Cleared glossary for {self.novel_id}.")
        self.new_term()
        self.refresh()


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
        self.orchestrator = container.orchestrator
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

        # Progress mode
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

        # Review mode
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
            (container.storage.load_metadata(self.novel_id) or {}).get("input_adapter_key"),
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
        meta = container.storage.load_metadata(self.novel_id) or {}
        chapter_rows = [row for row in meta.get("chapters", []) if isinstance(row, dict)]
        chapter_title_map = {
            str(row.get("id")): safe_str(row.get("translated_title") or row.get("title"), "")
            for row in chapter_rows
            if row.get("id") is not None
        }
        chapter_ids = [str(row.get("id")) for row in chapter_rows if row.get("id") is not None]
        if not chapter_ids:
            chapter_ids = container.storage.list_stored_chapters(self.novel_id)

        self.review_chapter_list.clear()
        for chapter_id in chapter_ids:
            if not chapter_id.isdigit():
                continue
            translated = container.storage.load_translated_chapter(self.novel_id, chapter_id)
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

        raw_data = container.storage.load_chapter(self.novel_id, chapter_id) or {}
        media_state = container.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
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

        translated = container.storage.load_translated_chapter(self.novel_id, chapter_id) or {}
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
        existing = container.storage.load_translated_chapter(self.novel_id, chapter_id) or {}
        provider = existing.get("provider") if isinstance(existing.get("provider"), str) else None
        model = existing.get("model") if isinstance(existing.get("model"), str) else None
        container.storage.save_translated_chapter(
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
            provider_key = container.preferences.get_preferred_provider()
        model = self.model_input.currentText().strip() or container.preferences.get_preferred_model()
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

class ReembedTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.chapter_list = QListWidget()
        layout.addWidget(self.chapter_list)
        buttons = QHBoxLayout()
        self.complete_button = QPushButton("Mark Completed")
        self.pending_button = QPushButton("Mark Pending")
        buttons.addWidget(self.complete_button)
        buttons.addWidget(self.pending_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.complete_button.clicked.connect(self.mark_completed)
        self.pending_button.clicked.connect(self.mark_pending)
        self.refresh()

    def _current_chapter_id(self) -> str | None:
        item = self.chapter_list.currentItem()
        if item is None:
            return None
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        return chapter_id if isinstance(chapter_id, str) else None

    def mark_completed(self) -> None:
        chapter_id = self._current_chapter_id()
        if not chapter_id:
            return
        self.storage.save_chapter_media_state(self.novel_id, chapter_id, reembed_status="completed")
        self.activity.emit(f"Re-embedding marked completed for chapter {chapter_id}.")
        self.refresh()

    def mark_pending(self) -> None:
        chapter_id = self._current_chapter_id()
        if not chapter_id:
            return
        self.storage.save_chapter_media_state(self.novel_id, chapter_id, reembed_status="pending")
        self.activity.emit(f"Re-embedding marked pending for chapter {chapter_id}.")
        self.refresh()

    def refresh(self) -> None:
        pending = 0
        completed = 0
        self.chapter_list.clear()
        for chapter_id in self.storage.list_stored_chapters(self.novel_id):
            media = self.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
            status = str(media.get("reembed_status") or "skipped").strip().lower()
            if status == "pending":
                pending += 1
            elif status == "completed":
                completed += 1
            if status == "skipped" and not bool(media.get("ocr_required")):
                continue
            item = QListWidgetItem(f"Chapter {chapter_id} [{status}]")
            item.setData(Qt.ItemDataRole.UserRole, chapter_id)
            self.chapter_list.addItem(item)
        self.summary_label.setText(f"Pending re-embed: {pending} | Completed: {completed}")
        if self.chapter_list.count() == 0:
            self.chapter_list.addItem("No re-embed tasks yet.")


class ExportTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.exporter = container.export
        self._preflight_block_reason: str | None = None
        self._latest_export_plan: dict[str, Any] | None = None
        self._latest_export_plan_error: str | None = None
        layout = QVBoxLayout(self)
        eyebrow = QLabel("EXPORT")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Package chapters to EPUB, PDF, HTML, or Markdown")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        description = QLabel(
            "Use chapter scope diagnostics to see what will export now and what is still blocked."
        )
        description.setObjectName("HeroBody")
        description.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)

        readiness_box = QGroupBox("Readiness")
        readiness_layout = QVBoxLayout(readiness_box)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("HeroBody")
        readiness_layout.addWidget(self.summary_label)
        self.preflight_label = QLabel()
        self.preflight_label.setWordWrap(True)
        self.preflight_label.setObjectName("HeroBody")
        readiness_layout.addWidget(self.preflight_label)
        self.readiness_label = QLabel()
        self.readiness_label.setWordWrap(True)
        self.readiness_label.setObjectName("HeroBody")
        readiness_layout.addWidget(self.readiness_label)
        layout.addWidget(readiness_box)

        options_box = QGroupBox("Export Options")
        options_layout = QVBoxLayout(options_box)
        form = QFormLayout()
        self.format_input = QComboBox()
        self.format_input.addItems(["epub", "pdf", "html", "md"])
        self.chapter_selection_input = QLineEdit("full")
        self.chapter_selection_input.setPlaceholderText("full, 1, 1-3, 2,5")
        self.language_input = QComboBox()
        self.language_input.addItems(["translated", "source"])
        self.include_toc_input = QCheckBox("Include EPUB table of contents")
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("default library location")
        form.addRow("Format", self.format_input)
        form.addRow("Chapter Scope", self.chapter_selection_input)
        form.addRow("Language", self.language_input)
        form.addRow("Output Directory", self.output_dir_input)
        form.addRow("", self.include_toc_input)
        options_layout.addLayout(form)

        button_row = QHBoxLayout()
        self.export_button = QPushButton("Export Ready Chapters")
        self.export_button.clicked.connect(self.export_current)
        button_row.addWidget(self.export_button)
        button_row.addStretch()
        options_layout.addLayout(button_row)
        layout.addWidget(options_box)

        result_box = QGroupBox("Export Result")
        result_layout = QVBoxLayout(result_box)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Export status and skipped chapter diagnostics appear here.")
        result_layout.addWidget(self.output)
        layout.addWidget(result_box)
        self.language_input.currentIndexChanged.connect(lambda _index: self._apply_export_preflight())
        self.chapter_selection_input.textChanged.connect(lambda _text: self._apply_export_preflight())
        self.refresh()

    def _compute_export_plan(self) -> tuple[dict[str, Any] | None, str | None]:
        language = self.language_input.currentText().strip().lower()
        chapter_selection = self.chapter_selection_input.text().strip() or "full"
        try:
            plan = build_export_plan(
                self.storage,
                self.novel_id,
                chapter_selection=chapter_selection,
                language=language,
            )
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)
        return plan, None

    def _export_preflight_reason(self) -> str | None:
        meta = self.storage.load_metadata(self.novel_id) or {}
        chapters = [row for row in meta.get("chapters", []) if isinstance(row, dict)]
        if not chapters:
            return "Project metadata not found."
        plan, error = self._compute_export_plan()
        self._latest_export_plan = plan
        self._latest_export_plan_error = error
        if error is not None:
            return error
        if plan is None:
            return "Unable to compute export readiness."
        if int(plan.get("selected_count", 0)) <= 0:
            return "No chapters matched the selected scope."
        if len(plan.get("ready", [])) <= 0:
            language = self.language_input.currentText().strip().lower()
            return f"No {language} chapters are export-ready for the selected scope."
        return None

    def _refresh_export_diagnostics(self) -> None:
        if self._latest_export_plan_error is not None:
            self.readiness_label.setText(f"Readiness check failed: {self._latest_export_plan_error}")
            return
        if self._latest_export_plan is None:
            self.readiness_label.setText("")
            return
        selected_count = int(self._latest_export_plan.get("selected_count", 0))
        ready = self._latest_export_plan.get("ready", [])
        blocked = self._latest_export_plan.get("blocked", [])
        lines = [
            f"Scope diagnostics: Selected {selected_count} | Ready {len(ready)} | Blocked {len(blocked)}",
        ]
        for row in blocked[:4]:
            chapter_id = str(row.get("chapter_id") or "?")
            reason = str(row.get("reason") or "Blocked")
            lines.append(f"Ch {chapter_id}: {reason}")
        if len(blocked) > 4:
            lines.append(f"+ {len(blocked) - 4} more blocked chapter(s)")
        self.readiness_label.setText("\n".join(lines))

    def _apply_export_preflight(self) -> None:
        self._preflight_block_reason = self._export_preflight_reason()
        blocked = self._preflight_block_reason is not None
        self.export_button.setEnabled(not blocked)
        if blocked:
            self.preflight_label.setText(f"Blocked: {self._preflight_block_reason}")
        else:
            self.preflight_label.setText("Ready: current scope has exportable chapters.")
        self.export_button.setToolTip(self._preflight_block_reason or "")
        self._refresh_export_diagnostics()

    def export_current(self) -> None:
        self._apply_export_preflight()
        if self._preflight_block_reason is not None:
            self.output.setPlainText(self._preflight_block_reason)
            return
        meta = self.storage.load_metadata(self.novel_id)
        if not meta:
            self.output.setPlainText("Metadata not found.")
            return
        fmt = self.format_input.currentText()
        chapter_selection = self.chapter_selection_input.text().strip() or "full"
        language = self.language_input.currentText().strip()
        output_dir = self.output_dir_input.text().strip() or None
        include_toc = self.include_toc_input.isChecked()
        plan, error = self._compute_export_plan()
        self._latest_export_plan = plan
        self._latest_export_plan_error = error
        self._refresh_export_diagnostics()
        if error is not None:
            self.output.setPlainText(error)
            return
        if plan is None:
            self.output.setPlainText("Unable to compute export readiness.")
            return

        ready_rows = [row for row in plan.get("ready", []) if isinstance(row, dict)]
        blocked_rows = [row for row in plan.get("blocked", []) if isinstance(row, dict)]
        if not ready_rows:
            self.output.setPlainText(f"No {language} chapters available for export.")
            return
        chapters = [
            {
                "title": row["title"],
                "text": row["text"],
                "images": row["images"],
            }
            for row in ready_rows
        ]

        output_path = build_export_output_path(
            self.storage,
            self.novel_id,
            fmt,
            output_dir,
            chapter_selection,
            language,
        )
        book_title = meta.get("translated_title") or meta.get("title") or self.novel_id
        book_author = meta.get("translated_author") or meta.get("author") or ""
        self.exporter.export(
            fmt,
            novel_id=self.novel_id,
            chapters=chapters,
            output_path=output_path,
            title=book_title,
            author=book_author,
            include_toc=include_toc,
        )
        if language != "source":
            for row in ready_rows:
                chapter_id = str(row.get("chapter_id") or "")
                if not chapter_id:
                    continue
                with contextlib.suppress(Exception):
                    self.storage.update_chapter_state(self.novel_id, chapter_id, ChapterState.EXPORTED)
        lines = [f"Exported {len(chapters)} chapter(s) to:\n{output_path}"]
        if blocked_rows:
            lines.append(f"Skipped {len(blocked_rows)} blocked chapter(s).")
            for row in blocked_rows[:4]:
                chapter_id = str(row.get("chapter_id") or "?")
                reason = str(row.get("reason") or "Blocked")
                lines.append(f"- Ch {chapter_id}: {reason}")
            if len(blocked_rows) > 4:
                lines.append(f"- +{len(blocked_rows) - 4} more")
        self.output.setPlainText("\n".join(lines))
        self.activity.emit(f"Exported {fmt.upper()} to {output_path}.")
        self.refresh()

    def refresh(self) -> None:
        translated = len(self.storage.list_translated_chapters(self.novel_id))
        stored = self.storage.count_stored_chapters(self.novel_id)
        self.summary_label.setText(
            f"Library totals: {stored} stored | {translated} translated | "
            f"{len(recent_export_paths())} recent export file(s)"
        )
        self._apply_export_preflight()


class ActivityTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def append(self, message: str) -> None:
        current = self.output.toPlainText().strip()
        self.output.setPlainText(f"{current}\n{message}".strip())


class WorkspaceOverviewTab(QWidget):
    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        layout = QVBoxLayout(self)
        hero = QGroupBox("Project Snapshot")
        hero_layout = QVBoxLayout(hero)
        self.title_label = QLabel()
        self.title_label.setObjectName("HeroTitle")
        self.title_label.setWordWrap(True)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("HeroBody")
        self.subtitle_label.setWordWrap(True)
        hero_layout.addWidget(self.title_label)
        hero_layout.addWidget(self.subtitle_label)

        cards = QHBoxLayout()
        self.units_card = StatCard("Units")
        self.glossary_card = StatCard("Glossary")
        self.media_card = StatCard("Media")
        self.export_card = StatCard("Export Ready")
        cards.addWidget(self.units_card)
        cards.addWidget(self.glossary_card)
        cards.addWidget(self.media_card)
        cards.addWidget(self.export_card)
        hero_layout.addLayout(cards)
        layout.addWidget(hero)

        self.meta_output = QPlainTextEdit()
        self.meta_output.setReadOnly(True)
        layout.addWidget(self.meta_output)
        self.refresh()

    def refresh(self) -> None:
        meta = container.storage.load_metadata(self.novel_id) or {}
        snapshot = next((item for item in library_snapshots() if item["novel_id"] == self.novel_id), None)
        title = meta.get("translated_title") or meta.get("title") or self.novel_id
        author = meta.get("translated_author") or meta.get("author") or "Unknown author"
        self.title_label.setText(title)
        self.subtitle_label.setText(
            f"{author} | {safe_str(meta.get('document_type'))} | {safe_str(meta.get('origin_uri_or_path'))}"
        )
        if snapshot is not None:
            self.units_card.set_content(
                f"{snapshot['translated_units']}/{snapshot['total_units']}",
                "Translated / stored units",
            )
            self.glossary_card.set_content(
                str(snapshot["glossary_pending"]),
                "Pending glossary terms",
            )
            self.media_card.set_content(
                str(snapshot["ocr_pending"]),
                "OCR review items",
            )
            self.export_card.set_content(
                str(len(container.storage.get_chapters_ready_for_export(self.novel_id))),
                "Translated chapters ready for export",
            )
        lines = [
            f"Novel ID: {self.novel_id}",
            f"Input Adapter: {safe_str(meta.get('input_adapter_key'))}",
            f"Origin Type: {safe_str(meta.get('origin_type'))}",
            f"Source Language: {safe_str(meta.get('source_language'))}",
            f"Updated: {timestamp_label(meta.get('updated_at') or meta.get('scraped_at'))}",
            "",
            "Workflow Profiles:",
            profiles_snapshot_text(),
        ]
        self.meta_output.setPlainText("\n".join(lines))


class BookWorkspace(QWidget):
    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel,
        refresh_callback: Callable[[], None],
    ) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        header_row = QHBoxLayout()
        self.header_label = QLabel()
        self.header_label.setObjectName("HeroBody")
        self.header_label.setWordWrap(True)
        header_row.addWidget(self.header_label, stretch=1)
        self.activity_toggle_button = QPushButton("Show Activity Panel")
        self.activity_toggle_button.clicked.connect(self._toggle_activity_panel)
        header_row.addWidget(self.activity_toggle_button)
        layout.addLayout(header_row)
        tabs = QTabWidget()
        self.tabs = tabs
        self.overview_tab = WorkspaceOverviewTab(novel_id)
        self.ocr_tab = OCRReviewTab(novel_id)
        self.glossary_tab = GlossaryTab(
            novel_id,
            activity_model=activity_model,
        )
        self.translate_tab = TranslateTab(
            novel_id,
            activity_model=activity_model,
            refresh_callback=refresh_callback,
        )
        self.reembed_tab = ReembedTab(novel_id)
        self.export_tab = ExportTab(novel_id)
        tabs.addTab(self.overview_tab, "Overview")
        tabs.addTab(self.ocr_tab, "OCR Review")
        self._ocr_tab_index = tabs.indexOf(self.ocr_tab)
        tabs.addTab(self.glossary_tab, "Glossary")
        tabs.addTab(self.translate_tab, "Translate")
        tabs.addTab(self.reembed_tab, "Re-embed")
        tabs.addTab(self.export_tab, "Export")

        self.workspace_splitter = QSplitter()
        self.workspace_splitter.addWidget(tabs)
        self.activity_panel = QWidget()
        panel_layout = QVBoxLayout(self.activity_panel)
        panel_layout.addWidget(QLabel("Workspace Activity"))
        self.workspace_jobs_list = QListWidget()
        panel_layout.addWidget(self.workspace_jobs_list)
        self.workspace_phase_summary = QLabel("No phase activity yet.")
        self.workspace_phase_summary.setWordWrap(True)
        panel_layout.addWidget(self.workspace_phase_summary)
        self.workspace_phase_timeline = QListWidget()
        panel_layout.addWidget(self.workspace_phase_timeline)
        self.workspace_log = QPlainTextEdit()
        self.workspace_log.setReadOnly(True)
        panel_layout.addWidget(self.workspace_log)
        self.workspace_splitter.addWidget(self.activity_panel)
        self.workspace_splitter.setStretchFactor(0, 4)
        self.workspace_splitter.setStretchFactor(1, 2)
        layout.addWidget(self.workspace_splitter)
        self._activity_panel_visible = False
        self.workspace_splitter.setSizes([1, 0])

        for tab in [self.ocr_tab, self.glossary_tab, self.translate_tab, self.reembed_tab, self.export_tab]:
            tab.activity.connect(self.activity_model.add_message)
            tab.activity.connect(lambda _message: self.refresh_callback())
        self.activity_model.jobs_changed.connect(self._refresh_activity_panel)
        self.activity_model.messages_changed.connect(self._refresh_activity_panel)
        self.refresh()

    def _toggle_activity_panel(self) -> None:
        self._activity_panel_visible = not self._activity_panel_visible
        if self._activity_panel_visible:
            self.activity_toggle_button.setText("Hide Activity Panel")
            self.workspace_splitter.setSizes([3, 2])
        else:
            self.activity_toggle_button.setText("Show Activity Panel")
            self.workspace_splitter.setSizes([1, 0])

    def _refresh_activity_panel(self) -> None:
        self.workspace_jobs_list.clear()
        running = self.activity_model.running_jobs()
        for entry in running:
            if self.novel_id in entry:
                self.workspace_jobs_list.addItem(entry)
        if self.workspace_jobs_list.count() == 0:
            self.workspace_jobs_list.addItem("No active jobs for this workspace.")

        phase_counters = self.activity_model.phase_counters(self.novel_id)
        if not phase_counters:
            self.workspace_phase_summary.setText("No phase activity yet.")
        else:
            parts = []
            for phase, counts in sorted(phase_counters.items()):
                compact = ", ".join(f"{status}:{count}" for status, count in sorted(counts.items()))
                parts.append(f"{phase} ({compact})")
            self.workspace_phase_summary.setText("Phase counters: " + " | ".join(parts))

        self.workspace_phase_timeline.clear()
        _phase_colors: dict[str, str] = {
            "completed": "#4CAF50",
            "blocked": "#FF9800",
            "failed": "#F44336",
        }
        for event in self.activity_model.phase_events(self.novel_id)[-20:]:
            phase = safe_str(event.get("phase"), "phase")
            status = safe_str(event.get("status"), "completed")
            timestamp = safe_str(event.get("timestamp"), "-")
            message = safe_str(event.get("message"), "")
            item = QListWidgetItem(f"{timestamp} {phase} [{status}] {message}".strip())
            if status in _phase_colors:
                item.setForeground(QColor(_phase_colors[status]))
            self.workspace_phase_timeline.addItem(item)
        if self.workspace_phase_timeline.count() == 0:
            self.workspace_phase_timeline.addItem("No phase timeline events for this workspace.")

        lines = [
            line
            for line in self.activity_model.messages()
            if self.novel_id in line
        ]
        if not lines:
            self.workspace_log.setPlainText("No workspace-specific activity yet.")
        else:
            self.workspace_log.setPlainText("\n".join(lines[-120:]))

    def refresh(self) -> None:
        snapshot = next((item for item in library_snapshots() if item["novel_id"] == self.novel_id), None)
        if snapshot is None:
            self.header_label.setText(f"Workspace: {self.novel_id}")
        else:
            self.header_label.setText(
                f"{snapshot['title']} ({self.novel_id}) | "
                f"{snapshot['translated_units']}/{snapshot['total_units']} translated | "
                f"OCR pending {snapshot['ocr_pending']} | Glossary pending {snapshot['glossary_pending']}"
            )
        for widget in (self.overview_tab, self.ocr_tab, self.glossary_tab, self.translate_tab, self.reembed_tab, self.export_tab):
            if hasattr(widget, "refresh"):
                widget.refresh()
        self._update_ocr_tab_visibility()
        self._refresh_activity_panel()

    def _update_ocr_tab_visibility(self) -> None:
        needs_ocr = any(
            bool((container.storage.load_chapter_media_state(self.novel_id, cid) or {}).get("ocr_required"))
            for cid in container.storage.list_stored_chapters(self.novel_id)
        )
        self.tabs.setTabVisible(self._ocr_tab_index, needs_ocr)


class DesktopMainWindow(QMainWindow):
    SIDEBAR_PANEL_WIDTH = 200
    SIDEBAR_NAV_WIDTH = 180

    ICON_ASSETS = {
        "home": "home.svg",
        "library": "library.svg",
        "import": "import.svg",
        "activity": "activity.svg",
        "llmops": "profiles.svg",
        "diagnostics": "diagnostics.svg",
        "settings": "settings.svg",
    }

    TOP_LEVEL_PAGES = (
        ("home", "Home"),
        ("library", "Novel Library"),
        ("import", "Import and Scrape"),
        ("activity", "Activity"),
        ("llmops", "LLM Ops"),
        ("diagnostics", "Diagnostics"),
    )

    def __init__(self) -> None:
        super().__init__()
        bootstrap()
        self.activity_model = DesktopActivityModel()
        self.page_items: dict[str, QListWidgetItem] = {}
        self.page_widgets: dict[str, QWidget] = {}
        self._nav_labels_visible = True
        self.workspace_key: str | None = None
        self.workspace: BookWorkspace | None = None

        self.setWindowTitle("NovelAI2Book")
        self.resize(1380, 920)
        self.assets_dir = Path(__file__).resolve().parent / "assets"
        root = QSplitter()
        root.setObjectName("DesktopRoot")
        self.setCentralWidget(root)
        self.root_splitter = root

        self.nav_panel = QWidget()
        self.nav_panel.setObjectName("NavPanel")
        self.nav_panel.setMinimumWidth(self.SIDEBAR_PANEL_WIDTH)
        self.nav_panel.setMaximumWidth(self.SIDEBAR_PANEL_WIDTH)
        nav_layout = QVBoxLayout(self.nav_panel)
        nav_layout.setContentsMargins(6, 8, 6, 8)
        nav_layout.setSpacing(10)

        self.nav_brand_button = QPushButton()
        self.nav_brand_button.setObjectName("NavBrandButton")
        brand_icon = QIcon(str(self.assets_dir / "icons" / "workspace.svg"))
        if not brand_icon.isNull():
            self.nav_brand_button.setIcon(brand_icon)
            self.nav_brand_button.setIconSize(QSize(18, 18))
        else:
            self.nav_brand_button.setText("*")
        self.nav_brand_button.setToolTip("NovelAI2Book")
        nav_layout.addWidget(self.nav_brand_button, 0, Qt.AlignmentFlag.AlignHCenter)
        nav_layout.addSpacing(13)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setSpacing(7)
        self.nav.setUniformItemSizes(True)
        self.nav.setFlow(QListView.Flow.TopToBottom)
        self.nav.setMovement(QListView.Movement.Static)
        self.nav.setWrapping(False)
        self.nav.setWordWrap(False)
        self.nav.setGridSize(QSize(44, 44))
        self.nav.setResizeMode(QListView.ResizeMode.Adjust)
        self.nav.setIconSize(QSize(20, 20))
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setMinimumWidth(self.SIDEBAR_NAV_WIDTH)
        self.nav.setMaximumWidth(self.SIDEBAR_NAV_WIDTH)
        nav_layout.addWidget(self.nav)
        nav_layout.addStretch()

        self.nav_avatar = QLabel("AP")
        self.nav_avatar.setObjectName("NavAvatar")
        self.nav_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_avatar.setToolTip("Active Profile")
        nav_layout.addWidget(self.nav_avatar, 0, Qt.AlignmentFlag.AlignHCenter)

        root.addWidget(self.nav_panel)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 1)
        root.setSizes([60, 1220])

        self.home_view = HomeView(self.activity_model)
        self.library_view = LibraryView()
        self.import_view = ImportPage(self.activity_model, self.refresh_all_views)
        self.activity_view = ActivityView(self.activity_model)
        self.library_view.open_requested.connect(self.open_workspace)
        self.library_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.open_workspace_requested.connect(self.open_workspace)
        self.import_view.open_workspace_requested.connect(self.open_workspace)
        self.llmops_view = LLMOpsView(self.refresh_all_views)
        self.diagnostics_view = DiagnosticsView()

        for key, label in self.TOP_LEVEL_PAGES:
            widget = getattr(self, f"{key}_view")
            self._add_page(key, label, widget)

        self.nav.currentItemChanged.connect(self._switch_view)
        self.activity_model.jobs_changed.connect(self._refresh_status_bar)
        self.activity_model.messages_changed.connect(self._refresh_status_bar)
        self._apply_nav_mode()
        self._navigate_to_page("home")
        self._refresh_status_bar()

    def _toggle_nav_labels(self) -> None:
        self._apply_nav_mode()

    def _apply_nav_mode(self) -> None:
        self.nav.setViewMode(QListView.ViewMode.ListMode)
        self.nav.setMinimumWidth(self.SIDEBAR_NAV_WIDTH)
        self.nav.setMaximumWidth(self.SIDEBAR_NAV_WIDTH)
        self.root_splitter.setSizes([200, 1080])

        for item in self.page_items.values():
            label = item.data(Qt.ItemDataRole.UserRole + 1)
            label_text = str(label) if isinstance(label, str) else ""
            item.setText(label_text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item.setSizeHint(QSize(168, 42))

    def _nav_icon(self, key: str):
        icon_map = {
            "home": QStyle.StandardPixmap.SP_DirHomeIcon,
            "library": QStyle.StandardPixmap.SP_DirOpenIcon,
            "import": QStyle.StandardPixmap.SP_FileIcon,
            "activity": QStyle.StandardPixmap.SP_BrowserReload,
            "llmops": QStyle.StandardPixmap.SP_DialogApplyButton,
            "diagnostics": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        }
        if key.startswith("workspace:"):
            workspace_icon_path = self.assets_dir / "icons" / "workspace.svg"
            workspace_icon = QIcon(str(workspace_icon_path))
            if not workspace_icon.isNull():
                return workspace_icon
            return self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        asset_name = self.ICON_ASSETS.get(key)
        if asset_name:
            asset_icon_path = self.assets_dir / "icons" / asset_name
            asset_icon = QIcon(str(asset_icon_path))
            if not asset_icon.isNull():
                return asset_icon

        icon_type = icon_map.get(key, QStyle.StandardPixmap.SP_FileDialogListView)
        return self.style().standardIcon(icon_type)

    def _add_page(self, key: str, label: str, widget: QWidget) -> None:
        item = QListWidgetItem("")
        item.setIcon(self._nav_icon(key))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setData(Qt.ItemDataRole.UserRole + 1, label)
        item.setToolTip(label)
        item.setSizeHint(QSize(44, 44))
        self.page_items[key] = item
        self.page_widgets[key] = widget
        self.nav.addItem(item)
        self.stack.addWidget(widget)
        self._apply_nav_mode()

    def _navigate_to_page(self, key: str) -> None:
        item = self.page_items.get(key)
        if item is not None:
            self.nav.setCurrentItem(item)

    def _switch_view(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key in self.page_widgets:
            self.stack.setCurrentWidget(self.page_widgets[key])

    def _refresh_status_bar(self) -> None:
        provider = container.preferences.get_preferred_provider()
        model = container.preferences.get_preferred_model()
        jobs = len(self.activity_model.running_jobs())
        self.statusBar().showMessage(
            f"Library: {settings.NOVEL_LIBRARY_DIR} | Provider: {provider} | Model: {model} | Running Jobs: {jobs}"
        )

    def refresh_all_views(self) -> None:
        for key in ("home", "library", "activity", "diagnostics"):
            widget = self.page_widgets.get(key)
            if widget is not None and hasattr(widget, "refresh"):
                getattr(widget, "refresh")()
        if self.workspace is not None:
            self.workspace.refresh()
            workspace_item = self.page_items.get(self.workspace_key or "")
            if workspace_item is not None:
                title = (container.storage.load_metadata(self.workspace.novel_id) or {}).get("title") or self.workspace.novel_id
                workspace_label = f"Workspace: {title}"
                workspace_item.setData(Qt.ItemDataRole.UserRole + 1, workspace_label)
                workspace_item.setToolTip(f"Workspace: {title}")
                if self._nav_labels_visible:
                    workspace_item.setText(workspace_label)
        self._refresh_status_bar()

    def open_workspace(self, novel_id: str) -> None:
        key = f"workspace:{novel_id}"
        if self.workspace_key == key and self.workspace is not None:
            self.workspace.refresh()
            self._navigate_to_page(key)
            return

        if self.workspace is not None and self.workspace_key is not None:
            old_item = self.page_items.pop(self.workspace_key, None)
            old_widget = self.page_widgets.pop(self.workspace_key, None)
            if old_item is not None:
                row = self.nav.row(old_item)
                self.nav.takeItem(row)
            if old_widget is not None:
                self.stack.removeWidget(old_widget)
                old_widget.deleteLater()

        self.workspace_key = key
        self.workspace = BookWorkspace(
            novel_id,
            activity_model=self.activity_model,
            refresh_callback=self.refresh_all_views,
        )
        title = (container.storage.load_metadata(novel_id) or {}).get("title") or novel_id
        self._add_page(key, f"Workspace: {title}", self.workspace)
        self._navigate_to_page(key)
        self.refresh_all_views()


def main() -> None:
    bootstrap()
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI Variable Text", 10))
    assets_dir = Path(__file__).resolve().parent / "assets"
    app.setStyleSheet(build_stylesheet(assets_dir))
    window = DesktopMainWindow()
    window.show()
    app.exec()

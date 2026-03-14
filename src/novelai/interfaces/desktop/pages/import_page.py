from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop import shared as desktop_shared
from novelai.inputs.registry import detect_input_adapter
from novelai.interfaces.desktop.shared import AsyncTaskThread, DesktopActivityModel
from novelai.sources.registry import detect_source


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
        self.orchestrator = desktop_shared.container.orchestrator
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
        self.orchestrator = desktop_shared.container.orchestrator
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

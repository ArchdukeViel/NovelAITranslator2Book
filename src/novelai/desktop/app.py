from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.inputs.registry import available_input_adapters
from novelai.sources.registry import available_sources


class AsyncTaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class LibraryView(QWidget):
    open_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.storage = container.storage
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Library"))
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._open_current)
        layout.addWidget(self.list_widget)
        button_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.open_button = QPushButton("Open Workspace")
        self.open_button.clicked.connect(self._open_current)
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.open_button)
        layout.addLayout(button_row)
        self.refresh()

    def refresh(self) -> None:
        self.list_widget.clear()
        for novel_id in sorted(container.storage.list_novels()):
            meta = container.storage.load_metadata(novel_id) or {}
            item = QListWidgetItem(f"{meta.get('title') or novel_id} ({novel_id})")
            item.setData(Qt.ItemDataRole.UserRole, novel_id)
            self.list_widget.addItem(item)

    def _open_current(self, *_args: object) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_requested.emit(novel_id)


class ProfilesView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.preferences = container.preferences
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Workflow Profiles"))
        grid = QGridLayout()
        grid.addWidget(QLabel("Step"), 0, 0)
        grid.addWidget(QLabel("Provider"), 0, 1)
        grid.addWidget(QLabel("Model"), 0, 2)
        self.inputs: dict[str, tuple[QLineEdit, QLineEdit]] = {}
        for row, step in enumerate(WORKFLOW_PROFILE_STEPS, start=1):
            profile = self.preferences.get_workflow_profile(step)
            provider_input = QLineEdit(profile["provider"] or "")
            model_input = QLineEdit(profile["model"] or "")
            grid.addWidget(QLabel(step.replace("_", " ").title()), row, 0)
            grid.addWidget(provider_input, row, 1)
            grid.addWidget(model_input, row, 2)
            self.inputs[step] = (provider_input, model_input)
        layout.addLayout(grid)
        save_button = QPushButton("Save Profiles")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()

    def save(self) -> None:
        for step, (provider_input, model_input) in self.inputs.items():
            self.preferences.set_workflow_profile(
                step,
                provider=provider_input.text(),
                model=model_input.text(),
            )
        QMessageBox.information(self, "Profiles Saved", "Workflow profiles were updated.")


class ImportTab(QWidget):
    activity = Signal(str)
    completed = Signal()

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.orchestrator = container.orchestrator
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.adapter_input = QComboBox()
        self.adapter_input.addItems(available_input_adapters())
        self.source_input = QLineEdit()
        self.max_units_input = QLineEdit()
        form.addRow("Adapter", self.adapter_input)
        form.addRow("Source Path/URL", self.source_input)
        form.addRow("Max Units", self.max_units_input)
        layout.addLayout(form)
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.start_import)
        layout.addWidget(self.import_button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def start_import(self) -> None:
        adapter_key = self.adapter_input.currentText()
        source = self.source_input.text().strip()
        max_units = self.max_units_input.text().strip()
        if not source:
            QMessageBox.warning(self, "Missing Source", "Provide a source path or URL.")
            return
        self.import_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.import_document(
                    adapter_key,
                    self.novel_id,
                    source,
                    max_units=int(max_units) if max_units.isdigit() else None,
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
        self.activity.emit("Import completed.")
        self.completed.emit()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        self.activity.emit(f"Import failed: {message}")


class OCRReviewTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        layout = QVBoxLayout(self)
        self.chapter_list = QListWidget()
        self.chapter_list.currentItemChanged.connect(self._load_current)
        layout.addWidget(self.chapter_list)
        self.ocr_text = QPlainTextEdit()
        layout.addWidget(self.ocr_text)
        review_button = QPushButton("Mark Reviewed")
        review_button.clicked.connect(self.mark_reviewed)
        layout.addWidget(review_button)
        self.refresh()

    def refresh(self) -> None:
        self.chapter_list.clear()
        for chapter_id in self.storage.list_stored_chapters(self.novel_id):
            media = self.storage.load_chapter_media_state(self.novel_id, chapter_id) or {}
            if not bool(media.get("ocr_required", False)):
                continue
            item = QListWidgetItem(f"Chapter {chapter_id} [{media.get('ocr_status', 'pending')}]")
            item.setData(Qt.ItemDataRole.UserRole, chapter_id)
            self.chapter_list.addItem(item)

    def _load_current(self, current: QListWidgetItem | None = None, _previous: QListWidgetItem | None = None) -> None:
        item = current or self.chapter_list.currentItem()
        if item is None:
            self.ocr_text.clear()
            return
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        media = self.storage.load_chapter_media_state(self.novel_id, str(chapter_id)) or {}
        self.ocr_text.setPlainText(str(media.get("ocr_text") or ""))

    def mark_reviewed(self) -> None:
        item = self.chapter_list.currentItem()
        if item is None:
            return
        chapter_id = str(item.data(Qt.ItemDataRole.UserRole))
        self.storage.save_chapter_media_state(
            self.novel_id,
            chapter_id,
            ocr_required=True,
            ocr_text=self.ocr_text.toPlainText(),
            ocr_status="reviewed",
        )
        self.activity.emit(f"OCR reviewed for chapter {chapter_id}.")
        self.refresh()


class GlossaryTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.orchestrator = container.orchestrator
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        extract_button = QPushButton("Extract Candidates")
        extract_button.clicked.connect(self.extract_terms)
        approve_button = QPushButton("Approve Pending")
        approve_button.clicked.connect(self.approve_pending)
        actions.addWidget(extract_button)
        actions.addWidget(approve_button)
        layout.addLayout(actions)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        entries = self.storage.load_glossary(self.novel_id)
        self.output.setPlainText("\n".join(f"[{entry.get('status', 'pending')}] {entry.get('source')} -> {entry.get('target')}" for entry in entries))

    def extract_terms(self) -> None:
        summary = asyncio.run(self.orchestrator.extract_glossary_terms(self.novel_id))
        self.activity.emit(f"Glossary extraction added {summary['added']} term(s).")
        self.refresh()

    def approve_pending(self) -> None:
        entries = self.storage.load_glossary(self.novel_id)
        for entry in entries:
            if str(entry.get("status") or "").lower() == "pending":
                entry["status"] = "approved"
        self.storage.save_glossary(self.novel_id, entries)
        self.activity.emit("Approved pending glossary terms.")
        self.refresh()


class TranslateTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.orchestrator = container.orchestrator
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.source_key_input = QComboBox()
        self.source_key_input.addItems(sorted(set(available_sources() + available_input_adapters() + ["imported"])))
        self.chapter_selection_input = QLineEdit("all")
        form.addRow("Source/Input Key", self.source_key_input)
        form.addRow("Chapter Selection", self.chapter_selection_input)
        layout.addLayout(form)
        self.translate_button = QPushButton("Translate")
        self.translate_button.clicked.connect(self.start_translation)
        layout.addWidget(self.translate_button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def start_translation(self) -> None:
        source_key = self.source_key_input.currentText()
        chapters = self.chapter_selection_input.text().strip() or "all"
        self.translate_button.setEnabled(False)

        def _run() -> Any:
            asyncio.run(self.orchestrator.translate_chapters(source_key, self.novel_id, chapters))
            return "Translation completed."

        worker = AsyncTaskThread(_run, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self.translate_button.setEnabled(True))
        worker.start()
        self._worker = worker

    def _on_success(self, payload: object) -> None:
        self.output.setPlainText(str(payload))
        self.activity.emit(str(payload))

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        self.activity.emit(f"Translation failed: {message}")


class ReembedTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        layout = QVBoxLayout(self)
        self.chapter_input = QLineEdit()
        layout.addWidget(QLabel("Mark a chapter as re-embedded (placeholder workflow)."))
        layout.addWidget(self.chapter_input)
        button = QPushButton("Mark Completed")
        button.clicked.connect(self.mark_completed)
        layout.addWidget(button)
        layout.addStretch()

    def mark_completed(self) -> None:
        chapter_id = self.chapter_input.text().strip()
        if not chapter_id:
            return
        self.storage.save_chapter_media_state(self.novel_id, chapter_id, reembed_status="completed")
        self.activity.emit(f"Re-embedding marked completed for chapter {chapter_id}.")


class ExportTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.exporter = container.export
        layout = QVBoxLayout(self)
        self.format_input = QComboBox()
        self.format_input.addItems(["epub", "html", "md"])
        layout.addWidget(self.format_input)
        button = QPushButton("Export")
        button.clicked.connect(self.export_current)
        layout.addWidget(button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def export_current(self) -> None:
        meta = self.storage.load_metadata(self.novel_id)
        if not meta:
            self.output.setPlainText("Metadata not found.")
            return
        chapters: list[dict[str, Any]] = []
        for chapter in meta.get("chapters", []):
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("id"))
            translated = self.storage.load_translated_chapter(self.novel_id, chapter_id)
            if translated is None:
                continue
            chapters.append(
                {
                    "title": chapter.get("title"),
                    "text": translated.get("text"),
                    "images": self.storage.load_chapter_export_images(self.novel_id, chapter_id),
                }
            )
        if not chapters:
            self.output.setPlainText("No translated chapters available.")
            return
        fmt = self.format_input.currentText()
        output_path = str(self.storage.build_export_path(self.novel_id, fmt))
        self.exporter.export(fmt, novel_id=self.novel_id, chapters=chapters, output_path=output_path)
        self.output.setPlainText(output_path)
        self.activity.emit(f"Exported {fmt.upper()} to {output_path}.")


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


class BookWorkspace(QWidget):
    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Workspace: {novel_id}"))
        tabs = QTabWidget()
        self.import_tab = ImportTab(novel_id)
        self.ocr_tab = OCRReviewTab(novel_id)
        self.glossary_tab = GlossaryTab(novel_id)
        self.translate_tab = TranslateTab(novel_id)
        self.reembed_tab = ReembedTab(novel_id)
        self.export_tab = ExportTab(novel_id)
        self.activity_tab = ActivityTab()
        tabs.addTab(self.import_tab, "Import")
        tabs.addTab(self.ocr_tab, "OCR Review")
        tabs.addTab(self.glossary_tab, "Glossary")
        tabs.addTab(self.translate_tab, "Translate")
        tabs.addTab(self.reembed_tab, "Re-embed")
        tabs.addTab(self.export_tab, "Export")
        tabs.addTab(self.activity_tab, "Activity")
        layout.addWidget(tabs)

        for tab in [self.import_tab, self.ocr_tab, self.glossary_tab, self.translate_tab, self.reembed_tab, self.export_tab]:
            tab.activity.connect(self.activity_tab.append)
        self.import_tab.completed.connect(self.ocr_tab.refresh)
        self.import_tab.completed.connect(self.glossary_tab.refresh)


class DesktopMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        bootstrap()
        self.setWindowTitle("Novel AI Desktop")
        self.resize(1280, 860)
        root = QSplitter()
        self.setCentralWidget(root)
        self.nav = QListWidget()
        for name in ("Library", "Profiles"):
            self.nav.addItem(name)
        self.nav.currentRowChanged.connect(self._switch_view)
        root.addWidget(self.nav)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        self.library_view = LibraryView()
        self.library_view.open_requested.connect(self.open_workspace)
        self.profiles_view = ProfilesView()
        self.stack.addWidget(self.library_view)
        self.stack.addWidget(self.profiles_view)
        self.workspace: BookWorkspace | None = None
        self.nav.setCurrentRow(0)

    def _switch_view(self, index: int) -> None:
        if index >= 0 and index < self.stack.count():
            self.stack.setCurrentIndex(index)

    def open_workspace(self, novel_id: str) -> None:
        if self.workspace is not None:
            self.stack.removeWidget(self.workspace)
            self.workspace.deleteLater()
        self.workspace = BookWorkspace(novel_id)
        self.stack.addWidget(self.workspace)
        self.stack.setCurrentWidget(self.workspace)
        while self.nav.count() > 2:
            self.nav.takeItem(2)
        self.nav.addItem(f"Workspace: {novel_id}")
        self.nav.setCurrentRow(2)


def main() -> None:
    bootstrap()
    app = QApplication.instance() or QApplication([])
    window = DesktopMainWindow()
    window.show()
    app.exec()

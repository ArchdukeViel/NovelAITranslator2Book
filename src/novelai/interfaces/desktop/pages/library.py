from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novelai.export.registry import available_exporters
from novelai.config.settings import settings
from novelai.interfaces.desktop.export_helpers import build_export_output_path, collect_export_chapters
from novelai.interfaces.desktop.shared import AsyncTaskThread, StatCard, library_snapshots, safe_str
from novelai.runtime.container import container


class LibraryView(QWidget):
    open_requested = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.storage = container.storage
        self.export_service = container.export
        self.orchestrator = container.orchestrator
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("NOVEL LIBRARY")
        title.setObjectName("HeroTitle")
        layout.addWidget(title)

        stats_layout = QHBoxLayout()
        self.projects_card = StatCard("Projects")
        self.translated_card = StatCard("Translated")
        self.attention_card = StatCard("Attention")
        stats_layout.addWidget(self.projects_card)
        stats_layout.addWidget(self.translated_card)
        stats_layout.addWidget(self.attention_card)
        layout.addLayout(stats_layout)

        list_group = QGroupBox("Novel List")
        list_layout = QVBoxLayout(list_group)
        self.list_table = QTableWidget(0, 5)
        self.list_table.setHorizontalHeaderLabels(["No.", "Title", "Novel ID", "Chapters", "Translated"])
        self.list_table.setMinimumHeight(360)
        self.list_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.list_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_table.verticalHeader().setVisible(False)
        table_header = self.list_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 5):
            table_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.list_table.cellDoubleClicked.connect(self._open_current)
        self.list_table.currentCellChanged.connect(self._load_current)
        list_layout.addWidget(self.list_table)
        layout.addWidget(list_group)

        details_group = QGroupBox("Novel Details")
        details_layout = QVBoxLayout(details_group)
        self.details_output = QPlainTextEdit()
        self.details_output.setReadOnly(True)
        self.details_output.setMinimumHeight(220)
        self.details_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.details_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_output.setFont(QFont("Consolas", 10))
        details_layout.addWidget(self.details_output)
        layout.addWidget(details_group)

        toolbar = QHBoxLayout()
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._open_export_dialog)
        self.translate_button = QPushButton("Translate")
        self.translate_button.clicked.connect(self._open_translate_dialog)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self._delete_selected)
        self.delete_all_button = QPushButton("Delete All")
        self.delete_all_button.clicked.connect(self._delete_all)
        toolbar.addWidget(self.export_button)
        toolbar.addWidget(self.translate_button)
        toolbar.addWidget(self.delete_button)
        toolbar.addWidget(self.delete_all_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        current_novel_id = None
        current_row = self.list_table.currentRow()
        if current_row >= 0:
            current_id_item = self.list_table.item(current_row, 2)
            if current_id_item is not None:
                current_novel_id = current_id_item.data(Qt.ItemDataRole.UserRole)
        snapshots = library_snapshots()
        translated_total = sum(int(item.get("translated_units", 0)) for item in snapshots)
        attention_total = sum(
            int(item.get("ocr_pending", 0)) + int(item.get("glossary_pending", 0)) + int(item.get("errors", 0))
            for item in snapshots
        )
        self.projects_card.set_content(str(len(snapshots)), "Projects indexed in the current library")
        self.translated_card.set_content(str(translated_total), "Translated chapters currently available")
        self.attention_card.set_content(str(attention_total), "Items needing review or recovery")

        self.list_table.setRowCount(0)
        selected_row = -1
        for row_index, snapshot in enumerate(snapshots):
            self.list_table.insertRow(row_index)
            chapters = int(snapshot.get("total_units", 0))
            row_values = [
                str(row_index + 1),
                safe_str(snapshot.get("title")),
                snapshot["novel_id"],
                str(chapters),
                str(int(snapshot.get("translated_units", 0))),
            ]
            for column, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
                    item.setToolTip(snapshot["novel_id"])
                self.list_table.setItem(row_index, column, item)
            if current_novel_id == snapshot["novel_id"]:
                selected_row = row_index

        if self.list_table.rowCount() == 0:
            self.details_output.setPlainText("No projects in the library yet.")
            return

        if selected_row >= 0:
            self.list_table.setCurrentCell(selected_row, 0)
        elif self.list_table.currentRow() < 0:
            self.list_table.setCurrentCell(0, 0)

    def _load_current(
        self,
        current_row: int = -1,
        _current_column: int = -1,
        _previous_row: int = -1,
        _previous_column: int = -1,
    ) -> None:
        row = current_row if current_row >= 0 else self.list_table.currentRow()
        if row < 0:
            self.details_output.clear()
            return
        id_item = self.list_table.item(row, 2)
        if id_item is None:
            self.details_output.clear()
            return
        novel_id = id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(novel_id, str):
            self.details_output.clear()
            return
        snapshot = next((entry for entry in library_snapshots() if entry["novel_id"] == novel_id), None)
        if snapshot is None:
            self.details_output.setPlainText(f"No metadata found for {novel_id}.")
            return
        meta = self.storage.load_metadata(novel_id) or {}
        titles = meta.get("titles") if isinstance(meta.get("titles"), dict) else {}
        authors = meta.get("authors") if isinstance(meta.get("authors"), dict) else {}
        target_title = safe_str(titles.get("translated") or meta.get("translated_title") or meta.get("title"))
        original_title = safe_str(titles.get("original") or meta.get("title"))
        target_author = safe_str(authors.get("translated") or meta.get("translated_author") or meta.get("author"))
        original_author = safe_str(authors.get("original") or meta.get("author"))
        origin = safe_str(meta.get("source") or snapshot.get("origin_type") or snapshot.get("input_adapter_key"))
        chapters = int(snapshot.get("total_units", 0))
        translated = int(snapshot.get("translated_units", 0))
        labels = [
            "Target Title",
            "Original Title",
            "Author (target|original)",
            "Origin",
            "Source Language",
            "Chapters",
            "Translated Chapters",
            "Glossary Pending",
            "Failed Chapters",
        ]
        if int(snapshot.get("ocr_pending", 0)) > 0:
            labels.append("OCR Pending")
        label_width = max(len(label) for label in labels)

        def _detail(label: str, value: str) -> str:
            return f"{label:<{label_width}} : {value}"

        lines = [
            _detail("Target Title", target_title),
            _detail("Original Title", original_title),
            _detail("Author (target|original)", f"{target_author} | {original_author}"),
            _detail("Origin", origin),
            _detail("Source Language", safe_str(snapshot.get("source_language"))),
            _detail("Chapters", str(chapters)),
            _detail("Translated Chapters", str(translated)),
            _detail("Glossary Pending", str(snapshot["glossary_pending"])),
            _detail("Failed Chapters", str(snapshot["errors"])),
        ]
        if int(snapshot.get("ocr_pending", 0)) > 0:
            lines.append(_detail("OCR Pending", str(snapshot["ocr_pending"])))
        self.details_output.setPlainText("\n".join(lines))

    def _selected_novel_ids(self) -> list[str]:
        ids: list[str] = []
        for item in self.list_table.selectedItems():
            if item.column() != 2:
                continue
            novel_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(novel_id, str) and novel_id not in ids:
                ids.append(novel_id)
        if ids:
            return ids
        row = self.list_table.currentRow()
        if row < 0:
            return []
        id_item = self.list_table.item(row, 2)
        if id_item is None:
            return []
        novel_id = id_item.data(Qt.ItemDataRole.UserRole)
        return [novel_id] if isinstance(novel_id, str) else []

    def _open_export_dialog(self) -> None:
        novel_ids = self._selected_novel_ids()
        if not novel_ids:
            QMessageBox.information(self, "Export", "Select at least one novel to export.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Export")
        form = QFormLayout(dialog)

        format_input = QComboBox(dialog)
        for fmt in available_exporters():
            format_input.addItem(fmt.upper(), fmt)
        if format_input.count() == 0:
            format_input.addItem("EPUB", "epub")

        language_input = QComboBox(dialog)
        language_input.addItem("Translated", "translated")
        language_input.addItem("Source", "source")

        chapter_input = QLineEdit("", dialog)
        chapter_input.setPlaceholderText("all or range like 1-10, 12")

        toc_input = QCheckBox("Include table of contents (EPUB)", dialog)

        def _toggle_toc_visibility() -> None:
            selected_format = str(format_input.currentData() or "")
            toc_input.setVisible(selected_format == "epub")

        format_input.currentIndexChanged.connect(lambda _idx: _toggle_toc_visibility())
        _toggle_toc_visibility()

        form.addRow("Format", format_input)
        form.addRow("Language", language_input)
        form.addRow("Chapters", chapter_input)
        form.addRow("", toc_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        export_format = str(format_input.currentData() or "epub")
        language = str(language_input.currentData() or "translated")
        chapter_selection = chapter_input.text().strip() or "full"
        include_toc = toc_input.isChecked() and export_format == "epub"

        exported: list[str] = []
        failed: list[str] = []
        for novel_id in novel_ids:
            try:
                chapters = collect_export_chapters(
                    self.storage,
                    novel_id,
                    chapter_selection=chapter_selection,
                    language=language,
                )
                if not chapters:
                    raise ValueError("No chapters available for selected export options.")
                output_path = build_export_output_path(
                    self.storage,
                    novel_id,
                    export_format,
                    None,
                    chapter_selection,
                    language,
                )
                options: dict[str, object] = {}
                if export_format == "epub":
                    options["include_toc"] = include_toc
                self.export_service.export(
                    export_format,
                    novel_id=novel_id,
                    chapters=chapters,
                    output_path=output_path,
                    **options,
                )
                exported.append(novel_id)
            except Exception as exc:
                failed.append(f"{novel_id}: {exc}")

        if exported and not failed:
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {len(exported)} novel(s) as {export_format.upper()} ({language}).",
            )
        elif exported and failed:
            QMessageBox.warning(
                self,
                "Export Partial",
                f"Exported {len(exported)} novel(s). Failed {len(failed)}:\n" + "\n".join(failed[:5]),
            )
        else:
            QMessageBox.warning(self, "Export Failed", "No selected novels could be exported.\n" + "\n".join(failed[:5]))

    def _open_translate_dialog(self) -> None:
        novel_ids = self._selected_novel_ids()
        if len(novel_ids) != 1:
            QMessageBox.information(self, "Translate", "Select exactly one novel to translate.")
            return
        novel_id = novel_ids[0]
        meta = self.storage.load_metadata(novel_id) or {}
        source_key = safe_str(meta.get("source") or meta.get("input_adapter_key"), "web")
        source_language = safe_str(meta.get("source_language"), "auto")

        dialog = QDialog(self)
        dialog.setWindowTitle("Translate")
        dialog_layout = QVBoxLayout(dialog)

        info_label = QLabel(f"Novel: {novel_id} | Source: {source_key} | Source Language: {source_language}", dialog)
        info_label.setWordWrap(True)
        dialog_layout.addWidget(info_label)

        chapter_status = QTableWidget(0, 5, dialog)
        chapter_status.setHorizontalHeaderLabels(["Chapter", "Title", "Translated", "Source", "Target"])
        chapter_status.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        chapter_status.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        chapter_status.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chapter_status.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chapter_status.verticalHeader().setVisible(False)
        status_header = chapter_status.horizontalHeader()
        status_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        status_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4):
            status_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        target_language = safe_str(settings.TRANSLATION_TARGET_LANGUAGE, "Indonesian")
        chapters = [chapter for chapter in meta.get("chapters", []) if isinstance(chapter, dict)]
        for row, chapter in enumerate(chapters):
            chapter_id = str(chapter.get("id") or "")
            if not chapter_id:
                continue
            translated_data = self.storage.load_translated_chapter(novel_id, chapter_id)
            translated_flag = "Yes" if translated_data is not None else "No"
            row_values = [
                chapter_id,
                safe_str(chapter.get("translated_title") or chapter.get("title"), f"Chapter {chapter_id}"),
                translated_flag,
                source_language,
                target_language,
            ]
            chapter_status.insertRow(row)
            for col, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                if col in {0, 2, 3, 4}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                chapter_status.setItem(row, col, item)
        dialog_layout.addWidget(chapter_status)

        form = QFormLayout()
        target_input = QComboBox(dialog)
        language_options = [
            "Indonesian",
            "English",
            "Japanese",
            "Chinese",
            "Korean",
            "Spanish",
            "French",
            "German",
            "Thai",
            "Vietnamese",
        ]
        for language_name in language_options:
            target_input.addItem(language_name)
        existing_target_index = target_input.findText(target_language)
        if existing_target_index >= 0:
            target_input.setCurrentIndex(existing_target_index)
        else:
            target_input.insertItem(0, target_language)
            target_input.setCurrentIndex(0)

        chapter_input = QLineEdit("", dialog)
        chapter_input.setPlaceholderText("all or range like 1-10, 12")
        form.addRow("Target Language", target_input)
        form.addRow("Chapters", chapter_input)
        dialog_layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return

        requested_target = target_input.currentText().strip() or target_language
        requested_chapters = chapter_input.text().strip() or "all"

        def _run_translate() -> object:
            asyncio.run(
                self.orchestrator.translate_chapters(
                    source_key=source_key,
                    novel_id=novel_id,
                    chapters=requested_chapters,
                    target_language=requested_target,
                )
            )
            return {"novel_id": novel_id, "chapters": requested_chapters, "target": requested_target}

        worker = AsyncTaskThread(_run_translate, self)

        def _on_success(_payload: object) -> None:
            msg = QMessageBox(self)
            msg.setWindowTitle("Translation Result")
            msg.setText("Translate completed successfully.")
            msg.setInformativeText("Choose whether to export now or later.")
            export_now_button = msg.addButton("Export Now", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Export Later", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == export_now_button:
                self._open_export_dialog()
            self.refresh()

        def _on_failed(message: str) -> None:
            msg = QMessageBox(self)
            msg.setWindowTitle("Translation Result")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("Translate failed.")
            msg.setInformativeText(message + "\n\nChoose whether to export now or later.")
            export_now_button = msg.addButton("Export Now", QMessageBox.ButtonRole.AcceptRole)
            msg.addButton("Export Later", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == export_now_button:
                self._open_export_dialog()
            self.refresh()

        worker.succeeded.connect(_on_success)
        worker.failed.connect(_on_failed)
        worker.start()
        self._translate_worker = worker

    def _delete_selected(self) -> None:
        novel_ids = self._selected_novel_ids()
        if not novel_ids:
            QMessageBox.information(self, "Delete", "Select at least one novel to delete.")
            return
        answer = QMessageBox.question(
            self,
            "Delete Selected",
            f"Delete {len(novel_ids)} selected novel(s)? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for novel_id in novel_ids:
            self.storage.delete_novel(novel_id)
        self.refresh()

    def _delete_all(self) -> None:
        snapshots = library_snapshots()
        if not snapshots:
            QMessageBox.information(self, "Delete All", "No novels in the library.")
            return
        answer = QMessageBox.question(
            self,
            "Delete All",
            f"Delete all {len(snapshots)} novel(s) from the library? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for snapshot in snapshots:
            self.storage.delete_novel(snapshot["novel_id"])
        self.refresh()

    def _open_current(self, *_args: object) -> None:
        row = self.list_table.currentRow()
        if row < 0:
            return
        id_item = self.list_table.item(row, 2)
        if id_item is None:
            return
        novel_id = id_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_requested.emit(novel_id)

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop.shared import StatCard, library_snapshots, safe_str, short_id, timestamp_label
from novelai.runtime.container import container


class LibraryView(QWidget):
    open_requested = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.storage = container.storage
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

        list_group = QGroupBox("Projects")
        list_layout = QVBoxLayout(list_group)
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(360)
        self.list_widget.setWordWrap(True)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.itemDoubleClicked.connect(self._open_current)
        self.list_widget.currentItemChanged.connect(self._load_current)
        list_layout.addWidget(self.list_widget)
        layout.addWidget(list_group)

        details_group = QGroupBox("Novel Details")
        details_layout = QVBoxLayout(details_group)
        self.details_output = QPlainTextEdit()
        self.details_output.setReadOnly(True)
        self.details_output.setMinimumHeight(220)
        self.details_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        details_layout.addWidget(self.details_output)
        layout.addWidget(details_group)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.open_button = QPushButton("Open Workspace")
        self.open_button.clicked.connect(self._open_current)
        self.import_button = QPushButton("Import Document")
        self.import_button.clicked.connect(lambda: self.navigate_requested.emit("import"))
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.import_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addStretch()

        self.refresh()

    def refresh(self) -> None:
        current_novel_id = None
        current_item = self.list_widget.currentItem()
        if current_item is not None:
            current_novel_id = current_item.data(Qt.ItemDataRole.UserRole)
        snapshots = library_snapshots()
        translated_total = sum(int(item.get("translated_units", 0)) for item in snapshots)
        attention_total = sum(
            int(item.get("ocr_pending", 0)) + int(item.get("glossary_pending", 0)) + int(item.get("errors", 0))
            for item in snapshots
        )
        self.projects_card.set_content(str(len(snapshots)), "Projects indexed in the current library")
        self.translated_card.set_content(str(translated_total), "Units with translated output on disk")
        self.attention_card.set_content(str(attention_total), "Pending manual review or failed states")

        self.list_widget.clear()
        for snapshot in snapshots:
            item = QListWidgetItem(f"{snapshot['title']}  [{short_id(snapshot['novel_id'])}]")
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.list_widget.addItem(item)
            if current_novel_id == snapshot["novel_id"]:
                self.list_widget.setCurrentItem(item)
        if self.list_widget.count() == 0:
            self.details_output.setPlainText("No projects in the library yet.")
        elif self.list_widget.currentItem() is None:
            self.list_widget.setCurrentRow(0)

    def _load_current(
        self,
        current: QListWidgetItem | None = None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        item = current or self.list_widget.currentItem()
        if item is None:
            self.details_output.clear()
            return
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(novel_id, str):
            self.details_output.clear()
            return
        snapshot = next((entry for entry in library_snapshots() if entry["novel_id"] == novel_id), None)
        if snapshot is None:
            self.details_output.setPlainText(f"No metadata found for {novel_id}.")
            return
        meta = self.storage.load_metadata(novel_id) or {}
        lines = [
            f"Title: {snapshot['title']}",
            f"Novel ID: {novel_id}",
            f"Author: {safe_str(snapshot.get('author'))}",
            f"Document Type: {safe_str(snapshot.get('document_type'))}",
            f"Origin Type: {safe_str(snapshot.get('origin_type'))}",
            f"Origin: {safe_str(snapshot.get('origin_uri_or_path'))}",
            f"Input Adapter: {safe_str(snapshot.get('input_adapter_key'))}",
            f"Source Language: {safe_str(snapshot.get('source_language'))}",
            f"Updated: {timestamp_label(snapshot.get('updated_at'))}",
            "",
            f"Units: {snapshot['total_units']}",
            f"Translated: {snapshot['translated_units']}",
            f"OCR Pending: {snapshot['ocr_pending']}",
            f"Glossary Pending: {snapshot['glossary_pending']}",
            f"Failed Chapters: {snapshot['errors']}",
        ]
        translated_title = meta.get("translated_title")
        if isinstance(translated_title, str) and translated_title.strip():
            lines.extend(["", f"Translated Title: {translated_title}"])
        self.details_output.setPlainText("\n".join(lines))

    def _open_current(self, *_args: object) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_requested.emit(novel_id)

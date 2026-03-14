from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop.shared import DesktopActivityModel, StatCard, library_snapshots, safe_str, short_id


class HomeView(QWidget):
    navigate_requested = Signal(str)
    open_workspace_requested = Signal(str)

    def __init__(self, activity_model: DesktopActivityModel) -> None:
        super().__init__()
        self.activity_model = activity_model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("NOVELAI2BOOK")
        title.setObjectName("HeroTitle")
        layout.addWidget(title)

        stats_layout = QHBoxLayout()
        self.projects_card = StatCard("Projects")
        self.translation_card = StatCard("Translated Units")
        self.attention_card = StatCard("Needs Attention")
        self.activity_card = StatCard("Running Jobs")
        stats_layout.addWidget(self.projects_card)
        stats_layout.addWidget(self.translation_card)
        stats_layout.addWidget(self.attention_card)
        stats_layout.addWidget(self.activity_card)
        layout.addLayout(stats_layout)

        quick_group = QGroupBox("Quick Actions")
        quick_layout = QGridLayout(quick_group)
        actions = [
            ("New Novel", lambda: self.navigate_requested.emit("import")),
            ("Start Translation", self._open_first_translation_workspace),
            ("Export Novel", self._open_first_export_workspace),
        ]
        for index, (label, handler) in enumerate(actions):
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(handler)
            quick_layout.addWidget(button, 0, index)
        for column in range(3):
            quick_layout.setColumnStretch(column, 1)
        layout.addWidget(quick_group)

        recent_group = QGroupBox("Novel List")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_table = QTableWidget(0, 5)
        self.recent_table.setHorizontalHeaderLabels(["No.", "Title", "Novel ID", "Chapters", "Translated"])
        self.recent_table.setMinimumHeight(190)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_table.verticalHeader().setVisible(False)
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for column in range(2, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.recent_table.cellDoubleClicked.connect(self._open_recent_row)
        recent_layout.addWidget(self.recent_table)
        layout.addWidget(recent_group)

        attention_group = QGroupBox("Needs Attention")
        attention_layout = QVBoxLayout(attention_group)
        self.attention_list = QListWidget()
        self._configure_home_list(self.attention_list, min_height=190)
        self.attention_list.itemDoubleClicked.connect(self._open_item_novel)
        attention_layout.addWidget(self.attention_list)
        layout.addWidget(attention_group)

        jobs_group = QGroupBox("Active Jobs")
        jobs_layout = QVBoxLayout(jobs_group)
        self.jobs_list = QListWidget()
        self._configure_home_list(self.jobs_list, min_height=96)
        jobs_layout.addWidget(self.jobs_list)
        layout.addWidget(jobs_group)
        layout.addStretch()

        self.activity_model.jobs_changed.connect(self.refresh)
        self.activity_model.messages_changed.connect(self.refresh)
        self.refresh()

    def _configure_home_list(self, widget: QListWidget, *, min_height: int) -> None:
        widget.setMinimumHeight(min_height)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setWordWrap(True)
        widget.setSpacing(4)

    def _first_snapshot(self, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any] | None:
        for snapshot in library_snapshots():
            if predicate(snapshot):
                return snapshot
        return None

    def _open_first_ocr_workspace(self) -> None:
        snapshot = self._first_snapshot(lambda item: int(item.get("ocr_pending", 0)) > 0)
        if snapshot is None:
            self.navigate_requested.emit("library")
            return
        self.open_workspace_requested.emit(snapshot["novel_id"])

    def _open_first_translation_workspace(self) -> None:
        snapshot = self._first_snapshot(
            lambda item: int(item.get("untranslated_units", 0)) > 0 and int(item.get("ocr_pending", 0)) == 0
        )
        if snapshot is None:
            self.navigate_requested.emit("library")
            return
        self.open_workspace_requested.emit(snapshot["novel_id"])

    def _open_first_export_workspace(self) -> None:
        snapshot = self._first_snapshot(lambda item: int(item.get("translated_units", 0)) > 0)
        if snapshot is None:
            self.navigate_requested.emit("library")
            return
        self.open_workspace_requested.emit(snapshot["novel_id"])

    def _open_item_novel(self, item: QListWidgetItem) -> None:
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_workspace_requested.emit(novel_id)

    def _open_recent_row(self, row: int, _column: int) -> None:
        id_item = self.recent_table.item(row, 2)
        if id_item is None:
            return
        novel_id = id_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_workspace_requested.emit(novel_id)

    def refresh(self) -> None:
        self.recent_table.setRowCount(0)
        self.attention_list.clear()
        self.jobs_list.clear()

        snapshots = library_snapshots()
        translated_units = sum(int(snapshot.get("translated_units", 0)) for snapshot in snapshots)
        total_attention = sum(
            int(snapshot.get("ocr_pending", 0)) + int(snapshot.get("glossary_pending", 0)) + int(snapshot.get("errors", 0))
            for snapshot in snapshots
        )
        self.projects_card.set_content(str(len(snapshots)), "Projects currently stored in the library")
        self.translation_card.set_content(str(translated_units), "Translated chapters ready for export or review")
        self.attention_card.set_content(str(total_attention), "Pending OCR, glossary review, or failed chapters")
        self.activity_card.set_content(str(len(self.activity_model.running_jobs())), "Background jobs active right now")

        for row_index, snapshot in enumerate(snapshots[:10]):
            self.recent_table.insertRow(row_index)
            chapters = int(snapshot.get("total_units", 0))
            row_values = [
                str(row_index + 1),
                safe_str(snapshot.get("title")),
                snapshot["novel_id"],
                str(chapters),
                str(int(snapshot.get("translated_units", 0))),
            ]
            for column, value in enumerate(row_values):
                table_item = QTableWidgetItem(value)
                if column != 1:
                    table_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    table_item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
                    table_item.setToolTip(snapshot["novel_id"])
                self.recent_table.setItem(row_index, column, table_item)

        if self.recent_table.rowCount() == 0:
            self.recent_table.setRowCount(1)
            empty_item = QTableWidgetItem("No projects in the library yet.")
            empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.recent_table.setSpan(0, 0, 1, 5)
            self.recent_table.setItem(0, 0, empty_item)

        for snapshot in snapshots:
            reasons: list[str] = []
            if int(snapshot.get("ocr_pending", 0)) > 0:
                reasons.append(f"{snapshot['ocr_pending']} OCR review")
            if int(snapshot.get("glossary_pending", 0)) > 0:
                reasons.append(f"{snapshot['glossary_pending']} glossary pending")
            if int(snapshot.get("errors", 0)) > 0:
                reasons.append(f"{snapshot['errors']} failed chapters")
            if int(snapshot.get("untranslated_units", 0)) > 0 and int(snapshot.get("ocr_pending", 0)) == 0:
                reasons.append(f"{snapshot['untranslated_units']} untranslated")
            if not reasons:
                continue
            item = QListWidgetItem(
                f"{snapshot['title']}  [{short_id(snapshot['novel_id'])}]\n{' \u00b7 '.join(reasons)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.attention_list.addItem(item)

        if self.attention_list.count() == 0:
            self.attention_list.addItem("No projects currently need manual attention.")

        for job in self.activity_model.running_jobs():
            self.jobs_list.addItem(job)
        if self.jobs_list.count() == 0:
            self.jobs_list.addItem("No active jobs.")

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
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

        eyebrow = QLabel("NOVELAI2BOOK")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Your novel translation workspace.")
        title.setObjectName("HeroTitle")
        description = QLabel(
            "Import, OCR, build glossaries, translate, and export \u2014 all from one place."
        )
        description.setObjectName("HeroBody")
        description.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)

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
            ("Import Document", lambda: self.navigate_requested.emit("import")),
            ("Open Library", lambda: self.navigate_requested.emit("library")),
            ("Resume OCR", self._open_first_ocr_workspace),
            ("Start Translation", self._open_first_translation_workspace),
            ("Export Latest", self._open_first_export_workspace),
            ("View Activity", lambda: self.navigate_requested.emit("activity")),
            ("Profiles", lambda: self.navigate_requested.emit("profiles")),
        ]
        for index, (label, handler) in enumerate(actions):
            button = QPushButton(label)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(handler)
            quick_layout.addWidget(button, index // 4, index % 4)
        for column in range(4):
            quick_layout.setColumnStretch(column, 1)
        layout.addWidget(quick_group)

        recent_group = QGroupBox("Recent Projects")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_list = QListWidget()
        self._configure_home_list(self.recent_list, min_height=190)
        self.recent_list.itemDoubleClicked.connect(self._open_item_novel)
        recent_layout.addWidget(self.recent_list)
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

    def refresh(self) -> None:
        self.recent_list.clear()
        self.attention_list.clear()
        self.jobs_list.clear()

        snapshots = library_snapshots()
        translated_units = sum(int(snapshot.get("translated_units", 0)) for snapshot in snapshots)
        total_attention = sum(
            int(snapshot.get("ocr_pending", 0)) + int(snapshot.get("glossary_pending", 0)) + int(snapshot.get("errors", 0))
            for snapshot in snapshots
        )
        self.projects_card.set_content(str(len(snapshots)), "Projects currently stored in the library")
        self.translation_card.set_content(str(translated_units), "Translated units ready for export or review")
        self.attention_card.set_content(str(total_attention), "Pending OCR, glossary review, or failed chapters")
        self.activity_card.set_content(str(len(self.activity_model.running_jobs())), "Background jobs active right now")

        for snapshot in snapshots[:10]:
            adapter = safe_str(snapshot.get("input_adapter_key"), "")
            meta = f"{snapshot['translated_units']}/{snapshot['total_units']} translated"
            if adapter:
                meta = f"{meta}  \u00b7  {adapter}"
            item = QListWidgetItem(
                f"{snapshot['title']}  [{short_id(snapshot['novel_id'])}]\n{meta}"
            )
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.recent_list.addItem(item)
        if self.recent_list.count() == 0:
            self.recent_list.addItem("No projects in the library yet.")

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

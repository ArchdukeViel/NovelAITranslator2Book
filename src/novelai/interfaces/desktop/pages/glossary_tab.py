from __future__ import annotations

import asyncio
from typing import Any

from PySide6.QtCore import Qt, Signal
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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novelai.glossary import glossary_status_counts
from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.shared import AsyncTaskThread, DesktopActivityModel, safe_str


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
        self.storage = desktop_shared.container.storage
        self.orchestrator = desktop_shared.container.orchestrator
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

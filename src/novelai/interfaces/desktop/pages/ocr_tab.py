from __future__ import annotations

import asyncio
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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.shared import AsyncTaskThread


class OCRReviewTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = desktop_shared.container.storage
        self.orchestrator = desktop_shared.container.orchestrator
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

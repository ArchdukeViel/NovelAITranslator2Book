from __future__ import annotations

import contextlib
from typing import Any

from PySide6.QtCore import Signal, Qt
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
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop import shared as desktop_shared
from novelai.core.chapter_state import ChapterState
from novelai.interfaces.desktop.export_helpers import build_export_output_path, build_export_plan
from novelai.interfaces.desktop.shared import (
    StatCard,
    library_snapshots,
    profiles_snapshot_text,
    recent_export_paths,
    safe_str,
    timestamp_label,
)


class ReembedTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = desktop_shared.container.storage
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
        self.storage = desktop_shared.container.storage
        self.exporter = desktop_shared.container.export
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
        meta = desktop_shared.container.storage.load_metadata(self.novel_id) or {}
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
                str(len(desktop_shared.container.storage.get_chapters_ready_for_export(self.novel_id))),
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

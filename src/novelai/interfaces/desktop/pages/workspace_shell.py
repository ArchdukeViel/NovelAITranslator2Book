from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop import shared as desktop_shared
from novelai.interfaces.desktop.pages.glossary_tab import GlossaryTab
from novelai.interfaces.desktop.pages.ocr_tab import OCRReviewTab
from novelai.interfaces.desktop.pages.translate_tab import TranslateTab
from novelai.interfaces.desktop.pages.workspace_panels import ExportTab, ReembedTab, WorkspaceOverviewTab
from novelai.interfaces.desktop.shared import DesktopActivityModel, library_snapshots, safe_str


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
            bool((desktop_shared.container.storage.load_chapter_media_state(self.novel_id, cid) or {}).get("ocr_required"))
            for cid in desktop_shared.container.storage.list_stored_chapters(self.novel_id)
        )
        self.tabs.setTabVisible(self._ocr_tab_index, needs_ocr)

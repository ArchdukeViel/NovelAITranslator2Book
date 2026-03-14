from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop.shared import DesktopActivityModel, StatCard
from novelai.runtime.container import container


class ActivityView(QWidget):
    def __init__(self, activity_model: DesktopActivityModel) -> None:
        super().__init__()
        self.activity_model = activity_model
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("ACTIVITY")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Usage history, running jobs, and recent operation events.")
        subtitle.setObjectName("HeroBody")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        stats_layout = QHBoxLayout()
        self.requests_card = StatCard("Requests")
        self.tokens_card = StatCard("Tokens")
        self.cost_card = StatCard("Estimated Cost")
        self.jobs_card = StatCard("Running Jobs")
        stats_layout.addWidget(self.requests_card)
        stats_layout.addWidget(self.tokens_card)
        stats_layout.addWidget(self.cost_card)
        stats_layout.addWidget(self.jobs_card)
        layout.addLayout(stats_layout)

        usage_group = QGroupBox("Usage History")
        usage_layout = QVBoxLayout(usage_group)
        self.usage_table = QTableWidget(0, 4)
        self.usage_table.setHorizontalHeaderLabels(["Date", "Requests", "Tokens", "Cost (USD)"])
        self.usage_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.usage_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.usage_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.usage_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.usage_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.usage_table.verticalHeader().setVisible(False)
        header = self.usage_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        usage_layout.addWidget(self.usage_table)
        layout.addWidget(usage_group)

        work_group = QGroupBox("Active Jobs and Events")
        work_layout = QVBoxLayout(work_group)
        jobs_title = QLabel("Running Jobs")
        jobs_title.setObjectName("HeroEyebrow")
        self.jobs_list = QListWidget()
        self.jobs_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.jobs_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        phase_title = QLabel("Phase Timeline")
        phase_title.setObjectName("HeroEyebrow")
        self.phase_summary_label = QLabel("No phase activity yet.")
        self.phase_summary_label.setWordWrap(True)
        self.phase_timeline_list = QListWidget()
        self.phase_timeline_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.phase_timeline_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        events_title = QLabel("Recent Events")
        events_title.setObjectName("HeroEyebrow")
        self.events_list = QListWidget()
        self.events_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.events_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        work_layout.addWidget(jobs_title)
        work_layout.addWidget(self.jobs_list)
        work_layout.addWidget(phase_title)
        work_layout.addWidget(self.phase_summary_label)
        work_layout.addWidget(self.phase_timeline_list)
        work_layout.addWidget(events_title)
        work_layout.addWidget(self.events_list)
        layout.addWidget(work_group)

        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.clear_button = QPushButton("Clear Log")
        self.refresh_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.activity_model.clear_messages)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.activity_model.jobs_changed.connect(self.refresh)
        self.activity_model.messages_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        summary = container.usage.summary(all_days=True)
        self.requests_card.set_content(str(summary.get("total_requests", 0)), "Total API requests")
        self.tokens_card.set_content(str(summary.get("total_tokens", 0)), "Total token usage")
        self.cost_card.set_content(f"${summary.get('estimated_cost_usd', 0.0):.4f}", "Estimated spend")
        self.jobs_card.set_content(str(len(self.activity_model.running_jobs())), "Currently active jobs")

        self.usage_table.setRowCount(0)
        for row, entry in enumerate(container.usage.daily_history(limit=14)):
            self.usage_table.insertRow(row)
            values = [
                str(entry.get("date") or "-"),
                str(int(entry.get("total_requests", 0))),
                str(int(entry.get("total_tokens", 0))),
                f"{float(entry.get('estimated_cost_usd', 0.0)):.4f}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.usage_table.setItem(row, col, item)
        if self.usage_table.rowCount() == 0:
            self.usage_table.setRowCount(1)
            empty = QTableWidgetItem("No usage history yet.")
            empty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.usage_table.setSpan(0, 0, 1, 4)
            self.usage_table.setItem(0, 0, empty)

        self.jobs_list.clear()
        for job in self.activity_model.running_jobs():
            self.jobs_list.addItem(job)
        if self.jobs_list.count() == 0:
            self.jobs_list.addItem("No active jobs.")

        counters = self.activity_model.phase_counters()
        if not counters:
            self.phase_summary_label.setText("No phase activity yet.")
        else:
            parts = []
            for phase, counts in sorted(counters.items()):
                compact = ", ".join(f"{status}:{count}" for status, count in sorted(counts.items()))
                parts.append(f"{phase} ({compact})")
            self.phase_summary_label.setText("Phase counters: " + " | ".join(parts))

        _phase_colors: dict[str, str] = {
            "completed": "#4CAF50",
            "blocked": "#FF9800",
            "failed": "#F44336",
        }
        self.phase_timeline_list.clear()
        for event in self.activity_model.phase_events()[-40:]:
            timestamp = str(event.get("timestamp") or "-")
            phase = str(event.get("phase") or "phase")
            status = str(event.get("status") or "completed")
            novel_id = str(event.get("novel_id") or "-")
            message = str(event.get("message") or "")
            item = QListWidgetItem(f"{timestamp} {phase} [{status}] {novel_id} {message}".strip())
            if status in _phase_colors:
                item.setForeground(QColor(_phase_colors[status]))
            self.phase_timeline_list.addItem(item)
        if self.phase_timeline_list.count() == 0:
            self.phase_timeline_list.addItem("No phase timeline events yet.")

        self.events_list.clear()
        for line in self.activity_model.messages()[-40:]:
            self.events_list.addItem(line)
        if self.events_list.count() == 0:
            self.events_list.addItem("No activity events yet.")

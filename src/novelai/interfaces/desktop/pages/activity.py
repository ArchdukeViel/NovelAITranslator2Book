from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from novelai.interfaces.desktop.shared import DesktopActivityModel


class ActivityView(QWidget):
    def __init__(self, activity_model: DesktopActivityModel) -> None:
        super().__init__()
        self.activity_model = activity_model
        layout = QVBoxLayout(self)
        eyebrow = QLabel("ACTIVITY")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Watch queued work, running jobs, and recent operation output.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.clear_button = QPushButton("Clear Log")
        self.refresh_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.activity_model.clear_messages)
        controls.addWidget(self.refresh_button)
        controls.addWidget(self.clear_button)
        controls.addStretch()
        layout.addLayout(controls)

        splitter = QSplitter()
        self.jobs_list = QListWidget()
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        splitter.addWidget(self.jobs_list)
        splitter.addWidget(self.log_output)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        self.activity_model.jobs_changed.connect(self.refresh)
        self.activity_model.messages_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        self.jobs_list.clear()
        for job in self.activity_model.running_jobs():
            self.jobs_list.addItem(job)
        if self.jobs_list.count() == 0:
            self.jobs_list.addItem("No active jobs.")
        self.log_output.setPlainText("\n".join(self.activity_model.messages()))

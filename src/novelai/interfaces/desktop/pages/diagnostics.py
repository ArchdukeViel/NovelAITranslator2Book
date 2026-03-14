from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from novelai.config.settings import settings
from novelai.inputs.registry import available_input_adapters
from novelai.interfaces.desktop.shared import library_snapshots
from novelai.providers.registry import available_providers
from novelai.runtime.container import container
from novelai.sources.registry import available_sources


class DiagnosticsView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        eyebrow = QLabel("DIAGNOSTICS")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Check library health, adapter coverage, provider availability, and usage totals.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)
        controls.addStretch()
        layout.addLayout(controls)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        snapshots = library_snapshots()
        usage = container.usage.summary(all_days=True)
        lines = [
            f"Library Path: {settings.NOVEL_LIBRARY_DIR}",
            f"Projects: {len(snapshots)}",
            f"Sources: {', '.join(sorted(available_sources())) or '-'}",
            f"Input Adapters: {', '.join(sorted(available_input_adapters())) or '-'}",
            f"Providers: {', '.join(sorted(available_providers())) or '-'}",
            "",
            f"Usage Requests: {usage.get('total_requests', 0)}",
            f"Usage Tokens: {usage.get('total_tokens', 0)}",
            f"Usage Cost: ${usage.get('estimated_cost_usd', 0.0):.4f}",
            "",
            "Projects:",
        ]
        for snapshot in snapshots:
            lines.append(
                f"- {snapshot['novel_id']}: {snapshot['translated_units']}/{snapshot['total_units']} translated, "
                f"OCR pending {snapshot['ocr_pending']}, glossary pending {snapshot['glossary_pending']}, "
                f"errors {snapshot['errors']}"
            )
        if not snapshots:
            lines.append("- No projects found.")
        self.output.setPlainText("\n".join(lines))

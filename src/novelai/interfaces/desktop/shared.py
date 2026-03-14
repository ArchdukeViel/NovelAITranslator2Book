from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from novelai.config.settings import settings
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.glossary import glossary_status_counts
from novelai.runtime.container import container


def timestamp_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
    return "-"


def safe_str(value: Any, fallback: str = "-") -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    if value is None:
        return fallback
    return str(value)


def short_id(novel_id: str) -> str:
    """Return a compact display form of a novel ID, truncating long hash-style IDs."""
    if len(novel_id) > 12:
        return novel_id[:8] + "\u2026"
    return novel_id


def snapshot_media_counts(novel_id: str) -> dict[str, int]:
    storage = container.storage
    counts = {
        "ocr_required": 0,
        "ocr_pending": 0,
        "ocr_reviewed": 0,
        "reembed_pending": 0,
        "reembed_completed": 0,
    }
    for chapter_id in storage.list_stored_chapters(novel_id):
        media = storage.load_chapter_media_state(novel_id, chapter_id) or {}
        ocr_required = bool(media.get("ocr_required"))
        if ocr_required:
            counts["ocr_required"] += 1
        ocr_status = str(media.get("ocr_status") or "skipped").strip().lower()
        if ocr_required and ocr_status in {"pending", "failed"}:
            counts["ocr_pending"] += 1
        if ocr_required and ocr_status == "reviewed":
            counts["ocr_reviewed"] += 1
        reembed_status = str(media.get("reembed_status") or "skipped").strip().lower()
        if reembed_status == "pending":
            counts["reembed_pending"] += 1
        elif reembed_status == "completed":
            counts["reembed_completed"] += 1
    return counts


def library_snapshots() -> list[dict[str, Any]]:
    storage = container.storage
    snapshots: list[dict[str, Any]] = []
    for novel_id in sorted(storage.list_novels()):
        meta = storage.load_metadata(novel_id) or {}
        chapter_rows = [row for row in meta.get("chapters", []) if isinstance(row, dict)]
        chapter_ids = [str(row.get("id")) for row in chapter_rows if row.get("id") is not None]
        if not chapter_ids:
            chapter_ids = storage.list_stored_chapters(novel_id)
        total_units = len(chapter_ids)
        translated_units = sum(
            1 for chapter_id in chapter_ids if storage.load_translated_chapter(novel_id, chapter_id) is not None
        )
        glossary_counts = glossary_status_counts(storage.load_glossary(novel_id))
        media_counts = snapshot_media_counts(novel_id)
        snapshots.append(
            {
                "novel_id": novel_id,
                "title": meta.get("title") or novel_id,
                "author": meta.get("author"),
                "document_type": meta.get("document_type"),
                "origin_type": meta.get("origin_type"),
                "origin_uri_or_path": meta.get("origin_uri_or_path"),
                "input_adapter_key": meta.get("input_adapter_key"),
                "source_language": meta.get("source_language"),
                "updated_at": meta.get("updated_at") or meta.get("scraped_at"),
                "total_units": total_units,
                "translated_units": translated_units,
                "untranslated_units": max(total_units - translated_units, 0),
                "ocr_pending": media_counts["ocr_pending"],
                "ocr_reviewed": media_counts["ocr_reviewed"],
                "reembed_pending": media_counts["reembed_pending"],
                "glossary_pending": glossary_counts.get("pending", 0),
                "glossary_approved": glossary_counts.get("approved", 0),
                "errors": len(storage.get_chapters_with_errors(novel_id, limit=max(total_units, 100))),
            }
        )
    snapshots.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return snapshots


def recent_export_paths(limit: int = 8) -> list[Path]:
    storage = container.storage
    root = getattr(storage, "novels_dir", settings.NOVEL_LIBRARY_DIR / "novels")
    if not isinstance(root, Path) or not root.exists():
        return []
    paths = [path for path in root.rglob("full_novel.*") if path.is_file()]
    paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[:limit]


def usage_snapshot_text() -> str:
    summary = container.usage.summary(all_days=True)
    lines = [
        f"Requests: {summary.get('total_requests', 0)}",
        f"Tokens: {summary.get('total_tokens', 0)}",
        f"Estimated Cost: ${summary.get('estimated_cost_usd', 0.0):.4f}",
        f"Projection Estimates: {summary.get('total_estimates', 0)}",
        f"Projected Tokens: {summary.get('estimated_total_tokens', 0)}",
    ]
    for entry in container.usage.daily_history(limit=5):
        lines.append(f"{entry.get('date')}: {entry.get('total_requests', 0)} req, {entry.get('total_tokens', 0)} tok")
    return "\n".join(lines)


def profiles_snapshot_text() -> str:
    profiles = container.preferences.get_workflow_profiles()
    lines: list[str] = []
    for step in WORKFLOW_PROFILE_STEPS:
        profile = profiles.get(step, {})
        provider = profile.get("provider") if isinstance(profile, dict) else None
        model = profile.get("model") if isinstance(profile, dict) else None
        lines.append(f"{step.replace('_', ' ').title()}: {safe_str(provider, 'inherit')} / {safe_str(model, 'inherit')}")
    return "\n".join(lines)


def build_stylesheet() -> str:
    return """  /* --- NovelAI2Book desktop stylesheet --- */
    QMainWindow, QWidget {
        background: #f3ede2;
        color: #182322;
        font-family: "Bahnschrift SemiCondensed", "Segoe UI Variable Text", "Segoe UI";
        font-size: 13px;
    }
    QMainWindow::separator {
        background: #d8c3a4;
        width: 1px;
        height: 1px;
    }
    QListWidget#NavList {
        background: #162126;
        color: #ecf1ea;
        border: none;
        border-radius: 20px;
        padding: 12px 8px;
        outline: none;
    }
    QListWidget#NavList::item {
        border-radius: 12px;
        padding: 12px 14px;
        margin: 4px 6px;
    }
    QListWidget#NavList::item:selected {
        background: #d2a868;
        color: #1a2221;
        font-weight: 700;
    }
    QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QTabWidget::pane {
        background: #fffaf3;
        border: 1px solid #dccab0;
        border-radius: 14px;
        selection-background-color: #184e5e;
        selection-color: #fffaf3;
    }
    QListWidget {
        padding: 6px;
        outline: none;
    }
    QListWidget::item {
        border-radius: 10px;
        padding: 8px 10px;
        margin: 2px 0;
    }
    QListWidget::item:selected {
        background: #184e5e;
        color: #fffaf3;
    }
    QPlainTextEdit, QLineEdit, QComboBox {
        padding: 8px 10px;
    }
    QComboBox::drop-down {
        border: none;
        width: 22px;
    }
    QPushButton {
        background: #184e5e;
        color: #fffaf3;
        border: none;
        border-radius: 12px;
        padding: 10px 14px;
        font-weight: 700;
    }
    QPushButton:hover {
        background: #21657a;
    }
    QPushButton:pressed {
        background: #103640;
    }
    QPushButton:disabled {
        background: #c0cac7;
        color: #6d7775;
    }
    QCheckBox {
        spacing: 8px;
    }
    QGroupBox {
        background: #fff8ee;
        border: 1px solid #dccab0;
        border-radius: 18px;
        margin-top: 16px;
        padding-top: 12px;
        font-weight: 700;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        top: 4px;
        padding: 0 6px;
        color: #6e5534;
    }
    QLabel#HeroEyebrow {
        color: #8a6a3a;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    QLabel#HeroTitle {
        color: #122224;
        font-size: 26px;
        font-weight: 800;
    }
    QLabel#HeroBody {
        color: #5d6460;
        font-size: 13px;
    }
    QFrame#StatCard {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #fff6e8, stop:1 #f4e2c7);
        border: 1px solid #d7bd8e;
        border-radius: 18px;
    }
    QLabel#StatTitle {
        color: #7c6340;
        font-size: 11px;
        font-weight: 700;
    }
    QLabel#StatValue {
        color: #122224;
        font-size: 28px;
        font-weight: 800;
    }
    QLabel#StatMeta {
        color: #5f6661;
        font-size: 12px;
    }
    QTabBar::tab {
        background: #ead9bf;
        color: #55422b;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        padding: 10px 14px;
        margin-right: 4px;
        font-weight: 700;
    }
    QTabBar::tab:selected {
        background: #fff8ee;
        color: #183138;
    }
    QStatusBar {
        background: #e9decb;
        color: #4f5a57;
    }
    QSplitter::handle {
        background: #dccab0;
    }
    """


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "-", meta: str = "") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.meta_label = QLabel(meta)
        self.meta_label.setObjectName("StatMeta")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.meta_label)

    def set_content(self, value: str, meta: str = "") -> None:
        self.value_label.setText(value)
        self.meta_label.setText(meta)


class DesktopActivityModel(QObject):
    messages_changed = Signal()
    jobs_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._messages: list[str] = []
        self._running_jobs: dict[str, str] = {}

    def add_message(self, message: str) -> None:
        self._messages.append(f"[{timestamp_label(datetime.now().astimezone())}] {message}")
        self.messages_changed.emit()

    def start_job(self, label: str) -> str:
        job_id = f"job-{int(datetime.now().timestamp() * 1000)}-{len(self._running_jobs) + 1}"
        self._running_jobs[job_id] = f"{timestamp_label(datetime.now().astimezone())} {label}"
        self.jobs_changed.emit()
        self.add_message(f"Started: {label}")
        return job_id

    def finish_job(self, job_id: str, message: str) -> None:
        self._running_jobs.pop(job_id, None)
        self.jobs_changed.emit()
        self.add_message(message)

    def clear_messages(self) -> None:
        self._messages.clear()
        self.messages_changed.emit()

    def messages(self) -> list[str]:
        return list(self._messages)

    def running_jobs(self) -> list[str]:
        return list(self._running_jobs.values())


class AsyncTaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

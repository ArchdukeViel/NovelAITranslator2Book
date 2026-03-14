from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

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


def resolve_theme_preference(theme: str, app: QApplication | None = None) -> str:
    if theme in {"dark", "light"}:
        return theme
    effective_app = app or QApplication.instance()
    if not isinstance(effective_app, QApplication):
        return "dark"
    palette = effective_app.palette()
    window_color = palette.color(QPalette.ColorRole.Window)
    window_text_color = palette.color(QPalette.ColorRole.WindowText)
    # Dark UIs commonly have light text over dark window backgrounds.
    return "dark" if window_text_color.lightnessF() > window_color.lightnessF() else "light"


def build_stylesheet(asset_dir: Path | None = None, theme: str = "dark") -> str:
    _ = asset_dir
    root_background = """
    QSplitter#DesktopRoot {
        background: qradialgradient(cx:0.18, cy:0.08, radius:1.1,
            fx:0.18, fy:0.08,
            stop:0 #31206f,
            stop:0.35 #1b1244,
            stop:0.75 #0c0824,
            stop:1 #050312);
    }
    """

    base = """  /* --- NovelAI2Book desktop stylesheet --- */
    QMainWindow {
        background: #0b0720;
    }
    QWidget {
        background: transparent;
        color: #efeaff;
        font-family: "Segoe UI", "Trebuchet MS", "Verdana";
        font-size: 13px;
        font-weight: 500;
    }
    QMainWindow::separator {
        background: #2e215d;
        width: 1px;
        height: 1px;
    }
    """ + root_background + """
    QWidget#NavPanel {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #090613,
            stop:1 #140a2f);
        border-right: 1px solid #3c2b74;
        border-top-right-radius: 14px;
        border-bottom-right-radius: 14px;
    }
    QPushButton#NavBrandButton {
        color: #f0e9ff;
        background: transparent;
        border: 1px solid #4d3a86;
        border-radius: 22px;
        min-height: 44px;
        max-height: 44px;
        min-width: 44px;
        max-width: 44px;
        font-size: 15px;
        font-weight: 700;
        padding: 0;
    }
    QPushButton#NavBrandButton:hover {
        background: #2a1b59;
    }
    QLabel#NavAvatar {
        color: #f2ecff;
        background: #4c2bb2;
        border: 1px solid #8f6dff;
        border-radius: 22px;
        min-height: 44px;
        max-height: 44px;
        min-width: 44px;
        max-width: 44px;
        font-size: 11px;
        font-weight: 700;
    }
    QListWidget#NavList {
        background: transparent;
        color: #e9e0ff;
        border: none;
        border-radius: 0;
        padding: 0;
        outline: none;
    }
    QListWidget#NavList::item {
        border-radius: 12px;
        min-height: 40px;
        padding: 8px 4px;
        margin: 3px 2px;
        color: #e9e0ff;
    }
    QListWidget#NavList::item:selected {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #5f36d8,
            stop:1 #8b5cf6);
        color: #f8f4ff;
        font-weight: 700;
    }
    QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QTabWidget::pane, QTableWidget {
        background: #130e2e;
        border: 1px solid #3e2f75;
        border-radius: 14px;
        selection-background-color: #7e57ff;
        selection-color: #ffffff;
    }
    QStackedWidget {
        background: rgba(7, 4, 24, 0.28);
        border: none;
    }
    QListWidget {
        padding: 6px 6px;
        outline: none;
    }
    QListWidget::item {
        border-radius: 10px;
        padding: 8px 10px;
        margin: 2px 0;
    }
    QListWidget::item:selected {
        background: #5f36d8;
        color: #ffffff;
    }
    QTableWidget {
        gridline-color: #2f245f;
        alternate-background-color: #120d2a;
        padding: 4px;
    }
    QListWidget#GlossaryTermList {
        background: #1e1548;
    }
    QTableWidget#GlossaryTermsTable {
        background: #1e1548;
        alternate-background-color: #18113e;
    }
    QTableWidget#GlossaryTermsTable QHeaderView::section {
        background: #2b1f62;
    }
    QHeaderView::section {
        background: #1d1441;
        color: #f3ecff;
        border: none;
        border-bottom: 1px solid #4d3c89;
        padding: 6px 8px;
        font-weight: 700;
    }
    QTableCornerButton::section {
        background: #1d1441;
        border: none;
        border-bottom: 1px solid #4d3c89;
    }
    QPlainTextEdit, QLineEdit, QComboBox {
        padding: 8px 10px;
        color: #ece7ff;
    }
    QLabel {
        background: transparent;
    }
    QComboBox::drop-down {
        border: none;
        width: 22px;
    }
    QPushButton {
        background: #512ab2;
        color: #f7f1ff;
        border: none;
        border-radius: 12px;
        padding: 9px 14px;
        font-weight: 700;
    }
    QPushButton:hover {
        background: #6736dc;
    }
    QPushButton:pressed {
        background: #3f218d;
    }
    QPushButton:disabled {
        background: #2a2250;
        color: #877db1;
    }
    QCheckBox {
        spacing: 8px;
    }
    QGroupBox {
        background: #110c28;
        border: 1px solid #3c2c71;
        border-radius: 18px;
        margin-top: 16px;
        padding: 12px;
        font-weight: 700;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 14px;
        top: 2px;
        padding: 0 8px;
        color: #b69bff;
        background: transparent;
    }
    QLabel#HeroEyebrow {
        color: #bba0ff;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    QLabel#HeroTitle {
        color: #f3ecff;
        font-size: 26px;
        font-weight: 800;
    }
    QLabel#HeroBody {
        color: #b8abde;
        font-size: 13px;
    }
    QFrame#StatCard {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #1f1545, stop:1 #2c1d63);
        border: 1px solid #5a3cb0;
        border-radius: 18px;
    }
    QLabel#StatTitle {
        color: #c2b3ea;
        font-size: 11px;
        font-weight: 700;
    }
    QLabel#StatValue {
        color: #f6f1ff;
        font-size: 28px;
        font-weight: 800;
    }
    QLabel#StatMeta {
        color: #afa5d4;
        font-size: 12px;
    }
    QTabBar::tab {
        background: #1f1546;
        color: #c7b8f0;
        border-top-left-radius: 12px;
        border-top-right-radius: 12px;
        padding: 9px 14px;
        margin-right: 4px;
        font-weight: 700;
        border: 1px solid #3f2f76;
        border-bottom: none;
    }
    QTabBar::tab:selected {
        background: #3f2a8d;
        color: #ffffff;
    }
    QStatusBar {
        background: #100a24;
        color: #ab9dd8;
    }
    QSplitter::handle {
        background: #30245a;
    }
    """

    if theme != "light":
        return base

    light_override = """
    QMainWindow {
        background: #f2f6ff;
    }
    QWidget {
        color: #1f2d4f;
    }
    QSplitter#DesktopRoot {
        background: qradialgradient(cx:0.18, cy:0.08, radius:1.1,
            fx:0.18, fy:0.08,
            stop:0 #cfe0ff,
            stop:0.35 #e8f1ff,
            stop:0.75 #f5f9ff,
            stop:1 #ffffff);
    }
    QWidget#NavPanel {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #e6efff,
            stop:1 #f7fbff);
        border-right: 1px solid #bbcff4;
    }
    QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QTabWidget::pane, QTableWidget {
        background: #ffffff;
        border: 1px solid #b8caec;
        selection-background-color: #3a67c8;
        selection-color: #ffffff;
    }
    QListWidget#NavList::item {
        color: #304169;
    }
    QListWidget#NavList::item:selected {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #2e5fc9,
            stop:1 #5f8cf0);
        color: #ffffff;
    }
    QPushButton {
        background: #2f63ca;
        color: #f7fbff;
    }
    QPushButton:hover {
        background: #4274d6;
    }
    QPushButton:pressed {
        background: #2550aa;
    }
    QPushButton:disabled {
        background: #cfd9ee;
        color: #7486ab;
    }
    QGroupBox {
        background: #f8fbff;
        border: 1px solid #bfd1f0;
    }
    QGroupBox::title {
        color: #36507f;
    }
    QLabel#HeroEyebrow {
        color: #4f6da5;
    }
    QLabel#HeroTitle {
        color: #1f315b;
    }
    QLabel#HeroBody {
        color: #5a6f9f;
    }
    QHeaderView::section {
        background: #e8f1ff;
        color: #28427a;
        border-bottom: 1px solid #bfd1f0;
    }
    QStatusBar {
        background: #eaf2ff;
        color: #456298;
    }
    QSplitter::handle {
        background: #c2d4f3;
    }
    """
    return base + light_override


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "-", meta: str = "") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_label = QLabel(meta)
        self.meta_label.setObjectName("StatMeta")
        self.meta_label.setWordWrap(True)
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self._phase_events: list[dict[str, str]] = []

    def add_message(self, message: str) -> None:
        self._messages.append(f"[{timestamp_label(datetime.now().astimezone())}] {message}")
        self.messages_changed.emit()

    def add_phase_event(self, novel_id: str, payload: dict[str, Any]) -> None:
        phase = safe_str(payload.get("phase"), "unknown_phase")
        status = safe_str(payload.get("status"), "completed")
        message = safe_str(payload.get("message"), "")
        timestamp = timestamp_label(datetime.now().astimezone())
        event = {
            "timestamp": timestamp,
            "novel_id": novel_id,
            "phase": phase,
            "status": status,
            "message": message,
        }
        self._phase_events.append(event)
        self.add_message(f"Phase {phase} [{status}] {novel_id}: {message}")

    def phase_events(self, novel_id: str | None = None) -> list[dict[str, str]]:
        if novel_id is None:
            return [dict(event) for event in self._phase_events]
        return [dict(event) for event in self._phase_events if event.get("novel_id") == novel_id]

    def phase_counters(self, novel_id: str | None = None) -> dict[str, dict[str, int]]:
        counters: dict[str, dict[str, int]] = {}
        for event in self.phase_events(novel_id):
            phase = safe_str(event.get("phase"), "unknown_phase")
            status = safe_str(event.get("status"), "completed")
            bucket = counters.setdefault(phase, {})
            bucket[status] = bucket.get(status, 0) + 1
        return counters

    def start_job(self, label: str) -> str:
        job_id = f"job-{int(datetime.now().timestamp() * 1000)}-{len(self._running_jobs) + 1}"
        self._running_jobs[job_id] = f"{timestamp_label(datetime.now().astimezone())} {label}"
        self.jobs_changed.emit()
        self.add_message(f"Started: {label}")
        return job_id

    def update_job(self, job_id: str, detail: str) -> None:
        if job_id not in self._running_jobs:
            return
        self._running_jobs[job_id] = f"{timestamp_label(datetime.now().astimezone())} {detail}"
        self.jobs_changed.emit()

    def finish_job(self, job_id: str, message: str) -> None:
        self._running_jobs.pop(job_id, None)
        self.jobs_changed.emit()
        self.add_message(message)

    def fail_job(self, job_id: str, message: str) -> None:
        self._running_jobs.pop(job_id, None)
        self.jobs_changed.emit()
        self.add_message(message)

    def clear_messages(self) -> None:
        self._messages.clear()
        self._phase_events.clear()
        self.messages_changed.emit()

    def messages(self) -> list[str]:
        return list(self._messages)

    def running_jobs(self) -> list[str]:
        return list(self._running_jobs.values())

class AsyncTaskThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.succeeded.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

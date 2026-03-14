from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container
from novelai.config.settings import settings
from novelai.config.workflow_profiles import WORKFLOW_PROFILE_STEPS
from novelai.core.chapter_state import ChapterState
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions
from novelai.cost_estimator.pricing import list_supported_models
from novelai.glossary import glossary_status_counts
from novelai.inputs.registry import available_input_adapters, detect_input_adapter
from novelai.providers.registry import available_models, available_providers
from novelai.sources.registry import available_sources, detect_source
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection


def _timestamp_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
    return "-"


def _safe_str(value: Any, fallback: str = "-") -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    if value is None:
        return fallback
    return str(value)


def _snapshot_media_counts(novel_id: str) -> dict[str, int]:
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


def _library_snapshots() -> list[dict[str, Any]]:
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
            1 for chapter_id in chapter_ids
            if storage.load_translated_chapter(novel_id, chapter_id) is not None
        )
        glossary_counts = glossary_status_counts(storage.load_glossary(novel_id))
        media_counts = _snapshot_media_counts(novel_id)
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


def _recent_export_paths(limit: int = 8) -> list[Path]:
    storage = container.storage
    root = getattr(storage, "novels_dir", settings.DATA_DIR / "novels")
    if not isinstance(root, Path) or not root.exists():
        return []
    paths = [path for path in root.rglob("full_novel.*") if path.is_file()]
    paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[:limit]


def _usage_snapshot_text() -> str:
    summary = container.usage.summary(all_days=True)
    lines = [
        f"Requests: {summary.get('total_requests', 0)}",
        f"Tokens: {summary.get('total_tokens', 0)}",
        f"Estimated Cost: ${summary.get('estimated_cost_usd', 0.0):.4f}",
        f"Projection Estimates: {summary.get('total_estimates', 0)}",
        f"Projected Tokens: {summary.get('estimated_total_tokens', 0)}",
    ]
    for entry in container.usage.daily_history(limit=5):
        lines.append(
            f"{entry.get('date')}: {entry.get('total_requests', 0)} req, "
            f"{entry.get('total_tokens', 0)} tok"
        )
    return "\n".join(lines)


def _profiles_snapshot_text() -> str:
    profiles = container.preferences.get_workflow_profiles()
    lines: list[str] = []
    for step in WORKFLOW_PROFILE_STEPS:
        profile = profiles.get(step, {})
        provider = profile.get("provider") if isinstance(profile, dict) else None
        model = profile.get("model") if isinstance(profile, dict) else None
        lines.append(
            f"{step.replace('_', ' ').title()}: "
            f"{_safe_str(provider, 'inherit')} / {_safe_str(model, 'inherit')}"
        )
    return "\n".join(lines)


def _build_stylesheet() -> str:
    return """
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


def _selected_numbers(chapter_selection: str) -> set[int] | None:
    if is_full_chapter_selection(chapter_selection):
        return None
    return {spec.chapter for spec in parse_chapter_selection(chapter_selection)}


def _collect_export_chapters(
    novel_id: str,
    chapter_selection: str = "full",
    language: str = "translated",
) -> list[dict[str, Any]]:
    storage = container.storage
    meta = storage.load_metadata(novel_id)
    if not meta:
        raise ValueError("Metadata not found; run scrape/import first.")

    selected_numbers = _selected_numbers(chapter_selection)
    use_source = language == "source"
    chapters: list[dict[str, Any]] = []
    for chapter in meta.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id"))
        if selected_numbers is not None:
            if not chapter_id.isdigit() or int(chapter_id) not in selected_numbers:
                continue

        if use_source:
            raw_data = storage.load_chapter(novel_id, chapter_id)
            text = raw_data.get("text") if isinstance(raw_data, dict) else None
        else:
            translated = storage.load_translated_chapter(novel_id, chapter_id)
            text = translated.get("text") if isinstance(translated, dict) else None

        if not isinstance(text, str) or not text.strip():
            continue

        chapters.append(
            {
                "title": chapter.get("translated_title") if language != "source" else chapter.get("title"),
                "text": text,
                "images": storage.load_chapter_export_images(novel_id, chapter_id),
            }
        )

    if not chapters:
        raise ValueError(f"No {language} chapters available for export.")
    return chapters


def _build_export_output_path(
    novel_id: str,
    export_format: str,
    output_dir: str | None,
    chapter_selection: str,
    language: str,
) -> str:
    base_path = Path(container.storage.build_export_path(novel_id, export_format, output_dir or None))
    name = base_path.stem
    if language == "source":
        name = f"{name}_source"
    if not is_full_chapter_selection(chapter_selection):
        suffix = chapter_selection.replace(" ", "").replace(",", "_").replace("-", "to")
        name = f"{name}_ch{suffix}"
    return str(base_path.with_name(f"{name}.{export_format}"))


def _estimate_translation_budget(novel_id: str, chapter_selection: str, provider_key: str | None, model: str | None) -> str:
    storage = container.storage
    meta = storage.load_metadata(novel_id)
    if not meta:
        raise ValueError("Metadata not found; import or scrape a project first.")

    selected_numbers = _selected_numbers(chapter_selection)
    chapter_count = 0
    japanese_characters = 0
    for chapter in meta.get("chapters", []):
        if not isinstance(chapter, dict):
            continue
        chapter_id = str(chapter.get("id"))
        if selected_numbers is not None:
            if not chapter_id.isdigit() or int(chapter_id) not in selected_numbers:
                continue
        raw_data = storage.load_chapter(novel_id, chapter_id) or {}
        media_state = storage.load_chapter_media_state(novel_id, chapter_id) or {}
        text = None
        reviewed_ocr = media_state.get("ocr_text")
        if (
            bool(media_state.get("ocr_required"))
            and str(media_state.get("ocr_status") or "").strip().lower() == "reviewed"
            and isinstance(reviewed_ocr, str)
            and reviewed_ocr.strip()
        ):
            text = reviewed_ocr
        elif isinstance(raw_data.get("text"), str):
            text = raw_data.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        chapter_count += 1
        japanese_characters += len("".join(text.split()))

    if japanese_characters <= 0:
        raise ValueError("Budget estimate unavailable because no source text was available.")

    if provider_key == "openai" and isinstance(model, str) and model in list_supported_models():
        estimate_models = [model]
        note = ""
    else:
        estimate_models = list(list_supported_models())
        note = "Reference estimate shown for supported priced models."

    comparison = compare_models(
        estimate_models,
        EstimationOptions(japanese_characters=japanese_characters),
    )

    lines = [
        f"Estimated source size: {japanese_characters} non-whitespace characters across {chapter_count} chapter(s).",
    ]
    if len(comparison.estimates) == 1:
        estimate = comparison.estimates[0]
        lines.append(
            f"Estimated tokens ({estimate.model_name}): {estimate.estimated_input_tokens} input / "
            f"{estimate.estimated_output_tokens} output."
        )
        lines.append(f"Estimated cost ({estimate.model_name}): ${estimate.estimated_total_cost_usd:.4f}.")
    else:
        lines.append("Estimated translation budget:")
        for estimate in comparison.estimates:
            lines.append(
                f"- {estimate.model_name}: {estimate.estimated_input_tokens} in / "
                f"{estimate.estimated_output_tokens} out / ${estimate.estimated_total_cost_usd:.4f}"
            )
        lines.append(
            f"Cheapest estimate: {comparison.cheapest_model} "
            f"(${comparison.cost_difference_usd:.4f} spread, {comparison.percentage_difference:.2f}%)."
        )
    if note:
        lines.append(note)
    return "\n".join(lines)


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "-", meta: str = "") -> None:
        super().__init__()
        self.setObjectName("StatCard")
        layout = QVBoxLayout(self)
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
        layout.addStretch()

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
        self._messages.append(f"[{_timestamp_label(datetime.now().astimezone())}] {message}")
        self.messages_changed.emit()

    def start_job(self, label: str) -> str:
        job_id = f"job-{int(datetime.now().timestamp() * 1000)}-{len(self._running_jobs) + 1}"
        self._running_jobs[job_id] = f"{_timestamp_label(datetime.now().astimezone())} {label}"
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


class HomeView(QWidget):
    navigate_requested = Signal(str)
    open_workspace_requested = Signal(str)

    def __init__(self, activity_model: DesktopActivityModel) -> None:
        super().__init__()
        self.activity_model = activity_model
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        hero_group = QGroupBox("Control Deck")
        hero_layout = QVBoxLayout(hero_group)
        eyebrow = QLabel("DESKTOP STUDIO")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Run imports, review terminology, and ship clean exports from one place.")
        title.setWordWrap(True)
        title.setObjectName("HeroTitle")
        body = QLabel(
            "The home screen is meant to answer four questions quickly: what exists, what needs attention, "
            "what is running, and what should happen next."
        )
        body.setWordWrap(True)
        body.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)

        stats_layout = QHBoxLayout()
        self.projects_card = StatCard("Projects")
        self.translation_card = StatCard("Translated Units")
        self.attention_card = StatCard("Needs Attention")
        self.activity_card = StatCard("Running Jobs")
        stats_layout.addWidget(self.projects_card)
        stats_layout.addWidget(self.translation_card)
        stats_layout.addWidget(self.attention_card)
        stats_layout.addWidget(self.activity_card)
        hero_layout.addLayout(stats_layout)

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
            button.clicked.connect(handler)
            quick_layout.addWidget(button, index // 2, index % 2)

        recent_group = QGroupBox("Recent Projects")
        recent_layout = QVBoxLayout(recent_group)
        self.recent_list = QListWidget()
        self.recent_list.itemDoubleClicked.connect(self._open_item_novel)
        recent_layout.addWidget(self.recent_list)

        attention_group = QGroupBox("Needs Attention")
        attention_layout = QVBoxLayout(attention_group)
        self.attention_list = QListWidget()
        self.attention_list.itemDoubleClicked.connect(self._open_item_novel)
        attention_layout.addWidget(self.attention_list)

        jobs_group = QGroupBox("Active Jobs")
        jobs_layout = QVBoxLayout(jobs_group)
        self.jobs_list = QListWidget()
        jobs_layout.addWidget(self.jobs_list)

        usage_group = QGroupBox("Usage Snapshot")
        usage_layout = QVBoxLayout(usage_group)
        self.usage_output = QPlainTextEdit()
        self.usage_output.setReadOnly(True)
        usage_layout.addWidget(self.usage_output)

        profiles_group = QGroupBox("Profile Summary")
        profiles_layout = QVBoxLayout(profiles_group)
        self.profiles_output = QPlainTextEdit()
        self.profiles_output.setReadOnly(True)
        profiles_layout.addWidget(self.profiles_output)

        exports_group = QGroupBox("Recent Outputs")
        exports_layout = QVBoxLayout(exports_group)
        self.exports_list = QListWidget()
        exports_layout.addWidget(self.exports_list)

        layout.addWidget(hero_group, 0, 0, 1, 2)
        layout.addWidget(quick_group, 1, 0, 1, 2)
        layout.addWidget(recent_group, 2, 0)
        layout.addWidget(attention_group, 2, 1)
        layout.addWidget(jobs_group, 3, 0)
        layout.addWidget(usage_group, 3, 1)
        layout.addWidget(profiles_group, 4, 0)
        layout.addWidget(exports_group, 4, 1)
        layout.setRowStretch(2, 1)
        layout.setRowStretch(3, 1)
        layout.setRowStretch(4, 1)

        self.activity_model.jobs_changed.connect(self.refresh)
        self.activity_model.messages_changed.connect(self.refresh)
        self.refresh()

    def _first_snapshot(self, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any] | None:
        for snapshot in _library_snapshots():
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
        self.exports_list.clear()

        snapshots = _library_snapshots()
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
            item = QListWidgetItem(
                f"{snapshot['title']} ({snapshot['novel_id']}) | "
                f"{snapshot['translated_units']}/{snapshot['total_units']} translated | "
                f"{_safe_str(snapshot.get('input_adapter_key'), 'unknown adapter')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.recent_list.addItem(item)

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
            item = QListWidgetItem(f"{snapshot['title']} ({snapshot['novel_id']}): {', '.join(reasons)}")
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.attention_list.addItem(item)

        if self.attention_list.count() == 0:
            self.attention_list.addItem("No projects currently need manual attention.")

        for job in self.activity_model.running_jobs():
            self.jobs_list.addItem(job)
        if self.jobs_list.count() == 0:
            self.jobs_list.addItem("No active jobs.")

        self.usage_output.setPlainText(_usage_snapshot_text())
        self.profiles_output.setPlainText(_profiles_snapshot_text())

        for path in _recent_export_paths():
            self.exports_list.addItem(str(path))
        if self.exports_list.count() == 0:
            self.exports_list.addItem("No exports found yet.")


class LibraryView(QWidget):
    open_requested = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.storage = container.storage
        layout = QVBoxLayout(self)
        eyebrow = QLabel("LIBRARY")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Inspect every stored project, see what is blocked, and jump into the right workspace.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)

        stats_layout = QHBoxLayout()
        self.projects_card = StatCard("Projects")
        self.translated_card = StatCard("Translated")
        self.attention_card = StatCard("Attention")
        stats_layout.addWidget(self.projects_card)
        stats_layout.addWidget(self.translated_card)
        stats_layout.addWidget(self.attention_card)
        layout.addLayout(stats_layout)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.open_button = QPushButton("Open Workspace")
        self.open_button.clicked.connect(self._open_current)
        self.import_button = QPushButton("Import Document")
        self.import_button.clicked.connect(lambda: self.navigate_requested.emit("import"))
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.import_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter()
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._open_current)
        self.list_widget.currentItemChanged.connect(self._load_current)
        self.details_output = QPlainTextEdit()
        self.details_output.setReadOnly(True)
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.details_output)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        self.refresh()

    def refresh(self) -> None:
        current_novel_id = None
        current_item = self.list_widget.currentItem()
        if current_item is not None:
            current_novel_id = current_item.data(Qt.ItemDataRole.UserRole)
        snapshots = _library_snapshots()
        translated_total = sum(int(item.get("translated_units", 0)) for item in snapshots)
        attention_total = sum(
            int(item.get("ocr_pending", 0)) + int(item.get("glossary_pending", 0)) + int(item.get("errors", 0))
            for item in snapshots
        )
        self.projects_card.set_content(str(len(snapshots)), "Projects indexed in the current library")
        self.translated_card.set_content(str(translated_total), "Units with translated output on disk")
        self.attention_card.set_content(str(attention_total), "Pending manual review or failed states")
        self.list_widget.clear()
        for snapshot in snapshots:
            item = QListWidgetItem(f"{snapshot['title']} ({snapshot['novel_id']})")
            item.setData(Qt.ItemDataRole.UserRole, snapshot["novel_id"])
            self.list_widget.addItem(item)
            if current_novel_id == snapshot["novel_id"]:
                self.list_widget.setCurrentItem(item)
        if self.list_widget.count() == 0:
            self.details_output.setPlainText("No projects in the library yet.")
        elif self.list_widget.currentItem() is None:
            self.list_widget.setCurrentRow(0)

    def _load_current(
        self,
        current: QListWidgetItem | None = None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        item = current or self.list_widget.currentItem()
        if item is None:
            self.details_output.clear()
            return
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(novel_id, str):
            self.details_output.clear()
            return
        snapshot = next((entry for entry in _library_snapshots() if entry["novel_id"] == novel_id), None)
        if snapshot is None:
            self.details_output.setPlainText(f"No metadata found for {novel_id}.")
            return
        meta = self.storage.load_metadata(novel_id) or {}
        lines = [
            f"Title: {snapshot['title']}",
            f"Novel ID: {novel_id}",
            f"Author: {_safe_str(snapshot.get('author'))}",
            f"Document Type: {_safe_str(snapshot.get('document_type'))}",
            f"Origin Type: {_safe_str(snapshot.get('origin_type'))}",
            f"Origin: {_safe_str(snapshot.get('origin_uri_or_path'))}",
            f"Input Adapter: {_safe_str(snapshot.get('input_adapter_key'))}",
            f"Source Language: {_safe_str(snapshot.get('source_language'))}",
            f"Updated: {_timestamp_label(snapshot.get('updated_at'))}",
            "",
            f"Units: {snapshot['total_units']}",
            f"Translated: {snapshot['translated_units']}",
            f"OCR Pending: {snapshot['ocr_pending']}",
            f"Glossary Pending: {snapshot['glossary_pending']}",
            f"Failed Chapters: {snapshot['errors']}",
        ]
        translated_title = meta.get("translated_title")
        if isinstance(translated_title, str) and translated_title.strip():
            lines.extend(["", f"Translated Title: {translated_title}"])
        self.details_output.setPlainText("\n".join(lines))

    def _open_current(self, *_args: object) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        novel_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(novel_id, str):
            self.open_requested.emit(novel_id)


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


class ProfilesView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.preferences = container.preferences
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        eyebrow = QLabel("PROFILES")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Assign provider and model preferences to each workflow stage.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        description = QLabel(
            "These settings let OCR, term extraction, glossary work, and body translation use different models when needed."
        )
        description.setObjectName("HeroBody")
        description.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)

        grid = QGridLayout()
        grid.addWidget(QLabel("Step"), 0, 0)
        grid.addWidget(QLabel("Provider"), 0, 1)
        grid.addWidget(QLabel("Model"), 0, 2)
        self.inputs: dict[str, tuple[QComboBox, QComboBox]] = {}
        for row, step in enumerate(WORKFLOW_PROFILE_STEPS, start=1):
            profile = self.preferences.get_workflow_profile(step)
            provider_input = QComboBox()
            provider_input.addItem("Inherit", None)
            for provider in sorted(available_providers()):
                provider_input.addItem(provider, provider)
            provider_input.setCurrentIndex(max(provider_input.findData(profile["provider"]), 0))
            model_input = QComboBox()
            model_input.setEditable(True)
            self._populate_models(model_input, profile["provider"], profile["model"])
            provider_input.currentIndexChanged.connect(
                lambda _index, current_step=step: self._refresh_models(current_step)
            )
            grid.addWidget(QLabel(step.replace("_", " ").title()), row, 0)
            grid.addWidget(provider_input, row, 1)
            grid.addWidget(model_input, row, 2)
            self.inputs[step] = (provider_input, model_input)
        layout.addLayout(grid)
        save_button = QPushButton("Save Profiles")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()

    def _populate_models(self, combo: QComboBox, provider: str | None, model: str | None) -> None:
        combo.clear()
        combo.addItem("")
        if isinstance(provider, str) and provider.strip():
            with contextlib.suppress(Exception):
                for current_model in available_models(provider):
                    combo.addItem(current_model)
        if isinstance(model, str) and model.strip() and combo.findText(model) < 0:
            combo.addItem(model)
        combo.setCurrentText(model or "")

    def _refresh_models(self, step: str) -> None:
        provider_input, model_input = self.inputs[step]
        provider = provider_input.currentData()
        if not isinstance(provider, str):
            provider = None
        self._populate_models(model_input, provider, model_input.currentText().strip() or None)

    def save(self) -> None:
        for step, (provider_input, model_input) in self.inputs.items():
            provider = provider_input.currentData()
            if not isinstance(provider, str):
                provider = None
            self.preferences.set_workflow_profile(
                step,
                provider=provider,
                model=model_input.currentText().strip() or None,
            )
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Profiles Saved", "Workflow profiles were updated.")


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
        snapshots = _library_snapshots()
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


class SettingsView(QWidget):
    def __init__(self, refresh_callback: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.preferences = container.preferences
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        eyebrow = QLabel("SETTINGS")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Control runtime defaults, provider access, and desktop preferences.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        body = QLabel(
            "Secrets remain environment-backed. The desktop page updates the runtime key without persisting it to disk."
        )
        body.setObjectName("HeroBody")
        body.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)
        form = QFormLayout()

        self.provider_input = QComboBox()
        for provider in sorted(available_providers()):
            self.provider_input.addItem(provider)

        self.model_input = QComboBox()
        self.model_input.setEditable(True)

        self.source_input = QComboBox()
        self.source_input.addItem("Auto", None)
        for source in sorted(available_sources()):
            self.source_input.addItem(source, source)

        self.theme_input = QComboBox()
        self.theme_input.addItems(["auto", "light", "dark"])
        self.language_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.target_language_label = QLabel(settings.TRANSLATION_TARGET_LANGUAGE)
        self.library_path_label = QLabel(str(settings.NOVEL_LIBRARY_DIR))

        form.addRow("Default Provider", self.provider_input)
        form.addRow("Default Model", self.model_input)
        form.addRow("Preferred Source", self.source_input)
        form.addRow("Theme", self.theme_input)
        form.addRow("UI Language", self.language_input)
        form.addRow("Runtime API Key", self.api_key_input)
        form.addRow("Library Path", self.library_path_label)
        form.addRow("Target Language", self.target_language_label)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save Settings")
        self.reload_button = QPushButton("Reload")
        self.save_button.clicked.connect(self.save)
        self.reload_button.clicked.connect(self.reload)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reload_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()

        self.provider_input.currentIndexChanged.connect(self._refresh_model_choices)
        self.reload()

    def _refresh_model_choices(self) -> None:
        provider = self.provider_input.currentText().strip()
        current_model = self.model_input.currentText().strip()
        self.model_input.clear()
        models: list[str] = []
        if provider:
            with contextlib.suppress(Exception):
                models = available_models(provider)
        for model in models:
            self.model_input.addItem(model)
        if current_model and self.model_input.findText(current_model) < 0:
            self.model_input.addItem(current_model)
        self.model_input.setCurrentText(current_model)

    def reload(self) -> None:
        provider = self.preferences.get_preferred_provider()
        provider_index = self.provider_input.findText(provider)
        self.provider_input.setCurrentIndex(provider_index if provider_index >= 0 else 0)
        self._refresh_model_choices()
        self.model_input.setCurrentText(self.preferences.get_preferred_model())
        source = self.preferences.get_preferred_source()
        self.source_input.setCurrentIndex(max(self.source_input.findData(source), 0))
        self.theme_input.setCurrentText(self.preferences.get_theme())
        self.language_input.setText(self.preferences.get_language())
        self.api_key_input.setText(self.preferences.get_api_key() or "")

    def save(self) -> None:
        self.preferences.set_preferred_provider(self.provider_input.currentText().strip())
        self.preferences.set_preferred_model(self.model_input.currentText().strip())
        source = self.source_input.currentData()
        self.preferences.set("preferred_source", source if isinstance(source, str) else None)
        self.preferences.set_theme(self.theme_input.currentText().strip())
        self.preferences.set_language(self.language_input.text().strip() or "en")
        api_key = self.api_key_input.text().strip()
        if api_key:
            self.preferences.set_api_key(api_key)
        else:
            self.preferences.clear_api_key()
        if self.refresh_callback is not None:
            self.refresh_callback()
        QMessageBox.information(self, "Settings Saved", "Desktop settings were updated.")


class ImportTab(QWidget):
    activity = Signal(str)
    completed = Signal()

    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.fixed_novel_id = novel_id or None
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = container.orchestrator
        self._active_job_id: str | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.novel_input = QLineEdit(self.fixed_novel_id or "")
        self.novel_input.setReadOnly(self.fixed_novel_id is not None)
        self.adapter_input = QComboBox()
        self.adapter_input.addItems(available_input_adapters())
        self.source_input = QLineEdit()
        self.max_units_input = QLineEdit()
        detect_button = QPushButton("Detect Adapter")
        detect_button.clicked.connect(self.detect_adapter)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_input)
        source_row.addWidget(detect_button)
        form.addRow("Novel ID", self.novel_input)
        form.addRow("Adapter", self.adapter_input)
        form.addRow("Source Path/URL", source_row)
        form.addRow("Max Units", self.max_units_input)
        layout.addLayout(form)
        self.import_button = QPushButton("Import")
        self.import_button.clicked.connect(self.start_import)
        layout.addWidget(self.import_button)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def detect_adapter(self) -> None:
        source = self.source_input.text().strip()
        if not source:
            return
        detected = detect_input_adapter(source)
        if detected is None:
            self.output.setPlainText("Could not auto-detect an input adapter for the current source.")
            return
        self.adapter_input.setCurrentText(detected)
        self.output.setPlainText(f"Detected input adapter: {detected}")

    def start_import(self) -> None:
        novel_id = (self.fixed_novel_id or self.novel_input.text()).strip()
        adapter_key = self.adapter_input.currentText()
        source = self.source_input.text().strip()
        max_units = self.max_units_input.text().strip()
        if not novel_id:
            QMessageBox.warning(self, "Missing Novel ID", "Provide a novel ID before importing.")
            return
        if not source:
            QMessageBox.warning(self, "Missing Source", "Provide a source path or URL.")
            return
        self.novel_id = novel_id
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(f"Import {novel_id} via {adapter_key}")
        self.import_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.import_document(
                    adapter_key,
                    novel_id,
                    source,
                    max_units=int(max_units) if max_units.isdigit() else None,
                )
            )

        worker = AsyncTaskThread(_run, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self.import_button.setEnabled(True))
        worker.start()
        self._worker = worker

    def _on_success(self, payload: object) -> None:
        self.output.setPlainText(str(payload))
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, f"Completed import for {self.novel_id}.")
        self._active_job_id = None
        self.activity.emit("Import completed.")
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.completed.emit()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, f"Import failed for {self.novel_id}: {message}")
        self._active_job_id = None
        self.activity.emit(f"Import failed: {message}")


class ImportPage(QWidget):
    open_workspace_requested = Signal(str)

    def __init__(
        self,
        activity_model: DesktopActivityModel,
        refresh_callback: Callable[[], None],
    ) -> None:
        super().__init__()
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        layout = QVBoxLayout(self)
        eyebrow = QLabel("ACQUIRE")
        eyebrow.setObjectName("HeroEyebrow")
        title = QLabel("Bring in books from files or scrape supported web novel sources.")
        title.setObjectName("HeroTitle")
        title.setWordWrap(True)
        description = QLabel(
            "Use document import for local files and archives. Use source scraping for Syosetu, Kakuyomu, "
            "Novel18, or generic supported web sources."
        )
        description.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)

        self.tabs = QTabWidget()
        self.import_panel = ImportTab(
            "",
            activity_model=self.activity_model,
            refresh_callback=self.refresh_callback,
        )
        self.import_panel.novel_id = ""
        self.source_panel = SourceScrapePanel(
            activity_model=self.activity_model,
            refresh_callback=self.refresh_callback,
        )
        self.tabs.addTab(self.import_panel, "Document Import")
        self.tabs.addTab(self.source_panel, "Source Scrape")
        layout.addWidget(self.tabs)

        self.import_panel.completed.connect(self._open_imported_workspace)
        self.source_panel.completed.connect(self._open_scraped_workspace)

    def _open_imported_workspace(self) -> None:
        novel_id = self.import_panel.novel_input.text().strip() if hasattr(self.import_panel, "novel_input") else ""
        if not novel_id:
            return
        self.open_workspace_requested.emit(novel_id)

    def _open_scraped_workspace(self) -> None:
        novel_id = self.source_panel._resolved_novel_id()
        if not novel_id:
            return
        self.open_workspace_requested.emit(novel_id)

    def refresh(self) -> None:
        return


class SourceScrapePanel(QWidget):
    activity = Signal(str)
    completed = Signal()

    def __init__(
        self,
        *,
        fixed_novel_id: str | None = None,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.fixed_novel_id = fixed_novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        self._active_job_id: str | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.novel_input = QLineEdit(fixed_novel_id or "")
        self.novel_input.setReadOnly(fixed_novel_id is not None)
        self.source_input = QComboBox()
        self.source_input.addItems(sorted(available_sources()))
        self.max_chapter_input = QLineEdit()
        self.max_chapter_input.setPlaceholderText("optional")
        self.metadata_mode_input = QComboBox()
        self.metadata_mode_input.addItems(["update", "full"])
        self.chapter_selection_input = QLineEdit("all")
        self.chapter_mode_input = QComboBox()
        self.chapter_mode_input.addItems(["update", "full"])
        form.addRow("Novel ID / Source Identifier", self.novel_input)
        form.addRow("Source Adapter", self.source_input)
        form.addRow("Metadata Mode", self.metadata_mode_input)
        form.addRow("Max Chapter", self.max_chapter_input)
        form.addRow("Chapter Selection", self.chapter_selection_input)
        form.addRow("Chapter Mode", self.chapter_mode_input)
        layout.addLayout(form)

        controls = QHBoxLayout()
        self.detect_button = QPushButton("Detect Source")
        self.metadata_button = QPushButton("Scrape Metadata")
        self.chapters_button = QPushButton("Scrape Chapters")
        self.sync_button = QPushButton("Sync Metadata + Chapters")
        controls.addWidget(self.detect_button)
        controls.addWidget(self.metadata_button)
        controls.addWidget(self.chapters_button)
        controls.addWidget(self.sync_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.detect_button.clicked.connect(self.detect_source_adapter)
        self.metadata_button.clicked.connect(self.start_metadata_scrape)
        self.chapters_button.clicked.connect(self.start_chapter_scrape)
        self.sync_button.clicked.connect(self.start_full_sync)

    def _resolved_novel_id(self) -> str:
        return (self.fixed_novel_id or self.novel_input.text()).strip()

    def detect_source_adapter(self) -> None:
        candidate = self._resolved_novel_id()
        detected = detect_source(candidate)
        if detected is None:
            self.output.setPlainText("Could not auto-detect a source adapter from the current identifier/URL.")
            return
        self.source_input.setCurrentText(detected)
        self.output.setPlainText(f"Detected source adapter: {detected}")

    def _set_busy(self, busy: bool) -> None:
        self.metadata_button.setEnabled(not busy)
        self.chapters_button.setEnabled(not busy)
        self.sync_button.setEnabled(not busy)

    def _start_task(self, label: str, fn: Callable[[], Any], success_message: str) -> None:
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(label)
        self._set_busy(True)
        self._worker = AsyncTaskThread(fn, self)
        self._worker.succeeded.connect(lambda payload: self._on_success(payload, success_message))
        self._worker.failed.connect(self._on_error)
        self._worker.finished.connect(lambda: self._set_busy(False))
        self._worker.start()

    def start_metadata_scrape(self) -> None:
        novel_id = self._resolved_novel_id()
        if not novel_id:
            QMessageBox.warning(self, "Missing Identifier", "Provide a novel ID or source identifier.")
            return
        source_key = self.source_input.currentText().strip()
        mode = self.metadata_mode_input.currentText().strip() or "update"
        max_chapter = self.max_chapter_input.text().strip()

        def _run() -> Any:
            return asyncio.run(
                self.orchestrator.scrape_metadata(
                    source_key,
                    novel_id,
                    mode=mode,
                    max_chapter=int(max_chapter) if max_chapter.isdigit() else None,
                )
            )

        self._start_task(
            f"Scrape metadata for {novel_id} via {source_key}",
            _run,
            f"Metadata scraped for {novel_id}.",
        )

    def start_chapter_scrape(self) -> None:
        novel_id = self._resolved_novel_id()
        if not novel_id:
            QMessageBox.warning(self, "Missing Identifier", "Provide a novel ID or source identifier.")
            return
        source_key = self.source_input.currentText().strip()
        selection = self.chapter_selection_input.text().strip() or "all"
        mode = self.chapter_mode_input.currentText().strip() or "update"

        def _run() -> Any:
            asyncio.run(
                self.orchestrator.scrape_chapters(
                    source_key,
                    novel_id,
                    selection,
                    mode=mode,
                )
            )
            return {"novel_id": novel_id, "selection": selection}

        self._start_task(
            f"Scrape chapters for {novel_id} ({selection})",
            _run,
            f"Chapters scraped for {novel_id} ({selection}).",
        )

    def start_full_sync(self) -> None:
        novel_id = self._resolved_novel_id()
        if not novel_id:
            QMessageBox.warning(self, "Missing Identifier", "Provide a novel ID or source identifier.")
            return
        source_key = self.source_input.currentText().strip()
        metadata_mode = self.metadata_mode_input.currentText().strip() or "update"
        chapter_mode = self.chapter_mode_input.currentText().strip() or "update"
        selection = self.chapter_selection_input.text().strip() or "all"
        max_chapter = self.max_chapter_input.text().strip()

        def _run() -> Any:
            metadata = asyncio.run(
                self.orchestrator.scrape_metadata(
                    source_key,
                    novel_id,
                    mode=metadata_mode,
                    max_chapter=int(max_chapter) if max_chapter.isdigit() else None,
                )
            )
            asyncio.run(
                self.orchestrator.scrape_chapters(
                    source_key,
                    novel_id,
                    selection,
                    mode=chapter_mode,
                )
            )
            return metadata

        self._start_task(
            f"Sync source novel {novel_id}",
            _run,
            f"Source sync completed for {novel_id}.",
        )

    def _on_success(self, payload: object, message: str) -> None:
        self.output.setPlainText(str(payload))
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, message)
        self._active_job_id = None
        self.activity.emit(message)
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.completed.emit()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, f"Source scrape failed: {message}")
        self._active_job_id = None
        self.activity.emit(f"Source scrape failed: {message}")


class OCRReviewTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

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
        self.refresh()

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
        elif self.chapter_list.currentItem() is None:
            self.chapter_list.setCurrentRow(0)

    def _load_current(self, current: QListWidgetItem | None = None, _previous: QListWidgetItem | None = None) -> None:
        item = current or self.chapter_list.currentItem()
        if item is None:
            self.ocr_text.clear()
            return
        chapter_id = item.data(Qt.ItemDataRole.UserRole)
        media = self.storage.load_chapter_media_state(self.novel_id, str(chapter_id)) or {}
        self.ocr_text.setPlainText(str(media.get("ocr_text") or ""))
        status = str(media.get("ocr_status") or "pending").strip().lower()
        self.status_input.setCurrentText(status if status in {"pending", "reviewed", "skipped", "failed"} else "pending")
        self.required_input.setChecked(bool(media.get("ocr_required", False)))

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
        item = self.chapter_list.currentItem()
        if item is None:
            return
        chapter_id = str(item.data(Qt.ItemDataRole.UserRole))
        self.storage.save_chapter_media_state(
            self.novel_id,
            chapter_id,
            ocr_required=True,
            ocr_text=self.ocr_text.toPlainText(),
            ocr_status="reviewed",
            reembed_status="pending",
        )
        self.activity.emit(f"OCR reviewed for chapter {chapter_id}.")
        self.refresh()

    def save_status(self) -> None:
        item = self.chapter_list.currentItem()
        if item is None:
            return
        chapter_id = str(item.data(Qt.ItemDataRole.UserRole))
        status = self.status_input.currentText().strip()
        payload: dict[str, Any] = {
            "ocr_required": self.required_input.isChecked(),
            "ocr_text": self.ocr_text.toPlainText(),
            "ocr_status": status,
        }
        if status == "reviewed":
            payload["reembed_status"] = "pending"
        self.storage.save_chapter_media_state(
            self.novel_id,
            chapter_id,
            **payload,
        )
        self.activity.emit(f"OCR status updated for chapter {chapter_id} -> {status}.")
        self.refresh()


class GlossaryTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
        self.orchestrator = container.orchestrator
        self._worker: AsyncTaskThread | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        toolbar = QHBoxLayout()
        self.extract_button = QPushButton("Extract Candidates")
        self.approve_button = QPushButton("Approve Pending")
        self.clear_button = QPushButton("Clear Glossary")
        self.max_terms_input = QLineEdit("50")
        self.max_terms_input.setMaximumWidth(120)
        toolbar.addWidget(QLabel("Max Terms"))
        toolbar.addWidget(self.max_terms_input)
        toolbar.addWidget(self.extract_button)
        toolbar.addWidget(self.approve_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        splitter = QSplitter()
        self.term_list = QListWidget()
        self.term_list.currentItemChanged.connect(self._load_current)
        editor_group = QGroupBox("Term Editor")
        editor_layout = QVBoxLayout(editor_group)
        form = QFormLayout()
        self.source_input = QLineEdit()
        self.target_input = QLineEdit()
        self.status_input = QComboBox()
        self.status_input.addItems(["pending", "approved", "ignored", "translated"])
        self.notes_input = QLineEdit()
        self.context_output = QPlainTextEdit()
        self.context_output.setReadOnly(True)
        form.addRow("Source", self.source_input)
        form.addRow("Target", self.target_input)
        form.addRow("Status", self.status_input)
        form.addRow("Notes", self.notes_input)
        editor_layout.addLayout(form)
        editor_layout.addWidget(QLabel("Context Summary"))
        editor_layout.addWidget(self.context_output)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("Save Term")
        self.remove_button = QPushButton("Remove Term")
        self.new_button = QPushButton("New Term")
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.new_button)
        buttons.addStretch()
        editor_layout.addLayout(buttons)
        splitter.addWidget(self.term_list)
        splitter.addWidget(editor_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.extract_button.clicked.connect(self.extract_terms)
        self.approve_button.clicked.connect(self.approve_pending)
        self.clear_button.clicked.connect(self.clear_glossary)
        self.save_button.clicked.connect(self.save_term)
        self.remove_button.clicked.connect(self.remove_term)
        self.new_button.clicked.connect(self.new_term)
        self.refresh()

    def refresh(self) -> None:
        entries = self.storage.load_glossary(self.novel_id)
        counts = glossary_status_counts(entries)
        self.summary_label.setText(
            f"Terms: {len(entries)} | Pending: {counts.get('pending', 0)} | "
            f"Approved: {counts.get('approved', 0)} | Ignored: {counts.get('ignored', 0)}"
        )
        current_source = self.source_input.text().strip()
        self.term_list.clear()
        for entry in entries:
            item = QListWidgetItem(
                f"[{entry.get('status', 'pending')}] {_safe_str(entry.get('source'))} -> {_safe_str(entry.get('target'))}"
            )
            item.setData(Qt.ItemDataRole.UserRole, dict(entry))
            self.term_list.addItem(item)
            if current_source and entry.get("source") == current_source:
                self.term_list.setCurrentItem(item)
        if self.term_list.count() == 0:
            self.output.setPlainText("No glossary entries yet.")
        else:
            self.output.setPlainText(f"Loaded {self.term_list.count()} glossary term(s).")
            if self.term_list.currentItem() is None:
                self.term_list.setCurrentRow(0)

    def _load_current(self, current: QListWidgetItem | None = None, _previous: QListWidgetItem | None = None) -> None:
        item = current or self.term_list.currentItem()
        if item is None:
            self.new_term()
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(entry, dict):
            self.new_term()
            return
        self.source_input.setText(_safe_str(entry.get("source"), ""))
        self.target_input.setText(_safe_str(entry.get("target"), ""))
        self.status_input.setCurrentText(_safe_str(entry.get("status"), "pending"))
        self.notes_input.setText(_safe_str(entry.get("notes"), ""))
        self.context_output.setPlainText(_safe_str(entry.get("context_summary"), ""))

    def new_term(self) -> None:
        self.source_input.clear()
        self.target_input.clear()
        self.status_input.setCurrentText("pending")
        self.notes_input.clear()
        self.context_output.clear()

    def extract_terms(self) -> None:
        max_terms_value = self.max_terms_input.text().strip()
        max_terms = int(max_terms_value) if max_terms_value.isdigit() else 50
        self.extract_button.setEnabled(False)

        def _run() -> Any:
            return asyncio.run(self.orchestrator.extract_glossary_terms(self.novel_id, max_terms=max_terms))

        self._worker = AsyncTaskThread(_run, self)
        self._worker.succeeded.connect(self._on_extract_success)
        self._worker.failed.connect(self._on_extract_error)
        self._worker.finished.connect(lambda: self.extract_button.setEnabled(True))
        self._worker.start()

    def _on_extract_success(self, payload: object) -> None:
        summary = payload if isinstance(payload, dict) else {}
        self.activity.emit(
            f"Glossary extraction added {summary.get('added', 0)} term(s) for {self.novel_id}."
        )
        self.output.setPlainText(str(payload))
        self.refresh()

    def _on_extract_error(self, message: str) -> None:
        self.activity.emit(f"Glossary extraction failed: {message}")
        self.output.setPlainText(message)

    def approve_pending(self) -> None:
        entries = self.storage.load_glossary(self.novel_id)
        for entry in entries:
            if str(entry.get("status") or "").lower() == "pending":
                entry["status"] = "approved"
        self.storage.save_glossary(self.novel_id, entries)
        self.activity.emit("Approved pending glossary terms.")
        self.refresh()

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
                "locked": True,
                "notes": self.notes_input.text().strip() or None,
                "status": self.status_input.currentText().strip(),
                "context_summary": self.context_output.toPlainText().strip() or None,
            }
        )
        self.storage.save_glossary(self.novel_id, entries)
        self.activity.emit(f"Saved glossary term '{source}'.")
        self.refresh()

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


class TranslateTab(QWidget):
    activity = Signal(str)

    def __init__(
        self,
        novel_id: str,
        *,
        activity_model: DesktopActivityModel | None = None,
        refresh_callback: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.activity_model = activity_model
        self.refresh_callback = refresh_callback
        self.orchestrator = container.orchestrator
        self._active_job_id: str | None = None
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        form = QFormLayout()
        self.source_key_input = QComboBox()
        self.source_key_input.addItems(sorted(set(available_sources() + available_input_adapters() + ["imported"])))
        self.chapter_selection_input = QLineEdit("all")
        self.provider_input = QComboBox()
        self.provider_input.addItem("Inherit", None)
        for provider in sorted(available_providers()):
            self.provider_input.addItem(provider, provider)
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.source_language_input = QLineEdit()
        self.source_language_input.setPlaceholderText("auto")
        self.target_language_input = QLineEdit(settings.TRANSLATION_TARGET_LANGUAGE)
        self.style_input = QComboBox()
        self.style_input.addItem("")
        self.style_input.addItems(["fantasy", "romance", "action", "comedy"])
        self.consistency_input = QCheckBox("Consistency mode")
        self.json_input = QCheckBox("JSON output mode")
        self.force_input = QCheckBox("Force retranslate")
        form.addRow("Source/Input Key", self.source_key_input)
        form.addRow("Chapter Selection", self.chapter_selection_input)
        form.addRow("Provider Override", self.provider_input)
        form.addRow("Model Override", self.model_input)
        form.addRow("Source Language Override", self.source_language_input)
        form.addRow("Target Language", self.target_language_input)
        form.addRow("Style Preset", self.style_input)
        form.addRow("", self.consistency_input)
        form.addRow("", self.json_input)
        form.addRow("", self.force_input)
        layout.addLayout(form)
        button_row = QHBoxLayout()
        self.estimate_button = QPushButton("Estimate Budget")
        self.translate_button = QPushButton("Translate")
        self.retranslate_button = QPushButton("Retranslate One")
        button_row.addWidget(self.estimate_button)
        button_row.addWidget(self.translate_button)
        button_row.addWidget(self.retranslate_button)
        button_row.addStretch()
        self.translate_button.clicked.connect(self.start_translation)
        self.estimate_button.clicked.connect(self.estimate_budget)
        self.retranslate_button.clicked.connect(self.retranslate_one)
        layout.addLayout(button_row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.provider_input.currentIndexChanged.connect(self._refresh_model_choices)
        self.refresh()

    def _refresh_model_choices(self) -> None:
        provider = self.provider_input.currentData()
        current_model = self.model_input.currentText().strip()
        self.model_input.clear()
        self.model_input.addItem("")
        if isinstance(provider, str) and provider.strip():
            with contextlib.suppress(Exception):
                for model in available_models(provider):
                    self.model_input.addItem(model)
        if current_model and self.model_input.findText(current_model) < 0:
            self.model_input.addItem(current_model)
        self.model_input.setCurrentText(current_model)

    def refresh(self) -> None:
        snapshot = next((item for item in _library_snapshots() if item["novel_id"] == self.novel_id), None)
        if snapshot is None:
            self.summary_label.setText("Project metadata not found.")
            return
        self.summary_label.setText(
            f"Translated: {snapshot['translated_units']}/{snapshot['total_units']} | "
            f"OCR Pending: {snapshot['ocr_pending']} | Glossary Pending: {snapshot['glossary_pending']}"
        )
        default_source = _safe_str(
            (container.storage.load_metadata(self.novel_id) or {}).get("input_adapter_key"),
            "imported",
        )
        source_index = self.source_key_input.findText(default_source)
        if source_index >= 0:
            self.source_key_input.setCurrentIndex(source_index)

    def estimate_budget(self) -> None:
        provider_key = self.provider_input.currentData()
        if not isinstance(provider_key, str):
            provider_key = container.preferences.get_preferred_provider()
        model = self.model_input.currentText().strip() or container.preferences.get_preferred_model()
        chapters = self.chapter_selection_input.text().strip() or "all"
        try:
            summary = _estimate_translation_budget(self.novel_id, chapters, provider_key, model)
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(str(exc))
            return
        self.output.setPlainText(summary)

    def start_translation(self) -> None:
        source_key = self.source_key_input.currentText()
        chapters = self.chapter_selection_input.text().strip() or "all"
        provider_key = self.provider_input.currentData()
        if not isinstance(provider_key, str):
            provider_key = None
        provider_model = self.model_input.currentText().strip() or None
        source_language = self.source_language_input.text().strip() or None
        target_language = self.target_language_input.text().strip() or None
        style_preset = self.style_input.currentText().strip() or None
        consistency_mode = self.consistency_input.isChecked()
        json_output = self.json_input.isChecked()
        force = self.force_input.isChecked()
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(f"Translate {self.novel_id} ({chapters})")
        self.translate_button.setEnabled(False)
        self.retranslate_button.setEnabled(False)

        def _run() -> Any:
            asyncio.run(
                self.orchestrator.translate_chapters(
                    source_key,
                    self.novel_id,
                    chapters,
                    provider_key=provider_key,
                    provider_model=provider_model,
                    force=force,
                    source_language=source_language,
                    target_language=target_language,
                    style_preset=style_preset,
                    consistency_mode=consistency_mode,
                    json_output=json_output,
                )
            )
            return "Translation completed."

        worker = AsyncTaskThread(_run, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self.translate_button.setEnabled(True))
        worker.finished.connect(lambda: self.retranslate_button.setEnabled(True))
        worker.start()
        self._worker = worker

    def retranslate_one(self) -> None:
        source_key = self.source_key_input.currentText()
        chapter_id = self.chapter_selection_input.text().strip()
        if not chapter_id.isdigit():
            self.output.setPlainText("Retranslate One requires a single numeric chapter ID in Chapter Selection.")
            return
        provider_key = self.provider_input.currentData()
        if not isinstance(provider_key, str):
            provider_key = None
        provider_model = self.model_input.currentText().strip() or None
        source_language = self.source_language_input.text().strip() or None
        target_language = self.target_language_input.text().strip() or None
        style_preset = self.style_input.currentText().strip() or None
        consistency_mode = self.consistency_input.isChecked()
        json_output = self.json_input.isChecked()
        if self.activity_model is not None:
            self._active_job_id = self.activity_model.start_job(f"Retranslate {self.novel_id}/{chapter_id}")
        self.translate_button.setEnabled(False)
        self.retranslate_button.setEnabled(False)

        def _run() -> Any:
            asyncio.run(
                self.orchestrator.retranslate_chapter(
                    source_key=source_key,
                    novel_id=self.novel_id,
                    chapter_id=chapter_id,
                    provider_key=provider_key,
                    provider_model=provider_model,
                    source_language=source_language,
                    target_language=target_language,
                    style_preset=style_preset,
                    consistency_mode=consistency_mode,
                    json_output=json_output,
                )
            )
            return f"Retranslated chapter {chapter_id}."

        worker = AsyncTaskThread(_run, self)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_error)
        worker.finished.connect(lambda: self.translate_button.setEnabled(True))
        worker.finished.connect(lambda: self.retranslate_button.setEnabled(True))
        worker.start()
        self._worker = worker

    def _on_success(self, payload: object) -> None:
        self.output.setPlainText(str(payload))
        finished_message = str(payload) if isinstance(payload, str) else f"Translation completed for {self.novel_id}."
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, finished_message)
        self._active_job_id = None
        self.activity.emit(str(payload))
        if self.refresh_callback is not None:
            self.refresh_callback()
        self.refresh()

    def _on_error(self, message: str) -> None:
        self.output.setPlainText(message)
        if self.activity_model is not None and self._active_job_id is not None:
            self.activity_model.finish_job(self._active_job_id, f"Translation failed for {self.novel_id}: {message}")
        self._active_job_id = None
        self.activity.emit(f"Translation failed: {message}")


class ReembedTab(QWidget):
    activity = Signal(str)

    def __init__(self, novel_id: str) -> None:
        super().__init__()
        self.novel_id = novel_id
        self.storage = container.storage
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
        self.storage = container.storage
        self.exporter = container.export
        layout = QVBoxLayout(self)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        form = QFormLayout()
        self.format_input = QComboBox()
        self.format_input.addItems(["epub", "pdf", "html", "md"])
        self.chapter_selection_input = QLineEdit("full")
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
        layout.addLayout(form)

        button_row = QHBoxLayout()
        button = QPushButton("Export")
        button.clicked.connect(self.export_current)
        button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def export_current(self) -> None:
        meta = self.storage.load_metadata(self.novel_id)
        if not meta:
            self.output.setPlainText("Metadata not found.")
            return
        fmt = self.format_input.currentText()
        chapter_selection = self.chapter_selection_input.text().strip() or "full"
        language = self.language_input.currentText().strip()
        output_dir = self.output_dir_input.text().strip() or None
        include_toc = self.include_toc_input.isChecked()
        try:
            chapters = _collect_export_chapters(self.novel_id, chapter_selection=chapter_selection, language=language)
        except Exception as exc:  # noqa: BLE001
            self.output.setPlainText(str(exc))
            return

        output_path = _build_export_output_path(
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
        selected_numbers = _selected_numbers(chapter_selection)
        if language != "source":
            for chapter in meta.get("chapters", []):
                if not isinstance(chapter, dict):
                    continue
                chapter_id = str(chapter.get("id"))
                if selected_numbers is not None:
                    if not chapter_id.isdigit() or int(chapter_id) not in selected_numbers:
                        continue
                with contextlib.suppress(Exception):
                    self.storage.update_chapter_state(self.novel_id, chapter_id, ChapterState.EXPORTED)
        self.output.setPlainText(f"Exported {len(chapters)} chapter(s) to:\n{output_path}")
        self.activity.emit(f"Exported {fmt.upper()} to {output_path}.")
        self.refresh()

    def refresh(self) -> None:
        translated = len(self.storage.list_translated_chapters(self.novel_id))
        stored = self.storage.count_stored_chapters(self.novel_id)
        self.summary_label.setText(
            f"Stored units: {stored} | Translated units: {translated} | "
            f"Recent exports: {len(_recent_export_paths())}"
        )


class ActivityTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def append(self, message: str) -> None:
        current = self.output.toPlainText().strip()
        self.output.setPlainText(f"{current}\n{message}".strip())


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
        meta = container.storage.load_metadata(self.novel_id) or {}
        snapshot = next((item for item in _library_snapshots() if item["novel_id"] == self.novel_id), None)
        title = meta.get("translated_title") or meta.get("title") or self.novel_id
        author = meta.get("translated_author") or meta.get("author") or "Unknown author"
        self.title_label.setText(title)
        self.subtitle_label.setText(
            f"{author} | {_safe_str(meta.get('document_type'))} | {_safe_str(meta.get('origin_uri_or_path'))}"
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
                str(len(container.storage.get_chapters_ready_for_export(self.novel_id))),
                "Translated chapters ready for export",
            )
        lines = [
            f"Novel ID: {self.novel_id}",
            f"Input Adapter: {_safe_str(meta.get('input_adapter_key'))}",
            f"Origin Type: {_safe_str(meta.get('origin_type'))}",
            f"Source Language: {_safe_str(meta.get('source_language'))}",
            f"Updated: {_timestamp_label(meta.get('updated_at') or meta.get('scraped_at'))}",
            "",
            "Workflow Profiles:",
            _profiles_snapshot_text(),
        ]
        self.meta_output.setPlainText("\n".join(lines))


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
        self.header_label = QLabel()
        self.header_label.setObjectName("HeroBody")
        self.header_label.setWordWrap(True)
        layout.addWidget(self.header_label)
        tabs = QTabWidget()
        self.overview_tab = WorkspaceOverviewTab(novel_id)
        self.import_tab = ImportTab(
            novel_id,
            activity_model=activity_model,
            refresh_callback=refresh_callback,
        )
        self.scrape_tab = SourceScrapePanel(
            fixed_novel_id=novel_id,
            activity_model=activity_model,
            refresh_callback=refresh_callback,
        )
        self.ocr_tab = OCRReviewTab(novel_id)
        self.glossary_tab = GlossaryTab(novel_id)
        self.translate_tab = TranslateTab(
            novel_id,
            activity_model=activity_model,
            refresh_callback=refresh_callback,
        )
        self.reembed_tab = ReembedTab(novel_id)
        self.export_tab = ExportTab(novel_id)
        tabs.addTab(self.overview_tab, "Overview")
        tabs.addTab(self.import_tab, "Import")
        tabs.addTab(self.scrape_tab, "Scrape")
        tabs.addTab(self.ocr_tab, "OCR Review")
        tabs.addTab(self.glossary_tab, "Glossary")
        tabs.addTab(self.translate_tab, "Translate")
        tabs.addTab(self.reembed_tab, "Re-embed")
        tabs.addTab(self.export_tab, "Export")
        layout.addWidget(tabs)

        for tab in [self.import_tab, self.scrape_tab, self.ocr_tab, self.glossary_tab, self.translate_tab, self.reembed_tab, self.export_tab]:
            tab.activity.connect(self.activity_model.add_message)
            tab.activity.connect(lambda _message: self.refresh_callback())
        self.import_tab.completed.connect(self.ocr_tab.refresh)
        self.import_tab.completed.connect(self.glossary_tab.refresh)
        self.scrape_tab.completed.connect(self.refresh)
        self.import_tab.completed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        snapshot = next((item for item in _library_snapshots() if item["novel_id"] == self.novel_id), None)
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


class DesktopMainWindow(QMainWindow):
    TOP_LEVEL_PAGES = (
        ("home", "Home"),
        ("library", "Library"),
        ("import", "Acquire"),
        ("activity", "Activity"),
        ("profiles", "Profiles"),
        ("diagnostics", "Diagnostics"),
        ("settings", "Settings"),
    )

    def __init__(self) -> None:
        super().__init__()
        bootstrap()
        self.activity_model = DesktopActivityModel()
        self.page_items: dict[str, QListWidgetItem] = {}
        self.page_widgets: dict[str, QWidget] = {}
        self.workspace_key: str | None = None
        self.workspace: BookWorkspace | None = None

        self.setWindowTitle("Novel AI Desktop")
        self.resize(1380, 920)
        root = QSplitter()
        root.setObjectName("DesktopRoot")
        self.setCentralWidget(root)
        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setMaximumWidth(260)
        root.addWidget(self.nav)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)
        root.setStretchFactor(0, 0)
        root.setStretchFactor(1, 1)

        self.home_view = HomeView(self.activity_model)
        self.library_view = LibraryView()
        self.import_view = ImportPage(self.activity_model, self.refresh_all_views)
        self.activity_view = ActivityView(self.activity_model)
        self.library_view.open_requested.connect(self.open_workspace)
        self.library_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.navigate_requested.connect(self._navigate_to_page)
        self.home_view.open_workspace_requested.connect(self.open_workspace)
        self.import_view.open_workspace_requested.connect(self.open_workspace)
        self.profiles_view = ProfilesView(self.refresh_all_views)
        self.diagnostics_view = DiagnosticsView()
        self.settings_view = SettingsView(self.refresh_all_views)

        for key, label in self.TOP_LEVEL_PAGES:
            widget = getattr(self, f"{key}_view")
            self._add_page(key, label, widget)

        self.nav.currentItemChanged.connect(self._switch_view)
        self.activity_model.jobs_changed.connect(self._refresh_status_bar)
        self.activity_model.messages_changed.connect(self._refresh_status_bar)
        self._navigate_to_page("home")
        self._refresh_status_bar()

    def _add_page(self, key: str, label: str, widget: QWidget) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.page_items[key] = item
        self.page_widgets[key] = widget
        self.nav.addItem(item)
        self.stack.addWidget(widget)

    def _navigate_to_page(self, key: str) -> None:
        item = self.page_items.get(key)
        if item is not None:
            self.nav.setCurrentItem(item)

    def _switch_view(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(key, str) and key in self.page_widgets:
            self.stack.setCurrentWidget(self.page_widgets[key])

    def _refresh_status_bar(self) -> None:
        provider = container.preferences.get_preferred_provider()
        model = container.preferences.get_preferred_model()
        jobs = len(self.activity_model.running_jobs())
        self.statusBar().showMessage(
            f"Library: {settings.NOVEL_LIBRARY_DIR} | Provider: {provider} | Model: {model} | Running Jobs: {jobs}"
        )

    def refresh_all_views(self) -> None:
        for key in ("home", "library", "activity", "diagnostics"):
            widget = self.page_widgets.get(key)
            if widget is not None and hasattr(widget, "refresh"):
                widget.refresh()
        if self.workspace is not None:
            self.workspace.refresh()
            workspace_item = self.page_items.get(self.workspace_key or "")
            if workspace_item is not None:
                title = (container.storage.load_metadata(self.workspace.novel_id) or {}).get("title") or self.workspace.novel_id
                workspace_item.setText(f"Workspace: {title}")
        self._refresh_status_bar()

    def open_workspace(self, novel_id: str) -> None:
        key = f"workspace:{novel_id}"
        if self.workspace_key == key and self.workspace is not None:
            self.workspace.refresh()
            self._navigate_to_page(key)
            return

        if self.workspace is not None and self.workspace_key is not None:
            old_item = self.page_items.pop(self.workspace_key, None)
            old_widget = self.page_widgets.pop(self.workspace_key, None)
            if old_item is not None:
                row = self.nav.row(old_item)
                self.nav.takeItem(row)
            if old_widget is not None:
                self.stack.removeWidget(old_widget)
                old_widget.deleteLater()

        self.workspace_key = key
        self.workspace = BookWorkspace(
            novel_id,
            activity_model=self.activity_model,
            refresh_callback=self.refresh_all_views,
        )
        title = (container.storage.load_metadata(novel_id) or {}).get("title") or novel_id
        self._add_page(key, f"Workspace: {title}", self.workspace)
        self._navigate_to_page(key)
        self.refresh_all_views()


def main() -> None:
    bootstrap()
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("Bahnschrift SemiCondensed", 10))
    app.setStyleSheet(_build_stylesheet())
    window = DesktopMainWindow()
    window.show()
    app.exec()

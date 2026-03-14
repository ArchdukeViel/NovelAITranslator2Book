from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QApplication

from novelai.interfaces.desktop.app import BookWorkspace, DesktopMainWindow, ExportTab, OCRReviewTab, TranslateTab
from novelai.interfaces.desktop.shared import DesktopActivityModel
from tests.conftest import TestFixture as FixtureEnv


@pytest.fixture(scope="module")
def qapp() -> Iterator[QApplication]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    yield app


@pytest.fixture
def desktop_env(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> Iterator[FixtureEnv]:
    fixture = FixtureEnv()
    monkeypatch.setattr("novelai.interfaces.desktop.app.container", fixture.container)
    monkeypatch.setattr("novelai.interfaces.desktop.shared.container", fixture.container)
    yield fixture
    fixture.cleanup()


def _seed_ocr_chapter(fixture: FixtureEnv, novel_id: str, chapter_id: str = "1") -> None:
    fixture.storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": "Desktop OCR Test",
            "chapters": [{"id": chapter_id, "title": "Chapter 1"}],
        },
    )
    fixture.storage.save_chapter(novel_id, chapter_id, "raw source text")


def test_ocr_review_tab_fallbacks_to_single_page_when_ocr_pages_missing(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_ocr_chapter(desktop_env, novel_id)
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "1",
        ocr_required=True,
        ocr_text="single page candidate",
        ocr_status="pending",
    )

    tab = OCRReviewTab(novel_id)

    assert tab.page_label.text() == "Page 1 of 1"
    assert tab.ocr_text.toPlainText() == "single page candidate"
    assert tab.status_input.currentText() == "pending"


def test_ocr_review_tab_saves_current_page_and_preserves_other_pages(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_ocr_chapter(desktop_env, novel_id)
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "1",
        ocr_required=True,
        ocr_pages=[
            {"page": 1, "text": "page one", "status": "pending"},
            {"page": 2, "text": "page two", "status": "pending"},
        ],
        ocr_status="pending",
    )

    tab = OCRReviewTab(novel_id)
    tab._go_to_page(1)
    tab.ocr_text.setPlainText("page two revised")
    tab.status_input.setCurrentText("reviewed")
    tab.save_status()

    media = desktop_env.storage.load_chapter_media_state(novel_id, "1")
    assert media is not None
    pages = media.get("ocr_pages")
    assert isinstance(pages, list)
    assert pages[0]["text"] == "page one"
    assert pages[0]["status"] == "pending"
    assert pages[1]["text"] == "page two revised"
    assert pages[1]["status"] == "reviewed"
    assert media["ocr_status"] == "pending"


def test_mark_reviewed_sets_chapter_reviewed_when_all_pages_reviewed(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_ocr_chapter(desktop_env, novel_id)
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "1",
        ocr_required=True,
        ocr_pages=[
            {"page": 1, "text": "already reviewed", "status": "reviewed"},
            {"page": 2, "text": "needs review", "status": "pending"},
        ],
        ocr_status="pending",
    )

    tab = OCRReviewTab(novel_id)
    tab._go_to_page(1)
    tab.mark_reviewed()

    media = desktop_env.storage.load_chapter_media_state(novel_id, "1")
    assert media is not None
    assert media["ocr_status"] == "reviewed"
    assert media["reembed_status"] == "pending"


def _seed_translate_chapters(fixture: FixtureEnv, novel_id: str) -> None:
    fixture.storage.save_metadata(
        novel_id,
        {
            "novel_id": novel_id,
            "title": "Desktop Translate Test",
            "chapters": [
                {"id": "1", "title": "Chapter 1"},
                {"id": "2", "title": "Chapter 2"},
            ],
        },
    )
    fixture.storage.save_chapter(novel_id, "1", "raw chapter one")
    fixture.storage.save_chapter(novel_id, "2", "raw chapter two")
    fixture.storage.save_translated_chapter(novel_id, "1", "initial translated one", provider="dummy", model="dummy")


def test_translate_review_mode_saves_edited_translation(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    tab = TranslateTab(novel_id)
    tab._switch_to_review()
    assert tab.review_chapter_list.count() >= 2

    # Select chapter 1 and edit translated output.
    tab.review_chapter_list.setCurrentRow(0)
    tab.review_translated_text.setPlainText("edited translation one")
    tab._save_review_translation()

    translated = desktop_env.storage.load_translated_chapter(novel_id, "1")
    assert translated is not None
    assert translated["text"] == "edited translation one"


def test_translate_retranslate_uses_selected_review_chapter_when_selection_not_numeric(
    desktop_env: FixtureEnv,
    qapp: QApplication,
) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    captured: dict[str, str] = {}

    class DummyOrchestrator:
        async def retranslate_chapter(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["chapter_id"] = str(kwargs.get("chapter_id"))

    activity = DesktopActivityModel()
    tab = TranslateTab(novel_id, activity_model=activity)
    tab.orchestrator = DummyOrchestrator()  # type: ignore[assignment]
    tab._switch_to_review()

    # Select chapter 2 in review mode and keep non-numeric chapter selection field.
    tab.review_chapter_list.setCurrentRow(1)
    tab.chapter_selection_input.setText("all")
    tab.retranslate_one()

    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()
    assert captured.get("chapter_id") == "2"


def test_activity_model_fail_job_removes_running_job_and_keeps_log() -> None:
    activity = DesktopActivityModel()
    job_id = activity.start_job("Translate sample")
    assert len(activity.running_jobs()) == 1

    activity.fail_job(job_id, "Translation failed for sample")

    assert len(activity.running_jobs()) == 0
    assert any("Translation failed for sample" in line for line in activity.messages())


def test_translate_preflight_blocks_when_ocr_or_glossary_pending(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)
    desktop_env.storage.save_glossary(
        novel_id,
        [
            {"source": "魔導具", "target": "perangkat sihir", "status": "pending", "locked": True},
        ],
    )
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "2",
        ocr_required=True,
        ocr_status="pending",
        ocr_text="ocr pending text",
    )

    tab = TranslateTab(novel_id)

    assert tab.translate_button.isEnabled() is False
    assert "Resolve OCR pending items" in tab.preflight_label.text()


def test_export_preflight_allows_partial_translated_export_with_blocked_chapters(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "2",
        ocr_required=True,
        ocr_status="pending",
        ocr_text="still pending",
    )

    tab = ExportTab(novel_id)
    tab.language_input.setCurrentText("translated")
    tab.refresh()

    assert tab.export_button.isEnabled() is True
    assert "Selected 2" in tab.readiness_label.text()
    assert "Blocked 1" in tab.readiness_label.text()


def test_export_preflight_blocks_scope_when_only_blocked_chapter_selected(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)
    desktop_env.storage.save_chapter_media_state(
        novel_id,
        "2",
        ocr_required=True,
        ocr_status="pending",
        ocr_text="still pending",
    )

    tab = ExportTab(novel_id)
    tab.language_input.setCurrentText("translated")
    tab.chapter_selection_input.setText("2")
    tab.refresh()

    assert tab.export_button.isEnabled() is False
    assert "No translated chapters are export-ready" in tab.preflight_label.text()


def test_workspace_activity_panel_toggle_and_filter(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)
    activity = DesktopActivityModel()
    workspace = BookWorkspace(
        novel_id,
        activity_model=activity,
        refresh_callback=lambda: None,
    )

    assert workspace._activity_panel_visible is False
    workspace._toggle_activity_panel()
    assert workspace._activity_panel_visible is True

    activity.add_message(f"Changed chapter for {novel_id}")
    job_id = activity.start_job(f"Translate {novel_id} (all)")
    workspace._refresh_activity_panel()

    assert workspace.workspace_jobs_list.count() >= 1
    assert novel_id in workspace.workspace_jobs_list.item(0).text() or "No active jobs" in workspace.workspace_jobs_list.item(0).text()
    assert novel_id in workspace.workspace_log.toPlainText()

    activity.finish_job(job_id, f"Finished {novel_id}")
    workspace._toggle_activity_panel()
    assert workspace._activity_panel_visible is False


def test_main_window_uses_fixed_compact_side_rail(desktop_env: FixtureEnv) -> None:
    window = DesktopMainWindow()

    assert window.nav.isHidden() is False
    assert window.nav.maximumWidth() <= 64
    assert window.nav.minimumWidth() <= window.nav.maximumWidth()
    assert not hasattr(window, "nav_toggle_button")


def test_main_window_brand_button_toggles_sidebar_labels(desktop_env: FixtureEnv) -> None:
    window = DesktopMainWindow()

    assert window._nav_labels_visible is False
    assert window.nav.maximumWidth() <= 64

    window.nav_brand_button.click()

    assert window._nav_labels_visible is True
    assert window.nav.maximumWidth() >= 180
    first_item = window.nav.item(0)
    assert first_item is not None
    assert first_item.text() != ""

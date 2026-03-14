from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QApplication

from novelai.interfaces.desktop.app import BookWorkspace, DesktopMainWindow, ExportTab, GlossaryTab, OCRReviewTab, TranslateTab
from novelai.interfaces.desktop.pages import profiles as profiles_page
from novelai.interfaces.desktop.shared import DesktopActivityModel, build_stylesheet
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


def test_translate_glossary_terms_uses_orchestrator(desktop_env: FixtureEnv, qapp: QApplication) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    captured: dict[str, object] = {}

    class DummyOrchestrator:
        async def translate_glossary_terms(self, novel_id: str, **kwargs):  # type: ignore[no-untyped-def]
            captured["novel_id"] = novel_id
            captured["only_pending"] = kwargs.get("only_pending")

    tab = TranslateTab(novel_id)
    tab.orchestrator = DummyOrchestrator()  # type: ignore[assignment]
    tab.translate_glossary_terms()

    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()
    assert captured.get("novel_id") == novel_id
    assert captured.get("only_pending") is True


def test_run_phased_pipeline_uses_orchestrator(desktop_env: FixtureEnv, qapp: QApplication) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    captured: dict[str, object] = {}

    class DummyOrchestrator:
        async def run_phased_translation_pipeline(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["novel_id"] = kwargs.get("novel_id")
            captured["source_key"] = kwargs.get("source_key")

    tab = TranslateTab(novel_id)
    tab.orchestrator = DummyOrchestrator()  # type: ignore[assignment]
    tab.source_key_input.setCurrentText("imported")
    tab.run_phased_pipeline()

    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()
    assert captured.get("novel_id") == novel_id
    assert captured.get("source_key") == "imported"


def test_translate_run_phase2_passes_threshold_and_phase(desktop_env: FixtureEnv, qapp: QApplication) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    captured: dict[str, object] = {}

    class DummyOrchestrator:
        async def run_phased_translation_pipeline(self, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)

    tab = TranslateTab(novel_id)
    tab.orchestrator = DummyOrchestrator()  # type: ignore[assignment]
    tab.confidence_threshold_input.setCurrentText("0.65")
    tab.polish_low_confidence_only_input.setChecked(True)
    tab.run_phase2()

    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()
    assert captured.get("phase") == "2"
    threshold = captured.get("confidence_threshold")
    assert isinstance(threshold, float)
    assert threshold == pytest.approx(0.65)
    assert captured.get("polish_low_confidence_only") is True


def test_glossary_split_actions_call_orchestrator(desktop_env: FixtureEnv, qapp: QApplication) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)

    calls: list[str] = []

    class DummyOrchestrator:
        async def translate_glossary_terms(self, novel_id: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(f"translate:{novel_id}:{kwargs.get('only_pending')}")
            return {"translated": 1, "skipped": 0}

        async def review_glossary_terms(self, novel_id: str, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(f"review:{novel_id}")
            return {"approved": 1, "pending": 0}

    tab = GlossaryTab(novel_id)
    tab.orchestrator = DummyOrchestrator()  # type: ignore[assignment]
    tab.translate_glossary_terms()
    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()

    tab.review_pending_terms()
    assert hasattr(tab, "_worker")
    tab._worker.wait(3000)  # type: ignore[attr-defined]
    qapp.processEvents()

    assert any(call.startswith(f"translate:{novel_id}:True") for call in calls)
    assert any(call.startswith(f"review:{novel_id}") for call in calls)


def test_activity_model_fail_job_removes_running_job_and_keeps_log() -> None:
    activity = DesktopActivityModel()
    job_id = activity.start_job("Translate sample")
    assert len(activity.running_jobs()) == 1

    activity.fail_job(job_id, "Translation failed for sample")

    assert len(activity.running_jobs()) == 0
    assert any("Translation failed for sample" in line for line in activity.messages())


def test_activity_model_tracks_phase_counters_and_clear() -> None:
    activity = DesktopActivityModel()
    activity.add_phase_event(
        "novel-1",
        {
            "phase": "phase2_body_translation",
            "status": "completed",
            "message": "Phase 2 completed.",
        },
    )
    activity.add_phase_event(
        "novel-1",
        {
            "phase": "phase2_body_translation",
            "status": "blocked",
            "message": "Glossary review required before phase 2.",
        },
    )

    counters = activity.phase_counters("novel-1")
    assert counters["phase2_body_translation"]["completed"] == 1
    assert counters["phase2_body_translation"]["blocked"] == 1
    assert len(activity.phase_events("novel-1")) == 2

    activity.clear_messages()
    assert activity.phase_events("novel-1") == []


def test_phase_timeline_items_have_status_color_chips(desktop_env: FixtureEnv) -> None:
    novel_id = f"novel-{uuid4().hex}"
    _seed_translate_chapters(desktop_env, novel_id)
    activity = DesktopActivityModel()
    workspace = BookWorkspace(
        novel_id,
        activity_model=activity,
        refresh_callback=lambda: None,
    )
    # Add one event per status type
    for status in ["completed", "blocked", "failed"]:
        activity.add_phase_event(
            novel_id,
            {"phase": "phase2_body_translation", "status": status, "message": f"test {status}"},
        )

    workspace._activity_panel_visible = True
    workspace._refresh_activity_panel()

    expected_colors = {"completed": "#4caf50", "blocked": "#ff9800", "failed": "#f44336"}
    for i in range(workspace.workspace_phase_timeline.count()):
        item = workspace.workspace_phase_timeline.item(i)
        assert item is not None
        text = item.text()
        color = item.foreground().color()
        for status, hex_val in expected_colors.items():
            if f"[{status}]" in text:
                assert color.name() == hex_val, f"Expected {hex_val} for {status}, got {color.name()}"


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


def test_stylesheet_uses_color_theme_without_image_overlay() -> None:
    stylesheet = build_stylesheet()
    assert "background-image" not in stylesheet
    assert "qradialgradient" in stylesheet


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
    activity.add_phase_event(
        novel_id,
        {
            "phase": "phase1_glossary_extraction",
            "status": "completed",
            "message": "Glossary candidates extracted.",
        },
    )
    job_id = activity.start_job(f"Translate {novel_id} (all)")
    workspace._refresh_activity_panel()

    assert workspace.workspace_jobs_list.count() >= 1
    assert novel_id in workspace.workspace_jobs_list.item(0).text() or "No active jobs" in workspace.workspace_jobs_list.item(0).text()
    assert "phase1_glossary_extraction" in workspace.workspace_phase_summary.text()
    assert workspace.workspace_phase_timeline.count() >= 1
    assert novel_id in workspace.workspace_log.toPlainText()

    activity.finish_job(job_id, f"Finished {novel_id}")
    workspace._toggle_activity_panel()
    assert workspace._activity_panel_visible is False


def test_main_window_uses_fixed_expanded_side_rail(desktop_env: FixtureEnv) -> None:
    window = DesktopMainWindow()

    assert window.nav.isHidden() is False
    assert window.nav.minimumWidth() == 180
    assert window.nav.maximumWidth() == 180
    assert window.nav_panel.minimumWidth() == 200
    assert window.nav_panel.maximumWidth() == 200
    assert window.nav.minimumWidth() <= window.nav.maximumWidth()
    assert window.nav.gridSize().width() == 44
    assert window.nav.gridSize().height() == 44
    assert not hasattr(window, "nav_toggle_button")


def test_main_window_brand_button_no_longer_toggles_sidebar_labels(desktop_env: FixtureEnv) -> None:
    window = DesktopMainWindow()

    assert window._nav_labels_visible is True
    assert window.nav.maximumWidth() == 180
    first_item = window.nav.item(0)
    assert first_item is not None
    before_text = first_item.text()

    window.nav_brand_button.click()

    assert window._nav_labels_visible is True
    assert window.nav.maximumWidth() == 180
    after_text = first_item.text()
    assert after_text == before_text
    assert after_text != ""


def test_profiles_validate_endpoint_calls_provider_and_sets_status(
    desktop_env: FixtureEnv,
    monkeypatch: pytest.MonkeyPatch,
    qapp: QApplication,
) -> None:
    monkeypatch.setattr("novelai.interfaces.desktop.shared.container", desktop_env.container)
    monkeypatch.setattr("novelai.interfaces.desktop.pages.profiles.available_providers", lambda: ["mock"])
    monkeypatch.setattr("novelai.interfaces.desktop.pages.profiles.available_models", lambda _key: ["mock-model"])

    captured: dict[str, object] = {}

    class DummyProvider:
        async def validate_connection(self, model: str | None = None, **kwargs):  # type: ignore[no-untyped-def]
            captured["model"] = model
            return True, "mock endpoint reachable"

    monkeypatch.setattr("novelai.interfaces.desktop.pages.profiles.get_provider", lambda _key: DummyProvider())

    view = profiles_page.ProfilesView()
    view.endpoint_provider_input.setCurrentIndex(max(view.endpoint_provider_input.findData("mock"), 0))
    view.endpoint_model_input.setCurrentText("mock-model")
    view._validate_endpoint_profile()

    assert hasattr(view, "_endpoint_validate_worker")
    assert view._endpoint_validate_worker is not None
    view._endpoint_validate_worker.wait(3000)
    qapp.processEvents()

    assert captured.get("model") == "mock-model"
    status_text = view.endpoint_validation_status.text()
    assert "Validation passed" in status_text
    assert "Last validated:" in status_text

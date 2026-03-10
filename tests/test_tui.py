from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from rich.console import Console

from novelai.app.bootstrap import bootstrap
from novelai.config.settings import settings
from novelai.providers.registry import available_providers
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.sources.registry import available_sources
from novelai.services.usage_service import UsageService
from novelai.tui.app import LibrarySnapshot, TUIApp
from tests.conftest import TestFixture as FixtureEnv


@pytest.fixture
def tui(monkeypatch: pytest.MonkeyPatch) -> Iterator[TUIApp]:
    """Provide a bootstrapped TUI instance isolated from the real novel_library."""
    bootstrap()
    fixture = FixtureEnv()

    monkeypatch.setattr("novelai.tui.app.container", fixture.container)
    monkeypatch.setattr("novelai.tui.app.PreferencesService", lambda: fixture.settings_service)
    monkeypatch.setattr("novelai.tui.app.UsageService", lambda: fixture.usage_service)
    monkeypatch.setattr(
        "novelai.tui.app.NovelOrchestrationService",
        lambda storage, translation: NovelOrchestrationService(
            storage=storage,
            translation=translation,
            source_factory=lambda key: fixture.mock_source,
            provider_factory=lambda key: fixture.mock_provider,
            settings_service=fixture.settings_service,
            translation_cache=fixture.cache,
            usage_service=fixture.usage_service,
        ),
    )

    app = TUIApp()
    yield app
    fixture.cleanup()


def test_tui_initialization(tui: TUIApp) -> None:
    assert tui.console is not None
    assert tui.storage is not None
    assert tui.translation is not None
    assert tui.exporter is not None
    assert tui.orchestrator is not None


def test_library_snapshot_returns_a_list(tui: TUIApp) -> None:
    snapshots = tui._collect_library_snapshot(limit=100)

    assert isinstance(tui.storage.list_novels(), list)
    assert isinstance(snapshots, list)


def test_prompt_source_detects_registered_sources() -> None:
    assert available_sources()


def test_prompt_provider_detects_registered_providers() -> None:
    assert available_providers()


def test_resolve_source_from_url_detects_registered_source_and_normalizes_id(tui: TUIApp) -> None:
    assert tui._resolve_source_from_url("https://ncode.syosetu.com/n9669bk/") == (
        "syosetu_ncode",
        "n9669bk",
    )
    assert tui._resolve_source_from_url("https://ncode.syosetu.com/n9669bk/12/") == (
        "syosetu_ncode",
        "n9669bk",
    )
    assert tui._resolve_source_from_url("https://novel18.syosetu.com/n0813kx/1/") == (
        "novel18_syosetu",
        "n0813kx",
    )
    assert tui._resolve_source_from_url("https://noc.syosetu.com/n0813kx/") == (
        "novel18_syosetu",
        "n0813kx",
    )
    assert tui._resolve_source_from_url("https://kakuyomu.jp/works/822139845959461179/") == (
        "kakuyomu",
        "822139845959461179",
    )
    assert tui._resolve_source_from_url(
        "https://kakuyomu.jp/works/822139845959461179/episodes/822139845959540845"
    ) == (
        "kakuyomu",
        "822139845959461179",
    )


def test_resolve_source_from_url_rejects_unknown_domains(tui: TUIApp) -> None:
    assert tui._resolve_source_from_url("https://example.com/story/123") is None


def test_dashboard_render_contains_sections(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120)
    tui.console.print(tui._build_dashboard())
    output = tui.console.export_text()

    assert "NOVELAIBOOK" in output
    assert "Control Deck" in output
    assert "Library Snapshot" in output
    assert "System Pulse" in output
    assert "Guide Rail" in output


def test_control_deck_uses_numbered_labels(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_actions_panel())
    output = tui.console.export_text()

    assert "1) Novel Library" in output
    assert "2) Add Novel" in output
    assert "3) Update Novel" in output
    assert "4) Diagnostics" in output
    assert "5) Settings" in output
    assert "0) Exit" in output


def test_dashboard_panel_order_keeps_system_pulse_last(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_dashboard())
    output = tui.console.export_text()

    assert output.index("Library Snapshot") < output.index("Control Deck") < output.index("System Pulse")


def test_dashboard_secondary_panels_share_a_bottom_border_line_when_wide(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_primary_panels())
    lines = tui.console.export_text().splitlines()

    assert any(
        line.count("└") + line.count("╰") >= 2 and line.count("┘") + line.count("╯") >= 2
        for line in lines
    )


@pytest.mark.parametrize("width", [80, 120])
def test_dashboard_full_width_sections_match_the_console_width(tui: TUIApp, width: int) -> None:
    tui.console = Console(record=True, width=width)
    tui.console.print(tui._build_dashboard())
    lines = tui.console.export_text().splitlines()

    for title in [
        "Reading Room",
        "Library Snapshot",
        "Guide Rail",
    ]:
        line = next(line for line in lines if title in line)
        assert len(line.rstrip()) == width


def test_dashboard_metric_cards_share_one_row_on_wide_terminals(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_dashboard())
    lines = tui.console.export_text().splitlines()
    metric_line = next(line for line in lines if "NOVELS" in line)

    assert "TRANSLATED" in metric_line
    assert "SOURCES" in metric_line
    assert "REQUESTS" in metric_line


def test_dashboard_secondary_panels_share_one_row_on_wide_terminals(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_dashboard())
    lines = tui.console.export_text().splitlines()
    title_line = next(line for line in lines if "Control Deck" in line)

    assert "System Pulse" in title_line


@pytest.mark.parametrize("width", [60, 80, 120])
def test_dashboard_lines_fit_within_the_console_width(tui: TUIApp, width: int) -> None:
    tui.console = Console(record=True, width=width)
    tui.console.print(tui._build_dashboard())
    lines = tui.console.export_text().splitlines()

    assert max(len(line.rstrip()) for line in lines) <= width


def test_action_prompt_panel_hides_scroll_metadata_by_default(tui: TUIApp) -> None:
    panel = tui._build_action_prompt_panel("", None, 0, 3)
    tui.console = Console(record=True, width=120)
    tui.console.print(panel)
    output = tui.console.export_text()

    assert "Scroll with Up/Down" not in output
    assert "View " not in output


def test_action_prompt_defaults_to_menu_number_one(tui: TUIApp) -> None:
    panel = tui._build_action_prompt_panel("", None, 0, 0)
    tui.console = Console(record=True, width=120)
    tui.console.print(panel)
    output = tui.console.export_text()

    assert "Action  1" in output


def test_console_width_can_be_locked_for_the_session(tui: TUIApp) -> None:
    tui.console = Console(width=137)
    tui._lock_layout_width()

    assert tui._console_width() == 137

    tui.console = Console(width=90)
    assert tui._console_width() == 137


def test_numeric_menu_selection_maps_to_action_keys(tui: TUIApp) -> None:
    assert tui._resolve_menu_selection("") == "list"
    assert tui._resolve_menu_selection("1") == "list"
    assert tui._resolve_menu_selection("2") == "scrape"
    assert tui._resolve_menu_selection("3") == "update"
    assert tui._resolve_menu_selection("4") == "diagnostics"
    assert tui._resolve_menu_selection("5") == "settings"
    assert tui._resolve_menu_selection("6") == "glossary"
    assert tui._resolve_menu_selection("0") == "exit"
    assert tui._resolve_menu_selection("7") is None
    assert tui._resolve_menu_selection("8") is None
    assert tui._resolve_menu_selection("list") is None


def test_library_screen_uses_guide_rail_instead_of_embedded_command_panel(tui: TUIApp) -> None:
    screen = tui._build_library_screen(
        [
            {
                "novel_id": "novel-1",
                "title": "A Better Story",
                "total_chapters": 2,
                "stored_chapters": 1,
                "translated_chapters": 1,
                "language": "Japanese",
            }
        ],
        [
            {
                "index": 1,
                "language": "Japanese",
                "snapshots": [
                    {
                        "novel_id": "novel-1",
                        "title": "A Better Story",
                        "total_chapters": 2,
                        "stored_chapters": 1,
                        "translated_chapters": 1,
                        "language": "Japanese",
                    }
                ],
            }
        ],
    )
    tui.console = Console(record=True, width=120)
    tui.console.print(screen)
    output = tui.console.export_text()

    assert "Guide Rail" in output
    assert "0) back" in output
    assert "2) delete custom" in output
    assert "4) inspect" in output


def test_library_snapshot_prefers_latest_added_novels(tui: TUIApp, monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = {
        "novel-old": {
            "title": "Older Story",
            "chapters": [{}, {}],
            "scraped_at": "2026-03-01T10:00:00+00:00",
        },
        "novel-new": {
            "title": "Newest Story",
            "chapters": [{}, {}, {}],
            "scraped_at": "2026-03-03T10:00:00+00:00",
        },
        "novel-mid": {
            "title": "Middle Story",
            "chapters": [{}],
            "scraped_at": "2026-03-02T10:00:00+00:00",
        },
    }

    monkeypatch.setattr(tui.storage, "list_novels", lambda: ["novel-old", "novel-new", "novel-mid"])
    monkeypatch.setattr(tui.storage, "load_metadata", lambda novel_id: metadata[novel_id])
    monkeypatch.setattr(tui.storage, "count_translated_chapters", lambda novel_id: 1)

    snapshots = tui._collect_library_snapshot(limit=3)

    assert [snapshot["novel_id"] for snapshot in snapshots] == ["novel-new", "novel-mid", "novel-old"]


def test_library_snapshot_uses_novel_title_and_novel_id_headers(tui: TUIApp, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui, "_collect_library_snapshot", lambda limit: [
        {
            "novel_id": "novel-123",
            "title": "A Better Story",
            "total_chapters": 4,
            "stored_chapters": 3,
            "translated_chapters": 2,
            "language": "Japanese",
        }
    ])

    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_library_panel())
    output = tui.console.export_text()

    assert "Novel Title" in output
    assert "Novel ID" in output
    assert output.index("Novel Title") < output.index("Novel ID")


def test_library_frame_keeps_full_guide_rail_visible(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120, height=30)
    snapshots: list[LibrarySnapshot] = [
        LibrarySnapshot(
            novel_id=f"novel-{index}",
            title="A Better Story",
            total_chapters=2,
            stored_chapters=1,
            translated_chapters=1,
            language="Japanese",
        )
        for index in range(1, 25)
    ]
    groups = tui._group_library_snapshots(snapshots)
    frame, _ = tui._build_library_frame(snapshots, groups, "", None, 0)

    tui.console.print(frame)
    output = tui.console.export_text()

    assert "4) inspect" in output
    assert "0) back" in output
    assert "Command  0" in output


def test_library_frame_keeps_novel_list_visible_on_short_terminals(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120, height=14)
    snapshots: list[LibrarySnapshot] = [
        LibrarySnapshot(
            novel_id="novel-1",
            title="A Better Story",
            total_chapters=2,
            stored_chapters=1,
            translated_chapters=1,
            language="Japanese",
        )
    ]
    groups = tui._group_library_snapshots(snapshots)
    frame, _ = tui._build_library_frame(snapshots, groups, "", None, 0)

    tui.console.print(frame)
    output = tui.console.export_text()

    assert "Novel List" in output
    assert "A Better Story" in output or "novel-1" in output


def test_library_frame_keeps_novel_list_box_closed_while_scrolled(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120, height=20)
    snapshots: list[LibrarySnapshot] = [
        LibrarySnapshot(
            novel_id=f"novel-{index}",
            title="A Better Story",
            total_chapters=2,
            stored_chapters=1,
            translated_chapters=1,
            language="Japanese",
        )
        for index in range(1, 40)
    ]
    groups = tui._group_library_snapshots(snapshots)
    frame, _ = tui._build_library_frame(snapshots, groups, "", None, 12)

    tui.console.print(frame)
    output = tui.console.export_text()

    assert "Novel List" in output
    assert "Guide Rail" in output
    assert "9)" in output or "10)" in output


def test_diagnostics_screen_uses_guide_rail_and_command_options(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_diagnostics_screen())
    output = tui.console.export_text()

    assert "DIAGNOSTICS" in output
    assert "Guide Rail" in output
    assert "1) clear usage history" in output
    assert "0) back" in output
    assert "Daily History" in output


def test_settings_screen_shows_numbered_actions_and_provider_models(tui: TUIApp) -> None:
    tui.settings.set_provider_key("openai")
    tui.settings.set_provider_model("gpt-5.4")

    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_settings_screen())
    output = tui.console.export_text()

    assert "SETTINGS" in output
    assert "1) select provider" in output
    assert "2) set API key" in output
    assert "0) back" in output
    assert "gpt-5.4" in output
    assert "gpt-5.2" in output


def test_diagnostics_and_settings_command_parsers_support_numbered_actions(tui: TUIApp) -> None:
    assert tui._parse_diagnostics_command("") == "back"
    assert tui._parse_diagnostics_command("0") == "back"
    assert tui._parse_diagnostics_command("1") == "clear"
    assert tui._parse_settings_command("") == "back"
    assert tui._parse_settings_command("1") == "provider"
    assert tui._parse_settings_command("2") == "api_key"
    assert tui._parse_settings_command("3") == "advanced"
    assert tui._parse_api_key_command("") == "back"
    assert tui._parse_api_key_command("1") == "set"
    assert tui._parse_api_key_command("2") == "clear"
    assert tui._parse_api_key_command("3") == "validate"


def test_settings_choice_screen_lists_numbered_options_and_back(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120)
    tui.console.print(
        tui._build_settings_choice_screen(
            "Select Provider",
            "Choose the translation provider you want to use.",
            ["dummy", "openai"],
        )
    )
    output = tui.console.export_text()

    assert "Select Provider" in output
    assert "1)" in output
    assert "2)" in output
    assert "0)" in output
    assert "dummy" in output
    assert "openai" in output


def test_api_key_screen_shows_current_value_and_clear_option(tui: TUIApp) -> None:
    tui.settings.set_api_key("test-api-key")

    tui.console = Console(record=True, width=120)
    tui.console.print(tui._build_api_key_screen())
    output = tui.console.export_text()

    assert "API Key" in output
    assert "Current API key" in output
    assert "test-api-key" in output
    assert "1) set API key" in output
    assert "2) clear API key" in output
    assert "3) validate connection" in output
    assert "0) back" in output


def test_api_key_screen_shows_not_set_when_empty(tui: TUIApp) -> None:
    tui.settings.clear_api_key()

    tui.console = Console(record=True, width=120)
    tui.console.print(tui._build_api_key_screen())
    output = tui.console.export_text()

    assert "not set" in output


def test_validate_provider_connection_updates_api_validation_status(
    tui: TUIApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProvider:
        async def validate_connection(self, model: str | None = None) -> tuple[bool, str]:
            return True, f"validated {model}"

    tui.settings.set_provider_key("openai")
    tui.settings.set_provider_model("gpt-5.4")
    monkeypatch.setattr("novelai.tui.screens.settings.get_provider", lambda key: FakeProvider())

    is_valid, message = tui._validate_provider_connection()

    assert is_valid is True
    assert message == "validated gpt-5.4"
    assert tui.api_validation_message == "validated gpt-5.4"
    assert tui.api_validation_kind == "success"


def test_chapter_selection_validation_accepts_full_and_ranges(tui: TUIApp) -> None:
    assert tui._validate_chapter_selection("full") is True
    assert tui._validate_chapter_selection("1") is True
    assert tui._validate_chapter_selection("3-8") is True
    assert tui._validate_chapter_selection("nope") is False


def test_chapter_selection_upper_bound_uses_highest_requested_chapter(tui: TUIApp) -> None:
    assert tui._chapter_selection_upper_bound("34-46") == 46
    assert tui._chapter_selection_upper_bound("3;7-9") == 9
    assert tui._chapter_selection_upper_bound("full") is None


def test_scrape_flow_existing_novel_can_continue_and_skip_stored_chapters(
    tui: TUIApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "A Better Story",
            "chapters": [{"id": 1}, {"id": 2}],
        },
    )
    tui.storage.save_chapter(novel_id, "1", "chapter 1 raw")
    tui.storage.save_translated_chapter(novel_id, "1", "chapter 1 translated")
    tui.storage.save_chapter(novel_id, "2", "chapter 2 raw")

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        tui,
        "_prompt_novel_url",
        lambda *args, **kwargs: ("https://ncode.syosetu.com/n8733gf/", "syosetu_ncode", novel_id),
    )
    monkeypatch.setattr(tui, "_prompt_chapter_selection", lambda: "1-4")

    def fake_confirm(message: str) -> bool:
        captured["confirm_message"] = message
        return True

    async def fake_scrape_metadata(
        source_key: str,
        novel_id_arg: str,
        mode: str = "update",
        max_chapter: int | None = None,
    ) -> None:
        captured["max_chapter"] = max_chapter
        tui.storage.save_metadata(
            novel_id_arg,
            {
                "title": "A Better Story",
                "chapters": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
            },
        )

    async def fake_scrape_chapters(
        source_key: str,
        novel_id_arg: str,
        chapters: str,
        mode: str = "update",
    ) -> None:
        captured["fetch_selection"] = chapters

    def fake_run_translation_pipeline(
        *,
        title: str,
        novel_id: str,
        source: str,
        novel_url: str,
        chapters: str,
    ) -> None:
        captured["translate_selection"] = chapters

    monkeypatch.setattr(tui, "_confirm_library_action", fake_confirm)
    monkeypatch.setattr(tui, "_do_scrape_metadata", fake_scrape_metadata)
    monkeypatch.setattr(tui, "_do_scrape_chapters", fake_scrape_chapters)
    monkeypatch.setattr(tui, "_run_translation_pipeline", fake_run_translation_pipeline)

    tui._scrape_flow()

    assert "Stored chapters: 1-2." in str(captured["confirm_message"])
    assert captured["max_chapter"] == 4
    assert captured["fetch_selection"] == "3-4"
    assert captured["translate_selection"] == "2-4"


def test_effective_translation_target_falls_back_to_dummy_without_api_key(tui: TUIApp) -> None:
    previous_api_key = settings.PROVIDER_OPENAI_API_KEY
    try:
        settings.PROVIDER_OPENAI_API_KEY = None
        provider, model, fallback_used = tui._effective_translation_target("openai", "gpt-5.4")

        assert (provider, model, fallback_used) == ("dummy", "dummy", True)
    finally:
        settings.PROVIDER_OPENAI_API_KEY = previous_api_key


def test_update_selection_starts_after_latest_stored_chapter(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    metadata = {
        "title": "A Better Story",
        "chapters": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
    }
    tui.storage.save_metadata(novel_id, metadata)
    tui.storage.save_chapter(novel_id, "1", "chapter 1 raw")
    tui.storage.save_translated_chapter(novel_id, "2", "chapter 2 translated")

    assert tui._build_update_selection(novel_id, metadata) == "3-4"


def test_update_selection_returns_none_when_novel_is_current(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    metadata = {
        "title": "A Better Story",
        "chapters": [{"id": 1}, {"id": 2}],
    }
    tui.storage.save_metadata(novel_id, metadata)
    tui.storage.save_translated_chapter(novel_id, "1", "chapter 1 translated")
    tui.storage.save_translated_chapter(novel_id, "2", "chapter 2 translated")

    assert tui._build_update_selection(novel_id, metadata) is None


def test_library_prompt_defaults_to_zero(tui: TUIApp) -> None:
    panel = tui._build_library_prompt_panel("", None)
    tui.console = Console(record=True, width=120)
    tui.console.print(panel)
    output = tui.console.export_text()

    assert "Command  0" in output


def test_library_list_panel_numbers_novels_and_shows_title_before_novel_id(tui: TUIApp) -> None:
    panel = tui._build_library_list_panel(
        [
            {
                "novel_id": "novel-1",
                "title": "A Better Story",
                "total_chapters": 2,
                "stored_chapters": 1,
                "translated_chapters": 1,
                "language": "Japanese",
            }
        ]
    )
    tui.console = Console(record=True, width=120)
    tui.console.print(panel)
    output = tui.console.export_text()

    assert "1)" in output
    assert output.index("A Better Story") < output.index("novel-1")
    assert "Source" in output
    assert "Stored" in output


def test_library_command_parser_supports_delete_and_back(tui: TUIApp) -> None:
    assert tui._parse_library_command("") == "back"
    assert tui._parse_library_command("0") == "back"
    assert tui._parse_library_command("back") == "back"
    assert tui._parse_library_command("1") == "export"
    assert tui._parse_library_command("2") == "delete_custom"
    assert tui._parse_library_command("delete custom") == "delete_custom"
    assert tui._parse_library_command("3") == "delete_all"
    assert tui._parse_library_command("delete all") == "delete_all"
    assert tui._parse_library_command("4") == "inspect"
    assert tui._parse_library_command("inspect") == "inspect"
    assert tui._parse_library_command("1 2-6") is None


def test_library_confirmation_screen_uses_boxed_yes_and_cancel_options(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120)
    tui.console.print(tui._build_library_confirmation_screen("Delete 3 novel(s) from the library?"))
    output = tui.console.export_text()

    assert "CONFIRM ACTION" in output
    assert "1)" in output
    assert "Yes, continue" in output
    assert "0)" in output
    assert "No, cancel" in output


def test_library_selection_parser_supports_ranges_and_lists(tui: TUIApp) -> None:
    assert tui._parse_library_selection("2-4", 10) == [2, 3, 4]
    assert tui._parse_library_selection("3, 7-10", 10) == [3, 7, 8, 9, 10]
    assert tui._parse_library_selection("4, 2, 2", 10) == [2, 4]
    assert tui._parse_library_selection("8-6", 10) is None
    assert tui._parse_library_selection("11", 10) is None
    assert tui._parse_library_selection("nope", 10) is None


def test_delete_library_novels_removes_multiple_metadata_entries(tui: TUIApp) -> None:
    novel_ids = [f"novel-{uuid4().hex}" for _ in range(2)]
    for novel_id in novel_ids:
        tui.storage.save_metadata(
            novel_id,
            {
                "title": f"Delete {novel_id}",
                "chapters": [{"id": 1}],
            },
        )
    snapshots = tui._order_library_snapshots(tui._collect_library_snapshot(limit=200))
    selections = [
        next(index for index, snapshot in enumerate(snapshots, start=1) if snapshot["novel_id"] == novel_id)
        for novel_id in novel_ids
    ]

    deleted = tui._delete_library_novels(snapshots, selections)

    assert {snapshot["novel_id"] for snapshot in deleted} == set(novel_ids)
    for novel_id in novel_ids:
        assert tui.storage.load_metadata(novel_id) is None


def test_group_library_snapshots_separates_languages(tui: TUIApp) -> None:
    snapshots: list[LibrarySnapshot] = [
        LibrarySnapshot(
            novel_id="jp-1",
            title="JP Novel",
            total_chapters=10,
            stored_chapters=6,
            translated_chapters=5,
            language="Japanese",
        ),
        LibrarySnapshot(
            novel_id="en-1",
            title="EN Novel",
            total_chapters=4,
            stored_chapters=2,
            translated_chapters=1,
            language="English",
        ),
    ]

    groups = tui._group_library_snapshots(snapshots)

    assert [group["language"] for group in groups] == ["English", "Japanese"]
    assert groups[0]["index"] == 1
    assert groups[1]["index"] == 2


def test_collect_library_snapshot_uses_metadata(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "A Long Story",
            "translated_title": "A Better Story",
            "source": "syosetu_ncode",
            "chapters": [{"id": 1}, {"id": 2}],
        },
    )
    tui.storage.save_translated_chapter(novel_id, "1", "hello")

    snapshots = tui._collect_library_snapshot(limit=100)
    matching = next(snapshot for snapshot in snapshots if snapshot["novel_id"] == novel_id)

    assert matching["title"] == "A Better Story"
    assert matching["total_chapters"] == 2
    assert matching["stored_chapters"] == 1
    assert matching["translated_chapters"] == 1
    assert matching["language"] == "Japanese"


def test_library_inspection_panel_shows_stored_and_translated_ranges(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "Range Story",
            "source": "syosetu_ncode",
            "chapters": [{"id": chapter_id} for chapter_id in range(1, 46)],
        },
    )
    for chapter_id in list(range(1, 21)) + list(range(41, 46)):
        tui.storage.save_chapter(novel_id, str(chapter_id), f"raw {chapter_id}", title=f"Chapter {chapter_id}")
    for chapter_id in range(1, 16):
        tui.storage.save_translated_chapter(novel_id, str(chapter_id), f"translated {chapter_id}")

    snapshot = LibrarySnapshot(
        novel_id=novel_id,
        title="Range Story",
        total_chapters=45,
        stored_chapters=25,
        translated_chapters=15,
        language="Japanese",
    )

    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_library_inspection_panel(snapshot))
    output = tui.console.export_text()

    assert "Source chapters" in output
    assert "1-45 (45)" in output
    assert "Stored locally" in output
    assert "1-20, 41-45 (25)" in output
    assert "Translated" in output
    assert "1-15 (15)" in output
    assert "Missing locally" in output
    assert "21-40 (20)" in output
    assert "Stored untranslated" in output
    assert "16-20, 41-45 (10)" in output


def test_collect_export_chapters_can_filter_to_a_range(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "Export Story",
            "chapters": [
                {"id": 1, "title": "One"},
                {"id": 2, "title": "Two"},
                {"id": 3, "title": "Three"},
            ],
        },
    )
    tui.storage.save_translated_chapter(novel_id, "1", "chapter one")
    tui.storage.save_translated_chapter(novel_id, "2", "chapter two")
    tui.storage.save_translated_chapter(novel_id, "3", "chapter three")

    chapters = tui._collect_export_chapters(novel_id, chapter_selection="2-3")

    assert [chapter["title"] for chapter in chapters] == ["Two", "Three"]


def test_export_output_path_uses_chapter_range_filename_for_partial_exports(tui: TUIApp) -> None:
    output_path = tui._build_export_output_path("novel-1", "epub", None, "2-4")

    assert output_path.endswith("full_novel_ch2to4.epub")


def test_settings_round_trip(tui: TUIApp) -> None:
    tui.settings.set_provider_key("openai")
    tui.settings.set_provider_model("gpt-5.2")
    tui.settings.set_api_key("demo-key")

    assert tui.settings.get_provider_key() == "openai"
    assert tui.settings.get_provider_model() == "gpt-5.2"
    assert tui.settings.get_api_key() == "demo-key"

    tui.settings.clear_api_key()
    assert tui.settings.get_api_key() is None


def test_settings_falls_back_to_supported_openai_model_for_legacy_preference(tui: TUIApp) -> None:
    tui.settings.set_provider_key("openai")
    tui.settings.set_provider_model("legacy-openai-model")

    assert tui.settings.get_provider_model() == "gpt-5.4"


def test_usage_service_resets_daily_but_preserves_history() -> None:
    usage_dir = Path("tests/.tmp") / f"usage_{uuid4().hex}"
    usage_dir.mkdir(parents=True, exist_ok=False)
    usage = UsageService(usage_dir)
    now = datetime.now(timezone.utc)
    two_days_ago = now - timedelta(days=2)

    try:
        usage.record(
            {
                "timestamp": two_days_ago.isoformat().replace("+00:00", "Z"),
                "provider": "openai",
                "model": "gpt-5.4",
                "tokens": 12,
            }
        )
        usage.record(
            {
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "provider": "openai",
                "model": "gpt-5.4",
                "tokens": 5,
            }
        )

        summary = usage.summary()
        history = usage.daily_history()

        assert summary["total_requests"] == 1
        assert summary["total_tokens"] == 5
        assert len(history) == 2
        assert history[0]["date"] >= history[1]["date"]
    finally:
        shutil.rmtree(usage_dir, ignore_errors=True)


def test_usage_service_summary_includes_estimate_entries() -> None:
    usage_dir = Path("tests/.tmp") / f"usage_estimate_{uuid4().hex}"
    usage_dir.mkdir(parents=True, exist_ok=False)
    usage = UsageService(usage_dir)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    try:
        usage.record(
            {
                "timestamp": now,
                "provider": "openai",
                "model": "gpt-5.4",
                "tokens": 25,
            }
        )
        usage.record(
            {
                "entry_type": "estimate",
                "timestamp": now,
                "provider": "openai",
                "model": "gpt-5.2",
                "estimated_input_tokens": 9200,
                "estimated_output_tokens": 8000,
                "estimated_total_tokens": 17200,
                "estimated_cost_usd": 0.1281,
            }
        )

        summary = usage.summary()
        history = usage.daily_history(limit=1)

        assert summary["total_requests"] == 1
        assert summary["total_tokens"] == 25
        assert summary["total_estimates"] == 1
        assert summary["estimated_total_tokens"] == 17200
        assert summary["estimated_projection_cost_usd"] == pytest.approx(0.1281)
        assert history[0]["estimated_projection_cost_usd"] == pytest.approx(0.1281)
    finally:
        shutil.rmtree(usage_dir, ignore_errors=True)


def test_diagnostics_data_is_available(tui: TUIApp) -> None:
    novels = tui.storage.list_novels()
    total_translated = sum(tui.storage.count_translated_chapters(novel_id) for novel_id in novels)

    cache_path = Path(settings.DATA_DIR) / "translation_cache.json"
    cache_entries = 0
    if cache_path.exists():
        cache_entries = len(json.loads(cache_path.read_text(encoding="utf-8")))

    usage_summary = tui.usage.summary()

    assert len(novels) >= 0
    assert total_translated >= 0
    assert cache_entries >= 0
    assert usage_summary["total_requests"] >= 0
    assert usage_summary["total_tokens"] >= 0
    assert usage_summary["estimated_cost_usd"] >= 0


def test_exporter_has_required_methods(tui: TUIApp) -> None:
    assert tui.storage.load_metadata("missing-novel") is None
    assert hasattr(tui.exporter, "export_epub")
    assert hasattr(tui.exporter, "export_pdf")


def test_missing_chapter_is_handled_gracefully(tui: TUIApp) -> None:
    assert tui.storage.load_translated_chapter("fake-novel", "1") is None


def test_tui_budget_estimate_records_usage_for_supported_model(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "Budget Story",
            "chapters": [{"id": 1}, {"id": 2}],
        },
    )
    tui.storage.save_chapter(novel_id, "1", "魔導具の光が灯った。")
    tui.storage.save_chapter(novel_id, "2", "王都で冒険者たちが再会した。")

    budget = tui._estimate_translation_budget(
        title="Add Novel",
        novel_id=novel_id,
        chapters="1-2",
        active_provider="openai",
        active_model="gpt-5.2",
        fallback_used=False,
    )

    assert budget is not None
    assert budget["chapter_count"] == 2
    assert [estimate.model_name for estimate in budget["comparison"].estimates] == ["gpt-5.2"]
    estimate_entries = [entry for entry in tui.usage.list(limit=10) if entry.get("entry_type") == "estimate"]
    assert len(estimate_entries) == 1
    assert estimate_entries[0]["model"] == "gpt-5.2"
    assert estimate_entries[0]["estimated_total_tokens"] > 0


def test_tui_budget_estimate_falls_back_to_reference_models_for_unsupported_model(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "Budget Story",
            "chapters": [{"id": 1}],
        },
    )
    tui.storage.save_chapter(novel_id, "1", "魔王城で再戦が始まる。")

    budget = tui._estimate_translation_budget(
        title="Update Novel",
        novel_id=novel_id,
        chapters="1",
        active_provider="openai",
        active_model="legacy-openai-model",
        fallback_used=False,
    )

    assert budget is not None
    assert [estimate.model_name for estimate in budget["comparison"].estimates] == ["gpt-5.2", "gpt-5.4"]
    assert budget["note"] is not None
    assert "legacy-openai-model" in budget["note"]

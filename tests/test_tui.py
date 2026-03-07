from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from rich.console import Console

from novelai.app.bootstrap import bootstrap
from novelai.config.settings import settings
from novelai.providers.registry import available_providers
from novelai.sources.registry import available_sources
from novelai.tui.app import TUIApp


@pytest.fixture
def tui() -> TUIApp:
    """Provide a bootstrapped TUI instance for tests."""
    bootstrap()
    return TUIApp()


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


def test_dashboard_render_contains_sections(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=120)
    tui.console.print(tui._build_dashboard())
    output = tui.console.export_text()

    assert "NOVELAIBOOK" in output
    assert "Control Deck" in output
    assert "Library Snapshot" in output
    assert "System Pulse" in output
    assert "Guide Rail" in output


def test_dashboard_panel_order_keeps_system_pulse_last(tui: TUIApp) -> None:
    tui.console = Console(record=True, width=140)
    tui.console.print(tui._build_dashboard())
    output = tui.console.export_text()

    assert output.index("Library Snapshot") < output.index("Control Deck") < output.index("System Pulse")


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


def test_console_width_can_be_locked_for_the_session(tui: TUIApp) -> None:
    tui.console = Console(width=137)
    tui._lock_layout_width()

    assert tui._console_width() == 137

    tui.console = Console(width=90)
    assert tui._console_width() == 137


def test_collect_library_snapshot_uses_metadata(tui: TUIApp) -> None:
    novel_id = f"novel-{uuid4().hex}"
    tui.storage.save_metadata(
        novel_id,
        {
            "title": "A Long Story",
            "translated_title": "A Better Story",
            "chapters": [{"id": 1}, {"id": 2}],
        },
    )
    tui.storage.save_translated_chapter(novel_id, "1", "hello")

    snapshots = tui._collect_library_snapshot(limit=100)
    matching = next(snapshot for snapshot in snapshots if snapshot["novel_id"] == novel_id)

    assert matching["title"] == "A Better Story"
    assert matching["total_chapters"] == 2
    assert matching["translated_chapters"] == 1


def test_settings_round_trip(tui: TUIApp) -> None:
    tui.settings.set_provider_key("openai")
    tui.settings.set_provider_model("gpt-3.5-turbo")

    assert tui.settings.get_provider_key() == "openai"
    assert tui.settings.get_provider_model() == "gpt-3.5-turbo"


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

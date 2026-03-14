from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.segment import Segment, Segments
from rich.table import Table
from rich.text import Text

from novelai.interfaces.tui.screens import (
    DiagnosticsScreenMixin,
    GlossaryScreenMixin,
    LibraryScreenMixin,
    PipelineScreenMixin,
    SettingsScreenMixin,
)
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container
from novelai.config.settings import settings
from novelai.cost_estimator.models import CostComparison
from novelai.glossary import glossary_status_counts
from novelai.providers.registry import available_providers
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.preferences_service import PreferencesService
from novelai.services.usage_service import UsageService
from novelai.sources.registry import available_sources

if os.name == "nt":
    import msvcrt


class LibrarySnapshot(TypedDict):
    """Display-ready snapshot of one novel in storage."""

    novel_id: str
    title: str
    total_chapters: int
    stored_chapters: int
    translated_chapters: int
    language: str
    glossary_total: NotRequired[int]
    glossary_reviewed: NotRequired[int]
    glossary_pending: NotRequired[int]
    ocr_required: NotRequired[int]
    ocr_reviewed: NotRequired[int]
    ocr_pending: NotRequired[int]
    ocr_failed: NotRequired[int]
    reembed_completed: NotRequired[int]
    reembed_pending: NotRequired[int]
    reembed_failed: NotRequired[int]


class MenuOption(TypedDict):
    """Display and routing metadata for one dashboard action."""

    key: str
    label: str
    description: str


class LibraryLanguageGroup(TypedDict):
    """Grouped library rows for one detected source language."""

    index: int
    language: str
    snapshots: list[LibrarySnapshot]


class TranslationBudgetEstimate(TypedDict):
    """Display-ready budget estimate for one add/update run."""

    japanese_characters: int
    chapter_count: int
    comparison: CostComparison
    note: str | None


class TUIApp(
    LibraryScreenMixin,
    PipelineScreenMixin,
    DiagnosticsScreenMixin,
    SettingsScreenMixin,
    GlossaryScreenMixin,
):
    """Rich dashboard for adding, translating, and exporting novels."""

    MENU_OPTIONS: list[MenuOption] = [
        {
            "key": "list",
            "label": "Novel Library",
            "description": "Browse stored novels and translation progress",
        },
        {
            "key": "scrape",
            "label": "Add Novel",
            "description": "Detect the source from a URL, then fetch and translate chapters",
        },
        {
            "key": "update",
            "label": "Update Novel",
            "description": "Refresh metadata, raw chapters, and translations for an existing novel",
        },
        {
            "key": "diagnostics",
            "label": "Diagnostics",
            "description": "Inspect usage, cache health, and recent activity",
        },
        {
            "key": "settings",
            "label": "Settings",
            "description": "Review or change provider, model, and API key",
        },
        {
            "key": "glossary",
            "label": "Glossary",
            "description": "Manage translation glossary terms for a novel",
        },
        {
            "key": "exit",
            "label": "Exit",
            "description": "Close the dashboard",
        },
    ]

    STATUS_STYLES = {
        "info": "#7aa2f7",
        "success": "#9ece6a",
        "warning": "#e0af68",
        "error": "#f7768e",
        "muted": "#c0caf5",
    }

    def __init__(self) -> None:
        # Ensure providers/sources are registered before any user interaction.
        bootstrap()

        self.console = Console()
        self.locked_layout_width: int | None = None
        self.storage = container.storage
        self.translation = container.translation
        self.exporter = container.export
        self.settings = PreferencesService()
        self.usage = UsageService()
        self.orchestrator = NovelOrchestrationService(self.storage, self.translation)
        self.last_status_message = "Dashboard ready. Pick an action from the control deck."
        self.last_status_kind = "info"
        self.api_validation_message = "Not validated yet."
        self.api_validation_kind = "muted"

    def run(self) -> None:
        self._lock_layout_width()
        while True:
            option = self._prompt_action()
            pause_after_action = True

            if option == "list":
                self._list_novels()
                pause_after_action = False
            elif option == "scrape":
                self._scrape_flow()
            elif option == "update":
                self._update_flow()
            elif option == "diagnostics":
                self._diagnostics_menu()
                pause_after_action = False
            elif option == "settings":
                self._settings_menu()
                pause_after_action = False
            elif option == "glossary":
                self._glossary_menu()
                pause_after_action = False
            elif option == "exit":
                self.console.clear()
                return

            if pause_after_action:
                self._pause()

    def _render_dashboard(self) -> None:
        self.console.clear()
        self.console.print(self._build_dashboard())

    def _prompt_action(self) -> str:
        menu_choices = [number for number, _ in self._menu_number_pairs()]
        if os.name != "nt":
            self._render_dashboard()
            selection = Prompt.ask(
                "[bold #f6bd60]Action[/bold #f6bd60]",
                choices=menu_choices,
                default="1",
                console=self.console,
            )
            option = self._resolve_menu_selection(selection)
            if option is None:
                raise ValueError(f"Unsupported menu selection: {selection}")
            return option
        self._lock_layout_width()
        return self._prompt_action_live()

    def _prompt_action_live(self) -> str:
        action_buffer = ""
        prompt_message: str | None = None
        last_width = -1
        last_height = -1
        needs_refresh = True
        scroll_offset = 0
        max_scroll_offset = 0

        with Live(
            console=self.console,
            screen=True,
            auto_refresh=False,
            transient=True,
            vertical_overflow="visible",
        ) as live:
            while True:
                width = self._console_width()
                height = self._console_height()
                if needs_refresh or width != last_width or height != last_height:
                    frame, max_scroll_offset = self._build_dashboard_frame(
                        action_buffer,
                        prompt_message,
                        scroll_offset,
                    )
                    clamped_scroll_offset = min(scroll_offset, max_scroll_offset)
                    if clamped_scroll_offset != scroll_offset:
                        scroll_offset = clamped_scroll_offset
                        frame, max_scroll_offset = self._build_dashboard_frame(
                            action_buffer,
                            prompt_message,
                            scroll_offset,
                        )
                    live.update(
                        frame,
                        refresh=True,
                    )
                    last_width = width
                    last_height = height
                    needs_refresh = False

                key = self._read_keypress(timeout=0.1)
                if key is None:
                    continue

                prompt_message = None

                if key == "\x03":
                    raise KeyboardInterrupt

                if key == "UP":
                    scroll_offset = max(0, scroll_offset - 1)
                    needs_refresh = True
                    continue

                if key == "DOWN":
                    scroll_offset = min(max_scroll_offset, scroll_offset + 1)
                    needs_refresh = True
                    continue

                if key == "PAGEUP":
                    scroll_offset = max(0, scroll_offset - max(self._dashboard_viewport_height(prompt_message), 1))
                    needs_refresh = True
                    continue

                if key == "PAGEDOWN":
                    scroll_offset = min(
                        max_scroll_offset,
                        scroll_offset + max(self._dashboard_viewport_height(prompt_message), 1),
                    )
                    needs_refresh = True
                    continue

                if key == "HOME":
                    scroll_offset = 0
                    needs_refresh = True
                    continue

                if key == "END":
                    scroll_offset = max_scroll_offset
                    needs_refresh = True
                    continue

                if key in ("\r", "\n"):
                    option = self._resolve_menu_selection(action_buffer)
                    if option is not None:
                        return option
                    prompt_message = f"Unknown action '{action_buffer.strip() or '1'}'."
                    needs_refresh = True
                    continue

                if key == "\t":
                    completed = self._autocomplete_action(action_buffer)
                    if completed != action_buffer:
                        action_buffer = completed
                    elif action_buffer:
                        prompt_message = "No matching menu number."
                    needs_refresh = True
                    continue

                if key in ("\x08", "\x7f"):
                    action_buffer = action_buffer[:-1]
                    needs_refresh = True
                    continue

                if key in ("\x15", "\x1b"):
                    action_buffer = ""
                    needs_refresh = True
                    continue

                if key.isdigit():
                    action_buffer += key
                    needs_refresh = True

    def _build_dashboard_frame(
        self,
        action_buffer: str,
        prompt_message: str | None,
        scroll_offset: int,
    ) -> tuple[Group, int]:
        viewport_height = self._dashboard_viewport_height(prompt_message)
        dashboard_view, max_scroll_offset = self._build_dashboard_viewport(
            scroll_offset,
            viewport_height,
        )
        prompt_panel = self._build_action_prompt_panel(
            action_buffer,
            prompt_message,
            scroll_offset,
            max_scroll_offset,
        )
        return Group(dashboard_view, prompt_panel), max_scroll_offset

    def _build_action_prompt_panel(
        self,
        action_buffer: str,
        prompt_message: str | None,
        scroll_offset: int,
        max_scroll_offset: int,
    ) -> Panel:
        return self._build_input_prompt_panel("Action", action_buffer, "1", prompt_message)

    def _build_input_prompt_panel(
        self,
        label: str,
        current_value: str,
        default_value: str,
        prompt_message: str | None,
    ) -> Panel:
        input_text = Text.assemble(
            (f"{label}  ", "#9aa5ce"),
            (current_value or default_value, "bold #f6bd60" if current_value else "#7aa2f7"),
            (" ", "reverse"),
        )
        body: list[Text] = [input_text]

        if prompt_message:
            body.append(Text(prompt_message, style="bold #e0af68"))

        return Panel(
            Group(*body),
            title="Command Line",
            border_style="#e0af68" if prompt_message else "#7aa2f7",
            box=box.ROUNDED,
            expand=True,
            width=self._console_width(),
        )

    def _prompt_renderable_command(
        self,
        renderable: Any,
        *,
        default_value: str = "0",
        label: str = "Command",
        extra_allowed_characters: str = "",
        allow_any_printable: bool = False,
    ) -> str:
        if os.name != "nt":
            self.console.clear()
            self.console.print(renderable)
            return Prompt.ask(
                f"[bold #f6bd60]{label}[/bold #f6bd60]",
                default=default_value,
                console=self.console,
            )
        return self._prompt_renderable_command_live(
            renderable,
            default_value=default_value,
            label=label,
            extra_allowed_characters=extra_allowed_characters,
            allow_any_printable=allow_any_printable,
        )

    def _prompt_renderable_command_live(
        self,
        renderable: Any,
        *,
        default_value: str,
        label: str,
        extra_allowed_characters: str,
        allow_any_printable: bool,
    ) -> str:
        command_buffer = ""
        prompt_message: str | None = None
        last_height = -1
        needs_refresh = True
        scroll_offset = 0
        max_scroll_offset = 0

        with Live(
            console=self.console,
            screen=True,
            auto_refresh=False,
            transient=True,
            vertical_overflow="visible",
        ) as live:
            while True:
                height = self._console_height()
                if needs_refresh or height != last_height:
                    viewport_height = self._command_viewport_height(prompt_message)
                    renderable_view, max_scroll_offset = self._build_renderable_viewport(
                        renderable,
                        scroll_offset,
                        viewport_height,
                    )
                    clamped_scroll_offset = min(scroll_offset, max_scroll_offset)
                    if clamped_scroll_offset != scroll_offset:
                        scroll_offset = clamped_scroll_offset
                        renderable_view, max_scroll_offset = self._build_renderable_viewport(
                            renderable,
                            scroll_offset,
                            viewport_height,
                        )

                    prompt_panel = self._build_input_prompt_panel(
                        label,
                        command_buffer,
                        default_value,
                        prompt_message,
                    )
                    live.update(Group(renderable_view, prompt_panel), refresh=True)
                    last_height = height
                    needs_refresh = False

                key = self._read_keypress(timeout=0.1)
                if key is None:
                    continue

                prompt_message = None

                if key == "\x03":
                    raise KeyboardInterrupt

                if key == "UP":
                    scroll_offset = max(0, scroll_offset - 1)
                    needs_refresh = True
                    continue

                if key == "DOWN":
                    scroll_offset = min(max_scroll_offset, scroll_offset + 1)
                    needs_refresh = True
                    continue

                if key == "PAGEUP":
                    scroll_offset = max(0, scroll_offset - max(self._command_viewport_height(prompt_message), 1))
                    needs_refresh = True
                    continue

                if key == "PAGEDOWN":
                    scroll_offset = min(
                        max_scroll_offset,
                        scroll_offset + max(self._command_viewport_height(prompt_message), 1),
                    )
                    needs_refresh = True
                    continue

                if key == "HOME":
                    scroll_offset = 0
                    needs_refresh = True
                    continue

                if key == "END":
                    scroll_offset = max_scroll_offset
                    needs_refresh = True
                    continue

                if key in ("\r", "\n"):
                    return command_buffer.strip() or default_value

                if key in ("\x08", "\x7f"):
                    command_buffer = command_buffer[:-1]
                    needs_refresh = True
                    continue

                if key in ("\x15", "\x1b"):
                    command_buffer = ""
                    needs_refresh = True
                    continue

                if len(key) == 1 and (
                    (allow_any_printable and key.isprintable() and key not in ("\r", "\n", "\t"))
                    or key.isdigit()
                    or key in extra_allowed_characters
                ):
                    command_buffer += key
                    needs_refresh = True

    def _command_viewport_height(self, prompt_message: str | None) -> int:
        reserved_height = 5 if prompt_message else 4
        return max(self._console_height() - reserved_height, 10)

    def _build_dashboard_viewport(self, scroll_offset: int, viewport_height: int) -> tuple[Segments, int]:
        return self._build_renderable_viewport(self._build_dashboard(), scroll_offset, viewport_height)

    def _build_renderable_viewport(
        self,
        renderable: Any,
        scroll_offset: int,
        viewport_height: int,
        *,
        width: int | None = None,
    ) -> tuple[Segments, int]:
        render_width = width or self._console_width()
        renderable_lines = self.console.render_lines(
            renderable,
            options=self.console.options.update_dimensions(
                render_width,
                self._console_height(),
            ),
            pad=False,
            new_lines=False,
        )
        max_scroll_offset = max(0, len(renderable_lines) - viewport_height)
        clamped_offset = min(max(scroll_offset, 0), max_scroll_offset)
        visible_lines = renderable_lines[clamped_offset : clamped_offset + viewport_height]

        segments: list[Segment] = []
        for index, line in enumerate(visible_lines):
            segments.extend(line)
            if index < len(visible_lines) - 1:
                segments.append(Segment.line())
        if visible_lines:
            segments.append(Segment.line())

        return Segments(segments), max_scroll_offset

    def _dashboard_viewport_height(self, prompt_message: str | None) -> int:
        reserved_height = 5 if prompt_message else 4
        return max(self._console_height() - reserved_height, 10)

    def _build_dashboard(self) -> Group:
        """Compose the dashboard landing screen."""
        return Group(
            self._build_header_panel(),
            self._build_overview_panels(),
            self._build_primary_panels(),
            self._build_status_panel(),
        )

    def _build_header_panel(self) -> Panel:
        title = Text("NOVELAIBOOK", style="bold #f6bd60")
        subtitle = Text(
            "A reading-room dashboard for scraping, translating, and exporting web novels.",
            style="#d9d7ce",
        )
        provider_line = Text.assemble(
            ("Provider  ", "#9aa5ce"),
            (self.settings.get_provider_key(), "bold #7dcfff"),
            (" / ", "#9aa5ce"),
            (self.settings.get_provider_model(), "#e5e9f0"),
        )
        library_line = Text.assemble(
            ("Library  ", "#9aa5ce"),
            (self._short_path(settings.DATA_DIR), "bold #73daca"),
        )

        if self._console_width() < 150:
            content = Group(
                title,
                subtitle,
                Text(""),
                provider_line,
                library_line,
            )
        else:
            grid = Table.grid(expand=True)
            grid.add_column(ratio=2)
            grid.add_column(justify="right")
            grid.add_row(
                Group(title, subtitle),
                Group(Align.right(provider_line), Align.right(library_line)),
            )
            content = grid

        return Panel(
            content,
            title="Reading Room",
            border_style="#f6bd60",
            box=box.ROUNDED,
            padding=(1, 2),
            style="on #1b1e2b",
            expand=True,
        )

    def _build_overview_panels(self) -> Group | Columns:
        novels = self.storage.list_novels()
        total_translated = sum(self.storage.count_translated_chapters(novel_id) for novel_id in novels)
        usage_summary = self.usage.summary()

        cards = [
            ("Novels", str(len(novels)), "#f6bd60"),
            ("Translated", str(total_translated), "#9ece6a"),
            ("Sources", str(len(available_sources())), "#7dcfff"),
            ("Requests", str(usage_summary.get("total_requests", 0)), "#bb9af7"),
        ]
        width = self._console_width()

        if width < 76:
            return Group(*(self._build_metric_panel(label, value, accent) for label, value, accent in cards))
        if width < 100:
            return Group(
                self._build_metric_row(cards[:2]),
                self._build_metric_row(cards[2:]),
            )
        return self._build_metric_row(cards)

    def _build_primary_panels(self) -> Group:
        width = self._console_width()
        library_panel = self._build_library_panel(width)

        if width < 120:
            return Group(
                library_panel,
                self._build_actions_panel(width),
                self._build_system_panel(width),
            )

        control_width, system_width = self._split_row_width(width, (3, 2))
        control_panel, system_panel = self._build_balanced_primary_row(control_width, system_width)
        secondary_row = Columns(
            [
                control_panel,
                system_panel,
            ],
            expand=True,
            equal=False,
            padding=(0, 1),
        )
        return Group(library_panel, secondary_row)

    def _build_balanced_primary_row(self, control_width: int, system_width: int) -> tuple[Panel, Panel]:
        control_panel = self._build_actions_panel(control_width)
        system_panel = self._build_system_panel(system_width)
        shared_height = max(
            self._renderable_height(control_panel, width=control_width),
            self._renderable_height(system_panel, width=system_width),
        )
        return (
            self._build_actions_panel(control_width, height=shared_height),
            self._build_system_panel(system_width, height=shared_height),
        )

    def _build_metric_row(self, cards: list[tuple[str, str, str]]) -> Columns:
        widths = self._split_row_width(self._console_width(), [1] * len(cards))
        panels = [
            self._build_metric_panel(label, value, accent, width=width)
            for (label, value, accent), width in zip(cards, widths, strict=True)
        ]
        return Columns(panels, expand=True, equal=False, padding=(0, 1))

    def _build_metric_panel(self, label: str, value: str, accent: str, width: int | None = None) -> Panel:
        body = Group(
            Align.center(Text(value, style=f"bold {accent}"), vertical="middle"),
            Align.center(Text(label.upper(), style="#c0caf5")),
        )
        return Panel(
            body,
            border_style=accent,
            box=box.ROUNDED,
            padding=(1, 1),
            expand=True,
            width=width,
        )

    def _build_actions_panel(self, width: int | None = None, height: int | None = None) -> Panel:
        panel_width = width or self._console_width()
        numbered_options = self._menu_number_pairs()

        if panel_width < 88:
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style="bold #f6bd60", no_wrap=True)
            grid.add_column(style="#cbd5e1")

            for number, option in numbered_options:
                grid.add_row(f"{number}) {option['label']}", option["description"])

            return Panel(
                grid,
                title="Control Deck",
                border_style="#7aa2f7",
                box=box.ROUNDED,
                expand=True,
                width=width,
                height=height,
            )

        table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #f6bd60")
        table.add_column("Action", style="bold #e5e9f0", no_wrap=True)
        table.add_column("What It Does", style="#cbd5e1")

        for number, option in numbered_options:
            table.add_row(f"{number}) {option['label']}", option["description"])

        return Panel(
            table,
            title="Control Deck",
            border_style="#7aa2f7",
            box=box.ROUNDED,
            expand=True,
            width=width,
            height=height,
        )

    def _build_library_panel(self, width: int | None = None) -> Panel:
        snapshots = self._collect_library_snapshot(limit=6)
        panel_width = width or self._console_width()
        if not snapshots:
            empty = Text(
                "No novels are stored yet.\nUse Add Novel to pull metadata and chapters into the library.",
                style="#cbd5e1",
            )
            return Panel(
                Align.left(empty),
                title="Library Snapshot",
                border_style="#9ece6a",
                box=box.ROUNDED,
                padding=(1, 1),
                expand=True,
                width=width,
            )

        if panel_width < 95:
            lines: list[Text] = []
            title_width = max(panel_width - 18, 16)
            id_width = max(panel_width - 22, 12)

            for snapshot in snapshots:
                progress = self._snapshot_progress_text(snapshot)
                lines.append(
                    Text.assemble(
                        ("Novel Title: ", "#9ece6a"),
                        (self._truncate(snapshot["title"], title_width), "bold #e5e9f0"),
                    )
                )
                lines.append(
                    Text.assemble(
                        ("Novel ID: ", "#9ece6a"),
                        (self._truncate(snapshot["novel_id"], id_width), "#73daca"),
                        ("  ", "#cbd5e1"),
                        (progress, "#f6bd60"),
                    )
                )
                lines.append(Text(""))

            return Panel(
                Group(*lines[:-1]),
                title="Library Snapshot",
                border_style="#9ece6a",
                box=box.ROUNDED,
                expand=True,
                width=width,
            )

        if panel_width < 125:
            table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #9ece6a")
            table.add_column("Novel Title", style="bold #e5e9f0")
            table.add_column("Novel ID", style="#73daca")
            table.add_column("Progress", justify="right", style="#f6bd60", no_wrap=True)

            for snapshot in snapshots:
                table.add_row(
                    self._truncate(snapshot["title"], 28),
                    self._truncate(snapshot["novel_id"], 20),
                    self._snapshot_progress_text(snapshot),
                )

            return Panel(
                table,
                title="Library Snapshot",
                border_style="#9ece6a",
                box=box.ROUNDED,
                expand=True,
                width=width,
            )

        table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #9ece6a")
        table.add_column("Novel Title", style="bold #e5e9f0")
        table.add_column("Novel ID", style="#73daca", no_wrap=True)
        table.add_column("Source", justify="right", style="#73daca", no_wrap=True)
        table.add_column("Stored", justify="right", style="#7dcfff", no_wrap=True)
        table.add_column("Tl", justify="right", style="#f6bd60", no_wrap=True)
        table.add_column("Glossary", justify="right", style="#e0af68", no_wrap=True)
        table.add_column("Media", justify="right", style="#bb9af7", no_wrap=True)

        for snapshot in snapshots:
            table.add_row(
                self._truncate(snapshot["title"], 28),
                snapshot["novel_id"],
                str(snapshot["total_chapters"]),
                str(self._snapshot_stored_chapters(snapshot)),
                str(snapshot["translated_chapters"]),
                self._snapshot_glossary_review_text(snapshot),
                self._snapshot_media_overview_text(snapshot),
            )

        return Panel(
            table,
            title="Library Snapshot",
            border_style="#9ece6a",
            box=box.ROUNDED,
            expand=True,
            width=width,
        )

    def _build_system_panel(self, width: int | None = None, height: int | None = None) -> Panel:
        summary = self.usage.summary()
        panel_width = width or self._console_width()
        recent_usage = self.usage.list(limit=3)

        if panel_width < 72:
            details = [
                ("Provider", self.settings.get_provider_key()),
                ("Model", self.settings.get_provider_model()),
                ("API Key", "configured" if self.settings.get_api_key() else "missing"),
                ("Library", self._short_path(settings.DATA_DIR)),
                ("Providers", ", ".join(available_providers()) or "none"),
                ("Sources", ", ".join(available_sources()) or "none"),
                ("Cost", f"${summary.get('estimated_cost_usd', 0):.6f}"),
                ("Budget", f"${summary.get('estimated_projection_cost_usd', 0):.6f}"),
            ]
            lines: list[Text] = [
                Text.assemble((f"{label}: ", "#f6bd60"), (value, "#e5e9f0"))
                for label, value in details
            ]
            lines.append(Text(""))
            lines.append(Text("Recent", style="bold #7dcfff"))

            if recent_usage:
                for entry in reversed(recent_usage):
                    label = f"{entry.get('provider', '?')}/{entry.get('model', '?')}"
                    lines.append(
                        Text.assemble(
                            (self._truncate(label, max(panel_width - 18, 16)), "#cbd5e1"),
                            ("  ", "#cbd5e1"),
                            (self._usage_entry_metric(entry), "#f6bd60"),
                        )
                    )
            else:
                lines.append(Text("No usage yet", style="#cbd5e1"))

            return Panel(
                Group(*lines),
                title="System Pulse",
                border_style="#bb9af7",
                box=box.ROUNDED,
                expand=True,
                width=width,
                height=height,
            )

        if panel_width < 100:
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style="bold #f6bd60", no_wrap=True)
            grid.add_column(style="#e5e9f0")
            grid.add_row("Provider", self.settings.get_provider_key())
            grid.add_row("Model", self.settings.get_provider_model())
            grid.add_row("API Key", "configured" if self.settings.get_api_key() else "missing")
            grid.add_row("Library", self._short_path(settings.DATA_DIR))
            grid.add_row("Sources", ", ".join(available_sources()) or "none")
            grid.add_row("Cost", f"${summary.get('estimated_cost_usd', 0):.6f}")
            grid.add_row("Budget", f"${summary.get('estimated_projection_cost_usd', 0):.6f}")

            recent = Text("Recent  ", style="bold #7dcfff")
            if recent_usage:
                recent_items = [
                    Text.assemble(
                        (self._truncate(f"{entry.get('provider', '?')}/{entry.get('model', '?')}", 18), "#cbd5e1"),
                        ("  ", "#cbd5e1"),
                        (self._usage_entry_metric(entry), "#f6bd60"),
                    )
                    for entry in reversed(recent_usage)
                ]
            else:
                recent_items = [Text("No usage yet", style="#cbd5e1")]

            return Panel(
                Group(grid, Text(""), recent, *recent_items),
                title="System Pulse",
                border_style="#bb9af7",
                box=box.ROUNDED,
                expand=True,
                width=width,
                height=height,
            )

        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(style="bold #f6bd60", no_wrap=True)
        grid.add_column(style="#e5e9f0")
        grid.add_row("Provider", self.settings.get_provider_key())
        grid.add_row("Model", self.settings.get_provider_model())
        grid.add_row("API Key", "configured" if self.settings.get_api_key() else "missing")
        grid.add_row("Library", self._short_path(settings.DATA_DIR))
        grid.add_row("Providers", ", ".join(available_providers()) or "none")
        grid.add_row("Sources", ", ".join(available_sources()) or "none")
        grid.add_row("Cost", f"${summary.get('estimated_cost_usd', 0):.6f}")
        grid.add_row("Budget", f"${summary.get('estimated_projection_cost_usd', 0):.6f}")

        usage_table = Table(box=box.SIMPLE, expand=True, show_header=True, header_style="bold #7dcfff")
        usage_table.add_column("Recent")
        usage_table.add_column("Tokens", justify="right", style="#f6bd60")
        usage_table.add_column("Type", style="#9ece6a")

        if recent_usage:
            for entry in reversed(recent_usage):
                label = f"{entry.get('provider', '?')}/{entry.get('model', '?')}"
                usage_table.add_row(label, self._usage_entry_metric(entry), self._usage_entry_type_label(entry))
        else:
            usage_table.add_row("No usage yet", "-", "-")

        return Panel(
            Group(grid, Text(""), usage_table),
            title="System Pulse",
            border_style="#bb9af7",
            box=box.ROUNDED,
            expand=True,
            width=width,
            height=height,
        )

    def _build_status_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        status_line = Text.assemble(
            ("Status  ", "#9aa5ce"),
            (self.last_status_message, f"bold {status_style}"),
        )
        if self._console_width() < 90:
            help_line = Text(
                "Actions: 1-5, 0.",
                style="#cbd5e1",
            )
        else:
            help_line = Text(
                "Type 1-5 to choose Novel Library, Add Novel, Update Novel, Diagnostics, Settings, or 0 to Exit.",
                style="#cbd5e1",
            )
        return Panel(
            Group(status_line, help_line),
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _build_action_header(self, title: str, description: str) -> Panel:
        content = Group(
            Text(title.upper(), style="bold #f6bd60"),
            Text(description, style="#d9d7ce"),
        )
        return Panel(
            content,
            border_style="#f6bd60",
            box=box.ROUNDED,
            padding=(1, 2),
        )

    def _pause(self) -> None:
        self.console.input("[#9aa5ce]Press Enter to return to the dashboard...[/#9aa5ce] ")

    def _set_status(self, message: str, kind: str = "info") -> None:
        self.last_status_message = message
        self.last_status_kind = kind

    def _show_error(self, message: str) -> None:
        self.console.print(
            Panel(
                message,
                title="Error",
                border_style=self.STATUS_STYLES["error"],
                box=box.ROUNDED,
            )
        )
        self._set_status(message, "error")

    def _collect_library_snapshot(self, limit: int) -> list[LibrarySnapshot]:
        novels: list[tuple[float, str, dict[str, Any]]] = []
        for novel_id in self.storage.list_novels():
            metadata = self.storage.load_metadata(novel_id) or {}
            novels.append((self._library_snapshot_added_at(metadata), novel_id, metadata))

        novels.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)

        snapshots: list[LibrarySnapshot] = []
        for _, novel_id, metadata in novels[:limit]:
            raw_chapters = metadata.get("chapters", [])
            total_chapters = len(raw_chapters) if isinstance(raw_chapters, list) else 0
            title = metadata.get("translated_title") or metadata.get("title") or novel_id
            glossary_counts = glossary_status_counts(self.storage.load_glossary(novel_id))
            media_counts = self._snapshot_media_counts(novel_id)
            snapshots.append(
                {
                    "novel_id": novel_id,
                    "title": str(title),
                    "total_chapters": total_chapters,
                    "stored_chapters": self.storage.count_stored_chapters(novel_id),
                    "translated_chapters": self.storage.count_translated_chapters(novel_id),
                    "language": self._detect_novel_language(metadata),
                    "glossary_total": glossary_counts["total"],
                    "glossary_reviewed": glossary_counts["reviewed"],
                    "glossary_pending": glossary_counts["pending"],
                    "ocr_required": media_counts["ocr_required"],
                    "ocr_reviewed": media_counts["ocr_reviewed"],
                    "ocr_pending": media_counts["ocr_pending"],
                    "ocr_failed": media_counts["ocr_failed"],
                    "reembed_completed": media_counts["reembed_completed"],
                    "reembed_pending": media_counts["reembed_pending"],
                    "reembed_failed": media_counts["reembed_failed"],
                }
            )
        return snapshots

    def _snapshot_media_counts(self, novel_id: str) -> dict[str, int]:
        counts = {
            "ocr_required": 0,
            "ocr_reviewed": 0,
            "ocr_pending": 0,
            "ocr_failed": 0,
            "reembed_completed": 0,
            "reembed_pending": 0,
            "reembed_failed": 0,
        }

        for chapter_id in self.storage.list_stored_chapters(novel_id):
            media_state = self.storage.load_chapter_media_state(novel_id, chapter_id)
            if media_state is None:
                continue

            if bool(media_state.get("ocr_required", False)):
                counts["ocr_required"] += 1

            ocr_status = str(media_state.get("ocr_status") or "skipped").strip().lower()
            if ocr_status == "reviewed":
                counts["ocr_reviewed"] += 1
            elif ocr_status == "pending":
                counts["ocr_pending"] += 1
            elif ocr_status == "failed":
                counts["ocr_failed"] += 1

            reembed_status = str(media_state.get("reembed_status") or "skipped").strip().lower()
            if reembed_status == "completed":
                counts["reembed_completed"] += 1
            elif reembed_status == "pending":
                counts["reembed_pending"] += 1
            elif reembed_status == "failed":
                counts["reembed_failed"] += 1

        return counts

    def _library_snapshot_added_at(self, metadata: dict[str, Any]) -> float:
        for key in ("scraped_at", "created_at", "added_at", "updated_at"):
            timestamp = self._parse_iso_timestamp(metadata.get(key))
            if timestamp is not None:
                return timestamp
        return 0.0

    def _parse_iso_timestamp(self, value: Any) -> float | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return None

    def _detect_novel_language(self, metadata: dict[str, Any]) -> str:
        for key in ("language", "source_language", "lang"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().title()

        source_value = metadata.get("source") or metadata.get("source_key")
        if isinstance(source_value, str):
            normalized_source = source_value.strip().lower()
            source_language_map = {
                "syosetu_ncode": "Japanese",
                "novel18_syosetu": "Japanese",
                "kakuyomu": "Japanese",
                "narou": "Japanese",
            }
            if normalized_source in source_language_map:
                return source_language_map[normalized_source]

        title = metadata.get("title") or metadata.get("translated_title") or ""
        if isinstance(title, str) and self._contains_japanese_characters(title):
            return "Japanese"
        return "Unknown"

    def _usage_entry_type_label(self, entry: dict[str, Any]) -> str:
        return "Estimate" if str(entry.get("entry_type", "")).strip().lower() == "estimate" else "Usage"

    def _usage_entry_metric(self, entry: dict[str, Any]) -> str:
        if str(entry.get("entry_type", "")).strip().lower() == "estimate":
            total_tokens = entry.get("estimated_total_tokens")
            if not isinstance(total_tokens, int):
                total_tokens = int(entry.get("estimated_input_tokens", 0) or 0) + int(
                    entry.get("estimated_output_tokens", 0) or 0
                )
            return f"~{total_tokens} est"
        return f"{entry.get('tokens', 0) or 0} tokens"

    def _usage_entry_cost_usd(self, entry: dict[str, Any]) -> float:
        if str(entry.get("entry_type", "")).strip().lower() == "estimate":
            value = entry.get("estimated_cost_usd", 0)
            return float(value) if isinstance(value, (int, float)) else 0.0
        value = entry.get("actual_cost_usd")
        if isinstance(value, (int, float)):
            return float(value)
        tokens = entry.get("tokens", 0)
        token_count = int(tokens) if isinstance(tokens, (int, float)) else 0
        return token_count * settings.COST_PER_TOKEN_USD

    def _contains_japanese_characters(self, value: str) -> bool:
        return any(
            "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff"
            for char in value
        )

    def _order_library_snapshots(self, snapshots: list[LibrarySnapshot]) -> list[LibrarySnapshot]:
        return sorted(
            snapshots,
            key=lambda snapshot: (
                snapshot["language"].lower(),
                snapshot["title"].lower(),
                snapshot["novel_id"].lower(),
            ),
        )

    def _group_library_snapshots(self, snapshots: list[LibrarySnapshot]) -> list[LibraryLanguageGroup]:
        ordered = self._order_library_snapshots(snapshots)
        groups: list[LibraryLanguageGroup] = []

        for snapshot in ordered:
            if groups and groups[-1]["language"] == snapshot["language"]:
                groups[-1]["snapshots"].append(snapshot)
                continue

            groups.append(
                {
                    "index": len(groups) + 1,
                    "language": snapshot["language"],
                    "snapshots": [snapshot],
                }
            )
        return groups

    def _short_path(self, path: Path, max_length: int = 44) -> str:
        path_text = str(path)
        if len(path_text) <= max_length:
            return path_text
        return f"...{path_text[-(max_length - 3):]}"

    def _console_width(self) -> int:
        width = self.locked_layout_width or self.console.size.width
        return max(width, 60)

    def _console_height(self) -> int:
        return max(self.console.size.height, 20)

    def _lock_layout_width(self) -> None:
        if self.locked_layout_width is None:
            self.locked_layout_width = max(self.console.size.width, 60)

    def _split_row_width(self, total_width: int, ratios: tuple[int, ...] | list[int]) -> list[int]:
        gap_width = 3
        inner_width = max(total_width - gap_width * (len(ratios) - 1), len(ratios) * 12)
        ratio_total = sum(ratios)
        widths = [inner_width * ratio // ratio_total for ratio in ratios]
        remainder = inner_width - sum(widths)

        for index in range(remainder):
            widths[index % len(widths)] += 1

        return widths

    def _menu_number_pairs(self) -> list[tuple[str, MenuOption]]:
        numbered_options: list[tuple[str, MenuOption]] = []
        action_number = 1
        for option in self.MENU_OPTIONS:
            if option["key"] == "exit":
                continue
            numbered_options.append((str(action_number), option))
            action_number += 1

        exit_option = next(option for option in self.MENU_OPTIONS if option["key"] == "exit")
        numbered_options.append(("0", exit_option))
        return numbered_options

    def _autocomplete_action(self, action_buffer: str) -> str:
        prefix = action_buffer.strip()
        if not prefix:
            return action_buffer

        matches = [number for number, _ in self._menu_number_pairs() if number.startswith(prefix)]
        if len(matches) == 1:
            return matches[0]
        return action_buffer

    def _resolve_menu_selection(self, action_buffer: str) -> str | None:
        raw_value = action_buffer.strip() or "1"
        if not raw_value.isdigit():
            return None

        for number, option in self._menu_number_pairs():
            if raw_value == number:
                return option["key"]
        return None

    def _read_keypress(self, timeout: float) -> str | None:
        if os.name != "nt":
            time.sleep(timeout)
            return None

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    extended = msvcrt.getwch()
                    mapping = {
                        "H": "UP",
                        "P": "DOWN",
                        "I": "PAGEUP",
                        "Q": "PAGEDOWN",
                        "G": "HOME",
                        "O": "END",
                    }
                    return mapping.get(extended)
                return key
            time.sleep(0.02)
        return None

    def _truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return f"{value[: max_length - 3]}..."


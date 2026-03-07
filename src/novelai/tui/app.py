from __future__ import annotations

import asyncio
import json
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any, Callable, TypedDict

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

from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.config.settings import settings
from novelai.export.registry import available_exporters
from novelai.providers.registry import available_models as available_provider_models
from novelai.providers.registry import available_providers
from novelai.providers.registry import get_provider
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.settings_service import SettingsService
from novelai.services.usage_service import UsageService
from novelai.sources.registry import available_sources, detect_source, get_source
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection

if os.name == "nt":
    import msvcrt


class LibrarySnapshot(TypedDict):
    """Display-ready snapshot of one novel in storage."""

    novel_id: str
    title: str
    total_chapters: int
    translated_chapters: int
    language: str


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


class TUIApp:
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
        self.settings = SettingsService()
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
        secondary_row = Columns(
            [
                self._build_actions_panel(control_width),
                self._build_system_panel(system_width),
            ],
            expand=True,
            equal=False,
            padding=(0, 1),
        )
        return Group(library_panel, secondary_row)

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

    def _build_actions_panel(self, width: int | None = None) -> Panel:
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
                progress = f"{snapshot['translated_chapters']}/{snapshot['total_chapters']} translated"
                lines.append(
                    Text(self._truncate(snapshot["title"], title_width), style="bold #e5e9f0")
                )
                lines.append(
                    Text.assemble(
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
            table.add_column("Novel", style="bold #e5e9f0")
            table.add_column("Title", style="#cbd5e1")
            table.add_column("Progress", justify="right", style="#f6bd60", no_wrap=True)

            for snapshot in snapshots:
                table.add_row(
                    self._truncate(snapshot["novel_id"], 20),
                    self._truncate(snapshot["title"], 28),
                    f"{snapshot['translated_chapters']}/{snapshot['total_chapters']}",
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
        table.add_column("Novel", style="bold #e5e9f0", no_wrap=True)
        table.add_column("Title", style="#cbd5e1")
        table.add_column("Ch", justify="right", style="#73daca", no_wrap=True)
        table.add_column("Tl", justify="right", style="#f6bd60", no_wrap=True)

        for snapshot in snapshots:
            table.add_row(
                snapshot["novel_id"],
                self._truncate(snapshot["title"], 28),
                str(snapshot["total_chapters"]),
                str(snapshot["translated_chapters"]),
            )

        return Panel(
            table,
            title="Library Snapshot",
            border_style="#9ece6a",
            box=box.ROUNDED,
            expand=True,
            width=width,
        )

    def _build_system_panel(self, width: int | None = None) -> Panel:
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
                            (f"{entry.get('tokens', 0)} tokens", "#f6bd60"),
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

            recent = Text("Recent  ", style="bold #7dcfff")
            if recent_usage:
                recent_items = [
                    Text.assemble(
                        (self._truncate(f"{entry.get('provider', '?')}/{entry.get('model', '?')}", 18), "#cbd5e1"),
                        ("  ", "#cbd5e1"),
                        (str(entry.get("tokens", 0)), "#f6bd60"),
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

        usage_table = Table(box=box.SIMPLE, expand=True, show_header=True, header_style="bold #7dcfff")
        usage_table.add_column("Recent")
        usage_table.add_column("Tokens", justify="right", style="#f6bd60")

        if recent_usage:
            for entry in reversed(recent_usage):
                label = f"{entry.get('provider', '?')}/{entry.get('model', '?')}"
                usage_table.add_row(label, str(entry.get("tokens", 0)))
        else:
            usage_table.add_row("No usage yet", "-")

        return Panel(
            Group(grid, Text(""), usage_table),
            title="System Pulse",
            border_style="#bb9af7",
            box=box.ROUNDED,
            expand=True,
            width=width,
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
        snapshots: list[LibrarySnapshot] = []
        for novel_id in self.storage.list_novels()[:limit]:
            metadata = self.storage.load_metadata(novel_id) or {}
            raw_chapters = metadata.get("chapters", [])
            total_chapters = len(raw_chapters) if isinstance(raw_chapters, list) else 0
            title = metadata.get("translated_title") or metadata.get("title") or novel_id
            snapshots.append(
                {
                    "novel_id": novel_id,
                    "title": str(title),
                    "total_chapters": total_chapters,
                    "translated_chapters": self.storage.count_translated_chapters(novel_id),
                    "language": self._detect_novel_language(metadata),
                }
            )
        return snapshots

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
                "kakuyomu": "Japanese",
                "narou": "Japanese",
            }
            if normalized_source in source_language_map:
                return source_language_map[normalized_source]

        title = metadata.get("title") or metadata.get("translated_title") or ""
        if isinstance(title, str) and self._contains_japanese_characters(title):
            return "Japanese"
        return "Unknown"

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

    def _list_novels(self) -> None:
        self._set_status(
            "Use 1) export, 2) delete custom, 3) delete all, or 0) back.",
            "info",
        )
        while True:
            snapshots = self._order_library_snapshots(self._collect_library_snapshot(limit=200))
            groups = self._group_library_snapshots(snapshots)

            if not snapshots:
                self._set_status("The library is empty.", "warning")

            command = self._prompt_library_command(snapshots, groups)
            action = self._parse_library_command(command)

            if action is None:
                self._set_status("Unknown library command. Use 1, 2, 3, or 0.", "warning")
                continue

            if action == "back":
                self._set_status(f"Showing {len(snapshots)} novel(s) from the library.", "info")
                return

            if action == "delete_all":
                if not snapshots:
                    self._set_status("There are no novels to delete.", "warning")
                    continue
                if self._confirm_library_action(f"Delete all {len(snapshots)} novels from the library?"):
                    deleted = self._delete_library_novels(
                        snapshots,
                        list(range(1, len(snapshots) + 1)),
                    )
                    self._set_status(f"Deleted {len(deleted)} novel(s) from the library.", "success")
                else:
                    self._set_status("Delete all cancelled.", "warning")
                continue

            if action == "export":
                if not snapshots:
                    self._set_status("There are no novels to export.", "warning")
                    continue
                self._export_library_novels(snapshots, groups)
                continue

            if not snapshots:
                self._set_status("There are no novels to delete.", "warning")
                continue

            self._delete_custom_library_novels(snapshots, groups)

    def _build_library_screen(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> Group:
        return Group(
            self._build_library_header_panel(),
            self._build_library_list_panel(snapshots, groups),
            self._build_library_guide_panel(),
        )

    def _build_library_header_panel(self, compact: bool = False) -> Panel:
        description = "Browse stored novels, export selections, and manage what stays in the library."
        return Panel(
            Group(
                Text("LIBRARY", style="bold #f6bd60"),
                Text(description, style="#d9d7ce"),
            ),
            border_style="#f6bd60",
            box=box.ROUNDED,
            padding=(0, 2) if compact else (1, 2),
            expand=True,
        )

    def _prompt_library_command(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> str:
        if os.name != "nt":
            self.console.clear()
            self.console.print(self._build_library_screen(snapshots, groups))
            return Prompt.ask(
                "[bold #f6bd60]Command[/bold #f6bd60]",
                default="0",
                console=self.console,
            )
        return self._prompt_library_command_live(snapshots, groups)

    def _prompt_library_command_live(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
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
                    frame, max_scroll_offset = self._build_library_frame(
                        snapshots,
                        groups,
                        command_buffer,
                        prompt_message,
                        scroll_offset,
                    )
                    clamped_scroll_offset = min(scroll_offset, max_scroll_offset)
                    if clamped_scroll_offset != scroll_offset:
                        scroll_offset = clamped_scroll_offset
                        frame, max_scroll_offset = self._build_library_frame(
                            snapshots,
                            groups,
                            command_buffer,
                            prompt_message,
                            scroll_offset,
                        )
                    live.update(frame, refresh=True)
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
                    viewport_height = self._library_frame_viewport_height(command_buffer, prompt_message)
                    scroll_offset = max(0, scroll_offset - max(viewport_height, 1))
                    needs_refresh = True
                    continue

                if key == "PAGEDOWN":
                    viewport_height = self._library_frame_viewport_height(command_buffer, prompt_message)
                    scroll_offset = min(
                        max_scroll_offset,
                        scroll_offset + max(viewport_height, 1),
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
                    return command_buffer.strip() or "0"

                if key in ("\x08", "\x7f"):
                    command_buffer = command_buffer[:-1]
                    needs_refresh = True
                    continue

                if key in ("\x15", "\x1b"):
                    command_buffer = ""
                    needs_refresh = True
                    continue

                if len(key) == 1 and (key.isalnum() or key in " ,-"):
                    command_buffer += key
                    needs_refresh = True

    def _library_frame_viewport_height(self, command_buffer: str, prompt_message: str | None) -> int:
        header_panel = self._build_library_header_panel()
        guide_panel = self._build_library_guide_panel()
        prompt_panel = self._build_library_prompt_panel(command_buffer, prompt_message)
        viewport_height = self._library_viewport_height(
            header_panel,
            guide_panel,
            prompt_panel,
        )
        if viewport_height < 5:
            guide_panel = self._build_library_guide_panel(compact=True)
            viewport_height = self._library_viewport_height(
                header_panel,
                guide_panel,
                prompt_panel,
            )
        if viewport_height < 5:
            header_panel = self._build_library_header_panel(compact=True)
            viewport_height = self._library_viewport_height(
                header_panel,
                guide_panel,
                prompt_panel,
            )
        return self._library_viewport_height(
            header_panel,
            guide_panel,
            prompt_panel,
        )

    def _build_library_frame(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
        command_buffer: str,
        prompt_message: str | None,
        scroll_offset: int,
    ) -> tuple[Group, int]:
        header_panel = self._build_library_header_panel()
        compact_header_panel = self._build_library_header_panel(compact=True)
        guide_panel = self._build_library_guide_panel()
        compact_guide_panel = self._build_library_guide_panel(compact=True)
        prompt_panel = self._build_library_prompt_panel(command_buffer, prompt_message)
        active_header = header_panel
        active_guide = guide_panel
        viewport_height = self._library_viewport_height(active_header, active_guide, prompt_panel)
        if viewport_height < 5:
            active_guide = compact_guide_panel
            viewport_height = self._library_viewport_height(active_header, active_guide, prompt_panel)
        if viewport_height < 5:
            active_header = compact_header_panel
            viewport_height = self._library_viewport_height(active_header, active_guide, prompt_panel)

        library_panel, max_scroll_offset = self._build_library_list_scroll_panel(
            snapshots,
            groups,
            scroll_offset,
            viewport_height,
        )
        return Group(active_header, library_panel, active_guide, prompt_panel), max_scroll_offset

    def _renderable_height(self, renderable: Any) -> int:
        measuring_console = Console(
            file=StringIO(),
            force_terminal=False,
            color_system=None,
            width=self._console_width(),
            record=True,
        )
        measuring_console.print(renderable)
        return max(len(measuring_console.export_text().splitlines()), 1)

    def _library_viewport_height(self, header_panel: Panel, guide_panel: Panel, prompt_panel: Panel) -> int:
        fixed_height = (
            self._renderable_height(header_panel)
            + self._renderable_height(guide_panel)
            + self._renderable_height(prompt_panel)
        )
        return max(self._console_height() - fixed_height, 3)

    def _build_library_prompt_panel(
        self,
        command_buffer: str,
        prompt_message: str | None,
    ) -> Panel:
        return self._build_input_prompt_panel("Command", command_buffer, "0", prompt_message)

    def _build_library_list_scroll_panel(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
        scroll_offset: int,
        total_height: int,
    ) -> tuple[Panel, int]:
        if not snapshots:
            return self._build_library_list_panel(snapshots, groups), 0

        inner_height = max(total_height - 2, 1)
        inner_width = max(self._console_width() - 4, 20)
        visible_content, max_scroll_offset = self._build_renderable_viewport(
            self._build_library_list_content(snapshots, groups),
            scroll_offset,
            inner_height,
            width=inner_width,
        )
        return (
            Panel(
                visible_content,
                title="Novel List",
                border_style="#9ece6a",
                box=box.ROUNDED,
                expand=True,
                height=total_height,
            ),
            max_scroll_offset,
        )

    def _build_library_list_content(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup] | None = None,
    ) -> Any:
        if groups is None:
            groups = self._group_library_snapshots(snapshots)

        if not snapshots:
            return Text("No novels are stored yet.", style="#cbd5e1")

        items: list[Any] = []
        row_number = 1
        for group in groups:
            items.append(
                Text(
                    f"Language {group['index']}) {group['language']}",
                    style="bold #f6bd60",
                )
            )
            table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #9ece6a")
            table.add_column("No.", style="#f6bd60", no_wrap=True)
            table.add_column("Title", style="bold #e5e9f0")
            table.add_column("Novel ID", style="#73daca", no_wrap=True)
            table.add_column("Chapters", justify="right", style="#73daca", no_wrap=True)
            table.add_column("Translated", justify="right", style="#f6bd60", no_wrap=True)

            for snapshot in group["snapshots"]:
                table.add_row(
                    f"{row_number})",
                    snapshot["title"],
                    snapshot["novel_id"],
                    str(snapshot["total_chapters"]),
                    str(snapshot["translated_chapters"]),
                )
                row_number += 1

            items.append(table)
            items.append(Text(""))

        if items:
            items.pop()

        return Group(*items)

    def _build_library_list_panel(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup] | None = None,
    ) -> Panel:
        return Panel(
            self._build_library_list_content(snapshots, groups),
            title="Novel List",
            border_style="#9ece6a",
            box=box.ROUNDED,
            expand=True,
        )

    def _build_library_guide_panel(self, compact: bool = False) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        if compact:
            commands = Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text(
                    "1) export  2) delete custom  3) delete all  0) back",
                    style="#cbd5e1",
                ),
            )
        else:
            commands = Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text(""),
                Text("1) export                      Choose format, chapter scope, and which novels to export.", style="#cbd5e1"),
                Text("2) delete custom               Filter by language, then delete all or selected novel numbers.", style="#cbd5e1"),
                Text("3) delete all                  Remove every novel from the library.", style="#cbd5e1"),
                Text("0) back                        Return to the dashboard.", style="#cbd5e1"),
            )
        return Panel(
            commands,
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_library_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "export", "e"):
            return "export"
        if raw in ("2", "delete custom", "delete", "del", "d"):
            return "delete_custom"
        if raw in ("3", "delete all", "remove all"):
            return "delete_all"

        return None

    def _parse_library_selection(self, selection: str, max_value: int) -> list[int] | None:
        values: set[int] = set()
        for part in selection.split(","):
            token = part.strip()
            if not token:
                continue
            if "-" in token:
                start_text, end_text = token.split("-", 1)
                if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                    return None
                start = int(start_text.strip())
                end = int(end_text.strip())
                if start > end:
                    return None
                for value in range(start, end + 1):
                    if not 1 <= value <= max_value:
                        return None
                    values.add(value)
                continue
            if not token.isdigit():
                return None
            value = int(token)
            if not 1 <= value <= max_value:
                return None
            values.add(value)

        if not values:
            return None
        return sorted(values)

    def _build_library_confirmation_screen(self, message: str) -> Group:
        confirmation_panel = self._build_numbered_choice_panel(
            "Confirm",
            ["Yes, continue"],
            descriptions=[message],
            border_style="#e0af68",
            back_label="No, cancel",
        )
        return self._build_library_action_screen(
            "Confirm Action",
            "Review the action below, then confirm or cancel.",
            confirmation_panel,
        )

    def _confirm_library_action(self, message: str) -> bool:
        choice = self._prompt_numbered_choice(
            lambda: self._build_library_confirmation_screen(message),
            option_count=1,
            default_value="0",
            label="Confirm",
        )
        return choice == 1

    def _delete_library_novels(
        self,
        snapshots: list[LibrarySnapshot],
        selections: list[int],
    ) -> list[LibrarySnapshot]:
        deleted: list[LibrarySnapshot] = []
        for selection in selections:
            snapshot = snapshots[selection - 1]
            self.storage.delete_novel(snapshot["novel_id"])
            deleted.append(snapshot)
        return deleted

    def _build_library_action_screen(
        self,
        title: str,
        description: str,
        body: Any,
        *,
        snapshots: list[LibrarySnapshot] | None = None,
        groups: list[LibraryLanguageGroup] | None = None,
        include_list: bool = False,
    ) -> Group:
        sections: list[Any] = [self._build_action_header(title, description)]
        if include_list and snapshots is not None:
            sections.append(self._build_library_list_panel(snapshots, groups))
        sections.append(body)
        return Group(*sections)

    def _format_number_ranges(self, numbers: list[int]) -> str:
        if not numbers:
            return "-"

        ranges: list[str] = []
        start = numbers[0]
        end = numbers[0]
        for number in numbers[1:]:
            if number == end + 1:
                end = number
                continue
            ranges.append(f"{start}-{end}" if start != end else str(start))
            start = number
            end = number
        ranges.append(f"{start}-{end}" if start != end else str(start))
        return ", ".join(ranges)

    def _snapshot_number_map(self, snapshots: list[LibrarySnapshot]) -> dict[str, int]:
        return {snapshot["novel_id"]: index for index, snapshot in enumerate(snapshots, start=1)}

    def _group_allowed_numbers(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> dict[int, list[int]]:
        number_map = self._snapshot_number_map(snapshots)
        return {
            group["index"]: [number_map[snapshot["novel_id"]] for snapshot in group["snapshots"]]
            for group in groups
        }

    def _prompt_library_novel_selection(
        self,
        title: str,
        description: str,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
        *,
        allowed_numbers: list[int] | None = None,
        label: str = "Novel Numbers",
    ) -> list[int] | None:
        allowed_numbers = sorted(allowed_numbers) if allowed_numbers is not None else None
        allowed_text = self._format_number_ranges(allowed_numbers) if allowed_numbers is not None else "all"
        while True:
            selection_panel = Panel(
                Group(
                    Text("Enter novel numbers like 2-6 or 3, 7-10.", style="#cbd5e1"),
                    Text.assemble(("Allowed rows  ", "#9aa5ce"), (allowed_text, "#e5e9f0")),
                    Text("Leave blank to cancel.", style="#9aa5ce"),
                ),
                title="Selection",
                border_style="#7aa2f7",
                box=box.ROUNDED,
                expand=True,
            )
            command = self._prompt_renderable_command(
                self._build_library_action_screen(
                    title,
                    description,
                    selection_panel,
                    snapshots=snapshots,
                    groups=groups,
                    include_list=True,
                ),
                default_value="",
                label=label,
                extra_allowed_characters=" ,-",
            ).strip()
            if not command:
                return None

            selection = self._parse_library_selection(command, len(snapshots))
            if selection is None:
                self._set_status("Use novel numbers like 2-6 or 3, 7-10.", "warning")
                continue
            if allowed_numbers is not None and not set(selection).issubset(set(allowed_numbers)):
                self._set_status(
                    f"Choose only rows from {allowed_text} for this language selection.",
                    "warning",
                )
                continue
            return selection

    def _prompt_library_chapter_range(self, fmt: str) -> str | None:
        while True:
            chapter_panel = Panel(
                Group(
                    Text("Enter chapter numbers like 1, 3-8, or 1, 4-6.", style="#cbd5e1"),
                    Text(f"The same chapter range will be used for every {fmt.upper()} export in this run.", style="#9aa5ce"),
                    Text("Leave blank to cancel.", style="#9aa5ce"),
                ),
                title="Chapter Range",
                border_style="#7aa2f7",
                box=box.ROUNDED,
                expand=True,
            )
            selection = self._prompt_renderable_command(
                self._build_library_action_screen(
                    "Export Chapters",
                    f"Choose which translated chapters to include in the {fmt.upper()} export.",
                    chapter_panel,
                ),
                default_value="",
                label="Chapter Range",
                extra_allowed_characters=" ,-",
            ).strip()
            if not selection:
                return None
            if self._validate_chapter_selection(selection) and not is_full_chapter_selection(selection):
                return selection
            self._set_status("Use chapter selection like 1, 3-8, or 1, 4-6.", "warning")

    def _select_library_language_scope(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> tuple[str, list[int]] | None:
        group_numbers = self._group_allowed_numbers(snapshots, groups)
        options = ["All languages"] + [group["language"] for group in groups]
        descriptions = [f"{len(snapshots)} novel(s), rows {self._format_number_ranges(list(range(1, len(snapshots) + 1)))}."]
        for group in groups:
            numbers = group_numbers.get(group["index"], [])
            descriptions.append(f"{len(numbers)} novel(s), rows {self._format_number_ranges(numbers)}.")

        choice = self._prompt_numbered_choice(
            lambda: self._build_library_action_screen(
                "Delete Custom",
                "Choose which language scope to work with before deleting novels.",
                self._build_numbered_choice_panel(
                    "Language Scope",
                    options,
                    descriptions=descriptions,
                    border_style="#7aa2f7",
                ),
            ),
            option_count=len(options),
            default_value="1",
        )
        if choice is None:
            self._set_status("Delete custom cancelled.", "warning")
            return None
        if choice == 1:
            return "All languages", list(range(1, len(snapshots) + 1))

        group = groups[choice - 2]
        return group["language"], group_numbers.get(group["index"], [])

    def _select_custom_delete_mode(self, language_label: str, count: int) -> str | None:
        choice = self._prompt_numbered_choice(
            lambda: self._build_library_action_screen(
                "Delete Custom",
                f"Choose whether to delete every novel in {language_label} or only selected novel numbers.",
                self._build_numbered_choice_panel(
                    "Delete Mode",
                    ["Full delete", "Choose novel numbers"],
                    descriptions=[
                        f"Delete all {count} novel(s) in {language_label}.",
                        f"Delete only selected novel numbers from {language_label}.",
                    ],
                    border_style="#7aa2f7",
                ),
            ),
            option_count=2,
            default_value="1",
        )
        if choice is None:
            self._set_status("Delete custom cancelled.", "warning")
            return None
        return "full" if choice == 1 else "selection"

    def _delete_custom_library_novels(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> None:
        language_scope = self._select_library_language_scope(snapshots, groups)
        if language_scope is None:
            return

        language_label, allowed_numbers = language_scope
        if not allowed_numbers:
            self._set_status(f"There are no novels in {language_label} to delete.", "warning")
            return

        delete_mode = self._select_custom_delete_mode(language_label, len(allowed_numbers))
        if delete_mode is None:
            return

        if delete_mode == "full":
            if not self._confirm_library_action(f"Delete all {len(allowed_numbers)} novel(s) in {language_label}?"):
                self._set_status("Delete custom cancelled.", "warning")
                return
            deleted = self._delete_library_novels(snapshots, allowed_numbers)
            self._set_status(f"Deleted {len(deleted)} novel(s) from {language_label}.", "success")
            return

        selection = self._prompt_library_novel_selection(
            "Delete Custom",
            f"Choose which novel numbers to delete from {language_label}.",
            snapshots,
            groups,
            allowed_numbers=allowed_numbers,
            label="Delete Rows",
        )
        if selection is None:
            self._set_status("Delete custom cancelled.", "warning")
            return

        names = ", ".join(f"{index}) {snapshots[index - 1]['title']}" for index in selection[:3])
        if len(selection) > 3:
            names = f"{names}, ..."
        if not self._confirm_library_action(f"Delete {len(selection)} novel(s): {names}?"):
            self._set_status("Delete custom cancelled.", "warning")
            return

        deleted = self._delete_library_novels(snapshots, selection)
        self._set_status(f"Deleted {len(deleted)} novel(s) from {language_label}.", "success")

    def _export_library_novels(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> None:
        formats = available_exporters()
        if not formats:
            self._set_status("No export formats are registered.", "warning")
            return

        format_descriptions = [f"Create a {fmt.upper()} file." for fmt in formats]
        format_choice = self._prompt_numbered_choice(
            lambda: self._build_library_action_screen(
                "Export",
                "Choose the export format you want to generate.",
                self._build_numbered_choice_panel(
                    "Formats",
                    [fmt.upper() for fmt in formats],
                    descriptions=format_descriptions,
                    border_style="#7aa2f7",
                ),
            ),
            option_count=len(formats),
            default_value="1",
        )
        if format_choice is None:
            self._set_status("Export cancelled.", "warning")
            return
        fmt = formats[format_choice - 1]

        chapter_choice = self._prompt_numbered_choice(
            lambda: self._build_library_action_screen(
                "Export Chapters",
                f"Choose whether the {fmt.upper()} export should include all translated chapters or a specific range.",
                self._build_numbered_choice_panel(
                    "Chapter Scope",
                    ["Full translated chapters", "Custom chapter range"],
                    descriptions=[
                        "Export every translated chapter stored for each selected novel.",
                        "Export only the translated chapters that match a chapter range.",
                    ],
                    border_style="#7aa2f7",
                ),
            ),
            option_count=2,
            default_value="1",
        )
        if chapter_choice is None:
            self._set_status("Export cancelled.", "warning")
            return

        chapter_selection = "full"
        if chapter_choice == 2:
            chapter_selection = self._prompt_library_chapter_range(fmt) or ""
            if not chapter_selection:
                self._set_status("Export cancelled.", "warning")
                return

        selections = self._prompt_library_novel_selection(
            "Export",
            f"Choose which novel numbers to export as {fmt.upper()}.",
            snapshots,
            groups,
            label="Export Rows",
        )
        if selections is None:
            self._set_status("Export cancelled.", "warning")
            return

        exported: list[str] = []
        failures: list[str] = []
        for selection in selections:
            snapshot = snapshots[selection - 1]
            try:
                self._export_novel(snapshot["novel_id"], fmt, None, chapter_selection=chapter_selection)
                exported.append(snapshot["novel_id"])
            except Exception as exc:
                failures.append(f"{snapshot['novel_id']}: {exc}")

        if exported:
            summary = "\n".join(exported[:6])
            if len(exported) > 6:
                summary = f"{summary}\n..."
            self.console.print(
                Panel(
                    (
                        f"Exported {len(exported)} novel(s) as {fmt.upper()}.\n"
                        f"Chapters: {self._format_chapter_selection_label(chapter_selection)}\n"
                        f"{summary}"
                    ),
                    title="Export Complete",
                    border_style="#9ece6a",
                    box=box.ROUNDED,
                )
            )

        if failures:
            self.console.print(
                Panel(
                    "\n".join(failures[:6]),
                    title="Export Warnings",
                    border_style="#e0af68",
                    box=box.ROUNDED,
                )
            )
            if exported:
                self._set_status(
                    f"Exported {len(exported)} novel(s); {len(failures)} failed.",
                    "warning",
                )
            else:
                self._set_status("No novels were exported.", "error")
            return

        self._set_status(
            f"Exported {len(exported)} novel(s) as {fmt.upper()} with {self._format_chapter_selection_label(chapter_selection)}.",
            "success",
        )

    def _resolve_source_from_url(self, novel_url: str) -> tuple[str, str] | None:
        source_key = detect_source(novel_url)
        if source_key is None:
            return None

        source = get_source(source_key)
        novel_id = source.normalize_novel_id(novel_url).strip()
        if not novel_id:
            return None

        return source_key, novel_id

    def _available_models_for_provider(self, provider_key: str) -> list[str]:
        try:
            return available_provider_models(provider_key)
        except Exception:
            return []

    def _effective_translation_target(
        self,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> tuple[str, str, bool]:
        resolved_provider = provider_key or self.settings.get_provider_key()
        resolved_model = provider_model or self.settings.get_provider_model()
        if resolved_provider == "openai" and not self.settings.get_api_key():
            return "dummy", "dummy", True
        return resolved_provider, resolved_model, False

    def _prompt_chapter_selection(self) -> str:
        selection = Prompt.ask(
            "[bold #f6bd60]Chapter selection[/bold #f6bd60] (full, 1, 3-8)",
            default="full",
            console=self.console,
        ).strip()
        return selection or "full"

    def _validate_chapter_selection(self, selection: str) -> bool:
        if is_full_chapter_selection(selection):
            return True
        try:
            return bool(parse_chapter_selection(selection))
        except Exception:
            return False

    def _prompt_novel_url(
        self,
        title: str,
        description: str,
    ) -> tuple[str, str, str] | None:
        self.console.clear()
        self.console.print(self._build_action_header(title, description))

        if not available_sources():
            self._set_status(f"{title} cancelled because no source is registered.", "warning")
            return None

        novel_url = Prompt.ask("[bold #f6bd60]Novel URL[/bold #f6bd60]", console=self.console).strip()
        resolved_source = self._resolve_source_from_url(novel_url)
        if resolved_source is None:
            self._set_status(
                "Could not detect a supported source from that URL. Paste a full novel URL from a registered source.",
                "warning",
            )
            return None

        source_key, novel_id = resolved_source
        return novel_url, source_key, novel_id

    def _metadata_chapter_numbers(self, metadata: dict[str, Any] | None) -> list[int]:
        if not isinstance(metadata, dict):
            return []

        numbers: list[int] = []
        for chapter in metadata.get("chapters", []):
            if not isinstance(chapter, dict):
                continue
            chapter_id = str(chapter.get("id", "")).strip()
            if chapter_id.isdigit():
                numbers.append(int(chapter_id))
        return sorted(set(numbers))

    def _latest_library_chapter(self, novel_id: str, metadata: dict[str, Any] | None) -> int:
        latest = 0
        for chapter_num in self._metadata_chapter_numbers(metadata):
            chapter_id = str(chapter_num)
            if self.storage.load_chapter(novel_id, chapter_id) or self.storage.load_translated_chapter(novel_id, chapter_id):
                latest = chapter_num
        return latest

    def _build_update_selection(self, novel_id: str, metadata: dict[str, Any] | None) -> str | None:
        chapter_numbers = self._metadata_chapter_numbers(metadata)
        if not chapter_numbers:
            return None

        latest_library_chapter = self._latest_library_chapter(novel_id, metadata)
        latest_remote_chapter = chapter_numbers[-1]
        next_chapter = latest_library_chapter + 1

        if next_chapter > latest_remote_chapter:
            return None
        if next_chapter == latest_remote_chapter:
            return str(next_chapter)
        return f"{next_chapter}-{latest_remote_chapter}"

    def _format_chapter_selection_label(self, selection: str) -> str:
        return "all available chapters" if is_full_chapter_selection(selection) else f"chapters {selection}"

    def _show_existing_novel_notice(self, novel_id: str) -> None:
        self.console.print(
            Panel(
                f"{novel_id} is already in the library.\nUse Update Novel to pull any newer chapters.",
                title="Already In Library",
                border_style="#e0af68",
                box=box.ROUNDED,
            )
        )
        self._set_status(f"{novel_id} is already in the library. Use Update Novel.", "warning")

    def _show_missing_novel_notice(self, novel_id: str) -> None:
        self.console.print(
            Panel(
                f"{novel_id} is not in the library yet.\nUse Add Novel first so the initial chapters can be scraped.",
                title="Novel Not Found",
                border_style="#e0af68",
                box=box.ROUNDED,
            )
        )
        self._set_status(f"{novel_id} is not in the library. Use Add Novel first.", "warning")

    def _run_translation_pipeline(
        self,
        *,
        title: str,
        novel_id: str,
        source: str,
        novel_url: str,
        chapters: str,
    ) -> None:
        active_provider, active_model, fallback_used = self._effective_translation_target()

        try:
            with self.console.status("[bold #7dcfff]Translating chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(
                    self._do_translate_chapters(
                        source,
                        novel_id,
                        chapters,
                        active_provider,
                        active_model,
                        force=False,
                    )
                )
        except Exception as exc:
            self.console.print(
                Panel(
                    (
                        f"Saved metadata and raw chapters for {novel_id} from {source}.\n"
                        f"Source URL: {novel_url}\n"
                        f"Translation with {active_provider}/{active_model} failed: {exc}"
                    ),
                    title=f"{title}, Translation Pending",
                    border_style="#e0af68",
                    box=box.ROUNDED,
                )
            )
            self._set_status(
                f"{title} saved raw chapters for {novel_id}, but translation failed with {active_provider}/{active_model}.",
                "warning",
            )
            return

        selection_label = self._format_chapter_selection_label(chapters)
        fallback_note = ""
        if fallback_used:
            fallback_note = "\nOpenAI API key was missing, so translation used dummy/dummy."

        self.console.print(
            Panel(
                (
                    f"{title} finished for {novel_id} from {source}.\n"
                    f"Source URL: {novel_url}\n"
                    f"Fetched and translated {selection_label} with {active_provider}/{active_model}."
                    f"{fallback_note}"
                ),
                title=title,
                border_style="#9ece6a",
                box=box.ROUNDED,
            )
        )
        self._set_status(
            f"{title} finished for {novel_id} with {active_provider}/{active_model}.",
            "success",
        )

    async def _do_scrape_metadata(self, source_key: str, novel_id: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_metadata(source_key, novel_id, mode=mode)

    async def _do_scrape_chapters(self, source_key: str, novel_id: str, chapters: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_chapters(source_key, novel_id, chapters, mode=mode)

    def _scrape_flow(self) -> None:
        prompt = self._prompt_novel_url(
            "Add Novel",
            "Paste a novel URL and NovelAIBook will detect the source, scrape the selected chapters, and translate them into your library.",
        )
        if prompt is None:
            return

        novel_url, source, novel_id = prompt
        if self.storage.load_metadata(novel_id):
            self._show_existing_novel_notice(novel_id)
            return

        chapters = self._prompt_chapter_selection()
        if not self._validate_chapter_selection(chapters):
            self._set_status("Use chapter selection like full, 1, or 3-8.", "warning")
            return

        try:
            with self.console.status("[bold #7dcfff]Saving novel metadata...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_metadata(source, novel_id, mode="update"))
            with self.console.status("[bold #7dcfff]Fetching raw chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_chapters(source, novel_id, chapters, mode="update"))
        except Exception as exc:
            self._show_error(f"Add Novel failed: {exc}")
            return

        self._run_translation_pipeline(
            title="Add Novel",
            novel_id=novel_id,
            source=source,
            novel_url=novel_url,
            chapters=chapters,
        )

    def _update_flow(self) -> None:
        prompt = self._prompt_novel_url(
            "Update Novel",
            "Paste an existing novel URL and NovelAIBook will refresh metadata, then fetch and translate only the chapters that are newer than your latest stored chapter.",
        )
        if prompt is None:
            return

        novel_url, source, novel_id = prompt
        if self.storage.load_metadata(novel_id) is None:
            self._show_missing_novel_notice(novel_id)
            return

        try:
            with self.console.status("[bold #7dcfff]Refreshing novel metadata...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_metadata(source, novel_id, mode="update"))
        except Exception as exc:
            self._show_error(f"Update Novel failed: {exc}")
            return

        metadata = self.storage.load_metadata(novel_id)
        chapters = self._build_update_selection(novel_id, metadata)
        if chapters is None:
            self.console.print(
                Panel(
                    f"{novel_id} is already up to date.\nNo newer chapters were detected at the source.",
                    title="Update Novel",
                    border_style="#7aa2f7",
                    box=box.ROUNDED,
                )
            )
            self._set_status(f"{novel_id} is already up to date.", "info")
            return

        try:
            with self.console.status("[bold #7dcfff]Fetching new raw chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_chapters(source, novel_id, chapters, mode="update"))
        except Exception as exc:
            self._show_error(f"Update Novel failed: {exc}")
            return

        self._run_translation_pipeline(
            title="Update Novel",
            novel_id=novel_id,
            source=source,
            novel_url=novel_url,
            chapters=chapters,
        )

    async def _do_translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
        force: bool = False,
    ) -> None:
        await self.orchestrator.translate_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=provider_key,
            provider_model=provider_model,
            force=force,
        )

    def _collect_export_chapters(self, novel_id: str, chapter_selection: str = "full") -> list[dict[str, Any]]:
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise ValueError("Metadata not found; run scrape first.")

        chapters: list[dict[str, Any]] = []
        raw_chapters = meta.get("chapters", [])
        if not isinstance(raw_chapters, list):
            raise ValueError("Stored metadata has an invalid chapter list.")

        selected_numbers: set[int] | None = None
        if not is_full_chapter_selection(chapter_selection):
            try:
                selected_numbers = {spec.chapter for spec in parse_chapter_selection(chapter_selection)}
            except Exception as exc:
                raise ValueError("Use chapter selection like 1, 3-8, or 1, 4-6.") from exc

        for chap in raw_chapters:
            if not isinstance(chap, dict):
                continue
            chap_id_value = chap.get("id")
            if chap_id_value is None:
                continue
            chap_id = str(chap_id_value)
            if selected_numbers is not None:
                if not chap_id.isdigit() or int(chap_id) not in selected_numbers:
                    continue
            translated = self.storage.load_translated_chapter(novel_id, chap_id)
            if not translated:
                continue

            title = chap.get("title")
            text = translated.get("text")
            if not isinstance(text, str):
                continue

            chapters.append(
                {
                    "title": title if isinstance(title, str) and title else f"Chapter {chap_id}",
                    "text": text,
                }
            )

        if not chapters:
            if selected_numbers is not None:
                raise ValueError(f"No translated chapters are available for export in chapters {chapter_selection}.")
            raise ValueError("No translated chapters are available for export.")
        return chapters

    def _build_export_output_path(
        self,
        novel_id: str,
        fmt: str,
        output_dir: str | None,
        chapter_selection: str,
    ) -> str:
        base_path = Path(self.storage.build_export_path(novel_id, fmt, output_dir))
        if is_full_chapter_selection(chapter_selection):
            return str(base_path)

        suffix = chapter_selection.replace(" ", "").replace(",", "_").replace("-", "to")
        return str(base_path.with_name(f"chapters_{suffix}.{fmt}"))

    def _export_novel(
        self,
        novel_id: str,
        fmt: str,
        output_dir: str | None,
        *,
        chapter_selection: str = "full",
    ) -> str:
        chapters = self._collect_export_chapters(novel_id, chapter_selection=chapter_selection)
        output_path = self._build_export_output_path(novel_id, fmt, output_dir, chapter_selection)
        if fmt == "pdf":
            self.exporter.export_pdf(novel_id=novel_id, chapters=chapters, output_path=output_path)
        else:
            self.exporter.export_epub(novel_id=novel_id, chapters=chapters, output_path=output_path)
        return output_path

    def _build_diagnostics_screen(self) -> Group:
        novels = self.storage.list_novels()
        total_novels = len(novels)
        total_translated = sum(self.storage.count_translated_chapters(novel_id) for novel_id in novels)

        cache_path = Path(settings.DATA_DIR) / "translation_cache.json"
        cache_entries = 0
        if cache_path.exists():
            try:
                cache_entries = len(json.loads(cache_path.read_text(encoding="utf-8")))
            except Exception:
                cache_entries = -1

        usage_summary = self.usage.summary()
        recent_usage = self.usage.list(limit=5)
        daily_history = self.usage.daily_history(limit=7)
        local_day = time.strftime("%Y-%m-%d")

        stats = Table.grid(expand=True, padding=(0, 2))
        stats.add_column(style="bold #f6bd60")
        stats.add_column(style="#e5e9f0")
        stats.add_row("Usage day", f"{local_day} (local)")
        stats.add_row("Novels stored", str(total_novels))
        stats.add_row("Translated chapters", str(total_translated))
        stats.add_row("Cached translations", str(cache_entries if cache_entries >= 0 else "error"))
        stats.add_row("Today's requests", str(usage_summary.get("total_requests")))
        stats.add_row("Today's tokens", str(usage_summary.get("total_tokens")))
        stats.add_row("Today's cost (USD)", f"${usage_summary.get('estimated_cost_usd', 0):.6f}")

        usage_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #7dcfff")
        usage_table.add_column("Timestamp", style="#cbd5e1")
        usage_table.add_column("Provider/Model", style="#e5e9f0")
        usage_table.add_column("Tokens", justify="right", style="#f6bd60")

        if recent_usage:
            for entry in recent_usage:
                usage_table.add_row(
                    str(entry.get("timestamp")),
                    f"{entry.get('provider')}/{entry.get('model')}",
                    str(entry.get("tokens") or 0),
                )
        else:
            usage_table.add_row("No usage records yet for today.", "-", "-")

        history_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #bb9af7")
        history_table.add_column("Date", style="#cbd5e1")
        history_table.add_column("Requests", justify="right", style="#e5e9f0")
        history_table.add_column("Tokens", justify="right", style="#7dcfff")
        history_table.add_column("Cost", justify="right", style="#f6bd60")

        if daily_history:
            for entry in daily_history:
                history_table.add_row(
                    str(entry.get("date")),
                    str(entry.get("total_requests")),
                    str(entry.get("total_tokens")),
                    f"${entry.get('estimated_cost_usd', 0):.6f}",
                )
        else:
            history_table.add_row("No stored usage history yet.", "-", "-", "-")

        diagnostics_panel = Panel(
            Group(
                stats,
                Text(""),
                Text("Recent Activity Today", style="bold #7dcfff"),
                usage_table,
                Text(""),
                Text("Daily History", style="bold #bb9af7"),
                history_table,
            ),
            border_style="#7aa2f7",
            box=box.ROUNDED,
        )

        return Group(
            self._build_action_header(
                "Diagnostics",
                "Inspect today's local usage, recent activity, and the saved history from previous days.",
            ),
            diagnostics_panel,
            self._build_diagnostics_guide_panel(),
        )

    def _build_diagnostics_guide_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        return Panel(
            Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text("Usage resets automatically at local midnight. Past days stay in history until you clear them.", style="#cbd5e1"),
                Text(""),
                Text("1) clear usage history        Remove today's usage and all saved daily history.", style="#cbd5e1"),
                Text("0) back                       Return to the dashboard.", style="#cbd5e1"),
            ),
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_diagnostics_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "clear", "clear usage", "clear usage history"):
            return "clear"
        return None

    def _diagnostics_menu(self) -> None:
        self._set_status(
            "Diagnostics show today's local usage and keep past days in history until you clear them.",
            "info",
        )
        while True:
            command = self._prompt_renderable_command(
                self._build_diagnostics_screen(),
                default_value="0",
            )
            action = self._parse_diagnostics_command(command)
            if action is None:
                self._set_status("Unknown diagnostics command. Use 1 to clear usage history or 0 to go back.", "warning")
                continue
            if action == "back":
                self._set_status("Diagnostics refreshed.", "info")
                return

            self.usage.clear()
            self._set_status("Usage history cleared.", "success")

    def _build_settings_summary_panel(self) -> Panel:
        provider = self.settings.get_provider_key()
        model = self.settings.get_provider_model()
        models = self._available_models_for_provider(provider)
        api_key_state = "configured" if self.settings.get_api_key() else "missing"
        model_text = ", ".join(models) if models else "No provider-declared models."

        settings_table = Table.grid(expand=True, padding=(0, 2))
        settings_table.add_column(style="bold #f6bd60")
        settings_table.add_column(style="#e5e9f0")
        settings_table.add_row("Provider", provider)
        settings_table.add_row("Model", model)
        settings_table.add_row("API key", api_key_state)
        settings_table.add_row("Available models", model_text)

        return Panel(settings_table, border_style="#bb9af7", box=box.ROUNDED)

    def _current_api_key_text(self) -> str:
        api_key = self.settings.get_api_key()
        return api_key if api_key else "not set"

    def _set_api_validation(self, message: str, kind: str = "muted") -> None:
        self.api_validation_message = message
        self.api_validation_kind = kind

    async def _validate_provider_connection_async(self) -> tuple[bool, str]:
        provider = get_provider(self.settings.get_provider_key())
        return await provider.validate_connection(model=self.settings.get_provider_model())

    def _validate_provider_connection(self) -> tuple[bool, str]:
        try:
            with self.console.status("[bold #7dcfff]Validating provider connection...[/bold #7dcfff]", spinner="dots"):
                is_valid, message = asyncio.run(self._validate_provider_connection_async())
        except Exception as exc:
            is_valid, message = False, f"Validation failed: {exc}"

        self._set_api_validation(message, "success" if is_valid else "warning")
        return is_valid, message

    def _build_numbered_choice_panel(
        self,
        title: str,
        options: list[str],
        *,
        descriptions: list[str] | None = None,
        border_style: str = "#7aa2f7",
        back_label: str = "Back",
    ) -> Panel:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(style="bold #f6bd60", no_wrap=True)
        grid.add_column(style="#e5e9f0")

        for index, option in enumerate(options, start=1):
            description = descriptions[index - 1] if descriptions and index - 1 < len(descriptions) else ""
            grid.add_row(f"{index})", Text.assemble((option, "bold #e5e9f0"), (f"  {description}" if description else "", "#cbd5e1")))

        grid.add_row("0)", Text(back_label, style="#cbd5e1"))

        return Panel(
            grid,
            title=title,
            border_style=border_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _build_settings_choice_screen(
        self,
        title: str,
        description: str,
        options: list[str],
        *,
        descriptions: list[str] | None = None,
    ) -> Group:
        return Group(
            self._build_action_header(title, description),
            self._build_settings_summary_panel(),
            self._build_numbered_choice_panel(
                title,
                options,
                descriptions=descriptions,
                border_style="#bb9af7",
            ),
        )

    def _build_api_key_screen(self) -> Group:
        validation_style = self.STATUS_STYLES.get(self.api_validation_kind, self.STATUS_STYLES["muted"])
        api_key_panel = Panel(
            Group(
                Text.assemble(
                    ("Current API key  ", "#9aa5ce"),
                    (self._current_api_key_text(), "bold #e5e9f0"),
                ),
                Text.assemble(
                    ("Validation  ", "#9aa5ce"),
                    (self.api_validation_message, f"bold {validation_style}"),
                ),
                Text(""),
                Text("1) set API key                Enter or replace the runtime API key.", style="#cbd5e1"),
                Text("2) clear API key              Remove the current runtime API key.", style="#cbd5e1"),
                Text("3) validate connection        Check that the current provider can reach its service.", style="#cbd5e1"),
                Text("0) back                       Return to settings.", style="#cbd5e1"),
            ),
            title="API Key",
            border_style="#bb9af7",
            box=box.ROUNDED,
            expand=True,
        )
        return Group(
            self._build_action_header(
                "API Key",
                "Review the current runtime API key, set a new one, or clear it.",
            ),
            self._build_settings_summary_panel(),
            api_key_panel,
        )

    def _build_api_key_entry_screen(self) -> Group:
        return Group(
            self._build_action_header(
                "Set API Key",
                "Enter a runtime API key for the current provider. Press Enter on an empty line to keep the current key.",
            ),
            self._build_settings_summary_panel(),
            Panel(
                Text.assemble(
                    ("Current API key  ", "#9aa5ce"),
                    (self._current_api_key_text(), "bold #e5e9f0"),
                ),
                title="API Key",
                border_style="#bb9af7",
                box=box.ROUNDED,
                expand=True,
            ),
        )

    def _parse_api_key_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "set", "set api key", "update", "update api key"):
            return "set"
        if raw in ("2", "clear", "clear api key", "remove"):
            return "clear"
        if raw in ("3", "validate", "validate api key", "validate connection", "test"):
            return "validate"
        return None

    def _api_key_menu(self) -> None:
        self._set_status("Use 1 to set the API key, 2 to clear it, 3 to validate it, or 0 to go back.", "info")
        while True:
            command = self._prompt_renderable_command(
                self._build_api_key_screen(),
                default_value="0",
            )
            action = self._parse_api_key_command(command)
            if action is None:
                self._set_status("Unknown API key command. Use 1, 2, 3, or 0.", "warning")
                continue
            if action == "back":
                self._set_status("Settings ready.", "info")
                return
            if action == "clear":
                if self.settings.get_api_key():
                    self.settings.clear_api_key()
                    self._set_api_validation("Not validated yet.", "muted")
                    self._set_status("API key cleared.", "success")
                else:
                    self._set_status("API key is already not set.", "info")
                continue
            if action == "validate":
                is_valid, message = self._validate_provider_connection()
                self._set_status(message, "success" if is_valid else "warning")
                continue

            api_key = self._prompt_renderable_command(
                self._build_api_key_entry_screen(),
                default_value="",
                label="API Key",
                allow_any_printable=True,
            ).strip()
            if not api_key:
                self._set_status("API key unchanged.", "info")
                continue

            self.settings.set_api_key(api_key)
            is_valid, message = self._validate_provider_connection()
            if is_valid:
                self._set_status(f"API key updated for {self.settings.get_provider_key()}. {message}", "success")
            else:
                self._set_status(
                    f"API key updated for {self.settings.get_provider_key()}, but validation failed. {message}",
                    "warning",
                )

    def _prompt_numbered_choice(
        self,
        renderable_factory: Callable[[], Any],
        *,
        option_count: int,
        default_value: str = "1",
        label: str = "Choice",
    ) -> int | None:
        while True:
            command = self._prompt_renderable_command(
                renderable_factory(),
                default_value=default_value,
                label=label,
            )
            raw = command.strip().lower()
            if raw in ("0", "back", "b", "cancel"):
                return None
            if raw.isdigit():
                selection = int(raw)
                if 1 <= selection <= option_count:
                    return selection
            self._set_status(f"Choose a number from 1 to {option_count}, or 0 to go back.", "warning")

    def _select_provider_and_model(self) -> tuple[str, str] | None:
        providers = available_providers()
        if not providers:
            self._set_status("No providers are registered.", "warning")
            return None

        current_provider = self.settings.get_provider_key()
        default_provider_index = providers.index(current_provider) + 1 if current_provider in providers else 1
        provider_choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Select Provider",
                "Choose the translation provider you want to use.",
                providers,
            ),
            option_count=len(providers),
            default_value=str(default_provider_index),
        )
        if provider_choice is None:
            self._set_status("Provider selection cancelled.", "warning")
            return None

        provider = providers[provider_choice - 1]
        models = self._available_models_for_provider(provider)
        if not models:
            current_model = self.settings.get_provider_model()
            return provider, current_model

        current_model = self.settings.get_provider_model()
        default_model_index = models.index(current_model) + 1 if current_model in models else 1
        model_choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Select Model",
                f"Choose the default model for {provider}.",
                models,
            ),
            option_count=len(models),
            default_value=str(default_model_index),
        )
        if model_choice is None:
            self._set_status("Model selection cancelled.", "warning")
            return None

        return provider, models[model_choice - 1]

    def _build_settings_screen(self) -> Group:
        return Group(
            self._build_action_header(
                "Settings",
                "Choose the provider, then the model for that provider, and update the API key used by Add Novel translation.",
            ),
            self._build_settings_summary_panel(),
            self._build_settings_guide_panel(),
        )

    def _build_settings_guide_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        provider = self.settings.get_provider_key()
        models = self._available_models_for_provider(provider)
        model_text = ", ".join(models) if models else "No provider-declared models."
        return Panel(
            Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text.assemble(("Provider models  ", "#9aa5ce"), (model_text, "#cbd5e1")),
                Text(""),
                Text("1) select provider            Pick a provider, then choose one of its models.", style="#cbd5e1"),
                Text("2) set API key                Update the runtime API key used by the provider.", style="#cbd5e1"),
                Text("0) back                       Return to the dashboard.", style="#cbd5e1"),
            ),
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_settings_command(self, command: str) -> str | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return "back"
        if raw in ("1", "provider", "select provider"):
            return "provider"
        if raw in ("2", "api", "api key", "set api key"):
            return "api_key"
        return None

    def _settings_menu(self) -> None:
        self._set_status("Use 1 to choose a provider and model, 2 to set the API key, or 0 to go back.", "info")
        while True:
            command = self._prompt_renderable_command(
                self._build_settings_screen(),
                default_value="0",
            )
            action = self._parse_settings_command(command)
            if action is None:
                self._set_status("Unknown settings command. Use 1, 2, or 0.", "warning")
                continue
            if action == "back":
                self._set_status("Settings ready.", "info")
                return

            if action == "provider":
                selection = self._select_provider_and_model()
                if selection is None:
                    continue
                provider, model = selection
                self.settings.set_provider_key(provider)
                self.settings.set_provider_model(model)
                self._set_api_validation("Not validated yet.", "muted")
                self._set_status(f"Provider set to {provider}. Default model set to {model}.", "success")
                continue

            self._api_key_menu()

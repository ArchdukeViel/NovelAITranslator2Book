from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, TypedDict

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
from novelai.providers.registry import available_models as available_provider_models
from novelai.providers.registry import available_providers
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
                self._set_status("Session closed.", "muted")
                break

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
            screen=False,
            auto_refresh=False,
            transient=False,
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
        )

    def _prompt_renderable_command_live(
        self,
        renderable: Any,
        *,
        default_value: str,
        label: str,
        extra_allowed_characters: str,
    ) -> str:
        command_buffer = ""
        prompt_message: str | None = None
        last_height = -1
        needs_refresh = True
        scroll_offset = 0
        max_scroll_offset = 0

        with Live(
            console=self.console,
            screen=False,
            auto_refresh=False,
            transient=False,
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

                if len(key) == 1 and (key.isdigit() or key in extra_allowed_characters):
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
    ) -> tuple[Segments, int]:
        renderable_lines = self.console.render_lines(
            renderable,
            options=self.console.options.update_dimensions(
                self._console_width(),
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
            "Use 1) export, 2) delete, 3) delete language, 4) delete all, or 0) back.",
            "info",
        )
        while True:
            snapshots = self._order_library_snapshots(self._collect_library_snapshot(limit=200))
            groups = self._group_library_snapshots(snapshots)

            if not snapshots:
                self._set_status("The library is empty.", "warning")

            command = self._prompt_library_command(snapshots, groups)
            parsed = self._parse_library_command(command)

            if parsed is None:
                self._set_status(
                    "Unknown library command. Use a numbered action like 1 2-6, 2 3,7-10, 3 1, 4, or 0.",
                    "warning",
                )
                continue

            action, payload = parsed
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

            if action == "delete_language":
                if not groups:
                    self._set_status("There are no language groups to delete.", "warning")
                    continue
                if payload is None or not payload.isdigit():
                    self._set_status("Choose a valid language group number.", "warning")
                    continue
                group_index = int(payload)
                target_group = next((group for group in groups if group["index"] == group_index), None)
                if target_group is None:
                    self._set_status("Choose a valid language group number.", "warning")
                    continue
                if self._confirm_library_action(
                    f"Delete all novels in language group {group_index}) {target_group['language']}?"
                ):
                    deleted = self._delete_library_language_group(groups, group_index)
                    self._set_status(
                        f"Deleted {len(deleted)} novel(s) from {target_group['language']}.",
                        "success",
                    )
                else:
                    self._set_status("Delete language group cancelled.", "warning")
                continue

            if action == "export":
                if not snapshots:
                    self._set_status("There are no novels to export.", "warning")
                    continue
                if payload is None:
                    self._set_status("Choose one or more novel numbers to export.", "warning")
                    continue
                selection = self._parse_library_selection(payload, len(snapshots))
                if selection is None:
                    self._set_status("Use novel numbers like 2-6 or 3, 7-10.", "warning")
                    continue
                self._export_library_novels(snapshots, selection)
                continue

            if not snapshots:
                self._set_status("There are no novels to delete.", "warning")
                continue

            if payload is None:
                self._set_status("Choose one or more novel numbers to delete.", "warning")
                continue
            selection = self._parse_library_selection(payload, len(snapshots))
            if selection is None:
                self._set_status("Use novel numbers like 2-6 or 3, 7-10.", "warning")
                continue
            names = ", ".join(f"{index}) {snapshots[index - 1]['title']}" for index in selection[:3])
            if len(selection) > 3:
                names = f"{names}, ..."
            if not self._confirm_library_action(f"Delete {len(selection)} novel(s): {names}?"):
                self._set_status("Delete cancelled.", "warning")
                continue

            deleted = self._delete_library_novels(snapshots, selection)
            self._set_status(f"Deleted {len(deleted)} novel(s) from the library.", "success")

    def _build_library_screen(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> Group:
        return Group(
            self._build_library_scrollable_content(snapshots, groups),
            self._build_library_guide_panel(),
        )

    def _build_library_scrollable_content(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> Group:
        return Group(
            self._build_action_header(
                "Library",
                "Browse stored novels, export selections, and manage what stays in the library.",
            ),
            self._build_library_list_panel(snapshots, groups),
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
            screen=False,
            auto_refresh=False,
            transient=False,
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
        return self._library_viewport_height(
            self._build_library_guide_panel(),
            self._build_library_prompt_panel(command_buffer, prompt_message),
        )

    def _build_library_frame(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
        command_buffer: str,
        prompt_message: str | None,
        scroll_offset: int,
    ) -> tuple[Group, int]:
        scrollable_content = self._build_library_scrollable_content(snapshots, groups)
        guide_panel = self._build_library_guide_panel()
        prompt_panel = self._build_library_prompt_panel(command_buffer, prompt_message)
        viewport_height = self._library_viewport_height(guide_panel, prompt_panel)
        library_view, max_scroll_offset = self._build_renderable_viewport(
            scrollable_content,
            scroll_offset,
            viewport_height,
        )
        return Group(library_view, guide_panel, prompt_panel), max_scroll_offset

    def _renderable_height(self, renderable: Any) -> int:
        renderable_lines = self.console.render_lines(
            renderable,
            options=self.console.options.update_dimensions(
                self._console_width(),
                self._console_height(),
            ),
            pad=False,
            new_lines=False,
        )
        return len(renderable_lines)

    def _library_viewport_height(self, guide_panel: Panel, prompt_panel: Panel) -> int:
        fixed_height = self._renderable_height(guide_panel) + self._renderable_height(prompt_panel)
        return max(self._console_height() - fixed_height, 6)

    def _build_library_prompt_panel(
        self,
        command_buffer: str,
        prompt_message: str | None,
    ) -> Panel:
        return self._build_input_prompt_panel("Command", command_buffer, "0", prompt_message)

    def _build_library_list_panel(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup] | None = None,
    ) -> Panel:
        if groups is None:
            groups = self._group_library_snapshots(snapshots)

        if not snapshots:
            return Panel(
                "No novels are stored yet.",
                title="Novel List",
                border_style="#9ece6a",
                box=box.ROUNDED,
                expand=True,
            )

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

        return Panel(
            Group(*items),
            title="Novel List",
            border_style="#9ece6a",
            box=box.ROUNDED,
            expand=True,
        )

    def _build_library_guide_panel(self) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        commands = Group(
            Text.assemble(
                ("Status  ", "#9aa5ce"),
                (self.last_status_message, f"bold {status_style}"),
            ),
            Text(""),
            Text("1) export <numbers>            Export novels like 1 or 2-6 or 3, 7-10.", style="#cbd5e1"),
            Text("2) delete <numbers>            Remove one or more novels by number.", style="#cbd5e1"),
            Text("3) delete language <group>     Remove all novels in a language group.", style="#cbd5e1"),
            Text("4) delete all                  Remove every novel from the library.", style="#cbd5e1"),
            Text("0) back                        Return to the dashboard.", style="#cbd5e1"),
        )
        return Panel(
            commands,
            title="Guide Rail",
            border_style=status_style,
            box=box.ROUNDED,
            expand=True,
        )

    def _parse_library_command(self, command: str) -> tuple[str, str | None] | None:
        raw = command.strip().lower()
        if raw in ("", "0", "back", "b"):
            return ("back", None)

        if raw in ("4", "delete all", "remove all"):
            return ("delete_all", None)

        for prefix in ("3 ", "delete language ", "delete lang ", "remove language "):
            if raw.startswith(prefix):
                payload = raw[len(prefix) :].strip()
                return ("delete_language", payload or None)

        for prefix in ("1 ", "export "):
            if raw.startswith(prefix):
                payload = raw[len(prefix) :].strip()
                return ("export", payload or None)

        for prefix in ("2 ", "delete ", "del ", "d "):
            if raw.startswith(prefix):
                payload = raw[len(prefix) :].strip()
                return ("delete", payload or None)

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

    def _confirm_library_action(self, message: str) -> bool:
        return (
            Prompt.ask(
                f"[bold #f6bd60]{message}[/bold #f6bd60]",
                choices=["yes", "no"],
                default="no",
                console=self.console,
            )
            == "yes"
        )

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

    def _delete_library_language_group(
        self,
        groups: list[LibraryLanguageGroup],
        group_index: int,
    ) -> list[LibrarySnapshot]:
        target_group = next(group for group in groups if group["index"] == group_index)
        deleted: list[LibrarySnapshot] = []
        for snapshot in target_group["snapshots"]:
            self.storage.delete_novel(snapshot["novel_id"])
            deleted.append(snapshot)
        return deleted

    def _export_library_novels(self, snapshots: list[LibrarySnapshot], selections: list[int]) -> None:
        fmt = Prompt.ask(
            "[bold #f6bd60]Format[/bold #f6bd60]",
            choices=["epub", "pdf"],
            default="epub",
            console=self.console,
        )
        output = Prompt.ask(
            "[bold #f6bd60]Output directory[/bold #f6bd60] (leave blank for novel library)",
            default="",
            console=self.console,
        )

        exported: list[str] = []
        failures: list[str] = []
        for selection in selections:
            snapshot = snapshots[selection - 1]
            try:
                self._export_novel(snapshot["novel_id"], fmt, output.strip() or None)
                exported.append(snapshot["novel_id"])
            except Exception as exc:
                failures.append(f"{snapshot['novel_id']}: {exc}")

        if exported:
            summary = "\n".join(exported[:6])
            if len(exported) > 6:
                summary = f"{summary}\n..."
            self.console.print(
                Panel(
                    f"Exported {len(exported)} novel(s) as {fmt.upper()}.\n{summary}",
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

        self._set_status(f"Exported {len(exported)} novel(s) as {fmt.upper()}.", "success")

    def _prompt_source(self) -> str | None:
        sources = available_sources()
        if not sources:
            self.console.print("[red]No sources are registered.[/red]")
            return None
        return Prompt.ask(
            "[bold #f6bd60]Source[/bold #f6bd60]",
            choices=sources,
            default=sources[0],
        )

    def _prompt_provider(self) -> str | None:
        providers = available_providers()
        if not providers:
            self.console.print("[red]No providers are registered.[/red]")
            return None

        default_provider = self.settings.get_provider_key()
        if default_provider not in providers:
            default_provider = providers[0]
        return Prompt.ask(
            "[bold #f6bd60]Provider[/bold #f6bd60]",
            choices=providers,
            default=default_provider,
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

    async def _do_scrape_metadata(self, source_key: str, novel_id: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_metadata(source_key, novel_id, mode=mode)

    async def _do_scrape_chapters(self, source_key: str, novel_id: str, chapters: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_chapters(source_key, novel_id, chapters, mode=mode)

    def _run_novel_ingest_flow(self, title: str, description: str, mode: str) -> None:
        self.console.clear()
        self.console.print(self._build_action_header(title, description))

        if not available_sources():
            self._set_status(f"{title} cancelled because no source is registered.", "warning")
            return

        novel_url = Prompt.ask("[bold #f6bd60]Novel URL[/bold #f6bd60]", console=self.console).strip()
        resolved_source = self._resolve_source_from_url(novel_url)
        if resolved_source is None:
            self._set_status(
                "Could not detect a supported source from that URL. Paste a full novel URL from a registered source.",
                "warning",
            )
            return

        source, novel_id = resolved_source
        chapters = self._prompt_chapter_selection()
        if not self._validate_chapter_selection(chapters):
            self._set_status("Use chapter selection like full, 1, or 3-8.", "warning")
            return

        try:
            with self.console.status("[bold #7dcfff]Saving novel metadata...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_metadata(source, novel_id, mode=mode))
            with self.console.status("[bold #7dcfff]Fetching raw chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_chapters(source, novel_id, chapters, mode=mode))
        except Exception as exc:
            self._show_error(f"{title} failed: {exc}")
            return

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
                        force=(mode == "update"),
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

        fallback_note = ""
        if fallback_used:
            fallback_note = "\nOpenAI API key was missing, so translation used dummy/dummy."

        self.console.print(
            Panel(
                (
                    f"{title} finished for {novel_id} from {source}.\n"
                    f"Source URL: {novel_url}\n"
                    f"Fetched and translated chapters {chapters} with {active_provider}/{active_model}."
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

    def _scrape_flow(self) -> None:
        self._run_novel_ingest_flow(
            "Add Novel",
            "Paste a novel URL and NovelAIBook will detect the source, scrape the novel, and translate the chapters into your library.",
            mode="full",
        )

    def _update_flow(self) -> None:
        self._run_novel_ingest_flow(
            "Update Novel",
            "Paste an existing novel URL to refresh metadata, raw chapters, and translated chapters for the selection you choose.",
            mode="update",
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

    def _collect_export_chapters(self, novel_id: str) -> list[dict[str, Any]]:
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise ValueError("Metadata not found; run scrape first.")

        chapters: list[dict[str, Any]] = []
        raw_chapters = meta.get("chapters", [])
        if not isinstance(raw_chapters, list):
            raise ValueError("Stored metadata has an invalid chapter list.")

        for chap in raw_chapters:
            if not isinstance(chap, dict):
                continue
            chap_id_value = chap.get("id")
            if chap_id_value is None:
                continue
            chap_id = str(chap_id_value)
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
            raise ValueError("No translated chapters are available for export.")
        return chapters

    def _export_novel(self, novel_id: str, fmt: str, output_dir: str | None) -> str:
        chapters = self._collect_export_chapters(novel_id)
        output_path = str(
            self.storage.build_export_path(
                novel_id,
                fmt,
                output_dir,
            )
        )
        if fmt == "pdf":
            self.exporter.export_pdf(novel_id=novel_id, chapters=chapters, output_path=output_path)
        else:
            self.exporter.export_epub(novel_id=novel_id, chapters=chapters, output_path=output_path)
        return output_path

    def _export_flow(self) -> None:
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Export",
                "Build EPUB or PDF from the translated chapters stored in the novel library.",
            )
        )

        novel_id = Prompt.ask("[bold #f6bd60]Novel ID[/bold #f6bd60]")
        output = Prompt.ask(
            "[bold #f6bd60]Output directory[/bold #f6bd60] (leave blank for novel library)",
            default="",
        )
        fmt = Prompt.ask(
            "[bold #f6bd60]Format[/bold #f6bd60]",
            choices=["epub", "pdf"],
            default="epub",
        )

        try:
            output_path = self._export_novel(novel_id, fmt, output.strip() or None)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self.console.print(
            Panel(
                f"Exported {fmt.upper()} to {output_path}",
                title="Export Complete",
                border_style="#9ece6a",
                box=box.ROUNDED,
            )
        )
        self._set_status(f"Exported {novel_id} as {fmt.upper()}.", "success")

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

    def _build_settings_screen(self) -> Group:
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

        return Group(
            self._build_action_header(
                "Settings",
                "Choose the provider, default model, and API key used by Add Novel translation.",
            ),
            Panel(settings_table, border_style="#bb9af7", box=box.ROUNDED),
            self._build_settings_guide_panel(provider, models),
        )

    def _build_settings_guide_panel(self, provider: str, models: list[str]) -> Panel:
        status_style = self.STATUS_STYLES.get(self.last_status_kind, self.STATUS_STYLES["info"])
        model_text = ", ".join(models) if models else "No provider-declared models."
        return Panel(
            Group(
                Text.assemble(
                    ("Status  ", "#9aa5ce"),
                    (self.last_status_message, f"bold {status_style}"),
                ),
                Text.assemble(("Provider models  ", "#9aa5ce"), (model_text, "#cbd5e1")),
                Text(""),
                Text("1) select provider            Switch the active translation provider.", style="#cbd5e1"),
                Text("2) choose model               Set the default model for the current provider.", style="#cbd5e1"),
                Text("3) set API key                Update the runtime API key used by the provider.", style="#cbd5e1"),
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
        if raw in ("2", "model", "choose model"):
            return "model"
        if raw in ("3", "api", "api key", "set api key"):
            return "api_key"
        return None

    def _settings_menu(self) -> None:
        self._set_status("Use 1 to choose a provider, 2 to choose a model, 3 to set the API key, or 0 to go back.", "info")
        while True:
            command = self._prompt_renderable_command(
                self._build_settings_screen(),
                default_value="0",
            )
            action = self._parse_settings_command(command)
            if action is None:
                self._set_status("Unknown settings command. Use 1, 2, 3, or 0.", "warning")
                continue
            if action == "back":
                self._set_status("Settings ready.", "info")
                return

            if action == "provider":
                providers = available_providers()
                if not providers:
                    self._set_status("No providers are registered.", "warning")
                    continue

                current_provider = self.settings.get_provider_key()
                default_provider = current_provider if current_provider in providers else providers[0]
                provider = Prompt.ask(
                    "[bold #f6bd60]Provider[/bold #f6bd60]",
                    choices=providers,
                    default=default_provider,
                    console=self.console,
                )
                self.settings.set_provider_key(provider)

                models = self._available_models_for_provider(provider)
                current_model = self.settings.get_provider_model()
                if models and current_model not in models:
                    self.settings.set_provider_model(models[0])
                    self._set_status(f"Provider set to {provider}. Default model changed to {models[0]}.", "success")
                else:
                    self._set_status(f"Provider set to {provider}.", "success")
                continue

            if action == "model":
                provider = self.settings.get_provider_key()
                models = self._available_models_for_provider(provider)
                current_model = self.settings.get_provider_model()
                if models:
                    default_model = current_model if current_model in models else models[0]
                    model = Prompt.ask(
                        "[bold #f6bd60]Model[/bold #f6bd60]",
                        choices=models,
                        default=default_model,
                        console=self.console,
                    )
                else:
                    model = Prompt.ask(
                        "[bold #f6bd60]Model[/bold #f6bd60]",
                        default=current_model,
                        console=self.console,
                    )
                self.settings.set_provider_model(model)
                self._set_status(f"Default model set to {model}.", "success")
                continue

            api_key = Prompt.ask(
                "[bold #f6bd60]API key[/bold #f6bd60] (leave blank to keep current)",
                password=True,
                default="",
                console=self.console,
            )
            if not api_key:
                self._set_status("API key unchanged.", "info")
                continue

            self.settings.set_api_key(api_key)
            self._set_status(f"API key updated for {self.settings.get_provider_key()}.", "success")

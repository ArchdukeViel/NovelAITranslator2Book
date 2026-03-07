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
from novelai.providers.registry import available_providers
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.settings_service import SettingsService
from novelai.services.usage_service import UsageService
from novelai.sources.registry import available_sources

if os.name == "nt":
    import msvcrt


class LibrarySnapshot(TypedDict):
    """Display-ready snapshot of one novel in storage."""

    novel_id: str
    title: str
    total_chapters: int
    translated_chapters: int


class TUIApp:
    """Rich dashboard for scraping, translating, and exporting novels."""

    MENU_OPTIONS = [
        ("list", "Browse stored novels and translation progress"),
        ("scrape", "Fetch metadata and raw chapters into the library"),
        ("translate", "Run chapter translation with the active provider"),
        ("export", "Build EPUB or PDF from translated chapters"),
        ("diagnostics", "Inspect usage, cache health, and recent activity"),
        ("settings", "Review or change provider, model, and API key"),
        ("exit", "Close the dashboard"),
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

            if option == "list":
                self._list_novels()
            elif option == "scrape":
                self._scrape_flow()
            elif option == "translate":
                self._translate_flow()
            elif option == "export":
                self._export_flow()
            elif option == "diagnostics":
                self._diagnostics_menu()
            elif option == "settings":
                self._settings_menu()
            elif option == "exit":
                self._set_status("Session closed.", "muted")
                break

            self._pause()

    def _render_dashboard(self) -> None:
        self.console.clear()
        self.console.print(self._build_dashboard())

    def _prompt_action(self) -> str:
        if os.name != "nt":
            self._render_dashboard()
            return Prompt.ask(
                "[bold #f6bd60]Action[/bold #f6bd60]",
                choices=[key for key, _ in self.MENU_OPTIONS],
                default="list",
                console=self.console,
            )
        self._lock_layout_width()
        return self._prompt_action_live()

    def _prompt_action_live(self) -> str:
        action_buffer = ""
        prompt_message: str | None = None
        actions = [key for key, _ in self.MENU_OPTIONS]
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
                    option = action_buffer.strip().lower() or "list"
                    if option in actions:
                        return option
                    prompt_message = f"Unknown action '{option}'."
                    needs_refresh = True
                    continue

                if key == "\t":
                    completed = self._autocomplete_action(action_buffer)
                    if completed != action_buffer:
                        action_buffer = completed
                    elif action_buffer:
                        prompt_message = "No matching action."
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

                if key.isprintable():
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
        input_text = Text.assemble(
            ("Action  ", "#9aa5ce"),
            (action_buffer or "list", "bold #f6bd60" if action_buffer else "#7aa2f7"),
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
        )

    def _build_dashboard_viewport(self, scroll_offset: int, viewport_height: int) -> tuple[Segments, int]:
        dashboard_lines = self.console.render_lines(
            self._build_dashboard(),
            pad=False,
            new_lines=False,
        )
        max_scroll_offset = max(0, len(dashboard_lines) - viewport_height)
        clamped_offset = min(max(scroll_offset, 0), max_scroll_offset)
        visible_lines = dashboard_lines[clamped_offset : clamped_offset + viewport_height]

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

        if panel_width < 88:
            grid = Table.grid(expand=True, padding=(0, 1))
            grid.add_column(style="bold #f6bd60", no_wrap=True)
            grid.add_column(style="#cbd5e1")

            for action, description in self.MENU_OPTIONS:
                grid.add_row(action, description)

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

        for action, description in self.MENU_OPTIONS:
            table.add_row(action, description)

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
                "No novels are stored yet.\nUse scrape to pull metadata and chapters into the library.",
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
                "Actions: list, scrape, translate, export, diagnostics, settings, exit.",
                style="#cbd5e1",
            )
        else:
            help_line = Text(
                "Type list, scrape, translate, export, diagnostics, settings, or exit.",
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
                }
            )
        return snapshots

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

    def _autocomplete_action(self, action_buffer: str) -> str:
        prefix = action_buffer.strip().lower()
        if not prefix:
            return action_buffer

        matches = [action for action, _ in self.MENU_OPTIONS if action.startswith(prefix)]
        if len(matches) == 1:
            return matches[0]
        return action_buffer

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
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Library",
                "Browse stored novels and their translation coverage.",
            )
        )

        snapshots = self._collect_library_snapshot(limit=50)
        if not snapshots:
            self.console.print(
                Panel(
                    "No novels are stored yet.",
                    border_style="#9ece6a",
                    box=box.ROUNDED,
                )
            )
            self._set_status("The library is empty.", "warning")
            return

        table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #9ece6a")
        table.add_column("Novel ID", style="bold #e5e9f0", no_wrap=True)
        table.add_column("Title", style="#cbd5e1")
        table.add_column("Chapters", justify="right", style="#73daca", no_wrap=True)
        table.add_column("Translated", justify="right", style="#f6bd60", no_wrap=True)

        for snapshot in snapshots:
            table.add_row(
                snapshot["novel_id"],
                snapshot["title"],
                str(snapshot["total_chapters"]),
                str(snapshot["translated_chapters"]),
            )

        self.console.print(Panel(table, border_style="#9ece6a", box=box.ROUNDED))
        self._set_status(f"Showing {len(snapshots)} novel(s) from the library.", "success")

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

    async def _do_scrape_metadata(self, source_key: str, novel_id: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_metadata(source_key, novel_id, mode=mode)

    async def _do_scrape_chapters(self, source_key: str, novel_id: str, chapters: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_chapters(source_key, novel_id, chapters, mode=mode)

    def _scrape_flow(self) -> None:
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Scrape",
                "Pull metadata and raw chapter text into the novel library.",
            )
        )

        source = self._prompt_source()
        if source is None:
            self._set_status("Scrape cancelled because no source is registered.", "warning")
            return
        novel_id = Prompt.ask("[bold #f6bd60]Novel ID or URL[/bold #f6bd60]")
        chapters = Prompt.ask(
            "[bold #f6bd60]Chapter selection[/bold #f6bd60]",
            default="1",
        )
        mode = Prompt.ask(
            "[bold #f6bd60]Scrape mode[/bold #f6bd60]",
            choices=["full", "update"],
            default="update",
        )

        try:
            with self.console.status("[bold #7dcfff]Scraping metadata...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_metadata(source, novel_id, mode=mode))
            with self.console.status("[bold #7dcfff]Scraping chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_chapters(source, novel_id, chapters, mode=mode))

            self.console.print(
                Panel(
                    f"Saved metadata and chapters for {novel_id} from {source}.",
                    title="Scrape Complete",
                    border_style="#9ece6a",
                    box=box.ROUNDED,
                )
            )
            self._set_status(f"Scraped {novel_id} from {source}.", "success")
        except Exception as exc:
            self._show_error(f"Scrape failed: {exc}")

    def _translate_flow(self) -> None:
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Translate",
                "Translate selected chapters with the default provider or a manual override.",
            )
        )

        source = self._prompt_source()
        if source is None:
            self._set_status("Translation cancelled because no source is registered.", "warning")
            return
        novel_id = Prompt.ask("[bold #f6bd60]Novel ID or URL[/bold #f6bd60]")
        chapters = Prompt.ask(
            "[bold #f6bd60]Chapter selection[/bold #f6bd60]",
            default="1",
        )

        if (
            Prompt.ask(
                "[bold #f6bd60]Use configured provider and model?[/bold #f6bd60]",
                choices=["yes", "no"],
                default="yes",
            )
            == "no"
        ):
            provider = self._prompt_provider()
            if provider is None:
                self._set_status("Translation cancelled because no provider is registered.", "warning")
                return
            model = Prompt.ask(
                "[bold #f6bd60]Provider model[/bold #f6bd60]",
                default=self.settings.get_provider_model(),
            )
        else:
            provider = None
            model = None

        try:
            with self.console.status("[bold #7dcfff]Translating chapters...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(
                    self._do_translate_chapters(
                        source,
                        novel_id,
                        chapters,
                        provider,
                        model,
                    )
                )

            active_provider = provider or self.settings.get_provider_key()
            active_model = model or self.settings.get_provider_model()
            self.console.print(
                Panel(
                    f"Translated chapters {chapters} for {novel_id} with {active_provider}/{active_model}.",
                    title="Translation Complete",
                    border_style="#9ece6a",
                    box=box.ROUNDED,
                )
            )
            self._set_status(f"Translated {novel_id} with {active_provider}/{active_model}.", "success")
        except Exception as exc:
            self._show_error(f"Translation failed: {exc}")

    async def _do_translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> None:
        await self.orchestrator.translate_chapters(
            source_key=source_key,
            novel_id=novel_id,
            chapters=chapters,
            provider_key=provider_key,
            provider_model=provider_model,
        )

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

        meta = self.storage.load_metadata(novel_id)
        if not meta:
            self._show_error("Metadata not found; run scrape first.")
            return

        chapters: list[dict[str, Any]] = []
        raw_chapters = meta.get("chapters", [])
        if not isinstance(raw_chapters, list):
            self._show_error("Stored metadata has an invalid chapter list.")
            return

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

        output_path = str(
            self.storage.build_export_path(
                novel_id,
                fmt,
                output.strip() or None,
            )
        )
        if fmt == "pdf":
            self.exporter.export_pdf(novel_id=novel_id, chapters=chapters, output_path=output_path)
        else:
            self.exporter.export_epub(novel_id=novel_id, chapters=chapters, output_path=output_path)

        self.console.print(
            Panel(
                f"Exported {fmt.upper()} to {output_path}",
                title="Export Complete",
                border_style="#9ece6a",
                box=box.ROUNDED,
            )
        )
        self._set_status(f"Exported {novel_id} as {fmt.upper()}.", "success")

    def _diagnostics_menu(self) -> None:
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Diagnostics",
                "Inspect library health, translation usage, and cache activity.",
            )
        )

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

        stats = Table.grid(expand=True, padding=(0, 2))
        stats.add_column(style="bold #f6bd60")
        stats.add_column(style="#e5e9f0")
        stats.add_row("Novels stored", str(total_novels))
        stats.add_row("Translated chapters", str(total_translated))
        stats.add_row("Cached translations", str(cache_entries if cache_entries >= 0 else "error"))
        stats.add_row("Total translation requests", str(usage_summary.get("total_requests")))
        stats.add_row("Total tokens used", str(usage_summary.get("total_tokens")))
        stats.add_row("Estimated cost (USD)", f"${usage_summary.get('estimated_cost_usd', 0):.6f}")

        usage_table = Table(box=box.SIMPLE_HEAVY, expand=True, show_header=True, header_style="bold #7dcfff")
        usage_table.add_column("Timestamp", style="#cbd5e1")
        usage_table.add_column("Provider/Model", style="#e5e9f0")
        usage_table.add_column("Tokens", justify="right", style="#f6bd60")

        if recent_usage:
            for entry in recent_usage:
                usage_table.add_row(
                    str(entry.get("timestamp")),
                    f"{entry.get('provider')}/{entry.get('model')}",
                    str(entry.get("tokens")),
                )
        else:
            usage_table.add_row("No usage records yet.", "-", "-")

        self.console.print(
            Panel(
                Group(stats, Text(""), usage_table),
                border_style="#7aa2f7",
                box=box.ROUNDED,
            )
        )

        if (
            Prompt.ask(
                "[bold #f6bd60]Clear usage history?[/bold #f6bd60]",
                choices=["yes", "no"],
                default="no",
            )
            == "yes"
        ):
            self.usage.clear()
            self.console.print("[green]Usage history cleared.[/green]")
            self._set_status("Usage history cleared.", "success")
            return

        self._set_status("Diagnostics refreshed.", "info")

    def _settings_menu(self) -> None:
        self.console.clear()
        self.console.print(
            self._build_action_header(
                "Settings",
                "Review and update the active provider configuration.",
            )
        )

        settings_table = Table.grid(expand=True, padding=(0, 2))
        settings_table.add_column(style="bold #f6bd60")
        settings_table.add_column(style="#e5e9f0")
        settings_table.add_row("Provider", self.settings.get_provider_key())
        settings_table.add_row("Model", self.settings.get_provider_model())
        settings_table.add_row("API key", "yes" if self.settings.get_api_key() else "no")

        self.console.print(Panel(settings_table, border_style="#bb9af7", box=box.ROUNDED))

        if (
            Prompt.ask(
                "[bold #f6bd60]Change settings?[/bold #f6bd60]",
                choices=["yes", "no"],
                default="no",
            )
            != "yes"
        ):
            self._set_status("Settings unchanged.", "info")
            return

        provider = self._prompt_provider()
        if provider is None:
            self._set_status("Settings update cancelled because no provider is registered.", "warning")
            return
        model = Prompt.ask(
            "[bold #f6bd60]Provider model[/bold #f6bd60]",
            default=self.settings.get_provider_model(),
        )
        api_key = Prompt.ask(
            "[bold #f6bd60]API key[/bold #f6bd60] (leave blank to keep current)",
            password=True,
            default="",
        )

        self.settings.set_provider_key(provider)
        self.settings.set_provider_model(model)
        if api_key:
            self.settings.set_api_key(api_key)

        self.console.print(
            Panel(
                f"Provider set to {provider} with model {model}.",
                title="Settings Updated",
                border_style="#9ece6a",
                box=box.ROUNDED,
            )
        )
        self._set_status(f"Updated provider settings to {provider}/{model}.", "success")

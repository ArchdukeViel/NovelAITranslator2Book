from __future__ import annotations

# pyright: reportAttributeAccessIssue=false
import os
from io import StringIO
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from novelai.export.registry import available_exporters
from novelai.utils.chapter_selection import is_full_chapter_selection

if os.name == "nt":
    pass

if TYPE_CHECKING:
    from novelai.tui.app import LibraryLanguageGroup, LibrarySnapshot


class LibraryScreenMixin:
    """Library browsing, inspection, deletion, and export screen methods."""

    def _list_novels(self) -> None:
        self._set_status(
            "Use 1) export, 2) delete custom, 3) delete all, 4) inspect, or 0) back.",
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
                self._set_status("Unknown library command. Use 1, 2, 3, 4, or 0.", "warning")
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

            if action == "inspect":
                if not snapshots:
                    self._set_status("There are no novels to inspect.", "warning")
                    continue
                self._inspect_library_novel(snapshots, groups)
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

    def _renderable_height(self, renderable: Any, width: int | None = None) -> int:
        measuring_console = Console(
            file=StringIO(),
            force_terminal=False,
            color_system=None,
            width=width or self._console_width(),
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
            groups = self._group_library_snapshots(snapshots)  # type: ignore[attr-defined]

        assert groups is not None

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
            table.add_column("Source", justify="right", style="#73daca", no_wrap=True)
            table.add_column("Stored", justify="right", style="#7dcfff", no_wrap=True)
            table.add_column("Translated", justify="right", style="#f6bd60", no_wrap=True)

            for snapshot in group["snapshots"]:
                table.add_row(
                    f"{row_number})",
                    snapshot["title"],
                    snapshot["novel_id"],
                    str(snapshot["total_chapters"]),
                    str(self._snapshot_stored_chapters(snapshot)),
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
                    "1) export  2) delete custom  3) delete all  4) inspect  0) back",
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
                Text("4) inspect                     Review source, stored, translated, and missing chapter ranges.", style="#cbd5e1"),
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
        if raw in ("4", "inspect", "i", "details", "detail", "info"):
            return "inspect"

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

    def _snapshot_stored_chapters(self, snapshot: LibrarySnapshot) -> int:
        stored = snapshot.get("stored_chapters")
        if isinstance(stored, int):
            return stored
        return snapshot["total_chapters"]

    def _snapshot_progress_text(self, snapshot: LibrarySnapshot) -> str:
        stored = self._snapshot_stored_chapters(snapshot)
        total = snapshot["total_chapters"]
        translated = snapshot["translated_chapters"]
        if total > 0:
            return f"stored {stored}/{total} · tl {translated}"
        return f"stored {stored} · tl {translated}"

    def _format_chapter_inventory(self, numbers: list[int], *, empty_label: str = "none") -> str:
        if not numbers:
            return f"{empty_label} (0)"
        return f"{self._format_number_ranges(numbers)} ({len(numbers)})"

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

    def _build_library_inspection_panel(
        self,
        snapshot: LibrarySnapshot,
        metadata: dict[str, Any] | None = None,
    ) -> Panel:
        metadata = metadata or self.storage.load_metadata(snapshot["novel_id"]) or {}
        source_numbers = self._metadata_chapter_numbers(metadata)
        stored_numbers = self._stored_chapter_numbers(snapshot["novel_id"], metadata)
        translated_numbers = self._translated_chapter_numbers(snapshot["novel_id"], metadata)
        missing_numbers = sorted(set(source_numbers) - set(stored_numbers))
        untranslated_numbers = sorted(set(stored_numbers) - set(translated_numbers))

        details = Table.grid(expand=True, padding=(0, 2))
        details.add_column(style="#9aa5ce", no_wrap=True)
        details.add_column(style="#e5e9f0")
        details.add_row("Title", snapshot["title"])
        details.add_row("Novel ID", snapshot["novel_id"])
        details.add_row("Language", snapshot["language"])
        details.add_row("Source chapters", self._format_chapter_inventory(source_numbers, empty_label="unknown"))
        details.add_row("Stored locally", self._format_chapter_inventory(stored_numbers))
        details.add_row("Translated", self._format_chapter_inventory(translated_numbers))
        details.add_row("Missing locally", self._format_chapter_inventory(missing_numbers))
        details.add_row("Stored untranslated", self._format_chapter_inventory(untranslated_numbers))

        source_key = metadata.get("source") or metadata.get("source_key")
        if isinstance(source_key, str) and source_key.strip():
            details.add_row("Source key", source_key.strip())

        return Panel(
            Group(
                details,
                Text(""),
                Text("0) back", style="#cbd5e1"),
            ),
            title="Library Coverage",
            border_style="#7aa2f7",
            box=box.ROUNDED,
            expand=True,
        )

    def _inspect_library_novel(
        self,
        snapshots: list[LibrarySnapshot],
        groups: list[LibraryLanguageGroup],
    ) -> None:
        while True:
            selection = self._prompt_library_novel_selection(
                "Inspect Novel",
                "Choose one novel to review which chapters are stored locally and which are translated.",
                snapshots,
                groups,
                label="Novel Number",
            )
            if selection is None:
                self._set_status("Inspect novel cancelled.", "warning")
                return
            if len(selection) != 1:
                self._set_status("Choose exactly one novel row to inspect.", "warning")
                continue

            snapshot = snapshots[selection[0] - 1]
            self._show_library_novel_inspection(snapshot)
            return

    def _show_library_novel_inspection(self, snapshot: LibrarySnapshot) -> None:
        metadata = self.storage.load_metadata(snapshot["novel_id"]) or {}
        while True:
            command = self._prompt_renderable_command(
                self._build_library_action_screen(
                    "Novel Coverage",
                    "Review remote, stored, translated, missing, and untranslated chapter ranges for this novel.",
                    self._build_library_inspection_panel(snapshot, metadata),
                ),
                default_value="0",
                label="Command",
            ).strip()
            if command.lower() in ("", "0", "back", "b"):
                self._set_status(f"Reviewed chapter coverage for {snapshot['novel_id']}.", "info")
                return
            self._set_status("Use 0 to return to the library list.", "warning")

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

        language_choice = self._prompt_numbered_choice(
            lambda: self._build_library_action_screen(
                "Export Language",
                "Choose which language version to export.",
                self._build_numbered_choice_panel(
                    "Language",
                    ["Translated", "Source (original)"],
                    descriptions=[
                        "Export the translated text.",
                        "Export the original source text.",
                    ],
                    border_style="#7aa2f7",
                ),
            ),
            option_count=2,
            default_value="1",
        )
        if language_choice is None:
            self._set_status("Export cancelled.", "warning")
            return
        language = "source" if language_choice == 2 else "translated"

        include_toc = False
        if fmt == "epub":
            toc_choice = self._prompt_numbered_choice(
                lambda: self._build_library_action_screen(
                    "Table of Contents",
                    "Include a table of contents page in the EPUB?",
                    self._build_numbered_choice_panel(
                        "TOC",
                        ["No", "Yes"],
                        descriptions=[
                            "Skip the table of contents page.",
                            "Add a table of contents page after the title page.",
                        ],
                        border_style="#7aa2f7",
                    ),
                ),
                option_count=2,
                default_value="1",
            )
            if toc_choice is None:
                self._set_status("Export cancelled.", "warning")
                return
            include_toc = toc_choice == 2

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

        language_label_text = "source" if language == "source" else "translated"
        exported: list[str] = []
        failures: list[str] = []
        for selection in selections:
            snapshot = snapshots[selection - 1]
            try:
                self._export_novel(
                    snapshot["novel_id"], fmt, None,
                    chapter_selection=chapter_selection, language=language, include_toc=include_toc,
                )
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
                        f"Exported {len(exported)} novel(s) as {fmt.upper()} ({language_label_text}).\n"
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


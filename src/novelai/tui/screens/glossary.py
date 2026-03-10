from __future__ import annotations

# pyright: reportAttributeAccessIssue=false
from typing import TYPE_CHECKING, Any

from rich import box
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

if TYPE_CHECKING:
    from novelai.tui.app import LibrarySnapshot


class GlossaryScreenMixin:
    """Glossary browsing, add, and remove screen methods."""

    def _glossary_menu(self) -> None:
        snapshots: list[LibrarySnapshot] = self._collect_library_snapshot(limit=200)
        if not snapshots:
            self._set_status("Library is empty — add a novel first.", "warning")
            return

        # Pick a novel
        novel_id = self._pick_novel_for_glossary(snapshots)
        if novel_id is None:
            return

        self._set_status(f"Managing glossary for '{novel_id}'.", "info")
        while True:
            entries = self.storage.load_glossary(novel_id)
            panel = self._build_glossary_panel(novel_id, entries)
            command = self._prompt_renderable_command(
                panel,
                label="Glossary",
                allow_any_printable=True,
            )
            command = command.strip().lower()

            if command in ("0", "back", ""):
                return
            elif command in ("1", "add"):
                self._glossary_add_term(novel_id)
            elif command in ("2", "remove"):
                self._glossary_remove_term(novel_id, entries)
            elif command in ("3", "clear"):
                if entries:
                    self.storage.save_glossary(novel_id, [])
                    self._set_status("Glossary cleared.", "success")
                else:
                    self._set_status("Glossary is already empty.", "warning")
            else:
                self._set_status("Unknown command. Use 1 (add), 2 (remove), 3 (clear), or 0 (back).", "warning")

    def _pick_novel_for_glossary(self, snapshots: list[LibrarySnapshot]) -> str | None:
        table = Table(
            title="Select a novel",
            box=box.ROUNDED,
            border_style="#bb9af7",
            padding=(0, 1),
        )
        table.add_column("#", style="bold #f6bd60", width=4)
        table.add_column("Novel ID", style="#7aa2f7")
        table.add_column("Title", style="#e5e9f0")
        for idx, snap in enumerate(snapshots, 1):
            table.add_row(str(idx), snap["novel_id"], snap["title"])

        command = self._prompt_renderable_command(table, label="Novel #")
        command = command.strip()
        if command in ("0", "back", ""):
            return None
        try:
            index = int(command) - 1
            if 0 <= index < len(snapshots):
                return snapshots[index]["novel_id"]
        except ValueError:
            pass
        self._set_status("Invalid selection.", "warning")
        return None

    def _build_glossary_panel(self, novel_id: str, entries: list[dict[str, Any]]) -> Panel:
        table = Table(box=box.SIMPLE, padding=(0, 2))
        table.add_column("#", style="bold #f6bd60", width=4)
        table.add_column("Source", style="#7aa2f7")
        table.add_column("Target", style="#9ece6a")
        table.add_column("Notes", style="#c0caf5")

        if entries:
            for idx, entry in enumerate(entries, 1):
                table.add_row(
                    str(idx),
                    str(entry.get("source", "")),
                    str(entry.get("target", "")),
                    str(entry.get("notes", "") or ""),
                )
        else:
            table.add_row("-", "(empty)", "", "")

        footer = "1) add  2) remove  3) clear  0) back"
        return Panel(
            table,
            title=f"Glossary — {novel_id}",
            subtitle=footer,
            border_style="#bb9af7",
            box=box.ROUNDED,
        )

    def _glossary_add_term(self, novel_id: str) -> None:
        source = Prompt.ask("[bold #f6bd60]Source term[/bold #f6bd60]", console=self.console).strip()
        if not source:
            self._set_status("Source term cannot be empty.", "warning")
            return
        target = Prompt.ask("[bold #f6bd60]Target term[/bold #f6bd60]", console=self.console).strip()
        if not target:
            self._set_status("Target term cannot be empty.", "warning")
            return
        notes = Prompt.ask("[bold #f6bd60]Notes (optional)[/bold #f6bd60]", default="", console=self.console).strip() or None

        entries = self.storage.load_glossary(novel_id)
        entries = [e for e in entries if e.get("source") != source]
        entries.append({"source": source, "target": target, "locked": True, "notes": notes})
        self.storage.save_glossary(novel_id, entries)
        self._set_status(f"Added: {source} → {target}", "success")

    def _glossary_remove_term(self, novel_id: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            self._set_status("Glossary is empty — nothing to remove.", "warning")
            return
        command = Prompt.ask("[bold #f6bd60]Term # to remove[/bold #f6bd60]", console=self.console).strip()
        try:
            index = int(command) - 1
            if 0 <= index < len(entries):
                removed = entries.pop(index)
                self.storage.save_glossary(novel_id, entries)
                self._set_status(f"Removed: {removed.get('source')}", "success")
                return
        except ValueError:
            pass
        self._set_status("Invalid term number.", "warning")

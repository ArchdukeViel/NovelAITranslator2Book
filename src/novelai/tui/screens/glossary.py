from __future__ import annotations

import asyncio

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
            elif command in ("4", "review", "status"):
                self._glossary_review_term(novel_id, entries)
            elif command in ("5", "ocr ingest", "ocr-ingest", "ingest"):
                self._glossary_ocr_ingest(novel_id)
            elif command in ("6", "ocr list", "ocr-list", "list ocr", "pending"):
                self._glossary_ocr_list_pending(novel_id)
            elif command in ("7", "ocr review", "ocr-review", "review ocr"):
                self._glossary_ocr_review(novel_id)
            else:
                self._set_status(
                    "Unknown command. Use 1 (add), 2 (remove), 3 (clear), 4 (review), 5 (ocr ingest), 6 (ocr list), 7 (ocr review), or 0 (back).",
                    "warning",
                )

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
        table.add_column("Status", style="#e0af68")
        table.add_column("Notes", style="#c0caf5")

        if entries:
            for idx, entry in enumerate(entries, 1):
                table.add_row(
                    str(idx),
                    str(entry.get("source", "")),
                    str(entry.get("target", "")),
                    str(entry.get("status") or "approved"),
                    str(entry.get("notes", "") or ""),
                )
        else:
            table.add_row("-", "(empty)", "", "", "")

        footer = "1) add  2) remove  3) clear  4) review status  5) ocr ingest  6) ocr list  7) ocr review  0) back"
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
        entries.append({"source": source, "target": target, "locked": True, "notes": notes, "status": "pending"})
        self.storage.save_glossary(novel_id, entries)
        self._set_status(f"Added: {source} → {target} [pending]", "success")

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

    def _glossary_review_term(self, novel_id: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            self._set_status("Glossary is empty — nothing to review.", "warning")
            return

        command = Prompt.ask("[bold #f6bd60]Term # to review[/bold #f6bd60]", console=self.console).strip()
        try:
            index = int(command) - 1
        except ValueError:
            self._set_status("Invalid term number.", "warning")
            return

        if index < 0 or index >= len(entries):
            self._set_status("Invalid term number.", "warning")
            return

        status = Prompt.ask(
            "[bold #f6bd60]Status[/bold #f6bd60]",
            choices=["pending", "approved", "ignored", "translated"],
            default="approved",
            console=self.console,
        ).strip().lower()

        updated_entries = list(entries)
        updated_entries[index] = {**updated_entries[index], "status": status}
        self.storage.save_glossary(novel_id, updated_entries)
        self._set_status(f"Updated status: {updated_entries[index].get('source')} -> {status}", "success")

    def _glossary_ocr_ingest(self, novel_id: str) -> None:
        chapters = Prompt.ask(
            "[bold #f6bd60]OCR ingest chapter selection[/bold #f6bd60]",
            default="all",
            console=self.console,
        ).strip() or "all"
        overwrite = (
            Prompt.ask(
                "[bold #f6bd60]Overwrite reviewed OCR?[/bold #f6bd60]",
                choices=["y", "n"],
                default="n",
                console=self.console,
            ).strip().lower()
            == "y"
        )
        mark_required = (
            Prompt.ask(
                "[bold #f6bd60]Require OCR review before translation?[/bold #f6bd60]",
                choices=["y", "n"],
                default="y",
                console=self.console,
            ).strip().lower()
            == "y"
        )

        summary = asyncio.run(
            self.orchestrator.ingest_ocr_candidates(
                novel_id=novel_id,
                chapters=chapters,
                mark_required=mark_required,
                overwrite=overwrite,
            )
        )
        failed = len(summary.get("failed", []))
        self._set_status(
            "OCR ingest complete: "
            f"updated={summary.get('updated', 0)}, "
            f"skipped_no_images={summary.get('skipped_no_images', 0)}, "
            f"skipped_reviewed={summary.get('skipped_reviewed', 0)}, "
            f"failed={failed}",
            "success" if failed == 0 else "warning",
        )

    def _glossary_ocr_list_pending(self, novel_id: str) -> None:
        chapter_ids = self.storage.list_stored_chapters(novel_id)
        pending: list[tuple[str, str]] = []
        for chapter_id in chapter_ids:
            media_state = self.storage.load_chapter_media_state(novel_id, chapter_id)
            if media_state is None:
                continue
            if not bool(media_state.get("ocr_required", False)):
                continue
            status = str(media_state.get("ocr_status") or "pending").strip().lower()
            if status != "reviewed":
                pending.append((chapter_id, status))

        if not pending:
            self._set_status("No chapters pending OCR review.", "success")
            return

        preview = ", ".join(f"{chapter}({status})" for chapter, status in pending[:6])
        if len(pending) > 6:
            preview += f", +{len(pending) - 6} more"
        self._set_status(f"OCR pending chapters: {preview}", "info")

    def _glossary_ocr_review(self, novel_id: str) -> None:
        chapter_id = Prompt.ask("[bold #f6bd60]Chapter # to review[/bold #f6bd60]", console=self.console).strip()
        if not chapter_id:
            self._set_status("Chapter number cannot be empty.", "warning")
            return

        status = Prompt.ask(
            "[bold #f6bd60]OCR status[/bold #f6bd60]",
            choices=["pending", "reviewed", "skipped", "failed"],
            default="reviewed",
            console=self.console,
        ).strip().lower()
        text = Prompt.ask(
            "[bold #f6bd60]OCR text (optional)[/bold #f6bd60]",
            default="",
            console=self.console,
        ).strip() or None

        existing = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
        self.storage.save_chapter_media_state(
            novel_id,
            chapter_id,
            ocr_required=True,
            ocr_status=status,
            ocr_text=text if text is not None else existing.get("ocr_text"),
        )
        self._set_status(f"Updated OCR chapter {chapter_id} -> {status}", "success")

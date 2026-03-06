from __future__ import annotations

import asyncio

import json
from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from novelai.config.settings import settings
from novelai.providers.registry import available_providers
from novelai.services.export_service import ExportService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.services.usage_service import UsageService
from novelai.sources.registry import available_sources, get_source
from novelai.utils.chapter_selection import parse_chapter_selection


class TUIApp:
    """Basic TUI application orchestration."""

    def __init__(self) -> None:
        self.console = Console()
        self.storage = StorageService()
        self.translation = TranslationService()
        self.exporter = ExportService()
        self.settings = SettingsService()
        self.usage = UsageService()

    def run(self) -> None:
        self.console.print("[bold green]Novel AI TUI[/bold green]\n")
        while True:
            option = Prompt.ask(
                "Select an option",
                choices=[
                    "list",
                    "scrape",
                    "translate",
                    "export",
                    "diagnostics",
                    "settings",
                    "exit",
                ],
                default="list",
            )

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
                break

    def _list_novels(self) -> None:
        novels = self.storage.list_novels()
        if not novels:
            self.console.print("No novels in storage yet.")
            return
        for n in novels:
            self.console.print(f"- {n}")

    async def _do_scrape_metadata(self, source_key: str, novel_id: str) -> None:
        source = get_source(source_key)
        meta = await source.fetch_metadata(novel_id)
        self.storage.save_metadata(novel_id, meta)
        self.console.print(f"Saved metadata for {novel_id} from {source_key}")

    async def _do_scrape_chapters(self, source_key: str, novel_id: str, chapters: str) -> None:
        source = get_source(source_key)
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        selection = parse_chapter_selection(chapters)
        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

        for spec in selection:
            chapter_num = spec.chapter
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                self.console.print(f"Skipping missing chapter {chapter_num}")
                continue
            text = await source.fetch_chapter(chapter["url"])
            self.storage.save_chapter(novel_id, str(chapter_num), text)
            self.console.print(f"Saved chapter {chapter_num}")

    def _scrape_flow(self) -> None:
        source = Prompt.ask(
            "Source",
            choices=available_sources(),
            default=available_sources()[0] if available_sources() else None,
        )
        novel_id = Prompt.ask("Novel ID or URL")
        chapters = Prompt.ask("Chapter selection (e.g. 1-3;5)", default="1")
        mode = Prompt.ask("Scrape mode", choices=["full", "update"], default="update")

        try:
            asyncio.run(self._do_scrape_metadata(source, novel_id, mode=mode))
            asyncio.run(self._do_scrape_chapters(source, novel_id, chapters, mode=mode))
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] {exc}")

    def _translate_flow(self) -> None:
        source = Prompt.ask(
            "Source",
            choices=available_sources(),
            default=available_sources()[0] if available_sources() else None,
        )
        novel_id = Prompt.ask("Novel ID or URL")
        chapters = Prompt.ask("Chapter selection (e.g. 1-3;5)", default="1")

        # Use settings by default; allow override via prompt
        if Prompt.ask("Use settings provider/model?", choices=["yes", "no"], default="yes") == "no":
            provider = Prompt.ask(
                "Provider",
                choices=available_providers(),
                default=self.settings.get_provider_key(),
            )
            model = Prompt.ask("Provider model", default=self.settings.get_provider_model())
        else:
            provider = None
            model = None

        try:
            asyncio.run(
                self._do_translate_chapters(
                    source,
                    novel_id,
                    chapters,
                    provider,
                    model,
                )
            )
        except Exception as exc:
            self.console.print(f"[red]Error:[/red] {exc}")

    async def _do_translate_chapters(
        self,
        source_key: str,
        novel_id: str,
        chapters: str,
        provider_key: str | None = None,
        provider_model: str | None = None,
    ) -> None:
        source = get_source(source_key)
        meta = self.storage.load_metadata(novel_id)
        if not meta:
            raise RuntimeError("Metadata not found; run scrape-metadata first.")

        selection = parse_chapter_selection(chapters)
        chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

        for spec in selection:
            chapter_num = spec.chapter
            chapter = chapter_map.get(chapter_num)
            if not chapter:
                self.console.print(f"Skipping missing chapter {chapter_num}")
                continue

            existing = self.storage.load_translated_chapter(novel_id, str(chapter_num))
            if existing:
                self.console.print(f"Skipping already translated chapter {chapter_num}")
                continue

            result = await self.translation.translate_chapter(
                source_adapter=source,
                chapter_url=chapter["url"],
                provider_key=provider_key,
                provider_model=provider_model,
            )
            translated = result.get("final_text", "")
            self.storage.save_translated_chapter(novel_id, str(chapter_num), translated)
            self.console.print(f"Translated chapter {chapter_num}")

    def _export_flow(self) -> None:
        novel_id = Prompt.ask("Novel ID")
        output = Prompt.ask("Output directory", default="output")
        fmt = Prompt.ask("Format", choices=["epub", "pdf"], default="epub")

        meta = self.storage.load_metadata(novel_id)
        if not meta:
            self.console.print("[red]Metadata not found; run scrape first.[/red]")
            return

        chapters = []
        for chap in meta.get("chapters", []):
            chap_id = str(chap.get("id"))
            text = self.storage.load_translated_chapter(novel_id, chap_id)
            if not text:
                continue
            chapters.append({"title": chap.get("title"), "text": text})

        output_path = f"{output}/{novel_id}.{fmt}"
        if fmt == "pdf":
            self.exporter.export_pdf(novel_id=novel_id, chapters=chapters, output_path=output_path)
        else:
            self.exporter.export_epub(novel_id=novel_id, chapters=chapters, output_path=output_path)

        self.console.print(f"Exported {fmt.upper()} to {output_path}")

    def _diagnostics_menu(self) -> None:
        self.console.print("[bold]System diagnostics[/bold]\n")

        novels = self.storage.list_novels()
        total_novels = len(novels)
        total_translated = sum(self.storage.count_translated_chapters(n) for n in novels)

        cache_path = Path(settings.DATA_DIR) / "translation_cache.json"
        cache_entries = 0
        if cache_path.exists():
            try:
                cache_entries = len(json.loads(cache_path.read_text(encoding="utf-8")))
            except Exception:
                cache_entries = -1

        usage_summary = self.usage.summary()
        recent_usage = self.usage.list(limit=5)

        self.console.print(f"Novels stored: {total_novels}")
        self.console.print(f"Translated chapters: {total_translated}")
        self.console.print(f"Cached translations: {cache_entries if cache_entries >= 0 else 'error'}")
        self.console.print(f"Total translation requests: {usage_summary.get('total_requests')}")
        self.console.print(f"Total tokens used: {usage_summary.get('total_tokens')}")
        self.console.print(
            f"Estimated cost (USD): ${usage_summary.get('estimated_cost_usd', 0):.6f}"
        )

        self.console.print("\n[bold]Recent translation usage[/bold]")
        if recent_usage:
            for entry in recent_usage:
                ts = entry.get("timestamp")
                prov = entry.get("provider")
                model = entry.get("model")
                tokens = entry.get("tokens")
                self.console.print(f"- {ts} | {prov}/{model} | tokens={tokens}")
        else:
            self.console.print("No usage records yet.")

        if Prompt.ask("Clear usage history?", choices=["yes", "no"], default="no") == "yes":
            self.usage.clear()
            self.console.print("[green]Usage history cleared.[/green]")

    def _settings_menu(self) -> None:
        self.console.print("[bold]Current settings[/bold]")
        self.console.print(f"Provider: {self.settings.get_provider_key()}")
        self.console.print(f"Model: {self.settings.get_provider_model()}")
        api_key = self.settings.get_api_key()
        self.console.print(f"API key set: {'yes' if api_key else 'no'}")

        if Prompt.ask("Change settings?", choices=["yes", "no"], default="no") == "yes":
            provider = Prompt.ask(
                "Provider",
                choices=available_providers(),
                default=self.settings.get_provider_key(),
            )
            model = Prompt.ask("Provider model", default=self.settings.get_provider_model())
            api_key = Prompt.ask("API key (leave blank to keep current)", password=True, default="")

            self.settings.set_provider_key(provider)
            self.settings.set_provider_model(model)
            if api_key:
                self.settings.set_api_key(api_key)

            self.console.print("[green]Settings updated.[/green]")

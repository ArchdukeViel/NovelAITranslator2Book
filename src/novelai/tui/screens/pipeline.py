from __future__ import annotations

# pyright: reportAttributeAccessIssue=false

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from novelai.config.settings import settings
from novelai.export.registry import available_exporters
from novelai.providers.registry import available_models as available_provider_models
from novelai.sources.registry import available_sources, detect_source, get_source
from novelai.utils.chapter_selection import is_full_chapter_selection, parse_chapter_selection
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions
from novelai.cost_estimator.pricing import list_supported_models
from novelai.utils import format_usd

if TYPE_CHECKING:
    from novelai.tui.app import TranslationBudgetEstimate


class PipelineScreenMixin:
    """Scrape, update, translation pipeline, and export screen methods."""

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

    def _chapter_numbers_from_ids(self, chapter_ids: list[str]) -> list[int]:
        numbers: list[int] = []
        for chapter_id in chapter_ids:
            normalized = str(chapter_id).strip()
            if normalized.isdigit():
                numbers.append(int(normalized))
        return sorted(set(numbers))

    def _chapter_in_library(self, novel_id: str, chapter_num: int) -> bool:
        chapter_id = str(chapter_num)
        return (
            self.storage.load_chapter(novel_id, chapter_id) is not None
            or self.storage.load_translated_chapter(novel_id, chapter_id) is not None
        )

    def _chapter_is_translated(self, novel_id: str, chapter_num: int) -> bool:
        return self.storage.load_translated_chapter(novel_id, str(chapter_num)) is not None

    def _stored_chapter_numbers(self, novel_id: str, metadata: dict[str, Any] | None) -> list[int]:
        stored_numbers = self._chapter_numbers_from_ids(self.storage.list_stored_chapters(novel_id))
        if stored_numbers:
            return stored_numbers
        return [
            chapter_num
            for chapter_num in self._metadata_chapter_numbers(metadata)
            if self._chapter_in_library(novel_id, chapter_num)
        ]

    def _translated_chapter_numbers(self, novel_id: str, metadata: dict[str, Any] | None) -> list[int]:
        translated_numbers = self._chapter_numbers_from_ids(self.storage.list_translated_chapters(novel_id))
        if translated_numbers:
            return translated_numbers
        return [
            chapter_num
            for chapter_num in self._metadata_chapter_numbers(metadata)
            if self._chapter_is_translated(novel_id, chapter_num)
        ]

    def _serialize_chapter_selection(self, numbers: list[int]) -> str | None:
        if not numbers:
            return None

        segments: list[str] = []
        start = numbers[0]
        end = numbers[0]
        for number in numbers[1:]:
            if number == end + 1:
                end = number
                continue
            segments.append(f"{start}-{end}" if start != end else str(start))
            start = number
            end = number
        segments.append(f"{start}-{end}" if start != end else str(start))
        return ";".join(segments)

    def _latest_library_chapter(self, novel_id: str, metadata: dict[str, Any] | None) -> int:
        latest = 0
        for chapter_num in self._metadata_chapter_numbers(metadata):
            if self._chapter_in_library(novel_id, chapter_num):
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

    def _selected_chapter_numbers(self, metadata: dict[str, Any] | None, selection: str) -> list[int]:
        chapter_numbers = set(self._metadata_chapter_numbers(metadata))
        if not chapter_numbers:
            return []
        if is_full_chapter_selection(selection):
            return sorted(chapter_numbers)
        try:
            requested = {spec.chapter for spec in parse_chapter_selection(selection)}
        except Exception:
            return []
        return [chapter_num for chapter_num in sorted(requested) if chapter_num in chapter_numbers]

    def _format_chapter_selection_label(self, selection: str) -> str:
        return "all available chapters" if is_full_chapter_selection(selection) else f"chapters {selection}"

    def _chapter_selection_upper_bound(self, selection: str) -> int | None:
        if is_full_chapter_selection(selection):
            return None
        try:
            chapter_numbers = [spec.chapter for spec in parse_chapter_selection(selection)]
        except Exception:
            return None
        return max(chapter_numbers) if chapter_numbers else None

    def _build_add_novel_selections(
        self,
        novel_id: str,
        metadata: dict[str, Any] | None,
        requested_selection: str,
    ) -> tuple[str | None, str | None]:
        selected_numbers = self._selected_chapter_numbers(metadata, requested_selection)
        if not selected_numbers:
            return None, None

        fetch_numbers = [
            chapter_num
            for chapter_num in selected_numbers
            if not self._chapter_in_library(novel_id, chapter_num)
        ]
        translate_numbers = [
            chapter_num
            for chapter_num in selected_numbers
            if not self._chapter_is_translated(novel_id, chapter_num)
        ]
        return (
            self._serialize_chapter_selection(fetch_numbers),
            self._serialize_chapter_selection(translate_numbers),
        )

    def _estimate_translation_budget(
        self,
        *,
        title: str,
        novel_id: str,
        chapters: str,
        active_provider: str,
        active_model: str,
        fallback_used: bool,
    ) -> TranslationBudgetEstimate | None:
        metadata = self.storage.load_metadata(novel_id)
        selected_numbers = self._selected_chapter_numbers(metadata, chapters)
        if not selected_numbers:
            return None

        japanese_characters = 0
        chapter_count = 0
        for chapter_num in selected_numbers:
            raw_chapter = self.storage.load_chapter(novel_id, str(chapter_num))
            text = raw_chapter.get("text") if isinstance(raw_chapter, dict) else None
            if not isinstance(text, str) or not text.strip():
                continue
            japanese_characters += sum(1 for char in text if not char.isspace())
            chapter_count += 1

        if japanese_characters <= 0 or chapter_count <= 0:
            return None

        supported_models = list(list_supported_models())
        note: str | None = None
        if active_model in supported_models:
            estimate_models = [active_model]
        else:
            estimate_models = supported_models
            if fallback_used:
                note = "Reference estimate shown for gpt-5.2 and gpt-5.4 because translation used dummy/dummy."
            else:
                note = (
                    f"Reference estimate shown for gpt-5.2 and gpt-5.4 because "
                    f"{active_provider}/{active_model} is not in the estimator catalog."
                )

        comparison = compare_models(
            estimate_models,
            EstimationOptions(japanese_characters=japanese_characters),
        )
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        operation = title.strip().lower().replace(" ", "_")
        representative = comparison.estimates[0]
        cheapest = min(comparison.estimates, key=lambda estimate: estimate.estimated_total_cost_usd)
        model_label = representative.model_name
        budget_basis = "selected_model"
        if len(comparison.estimates) > 1:
            model_label = " vs ".join(estimate.model_name for estimate in comparison.estimates)
            budget_basis = "cheapest_model"

        self.usage.record(
            {
                "entry_type": "estimate",
                "timestamp": timestamp,
                "provider": "openai",
                "model": model_label,
                "estimated_input_tokens": representative.estimated_input_tokens,
                "estimated_output_tokens": representative.estimated_output_tokens,
                "estimated_total_tokens": representative.estimated_input_tokens + representative.estimated_output_tokens,
                "estimated_cost_usd": cheapest.estimated_total_cost_usd,
                "metadata": {
                    "operation": operation,
                    "novel_id": novel_id,
                    "chapters": chapters,
                    "chapter_count": chapter_count,
                    "japanese_characters": japanese_characters,
                    "active_provider": active_provider,
                    "active_model": active_model,
                    "fallback_used": fallback_used,
                    "estimate_models": [item.model_name for item in comparison.estimates],
                    "cheapest_model": comparison.cheapest_model,
                    "cost_difference_usd": comparison.cost_difference_usd,
                    "percentage_difference": comparison.percentage_difference,
                    "budget_basis": budget_basis,
                    "per_model_estimates": [
                        {
                            "model_name": estimate.model_name,
                            "estimated_total_cost_usd": estimate.estimated_total_cost_usd,
                            "estimated_input_tokens": estimate.estimated_input_tokens,
                            "estimated_output_tokens": estimate.estimated_output_tokens,
                        }
                        for estimate in comparison.estimates
                    ],
                    "note": note,
                },
            }
        )

        return {
            "japanese_characters": japanese_characters,
            "chapter_count": chapter_count,
            "comparison": comparison,
            "note": note,
        }

    def _format_budget_summary(self, budget_estimate: TranslationBudgetEstimate | None) -> str:
        if budget_estimate is None:
            return "Budget estimate unavailable because no source text was available from the selected chapters."

        comparison = budget_estimate["comparison"]
        lines = [
            (
                "Estimated source size: "
                f"{budget_estimate['japanese_characters']} non-whitespace characters across "
                f"{budget_estimate['chapter_count']} chapter(s)."
            )
        ]
        if len(comparison.estimates) == 1:
            estimate = comparison.estimates[0]
            lines.append(
                f"Estimated tokens ({estimate.model_name}): "
                f"{estimate.estimated_input_tokens} input / {estimate.estimated_output_tokens} output."
            )
            lines.append(f"Estimated cost ({estimate.model_name}): {format_usd(estimate.estimated_total_cost_usd)}.")
        else:
            lines.append("Estimated translation budget:")
            for estimate in comparison.estimates:
                lines.append(
                    f"- {estimate.model_name}: "
                    f"{estimate.estimated_input_tokens} in / {estimate.estimated_output_tokens} out / "
                    f"{format_usd(estimate.estimated_total_cost_usd)}"
                )
            lines.append(
                f"Cheapest estimate: {comparison.cheapest_model} "
                f"({format_usd(comparison.cost_difference_usd)} difference, "
                f"{comparison.percentage_difference:.2f}%)."
            )
        if budget_estimate["note"]:
            lines.append(budget_estimate["note"])
        return "\n".join(lines)

    def _confirm_existing_novel_add(self, novel_id: str, metadata: dict[str, Any] | None) -> bool:
        stored_numbers = self._stored_chapter_numbers(novel_id, metadata)
        stored_label = self._format_number_ranges(stored_numbers) if stored_numbers else "none detected"
        return self._confirm_library_action(
            (
                f"{novel_id} is already in the library.\n"
                f"Stored chapters: {stored_label}.\n"
                "Continue Add Novel? Existing raw chapters will be skipped, and existing translations will not be re-run."
            )
        )

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
        budget_estimate = self._estimate_translation_budget(
            title=title,
            novel_id=novel_id,
            chapters=chapters,
            active_provider=active_provider,
            active_model=active_model,
            fallback_used=fallback_used,
        )
        budget_summary = self._format_budget_summary(budget_estimate)

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
                        f"Translation with {active_provider}/{active_model} failed: {exc}\n\n"
                        f"{budget_summary}"
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
                    f"Fetched raw text where needed and translated {selection_label} with {active_provider}/{active_model}.\n\n"
                    f"{budget_summary}"
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

        # Offer to export immediately after translation.
        self._offer_post_translation_export(novel_id)

    async def _do_scrape_metadata(
        self,
        source_key: str,
        novel_id: str,
        mode: str = "update",
        max_chapter: int | None = None,
    ) -> None:
        await self.orchestrator.scrape_metadata(source_key, novel_id, mode=mode, max_chapter=max_chapter)

    async def _do_scrape_chapters(self, source_key: str, novel_id: str, chapters: str, mode: str = "update") -> None:
        await self.orchestrator.scrape_chapters(source_key, novel_id, chapters, mode=mode)

    def _offer_post_translation_export(self, novel_id: str) -> None:
        """Prompt the user to export immediately after translation finishes."""
        formats = available_exporters()
        if not formats:
            return

        format_labels = [fmt.upper() for fmt in formats]
        format_descriptions = [f"Export {novel_id} as {fmt.upper()}." for fmt in formats]
        choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Export Now?",
                f"Translation finished for {novel_id}. Choose a format to export, or 0 to skip.",
                format_labels,
                descriptions=format_descriptions,
            ),
            option_count=len(formats),
            default_value="0",
            label="Export",
        )
        if choice is None:
            self._set_status("Export skipped.", "info")
            return

        fmt = formats[choice - 1]

        language_choice = self._prompt_numbered_choice(
            lambda: self._build_settings_choice_screen(
                "Export Language",
                "Choose which language version to export.",
                ["Translated", "Source (original)"],
                descriptions=[
                    "Export the translated text.",
                    "Export the original source text.",
                ],
            ),
            option_count=2,
            default_value="1",
            label="Language",
        )
        if language_choice is None:
            self._set_status("Export skipped.", "info")
            return
        language = "source" if language_choice == 2 else "translated"

        include_toc = False
        if fmt == "epub":
            toc_choice = self._prompt_numbered_choice(
                lambda: self._build_settings_choice_screen(
                    "Table of Contents",
                    "Include a table of contents page in the EPUB?",
                    ["No", "Yes"],
                    descriptions=[
                        "Skip the table of contents page.",
                        "Add a table of contents page after the title page.",
                    ],
                ),
                option_count=2,
                default_value="1",
                label="TOC",
            )
            if toc_choice is None:
                self._set_status("Export skipped.", "info")
                return
            include_toc = toc_choice == 2

        try:
            output_path = self._export_novel(novel_id, fmt, None, language=language, include_toc=include_toc)
            self._set_status(f"Exported {fmt.upper()} to {output_path}", "success")
        except Exception as exc:
            self._set_status(f"Export failed: {exc}", "error")

    def _scrape_flow(self) -> None:
        prompt = self._prompt_novel_url(
            "Add Novel",
            "Paste a novel URL and NovelAIBook will detect the source, scrape the selected chapters, and translate them into your library.",
        )
        if prompt is None:
            return

        novel_url, source, novel_id = prompt
        existing_metadata = self.storage.load_metadata(novel_id)
        if existing_metadata is not None and not self._confirm_existing_novel_add(novel_id, existing_metadata):
            self._set_status(f"Add Novel cancelled for {novel_id}.", "warning")
            return

        chapters = self._prompt_chapter_selection()
        if not self._validate_chapter_selection(chapters):
            self._set_status("Use chapter selection like full, 1, or 3-8.", "warning")
            return
        max_chapter = self._chapter_selection_upper_bound(chapters)

        try:
            with self.console.status("[bold #7dcfff]Saving novel metadata...[/bold #7dcfff]", spinner="dots"):
                asyncio.run(self._do_scrape_metadata(source, novel_id, mode="update", max_chapter=max_chapter))
        except Exception as exc:
            self._show_error(f"Add Novel failed: {exc}")
            return

        metadata = self.storage.load_metadata(novel_id)
        fetch_selection, translate_selection = self._build_add_novel_selections(novel_id, metadata, chapters)

        if fetch_selection is not None:
            try:
                with self.console.status("[bold #7dcfff]Fetching raw chapters...[/bold #7dcfff]", spinner="dots"):
                    asyncio.run(self._do_scrape_chapters(source, novel_id, fetch_selection, mode="update"))
            except Exception as exc:
                self._show_error(f"Add Novel failed: {exc}")
                return

        if translate_selection is None:
            stored_numbers = self._stored_chapter_numbers(novel_id, metadata)
            stored_label = self._format_number_ranges(stored_numbers) if stored_numbers else "none detected"
            self.console.print(
                Panel(
                    (
                        f"{novel_id} is already in the library.\n"
                        f"Stored chapters: {stored_label}.\n"
                        "The selected chapters are already stored and translated, so there was nothing new to add."
                    ),
                    title="Add Novel",
                    border_style="#7aa2f7",
                    box=box.ROUNDED,
                )
            )
            self._set_status(f"Add Novel found nothing new for {novel_id}.", "info")
            return

        self._run_translation_pipeline(
            title="Add Novel",
            novel_id=novel_id,
            source=source,
            novel_url=novel_url,
            chapters=translate_selection,
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

    def _collect_export_chapters(
        self,
        novel_id: str,
        chapter_selection: str = "full",
        language: str = "translated",
    ) -> list[dict[str, Any]]:
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

        use_source = language == "source"

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

            if use_source:
                raw_data = self.storage.load_chapter(novel_id, chap_id)
                if not raw_data:
                    continue
                text = raw_data.get("text")
            else:
                translated = self.storage.load_translated_chapter(novel_id, chap_id)
                if not translated:
                    continue
                text = translated.get("text")

            if not isinstance(text, str):
                continue

            title = chap.get("title")
            chapters.append(
                {
                    "title": title if isinstance(title, str) and title else f"Chapter {chap_id}",
                    "text": text,
                    "images": self.storage.load_chapter_export_images(novel_id, chap_id),
                }
            )

        if not chapters:
            label = "source" if use_source else "translated"
            if selected_numbers is not None:
                raise ValueError(f"No {label} chapters are available for export in chapters {chapter_selection}.")
            raise ValueError(f"No {label} chapters are available for export.")
        return chapters

    def _build_export_output_path(
        self,
        novel_id: str,
        fmt: str,
        output_dir: str | None,
        chapter_selection: str,
        language: str = "translated",
    ) -> str:
        base_path = Path(self.storage.build_export_path(novel_id, fmt, output_dir))
        name = base_path.stem

        if language == "source":
            name = f"{name}_source"

        if not is_full_chapter_selection(chapter_selection):
            suffix = chapter_selection.replace(" ", "").replace(",", "_").replace("-", "to")
            name = f"{name}_ch{suffix}"

        return str(base_path.with_name(f"{name}.{fmt}"))

    def _export_novel(
        self,
        novel_id: str,
        fmt: str,
        output_dir: str | None,
        *,
        chapter_selection: str = "full",
        language: str = "translated",
        include_toc: bool = False,
    ) -> str:
        chapters = self._collect_export_chapters(novel_id, chapter_selection=chapter_selection, language=language)
        output_path = self._build_export_output_path(novel_id, fmt, output_dir, chapter_selection, language=language)

        meta = self.storage.load_metadata(novel_id) or {}
        book_title = meta.get("translated_title") or meta.get("title") or novel_id
        book_author = meta.get("translated_author") or meta.get("author") or ""

        self.exporter.export(
            fmt,
            novel_id=novel_id,
            chapters=chapters,
            output_path=output_path,
            title=book_title,
            author=book_author,
            include_toc=include_toc,
        )
        return output_path


from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from novelai.services.export_service import ExportService
from novelai.services.settings_service import SettingsService
from novelai.services.storage_service import StorageService
from novelai.services.translation_service import TranslationService
from novelai.sources.registry import get_source
from novelai.tui.app import TUIApp
from novelai.utils.chapter_selection import parse_chapter_selection


def _normalize_action(action: str) -> str:
    return action.strip().lower().replace("_", "-")


async def _do_scrape_metadata(
    source_key: str, novel_id: str, storage: StorageService, mode: str = "update"
) -> None:
    source = get_source(source_key)
    if mode == "full":
        storage.delete_novel(novel_id)

    meta = await source.fetch_metadata(novel_id)
    storage.save_metadata(novel_id, meta)
    folder_name = meta.get("folder_name") or novel_id
    print(
        f"Saved metadata for {novel_id} from {source_key} (folder: {folder_name})"
    )


async def _do_scrape_chapters(
    source_key: str,
    novel_id: str,
    chapters: str,
    storage: StorageService,
    mode: str = "update",
) -> None:
    source = get_source(source_key)

    if mode == "full":
        storage.delete_novel(novel_id)
        meta = await source.fetch_metadata(novel_id)
        storage.save_metadata(novel_id, meta)
    else:
        meta = storage.load_metadata(novel_id)
        if not meta:
            raise SystemExit("Metadata not found; run scrape-metadata first.")

    selection = parse_chapter_selection(chapters)
    chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

    for spec in selection:
        chapter_num = spec.chapter
        chapter = chapter_map.get(chapter_num)
        if not chapter:
            print(f"Skipping missing chapter {chapter_num}")
            continue

        chapter_id = str(chapter_num)
        existing_hash = storage.existing_chapter_hash(novel_id, chapter_id)
        text = await source.fetch_chapter(chapter["url"])
        new_hash = storage._hash_text(text)

        if mode == "update" and existing_hash == new_hash:
            print(f"Skipping chapter {chapter_num} (unchanged)")
            continue

        storage.save_chapter(novel_id, chapter_id, text)
        print(
            f"{'Updated' if existing_hash else 'Saved'} chapter {chapter_num}"
        )


async def _do_translate_chapters(
    source_key: str,
    novel_id: str,
    chapters: str,
    storage: StorageService,
    translation: TranslationService,
    provider_key: Optional[str],
    provider_model: Optional[str] = None,
) -> None:
    source = get_source(source_key)
    meta = storage.load_metadata(novel_id)
    if not meta:
        raise SystemExit("Metadata not found; run scrape-metadata first.")

    selection = parse_chapter_selection(chapters)
    chapter_map = {int(c["id"]): c for c in meta.get("chapters", [])}

    for spec in selection:
        chapter_num = spec.chapter
        chapter = chapter_map.get(chapter_num)
        if not chapter:
            print(f"Skipping missing chapter {chapter_num}")
            continue

        existing = storage.load_translated_chapter(novel_id, str(chapter_num))
        if existing:
            print(f"Skipping already translated chapter {chapter_num}")
            continue

        result = await translation.translate_chapter(
            source_adapter=source,
            chapter_url=chapter["url"],
            provider_key=provider_key,
            provider_model=provider_model,
        )
        translated = result.get("final_text", "")
        storage.save_translated_chapter(novel_id, str(chapter_num), translated)
        print(f"Translated chapter {chapter_num}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    subparsers = parser.add_subparsers(dest="command")

    # TUI mode (default)
    subparsers.add_parser("tui", help="Run the interactive TUI")

    # Scrape metadata
    sm = subparsers.add_parser("scrape-metadata", help="Scrape novel metadata")
    sm.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    sm.add_argument("novel", help="Novel ID or URL")
    sm.add_argument(
        "--mode",
        choices=["full", "update"],
        default="update",
        help="Scrape mode: 'full' deletes existing data first; 'update' only adds/changes.",
    )

    # Scrape chapters
    sc = subparsers.add_parser("scrape-chapters", help="Scrape chapters")
    sc.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    sc.add_argument("novel", help="Novel ID or URL")
    sc.add_argument("chapters", help="Chapter selection (e.g. 1-3;5)")
    sc.add_argument(
        "--mode",
        choices=["full", "update"],
        default="update",
        help="Scrape mode: 'full' deletes existing data first; 'update' only adds/changes.",
    )

    # Translate chapters
    tc = subparsers.add_parser("translate-chapters", help="Translate chapters")
    tc.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    tc.add_argument("novel", help="Novel ID or URL")
    tc.add_argument("chapters", help="Chapter selection (e.g. 1-3;5)")
    tc.add_argument("--provider", help="Provider key (overrides default provider)")
    tc.add_argument("--model", help="Provider model (overrides default model)")

    # Export
    ec = subparsers.add_parser(
        "export-epub", help="Export translated chapters to EPUB or PDF"
    )
    ec.add_argument("novel", help="Novel ID")
    ec.add_argument("--output", default="output", help="Output directory")
    ec.add_argument(
        "--format",
        choices=["epub", "pdf"],
        default="epub",
        help="Export format (epub or pdf)",
    )

    args = parser.parse_args(argv)

    storage = StorageService()
    translation = TranslationService()
    exporter = ExportService()
    settings_service = SettingsService()

    if args.command == "tui" or args.command is None:
        app = TUIApp()
        app.run()
        return

    try:
        if args.command == "scrape-metadata":
            asyncio.run(
                _do_scrape_metadata(
                    args.source,
                    args.novel,
                    storage,
                    mode=args.mode,
                )
            )
        elif args.command == "scrape-chapters":
            asyncio.run(
                _do_scrape_chapters(
                    args.source,
                    args.novel,
                    args.chapters,
                    storage,
                    mode=args.mode,
                )
            )
        elif args.command == "translate-chapters":
            asyncio.run(
                _do_translate_chapters(
                    args.source,
                    args.novel,
                    args.chapters,
                    storage,
                    translation,
                    args.provider,
                    args.model,
                )
            )
        elif args.command == "export-epub":
            meta = storage.load_metadata(args.novel)
            if not meta:
                raise SystemExit("Metadata not found; run scrape-metadata first.")

            # Gather translated chapters in order
            chapters = []
            for chap in meta.get("chapters", []):
                chap_id = str(chap.get("id"))
                text = storage.load_translated_chapter(args.novel, chap_id)
                if not text:
                    continue
                chapters.append({"title": chap.get("title"), "text": text})

            output_path = f"{args.output}/{args.novel}.{args.format}"
            if args.format == "pdf":
                exporter.export_pdf(novel_id=args.novel, chapters=chapters, output_path=output_path)
            else:
                exporter.export_epub(novel_id=args.novel, chapters=chapters, output_path=output_path)

            print(f"Exported {args.format.upper()} to {output_path}")
        else:
            parser.print_help()
    except Exception as exc:
        if hasattr(exc, "__cause__") and exc.__cause__:
            # If the error was caused by a lower-level system, show the underlying message.
            print(f"Error: {exc} (caused by: {exc.__cause__})")
        else:
            print(f"Error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

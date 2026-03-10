from __future__ import annotations

import argparse
import asyncio

from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.app.web import main as web_main
from novelai.tui.app import TUIApp


def _normalize_action(action: str) -> str:
    return action.strip().lower().replace("_", "-")




def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelaibook")
    subparsers = parser.add_subparsers(dest="command")

    # Web mode
    subparsers.add_parser("web", help="Run the web server")

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
    sm.add_argument("--dry-run", action="store_true", help="Show what would happen without executing.")

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
    sc.add_argument("--dry-run", action="store_true", help="Show what would happen without executing.")

    # Translate chapters
    tc = subparsers.add_parser("translate-chapters", help="Translate chapters")
    tc.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    tc.add_argument("novel", help="Novel ID or URL")
    tc.add_argument("chapters", help="Chapter selection (e.g. 1-3;5)")
    tc.add_argument("--provider", help="Provider key (overrides default provider)")
    tc.add_argument("--model", help="Provider model (overrides default model)")
    tc.add_argument("--dry-run", action="store_true", help="Show what would happen without executing.")

    # Export
    ec = subparsers.add_parser(
        "export-epub", help="Export translated chapters"
    )
    ec.add_argument("novel", help="Novel ID")
    ec.add_argument(
        "--output",
        help="Optional custom export directory. Defaults to the novel library.",
    )
    ec.add_argument(
        "--format",
        choices=["epub", "pdf", "html", "md"],
        default="epub",
        help="Export format (epub, pdf, html, or md)",
    )

    # Glossary management
    gc = subparsers.add_parser("glossary", help="Manage translation glossary for a novel")
    gc.add_argument("novel", help="Novel ID")
    gc_sub = gc.add_subparsers(dest="glossary_action")
    gc_list = gc_sub.add_parser("list", help="List glossary terms")
    gc_add = gc_sub.add_parser("add", help="Add a glossary term")
    gc_add.add_argument("source", help="Source term (original language)")
    gc_add.add_argument("target", help="Target term (translation)")
    gc_add.add_argument("--notes", help="Optional notes about this term")
    gc_remove = gc_sub.add_parser("remove", help="Remove a glossary term")
    gc_remove.add_argument("source", help="Source term to remove")
    gc_clear = gc_sub.add_parser("clear", help="Remove all glossary terms")

    args = parser.parse_args(argv)

    # Ensure providers/sources are registered before we use them.
    bootstrap()

    if args.command == "tui" or args.command is None:
        app = TUIApp()
        app.run()
        return
    if args.command == "web":
        web_main()
        return

    try:
        if args.command == "scrape-metadata":
            if args.dry_run:
                print(f"[dry-run] Would scrape metadata for '{args.novel}' from source '{args.source}' (mode={args.mode})")
                return
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            asyncio.run(
                orchestrator.scrape_metadata(
                    args.source,
                    args.novel,
                    mode=args.mode,
                )
            )
        elif args.command == "scrape-chapters":
            if args.dry_run:
                meta = container.storage.load_metadata(args.novel)
                if meta:
                    from novelai.services.novel_orchestration_service import NovelOrchestrationService

                    orch = NovelOrchestrationService(container.storage, container.translation)
                    selected = orch._selected_chapter_numbers(meta, args.chapters)
                    print(f"[dry-run] Would scrape {len(selected)} chapter(s) for '{args.novel}' from '{args.source}' (mode={args.mode})")
                    print(f"[dry-run] Chapters: {', '.join(str(n) for n in selected)}")
                else:
                    print(f"[dry-run] Would scrape chapters for '{args.novel}' from '{args.source}' (mode={args.mode})")
                    print("[dry-run] No existing metadata — chapter count unknown until metadata is scraped.")
                return
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            asyncio.run(
                orchestrator.scrape_chapters(
                    args.source,
                    args.novel,
                    args.chapters,
                    mode=args.mode,
                )
            )
        elif args.command == "translate-chapters":
            if args.dry_run:
                meta = container.storage.load_metadata(args.novel)
                if meta:
                    from novelai.services.novel_orchestration_service import NovelOrchestrationService

                    orch = NovelOrchestrationService(container.storage, container.translation)
                    selected = orch._selected_chapter_numbers(meta, args.chapters)
                    already = sum(
                        1 for n in selected
                        if container.storage.load_translated_chapter(args.novel, str(n))
                    )
                    pending = len(selected) - already
                    provider = args.provider or "default"
                    model = args.model or "default"
                    print(f"[dry-run] Would translate {len(selected)} chapter(s) for '{args.novel}' (provider={provider}, model={model})")
                    print(f"[dry-run] Already translated: {already}, pending: {pending}")
                else:
                    print(f"[dry-run] Would translate chapters for '{args.novel}' — no metadata found.")
                return
        elif args.command == "export-epub":
            exporter = container.export
            meta = container.storage.load_metadata(args.novel)
            if not meta:
                raise SystemExit("Metadata not found; run scrape-metadata first.")

            # Gather translated chapters in order
            chapters = []
            for chap in meta.get("chapters", []):
                chap_id = str(chap.get("id"))
                translated = container.storage.load_translated_chapter(args.novel, chap_id)
                if not translated:
                    continue
                # ``load_translated_chapter`` now returns a dict with metadata.
                chapters.append(
                    {
                        "title": chap.get("title"),
                        "text": translated.get("text"),
                        "images": container.storage.load_chapter_export_images(args.novel, chap_id),
                    }
                )

            output_arg = args.output.strip() if isinstance(args.output, str) else None
            output_path = str(
                container.storage.build_export_path(
                    args.novel,
                    args.format,
                    output_arg or None,
                )
            )

            exporter.export(args.format, novel_id=args.novel, chapters=chapters, output_path=output_path)

            print(f"Exported {args.format.upper()} to {output_path}")
        elif args.command == "glossary":
            storage = container.storage
            if args.glossary_action == "list":
                entries = storage.load_glossary(args.novel)
                if not entries:
                    print(f"No glossary terms for '{args.novel}'.")
                else:
                    for entry in entries:
                        notes = f"  ({entry['notes']})" if entry.get("notes") else ""
                        print(f"  {entry['source']} → {entry['target']}{notes}")
            elif args.glossary_action == "add":
                entries = storage.load_glossary(args.novel)
                # Remove existing entry with same source term
                entries = [e for e in entries if e.get("source") != args.source]
                entries.append({"source": args.source, "target": args.target, "locked": True, "notes": args.notes})
                storage.save_glossary(args.novel, entries)
                print(f"Added: {args.source} → {args.target}")
            elif args.glossary_action == "remove":
                entries = storage.load_glossary(args.novel)
                before = len(entries)
                entries = [e for e in entries if e.get("source") != args.source]
                if len(entries) == before:
                    print(f"Term '{args.source}' not found.")
                else:
                    storage.save_glossary(args.novel, entries)
                    print(f"Removed: {args.source}")
            elif args.glossary_action == "clear":
                storage.save_glossary(args.novel, [])
                print(f"Glossary cleared for '{args.novel}'.")
            else:
                gc.print_help()
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

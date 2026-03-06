from __future__ import annotations

import argparse
import asyncio

from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.tui.app import TUIApp


def _normalize_action(action: str) -> str:
    return action.strip().lower().replace("_", "-")




def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelaibook")
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

    # Ensure providers/sources are registered before we use them.
    bootstrap()

    orchestrator = NovelOrchestrationService(container.storage, container.translation)
    exporter = container.export

    if args.command == "tui" or args.command is None:
        app = TUIApp()
        app.run()
        return

    try:
        if args.command == "scrape-metadata":
            asyncio.run(
                orchestrator.scrape_metadata(
                    args.source,
                    args.novel,
                    mode=args.mode,
                )
            )
        elif args.command == "scrape-chapters":
            asyncio.run(
                orchestrator.scrape_chapters(
                    args.source,
                    args.novel,
                    args.chapters,
                    mode=args.mode,
                )
            )
        elif args.command == "translate-chapters":
            asyncio.run(
                orchestrator.translate_chapters(
                    args.source,
                    args.novel,
                    args.chapters,
                    provider_key=args.provider,
                    provider_model=args.model,
                )
            )
        elif args.command == "export-epub":
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
                chapters.append({"title": chap.get("title"), "text": translated.get("text")})

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

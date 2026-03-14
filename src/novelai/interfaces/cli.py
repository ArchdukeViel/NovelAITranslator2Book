from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

from novelai.interfaces.tui.app import TUIApp
from novelai.interfaces.web.server import main as web_main
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container


def _normalize_action(action: str) -> str:
    return action.strip().lower().replace("_", "-")


def _expected_launcher_path() -> Path:
    launcher_name = "novelaibook.exe" if sys.platform.startswith("win") else "novelaibook"
    python_dir = Path(sys.executable).resolve().parent
    if sys.platform.startswith("win"):
        scripts_dir = python_dir / "Scripts"
        if scripts_dir.exists():
            return scripts_dir / launcher_name
        return python_dir / launcher_name
    bin_dir = python_dir.parent / "bin"
    if bin_dir.exists():
        return bin_dir / launcher_name
    return python_dir / launcher_name


def _doctor_check() -> tuple[int, list[str]]:
    warnings = 0
    lines: list[str] = []
    expected = _expected_launcher_path()
    resolved = shutil.which("novelaibook")

    lines.append("NovelAIBook Doctor")
    lines.append(f"Python: {sys.executable}")
    lines.append(f"Expected launcher: {expected}")
    lines.append(f"Resolved launcher: {resolved or 'not found on PATH'}")

    if not expected.exists():
        warnings += 1
        lines.append("WARN: Expected launcher does not exist in the current environment.")

    if resolved is None:
        warnings += 1
        lines.append("WARN: 'novelaibook' is not available on PATH.")
    else:
        expected_text = str(expected.resolve())
        resolved_text = str(Path(resolved).resolve())
        same_launcher = resolved_text.casefold() == expected_text.casefold()
        if not same_launcher:
            warnings += 1
            lines.append(
                "WARN: PATH points to a different launcher than the active Python environment. "
                "This can run stale entrypoint code."
            )

        try:
            probe = subprocess.run(
                [resolved, "--help"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except Exception as exc:  # noqa: BLE001
            warnings += 1
            lines.append(f"WARN: Failed to execute launcher probe: {exc}")
        else:
            if probe.returncode != 0:
                warnings += 1
                output = (probe.stderr or probe.stdout or "").strip().replace("\n", " ")
                short_output = output[:220]
                lines.append(f"WARN: Launcher probe failed with exit code {probe.returncode}. Output: {short_output}")
                if "novelai.app" in output or "novelai.desktop" in output:
                    lines.append("WARN: Legacy wrapper module reference detected in launcher output.")

    if warnings:
        lines.append("Result: WARN")
        lines.append("Fix: python -m pip install -e .")
    else:
        lines.append("Result: PASS")
    return warnings, lines




def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelaibook")
    subparsers = parser.add_subparsers(dest="command")

    # Web mode
    subparsers.add_parser("web", help="Run the web server")

    # TUI mode (default)
    subparsers.add_parser("tui", help="Run the interactive TUI")
    subparsers.add_parser("gui", help="Run the desktop GUI")
    subparsers.add_parser("doctor", help="Check launcher wiring and environment health")

    # Unified document import
    ic = subparsers.add_parser("import-document", help="Import a document or archive into the library")
    ic.add_argument("adapter", help="Input adapter key (e.g. web, text, epub, pdf, image_folder, cbz)")
    ic.add_argument("novel", help="Novel ID to create/update")
    ic.add_argument("source", help="Source URL or filesystem path")
    ic.add_argument("--max-units", type=int, help="Optional limit for imported units")

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
    tc.add_argument("--force", action="store_true", help="Retranslate chapters even if translated output exists.")
    tc.add_argument("--dry-run", action="store_true", help="Show what would happen without executing.")

    gt = subparsers.add_parser("glossary-translate", help="Translate glossary terms (phase 1b)")
    gt.add_argument("novel", help="Novel ID")
    gt.add_argument("--provider", help="Provider key override")
    gt.add_argument("--model", help="Provider model override")
    gt.add_argument("--all-status", action="store_true", help="Translate non-pending terms as well")

    gr = subparsers.add_parser("glossary-review", help="Review glossary terms (phase 1c)")
    gr.add_argument("novel", help="Novel ID")
    gr.add_argument("--min-target-length", type=int, default=2, help="Minimum target length for auto approval")
    gr.add_argument("--no-auto-approve", action="store_true", help="Keep all reviewed terms pending for manual validation")

    pr = subparsers.add_parser("pipeline-run", help="Run phased translation pipeline")
    pr.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    pr.add_argument("novel", help="Novel ID or URL")
    pr.add_argument("chapters", nargs="?", default="all", help="Chapter selection (default: all)")
    pr.add_argument("--phase", choices=["1", "1b", "2", "3", "full"], default="full", help="Pipeline phase to run")
    pr.add_argument("--provider", help="Provider key override")
    pr.add_argument("--model", help="Provider model override")
    pr.add_argument("--source-language", help="Source language override")
    pr.add_argument("--target-language", help="Target language override")
    pr.add_argument("--confidence-threshold", type=float, default=0.55, help="Threshold for low-confidence polish decisions")
    pr.add_argument("--all-confidence", action="store_true", help="Phase 3 can include chapters not marked low confidence")
    pr.add_argument("--run-polish-phase", action="store_true", help="When phase=full, run phase 3 at the end")

    # Retranslate one chapter
    rtc = subparsers.add_parser("retranslate-chapter", help="Force retranslate one chapter")
    rtc.add_argument("source", help="Source key (e.g., syosetu_ncode)")
    rtc.add_argument("novel", help="Novel ID or URL")
    rtc.add_argument("chapter", help="Chapter number to retranslate")
    rtc.add_argument("--provider", help="Provider key (overrides default provider)")
    rtc.add_argument("--model", help="Provider model (overrides default model)")
    rtc.add_argument("--dry-run", action="store_true", help="Show what would happen without executing.")

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
    gc_sub.add_parser("list", help="List glossary terms")
    gc_add = gc_sub.add_parser("add", help="Add a glossary term")
    gc_add.add_argument("source", help="Source term (original language)")
    gc_add.add_argument("target", help="Target term (translation)")
    gc_add.add_argument("--notes", help="Optional notes about this term")
    gc_remove = gc_sub.add_parser("remove", help="Remove a glossary term")
    gc_remove.add_argument("source", help="Source term to remove")
    gc_review = gc_sub.add_parser("review", help="Set glossary review status for one term")
    gc_review.add_argument("source", help="Source term to review")
    gc_review.add_argument("status", choices=["pending", "approved", "ignored", "translated"], help="Review status")
    gc_extract = gc_sub.add_parser("extract", help="Extract glossary candidates from stored chapters")
    gc_extract.add_argument("--chapters", default="all", help="Chapter selection (default: all)")
    gc_extract.add_argument("--max-terms", type=int, default=50, help="Maximum extracted terms")
    gc_extract.add_argument("--mode", choices=["heuristic", "llm", "hybrid"], help="Glossary extraction mode")
    gc_extract.add_argument("--provider", help="Optional provider override for LLM extraction mode")
    gc_extract.add_argument("--model", help="Optional model override for LLM extraction mode")
    gc_extract.add_argument("--prompt", help="Optional custom extraction prompt template")
    gc_sub.add_parser("approve-all", help="Mark all pending glossary terms as approved")
    gc_sub.add_parser("clear", help="Remove all glossary terms")

    # OCR media workflow
    oc = subparsers.add_parser("ocr", help="Manage chapter OCR review state")
    oc.add_argument("novel", help="Novel ID")
    oc_sub = oc.add_subparsers(dest="ocr_action")
    oc_ingest = oc_sub.add_parser("ingest", help="Extract OCR candidate text from stored image manifests")
    oc_ingest.add_argument("chapters", nargs="?", default="all", help="Chapter selection (default: all)")
    oc_ingest.add_argument("--overwrite", action="store_true", help="Overwrite existing OCR text and reviewed status")
    oc_ingest.add_argument(
        "--skip-required",
        action="store_true",
        help="Persist OCR candidates but do not require review before translation",
    )
    oc_sub.add_parser("list-pending", help="List chapters that require OCR review")
    oc_review = oc_sub.add_parser("review", help="Mark a chapter OCR review as completed")
    oc_review.add_argument("chapter", help="Chapter number")
    oc_review.add_argument("--text", help="Optional corrected OCR text")
    oc_set = oc_sub.add_parser("set-status", help="Set chapter OCR status directly")
    oc_set.add_argument("chapter", help="Chapter number")
    oc_set.add_argument("status", choices=["pending", "reviewed", "skipped", "failed"], help="OCR status")
    oc_set.add_argument("--required", action="store_true", help="Mark chapter as OCR-required")
    oc_set.add_argument("--text", help="Optional OCR text payload")

    args = parser.parse_args(argv)

    # Ensure providers/sources are registered before we use them.
    bootstrap()

    if args.command == "tui" or args.command is None:
        app = TUIApp()
        app.run()
        return
    if args.command == "gui":
        try:
            from novelai.interfaces.desktop.app import main as desktop_main
        except ModuleNotFoundError as exc:
            missing = getattr(exc, "name", "") or "PySide6"
            raise SystemExit(
                f"Desktop GUI dependency '{missing}' is not installed. "
                "Install the desktop extras before running 'novelaibook gui'."
            ) from exc
        desktop_main()
        return
    if args.command == "web":
        web_main()
        return
    if args.command == "doctor":
        warnings, lines = _doctor_check()
        print("\n".join(lines))
        if warnings:
            raise SystemExit(1)
        return

    try:
        if args.command == "import-document":
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            metadata = asyncio.run(
                orchestrator.import_document(
                    args.adapter,
                    args.novel,
                    args.source,
                    max_units=args.max_units,
                )
            )
            print(
                f"Imported '{metadata.get('title') or args.novel}' via {args.adapter} "
                f"with {len(metadata.get('chapters', []))} unit(s)."
            )
            return
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
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            asyncio.run(
                orchestrator.translate_chapters(
                    source_key=args.source,
                    novel_id=args.novel,
                    chapters=args.chapters,
                    provider_key=args.provider,
                    provider_model=args.model,
                    force=bool(args.force),
                )
            )
        elif args.command == "glossary-translate":
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            summary = asyncio.run(
                orchestrator.translate_glossary_terms(
                    args.novel,
                    provider_key=args.provider,
                    provider_model=args.model,
                    only_pending=not bool(args.all_status),
                )
            )
            print(
                "Glossary translation summary: "
                f"translated={summary.get('translated', 0)}, "
                f"skipped={summary.get('skipped', 0)}, "
                f"total={summary.get('total_terms', 0)}"
            )
        elif args.command == "glossary-review":
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            summary = asyncio.run(
                orchestrator.review_glossary_terms(
                    args.novel,
                    auto_approve_translated=not bool(args.no_auto_approve),
                    min_target_length=max(1, int(args.min_target_length)),
                )
            )
            print(
                "Glossary review summary: "
                f"approved={summary.get('approved', 0)}, "
                f"pending={summary.get('pending', 0)}, "
                f"ignored={summary.get('ignored', 0)}"
            )
        elif args.command == "pipeline-run":
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            summary = asyncio.run(
                orchestrator.run_phased_translation_pipeline(
                    source_key=args.source,
                    novel_id=args.novel,
                    chapters=args.chapters,
                    phase=args.phase,
                    glossary_provider_key=args.provider,
                    glossary_provider_model=args.model,
                    body_provider_key=args.provider,
                    body_provider_model=args.model,
                    source_language=args.source_language,
                    target_language=args.target_language,
                    confidence_threshold=max(0.0, min(1.0, float(args.confidence_threshold))),
                    polish_low_confidence_only=not bool(args.all_confidence),
                    run_polish_phase=bool(args.run_polish_phase),
                )
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        elif args.command == "retranslate-chapter":
            if args.dry_run:
                print(
                    f"[dry-run] Would force retranslate chapter {args.chapter} for '{args.novel}' "
                    f"(provider={args.provider or 'default'}, model={args.model or 'default'})."
                )
                return
            from novelai.services.novel_orchestration_service import NovelOrchestrationService

            orchestrator = NovelOrchestrationService(container.storage, container.translation)
            asyncio.run(
                orchestrator.retranslate_chapter(
                    source_key=args.source,
                    novel_id=args.novel,
                    chapter_id=args.chapter,
                    provider_key=args.provider,
                    provider_model=args.model,
                )
            )
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
                        status = str(entry.get("status") or "approved")
                        notes = f"  ({entry['notes']})" if entry.get("notes") else ""
                        print(f"  [{status}] {entry['source']} → {entry['target']}{notes}")
            elif args.glossary_action == "add":
                entries = storage.load_glossary(args.novel)
                # Remove existing entry with same source term
                entries = [e for e in entries if e.get("source") != args.source]
                entries.append(
                    {
                        "source": args.source,
                        "target": args.target,
                        "locked": True,
                        "notes": args.notes,
                        "status": "pending",
                    }
                )
                storage.save_glossary(args.novel, entries)
                print(f"Added: {args.source} → {args.target} [pending]")
            elif args.glossary_action == "remove":
                entries = storage.load_glossary(args.novel)
                before = len(entries)
                entries = [e for e in entries if e.get("source") != args.source]
                if len(entries) == before:
                    print(f"Term '{args.source}' not found.")
                else:
                    storage.save_glossary(args.novel, entries)
                    print(f"Removed: {args.source}")
            elif args.glossary_action == "review":
                entries = storage.load_glossary(args.novel)
                updated = False
                for entry in entries:
                    if entry.get("source") == args.source:
                        entry["status"] = args.status
                        updated = True
                        break
                if not updated:
                    print(f"Term '{args.source}' not found.")
                else:
                    storage.save_glossary(args.novel, entries)
                    print(f"Reviewed: {args.source} -> {args.status}")
            elif args.glossary_action == "extract":
                from novelai.services.novel_orchestration_service import NovelOrchestrationService

                orchestrator = NovelOrchestrationService(container.storage, container.translation)
                extraction_config: dict[str, object] = {
                    "chapters": args.chapters,
                    "max_terms": args.max_terms,
                }
                if getattr(args, "mode", None):
                    extraction_config["mode"] = args.mode
                if getattr(args, "provider", None):
                    extraction_config["provider"] = args.provider
                if getattr(args, "model", None):
                    extraction_config["model"] = args.model
                if getattr(args, "prompt", None):
                    extraction_config["prompt_template"] = args.prompt
                summary = asyncio.run(
                    orchestrator.extract_glossary_terms(
                        args.novel,
                        chapters=args.chapters,
                        max_terms=args.max_terms,
                        config=extraction_config,
                    )
                )
                print(
                    "Glossary extraction summary: "
                    f"chapters={summary['selected_chapters']}, "
                    f"found={summary['candidates_found']}, "
                    f"added={summary['added']}, "
                    f"total={summary['total_terms']}, "
                    f"mode={summary.get('config', {}).get('mode', 'heuristic')}"
                )
            elif args.glossary_action == "approve-all":
                entries = storage.load_glossary(args.novel)
                updated_count = 0
                for entry in entries:
                    if str(entry.get("status") or "approved").strip().lower() == "pending":
                        entry["status"] = "approved"
                        updated_count += 1
                storage.save_glossary(args.novel, entries)
                print(f"Approved {updated_count} pending term(s).")
            elif args.glossary_action == "clear":
                storage.save_glossary(args.novel, [])
                print(f"Glossary cleared for '{args.novel}'.")
            else:
                gc.print_help()
        elif args.command == "ocr":
            storage = container.storage
            if args.ocr_action == "ingest":
                from novelai.services.novel_orchestration_service import NovelOrchestrationService

                orchestrator = NovelOrchestrationService(container.storage, container.translation)
                summary = asyncio.run(
                    orchestrator.ingest_ocr_candidates(
                        novel_id=args.novel,
                        chapters=args.chapters,
                        mark_required=not bool(args.skip_required),
                        overwrite=bool(args.overwrite),
                    )
                )
                print(
                    "OCR ingest summary: "
                    f"selected={summary['selected']}, "
                    f"updated={summary['updated']}, "
                    f"skipped_no_images={summary['skipped_no_images']}, "
                    f"skipped_reviewed={summary['skipped_reviewed']}, "
                    f"failed={len(summary['failed'])}"
                )
                for failure in summary["failed"]:
                    print(f"  - chapter {failure.get('chapter_id')}: {failure.get('code')} ({failure.get('reason')})")
            elif args.ocr_action == "list-pending":
                chapter_ids = storage.list_stored_chapters(args.novel)
                pending: list[str] = []
                status_by_chapter: dict[str, str] = {}
                for chapter_id in chapter_ids:
                    media_state = storage.load_chapter_media_state(args.novel, chapter_id)
                    if media_state is None:
                        continue
                    if not bool(media_state.get("ocr_required", False)):
                        continue
                    status = str(media_state.get("ocr_status") or "pending").strip().lower()
                    if status != "reviewed":
                        pending.append(chapter_id)
                        status_by_chapter[chapter_id] = status

                if not pending:
                    print(f"No chapters pending OCR review for '{args.novel}'.")
                else:
                    print(f"Chapters pending OCR review for '{args.novel}':")
                    for chapter_id in pending:
                        status = status_by_chapter.get(chapter_id, "pending")
                        print(f"  [{status}] chapter {chapter_id}")
            elif args.ocr_action == "review":
                chapter_id = str(args.chapter).strip()
                existing = storage.load_chapter_media_state(args.novel, chapter_id) or {}
                storage.save_chapter_media_state(
                    args.novel,
                    chapter_id,
                    ocr_required=True,
                    ocr_text=args.text if args.text is not None else existing.get("ocr_text"),
                    ocr_status="reviewed",
                )
                print(f"Reviewed OCR for chapter {chapter_id}.")
            elif args.ocr_action == "set-status":
                chapter_id = str(args.chapter).strip()
                existing = storage.load_chapter_media_state(args.novel, chapter_id) or {}
                storage.save_chapter_media_state(
                    args.novel,
                    chapter_id,
                    ocr_required=True if args.required else bool(existing.get("ocr_required", False)),
                    ocr_text=args.text if args.text is not None else existing.get("ocr_text"),
                    ocr_status=args.status,
                )
                print(f"Set OCR status for chapter {chapter_id} -> {args.status}.")
            else:
                oc.print_help()
        else:
            parser.print_help()
    except Exception as exc:
        if hasattr(exc, "__cause__") and exc.__cause__:
            # If the error was caused by a lower-level system, show the underlying message.
            print(f"Error: {exc} (caused by: {exc.__cause__})")
        else:
            print(f"Error: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

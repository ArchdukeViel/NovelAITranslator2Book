"""Data migration script: file-backed storage -> Postgres.

This script performs a one-time backfill of novel and chapter metadata
from the file-backed StorageService into the PostgreSQL database.

It is designed to be run AFTER `alembic upgrade head` has created the schema.

Usage:
    # Dry run (default) - shows what would be migrated without writing
    .venv/Scripts/python -m novelai.scripts.migrate_file_to_db --dry-run

    # Live run - writes to the database
    .venv/Scripts/python -m novelai.scripts.migrate_file_to_db --live

    # With explicit database URL
    .venv/Scripts/python -m novelai.scripts.migrate_file_to_db --live --db-url postgresql+psycopg://...

Architecture note: This is a parallel-run migration. File-backed storage
remains the primary source until the cutover is complete. The script is
idempotent - running it multiple times will not create duplicates.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add backend/src to path if running as script
_backend_src = Path(__file__).resolve().parents[3]
if str(_backend_src) not in sys.path:
    sys.path.insert(0, str(_backend_src))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from novelai.config.settings import settings  # noqa: E402
from novelai.db.models import Chapter, Novel  # noqa: E402
from novelai.storage.service import StorageService  # noqa: E402

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the migration script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_session(db_url: str | None = None) -> Session:
    """Create a database session."""
    url = db_url or settings.DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not configured. "
            "Set DATABASE_URL in .env or pass --db-url explicitly."
        )
    engine = create_engine(url, pool_pre_ping=True)
    Session_ = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return Session_()


def extract_novel_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Extract novel fields from file-backed metadata dict.

    Returns a dict suitable for passing to Novel(**kwargs).
    """
    # Title: prefer translated, fall back to original
    titles = meta.get("titles", {})
    title = (
        titles.get("translated")
        or meta.get("translated_title")
        or titles.get("original")
        or meta.get("title")
        or meta.get("novel_id", "Unknown")
    )

    # Author: prefer translated, fall back to original
    authors = meta.get("authors", {})
    author = (
        authors.get("translated")
        or meta.get("translated_author")
        or authors.get("original")
        or meta.get("author")
    )

    source_site_raw = meta.get("source_site") or meta.get("origin_type")
    source_site = source_site_raw[:128] if source_site_raw else None

    return {
        "slug": meta.get("novel_id", meta.get("id")),
        "title": title[:512] if title else meta.get("novel_id", "Unknown"),
        "original_title": (meta.get("title") or "")[:512] or None,
        "author": author[:255] if author else None,
        "source_site": source_site,
        "source_url": meta.get("source_url") or meta.get("origin_uri_or_path"),
        "language": meta.get("language", "ja"),
        "status": meta.get("status", "unknown"),
        "synopsis": meta.get("synopsis"),
        "is_published": meta.get("is_published", False),
    }


def extract_chapter_metadata(
    chapter_id: str,
    chapter_num: int,
    bundle: dict[str, Any],
    novel_id: int,
) -> dict[str, Any]:
    """Extract chapter fields from file-backed bundle.

    Returns a dict suitable for passing to Chapter(**kwargs).
    """
    raw_data = bundle.get("raw", {})
    translated_data = bundle.get("translated", {})

    # Determine status
    raw_status = "fetched" if raw_data.get("text") else "pending"
    translation_status = "completed" if translated_data.get("text") else "pending"

    return {
        "novel_id": novel_id,
        "chapter_number": chapter_num,
        "title": (bundle.get("title") or chapter_id)[:512] if bundle.get("title") else None,
        "source_url": bundle.get("source_url") or raw_data.get("source_url"),
        "raw_storage_key": f"novels/{chapter_id}/raw",  # Placeholder; actual path from storage
        "translated_storage_key": f"novels/{chapter_id}/translated" if translated_data.get("text") else None,
        "raw_status": raw_status,
        "translation_status": translation_status,
        "word_count": None,  # Could compute from text if needed
    }


def migrate_novel(
    session: Session,
    storage: StorageService,
    novel_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Migrate a single novel and its chapters from file storage to DB.

    Returns a summary dict with counts and status.
    """
    result = {
        "novel_id": novel_id,
        "status": "skipped",
        "novel_created": False,
        "chapters_created": 0,
        "chapters_skipped": 0,
        "errors": [],
    }

    # Load metadata from file storage
    meta = storage.load_metadata(novel_id)
    if meta is None:
        result["errors"].append("No metadata found")
        return result

    # Check if novel already exists in DB
    existing = session.execute(
        select(Novel).where(Novel.slug == novel_id)
    ).scalar_one_or_none()

    novel: Novel | None = None

    if existing:
        result["status"] = "exists"
        novel = existing
        logger.debug("Novel %s already exists in DB (id=%d)", novel_id, novel.id)
    else:
        # Create novel record
        novel_data = extract_novel_metadata(meta)
        novel_data["slug"] = novel_id  # Ensure slug matches

        if dry_run:
            logger.info("[DRY-RUN] Would create novel: %s", novel_id)
            result["status"] = "would_create"
            result["novel_created"] = True
            # novel remains None in dry_run mode for new novels
        else:
            novel = Novel(**novel_data)
            session.add(novel)
            session.flush()  # Get the ID
            result["novel_created"] = True
            result["status"] = "created"
            logger.info("Created novel %s (id=%d)", novel_id, novel.id)

    # Migrate chapters
    chapters_meta = meta.get("chapters", [])
    if not chapters_meta:
        # Try to discover chapters from storage
        chapter_ids = storage.list_stored_chapters(novel_id)
        chapters_meta = [{"id": cid} for cid in chapter_ids]

    for idx, ch_meta in enumerate(chapters_meta):
        chapter_id = str(ch_meta.get("id") or ch_meta.get("chapter_id", f"c{idx+1}"))
        chapter_num_raw = ch_meta.get("num") or ch_meta.get("chapter_number") or (idx + 1)
        chapter_num = int(chapter_num_raw) if isinstance(chapter_num_raw, int) else idx + 1

        # Check if chapter already exists
        if not dry_run and existing and novel is not None:
            existing_ch = session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel.id,
                    Chapter.chapter_number == chapter_num,
                )
            ).scalar_one_or_none()
            if existing_ch:
                result["chapters_skipped"] += 1
                continue

        # Load chapter bundle from storage
        bundle = storage.load_chapter(novel_id, chapter_id)
        if bundle is None:
            result["errors"].append(f"Chapter {chapter_id}: no bundle found")
            continue

        if dry_run:
            logger.debug("[DRY-RUN] Would create chapter %s/%d", novel_id, chapter_num)
            result["chapters_created"] += 1
        else:
            # novel must exist if we're not in dry_run and got here
            if novel is None:
                result["errors"].append(f"Chapter {chapter_id}: novel not found")
                continue
            chapter_data = extract_chapter_metadata(
                chapter_id=chapter_id,
                chapter_num=chapter_num,
                bundle=bundle,
                novel_id=novel.id,
            )
            chapter = Chapter(**chapter_data)
            session.add(chapter)
            result["chapters_created"] += 1

    return result


def run_migration(
    session: Session,
    storage: StorageService,
    dry_run: bool = True,
    novel_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full migration from file storage to database.

    Args:
        session: SQLAlchemy session
        storage: StorageService instance
        dry_run: If True, don't commit changes
        novel_ids: Optional list of specific novel IDs to migrate;
                   if None, migrates all novels in storage

    Returns:
        Summary dict with overall statistics
    """
    summary = {
        "dry_run": dry_run,
        "novels_processed": 0,
        "novels_created": 0,
        "novels_existing": 0,
        "chapters_created": 0,
        "chapters_skipped": 0,
        "errors": [],
        "results": [],
    }

    # Get list of novels to migrate
    if novel_ids is None:
        novel_ids = storage.list_novels()

    logger.info(
        "Starting migration (dry_run=%s) for %d novels",
        dry_run,
        len(novel_ids),
    )

    for novel_id in novel_ids:
        result = migrate_novel(session, storage, novel_id, dry_run=dry_run)
        summary["results"].append(result)
        summary["novels_processed"] += 1

        if result["status"] == "created" or result["status"] == "would_create":
            summary["novels_created"] += 1
        elif result["status"] == "exists":
            summary["novels_existing"] += 1

        summary["chapters_created"] += result["chapters_created"]
        summary["chapters_skipped"] += result["chapters_skipped"]
        summary["errors"].extend(result["errors"])

    # Commit if not dry run
    if not dry_run:
        session.commit()
        logger.info("Migration committed to database")
    else:
        logger.info("Dry run complete - no changes committed")

    return summary


def main() -> int:
    """CLI entry point for the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate novel/chapter data from file storage to Postgres",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live migration (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be migrated without writing (default)",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (falls back to DATABASE_URL env var)",
    )
    parser.add_argument(
        "--novel-id",
        type=str,
        action="append",
        dest="novel_ids",
        help="Specific novel ID to migrate (can be used multiple times)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # --live overrides --dry-run
    dry_run = not args.live

    setup_logging(verbose=args.verbose)

    # Initialize storage (uses settings.NOVEL_LIBRARY_DIR by default)
    storage = StorageService()

    # Get database session
    try:
        session = get_session(args.db_url)
    except RuntimeError as e:
        logger.error(str(e))
        return 1

    # Run migration
    try:
        summary = run_migration(
            session=session,
            storage=storage,
            dry_run=dry_run,
            novel_ids=args.novel_ids,
        )

        # Print summary
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if summary['dry_run'] else 'LIVE'}")
        print(f"Novels processed: {summary['novels_processed']}")
        print(f"Novels created: {summary['novels_created']}")
        print(f"Novels already existing: {summary['novels_existing']}")
        print(f"Chapters created: {summary['chapters_created']}")
        print(f"Chapters skipped: {summary['chapters_skipped']}")
        print(f"Errors: {len(summary['errors'])}")

        if summary["errors"]:
            print("\nErrors:")
            for err in summary["errors"][:10]:
                print(f"  - {err}")
            if len(summary["errors"]) > 10:
                print(f"  ... and {len(summary['errors']) - 10} more")

        print("=" * 60)

        return 0 if not summary["errors"] else 1

    except Exception as e:
        logger.exception("Migration failed: %s", e)
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())

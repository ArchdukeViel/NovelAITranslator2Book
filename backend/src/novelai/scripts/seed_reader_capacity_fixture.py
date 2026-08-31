"""Seed and clean the disposable non-production reader fixture.

This command is deliberately narrower than the normal import pipeline. It
creates only the owner-approved synthetic fixture in the dedicated test R2
bucket and test database. The guard is fail-closed so a production-like
configuration cannot accidentally be used for fixture writes.

Examples::

    python -m novelai.scripts.seed_reader_capacity_fixture seed
    python -m novelai.scripts.seed_reader_capacity_fixture status
    python -m novelai.scripts.seed_reader_capacity_fixture cleanup

The command never prints credentials, connection strings, storage keys, or
fixture content. The content is synthetic and is used only by the bounded
reader-capacity profile.
"""

from __future__ import annotations

import argparse
import os
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select

from novelai.config.settings import settings
from novelai.core.chapter_state import TranslationState
from novelai.db.engine import session_scope
from novelai.db.models.chapter import Chapter
from novelai.db.models.novel import Novel
from novelai.storage.backends import build_r2_recovery_storage
from novelai.storage.service import StorageService

FIXTURE_SLUG = "test-novel"
FIXTURE_SOURCE_KEY = "kakuyomu"
FIXTURE_SOURCE_NOVEL_ID = "test-novel-001"
FIXTURE_NOVEL_ID = 123
FIXTURE_CHAPTERS: tuple[tuple[int, int, str], ...] = (
    (456, 1, "Chapter 1"),
    (457, 2, "Chapter 2"),
)
FIXTURE_BUCKET_PREFIX = "test-"
TARGET_GUARD_NAME = "READER_CAPACITY_FIXTURE_TARGET"
TARGET_GUARD_VALUE = "non-production"


def _rowcount(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def _assert_disposable_target() -> None:
    """Reject missing or production-like target configuration before writes."""

    if os.environ.get(TARGET_GUARD_NAME) != TARGET_GUARD_VALUE:
        raise RuntimeError(f"{TARGET_GUARD_NAME} must be set to the non-production guard value")
    if settings.ENV.strip().lower() not in {"test", "staging"}:
        raise RuntimeError("reader fixture writes require ENV=test or ENV=staging")
    bucket = settings.R2_BUCKET.strip()
    if not bucket.startswith(FIXTURE_BUCKET_PREFIX) or bucket in {"test-dokushodo-backup"}:
        raise RuntimeError("reader fixture writes require the dedicated test application R2 bucket")
    if bucket in {"dokushodo", "dokushodo-backup"}:
        raise RuntimeError("reader fixture writes are forbidden for canonical R2 buckets")
    if not settings.DATABASE_URL:
        raise RuntimeError("reader fixture writes require DATABASE_URL")
    if not settings.R2_GATEWAY_URL or not settings.R2_GATEWAY_CLIENT_ID or not settings.R2_GATEWAY_CLIENT_SECRET:
        raise RuntimeError("reader fixture writes require the test R2 application gateway identity")
    if (
        not settings.R2_RECOVERY_GATEWAY_URL
        or not settings.R2_RECOVERY_CLIENT_ID
        or not settings.R2_RECOVERY_CLIENT_SECRET
    ):
        raise RuntimeError("reader fixture cleanup requires the separate test R2 recovery gateway identity")


def _chapter_text(chapter_id: int, *, translated: bool) -> str:
    language = "translated" if translated else "source"
    return (
        f"Reader capacity synthetic {language} paragraph for chapter {chapter_id}.\n\n"
        "This content exists only in the disposable non-production fixture."
    )


def _metadata(now: datetime) -> dict[str, Any]:
    chapters = [
        {
            "id": str(chapter_id),
            "title": title,
            "num": number,
            "chapter_number": number,
            "sequence_number": number,
            "source_episode_id": str(chapter_id),
            "source_url": f"https://kakuyomu.jp/works/{FIXTURE_SOURCE_NOVEL_ID}/episodes/{chapter_id}",
            "translated": True,
            "translated_at": now.isoformat().replace("+00:00", "Z"),
        }
        for chapter_id, number, title in FIXTURE_CHAPTERS
    ]
    return {
        "schema_version": 2,
        "novel_id": FIXTURE_NOVEL_ID,
        "slug": FIXTURE_SLUG,
        "source_key": FIXTURE_SOURCE_KEY,
        "source_novel_id": FIXTURE_SOURCE_NOVEL_ID,
        "source_url": f"https://kakuyomu.jp/works/{FIXTURE_SOURCE_NOVEL_ID}",
        "title": "Phase 6 Reader Capacity Test Novel",
        "translated_title": "Phase 6 Reader Capacity Test Novel",
        "author": "Synthetic Test Author",
        "synopsis": "Synthetic non-production fixture for reader-capacity validation.",
        "publication_status": "published",
        "is_published": True,
        "published": True,
        "adult": False,
        "content_present": True,
        "chapters": chapters,
        "created_at": now.isoformat().replace("+00:00", "Z"),
    }


def _existing_novel() -> Novel | None:
    with session_scope() as db:
        novel = db.scalar(select(Novel).where(Novel.slug == FIXTURE_SLUG))
        if novel is not None and novel.id != FIXTURE_NOVEL_ID:
            raise RuntimeError("the approved fixture slug is already bound to a different database id")
        return novel


def _cleanup_database() -> dict[str, int]:
    """Delete only the approved fixture projection and its event records."""

    with session_scope() as db:
        novel = db.scalar(select(Novel).where(Novel.slug == FIXTURE_SLUG))
        if novel is not None and novel.id != FIXTURE_NOVEL_ID:
            raise RuntimeError("refusing to clean a different novel id under the approved fixture slug")
        novel_id = novel.id if novel is not None else FIXTURE_NOVEL_ID
        deleted_chapters = _rowcount(db.execute(delete(Chapter).where(Chapter.novel_id == novel_id)))

        deleted_analytics = 0
        with suppress(ImportError):
            from novelai.db.models.analytics_event import AnalyticsEvent

            deleted_analytics = _rowcount(
                db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.novel_id == FIXTURE_SLUG))
            )

        deleted_activities = 0
        with suppress(ImportError):
            from novelai.activity.database import ActivityRecord

            deleted_activities = _rowcount(
                db.execute(delete(ActivityRecord).where(ActivityRecord.novel_id == FIXTURE_SLUG))
            )

        deleted_novels = 0
        if novel is not None:
            db.delete(novel)
            db.flush()
            deleted_novels = 1

    return {
        "novels": deleted_novels,
        "chapters": deleted_chapters,
        "analytics_events": deleted_analytics,
        "activities": deleted_activities,
    }


def _cleanup() -> dict[str, int]:
    _assert_disposable_target()
    _existing_novel()
    recovery_storage = build_r2_recovery_storage(bucket_class="app")
    deleted_objects = recovery_storage.delete_prefix(f"novels/{FIXTURE_NOVEL_ID}")
    result = _cleanup_database()
    result["r2_objects"] = int(deleted_objects)
    return result


def _seed() -> dict[str, Any]:
    _assert_disposable_target()
    cleanup = _cleanup()
    storage = StorageService()
    now = datetime.now(UTC)
    metadata = _metadata(now)
    artifacts: list[tuple[int, int, str, Any, Any]] = []

    try:
        for chapter_id, number, title in FIXTURE_CHAPTERS:
            source_text = _chapter_text(chapter_id, translated=False)
            translated_text = _chapter_text(chapter_id, translated=True)
            raw = storage.save_raw_chapter_artifact(
                FIXTURE_SLUG,
                str(chapter_id),
                source_text,
                title=title,
                source_key=FIXTURE_SOURCE_KEY,
                source_url=f"https://kakuyomu.jp/works/{FIXTURE_SOURCE_NOVEL_ID}/episodes/{chapter_id}",
                storage_novel_id=str(FIXTURE_NOVEL_ID),
            )
            translated = storage.save_translation_artifact(
                FIXTURE_SLUG,
                str(chapter_id),
                translated_text,
                provider_key="reader-capacity-fixture",
                provider_model="reader-capacity-fixture",
                source_hash=raw.logical_sha256,
                artifact_payload={
                    "version_id": f"fixture-{chapter_id}",
                    "version_kind": "machine_translation",
                    "translated_at": now.isoformat().replace("+00:00", "Z"),
                },
                storage_novel_id=str(FIXTURE_NOVEL_ID),
            )
            artifacts.append((chapter_id, number, title, raw, translated))

        with session_scope() as db:
            novel = Novel(
                id=FIXTURE_NOVEL_ID,
                slug=FIXTURE_SLUG,
                public_slug=FIXTURE_SLUG,
                title=str(metadata["title"]),
                original_title=str(metadata["title"]),
                author="Synthetic Test Author",
                source_site=FIXTURE_SOURCE_KEY,
                source_url=str(metadata["source_url"]),
                language="ja",
                publication_status="published",
                chapter_count=len(FIXTURE_CHAPTERS),
                translated_count=len(FIXTURE_CHAPTERS),
                latest_chapter_id=str(FIXTURE_CHAPTERS[-1][0]),
                latest_chapter_number=FIXTURE_CHAPTERS[-1][1],
                latest_chapter_title=FIXTURE_CHAPTERS[-1][2],
                latest_chapter_updated_at=now,
                metadata_json=metadata,
                synopsis=str(metadata["synopsis"]),
                is_published=True,
                glossary_status="glossary_skipped",
            )
            db.add(novel)
            db.flush()

            for chapter_id, number, title, raw, translated in artifacts:
                translated_at = now.isoformat().replace("+00:00", "Z")
                db.add(
                    Chapter(
                        id=chapter_id,
                        novel_id=FIXTURE_NOVEL_ID,
                        chapter_number=number,
                        logical_chapter_id=str(chapter_id),
                        source_episode_id=str(chapter_id),
                        sequence_number=number,
                        title=title,
                        source_url=f"https://kakuyomu.jp/works/{FIXTURE_SOURCE_NOVEL_ID}/episodes/{chapter_id}",
                        raw_storage_key=raw.key,
                        translated_storage_key=translated.key,
                        raw_content_hash=raw.logical_sha256,
                        translated_content_hash=translated.logical_sha256,
                        raw_status="fetched",
                        translation_status="translated",
                        translation_state=TranslationState.COMPLETE.value,
                        translation_versions_json=[
                            {
                                "version_id": f"fixture-{chapter_id}",
                                "storage_key": translated.key,
                                "content_hash": translated.logical_sha256,
                                "created_at": translated_at,
                                "translated_at": translated_at,
                            }
                        ],
                        word_count=len(_chapter_text(chapter_id, translated=True).split()),
                    )
                )
            db.flush()
    except Exception:
        with suppress(Exception):
            build_r2_recovery_storage(bucket_class="app").delete_prefix(f"novels/{FIXTURE_NOVEL_ID}")
        with suppress(Exception):
            _cleanup_database()
        raise

    return {
        "fixture": "reader-fixture-test-v1",
        "source_key": FIXTURE_SOURCE_KEY,
        "novel_id": FIXTURE_NOVEL_ID,
        "chapter_ids": [chapter_id for chapter_id, _number, _title in FIXTURE_CHAPTERS],
        "published": True,
        "adult": False,
        "content_present": True,
        "cleanup_before_seed": cleanup,
        "r2_bucket_class": "dedicated_test_application_bucket",
        "database_class": "disposable_managed_test_database",
    }


def _status() -> dict[str, Any]:
    _assert_disposable_target()
    with session_scope() as db:
        novel = db.scalar(select(Novel).where(Novel.slug == FIXTURE_SLUG))
        chapter_count = (
            int(db.scalar(select(func.count(Chapter.id)).where(Chapter.novel_id == FIXTURE_NOVEL_ID)) or 0)
            if novel is not None
            else 0
        )
    return {
        "fixture": "reader-fixture-test-v1",
        "novel_count": 1 if novel is not None else 0,
        "chapter_count": chapter_count,
        "approved_ids_present": novel is not None and novel.id == FIXTURE_NOVEL_ID and chapter_count == 2,
        "r2_bucket_class": "dedicated_test_application_bucket",
        "database_class": "disposable_managed_test_database",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the disposable reader-capacity fixture.")
    parser.add_argument("action", choices=("seed", "status", "cleanup"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.action == "seed":
        result = _seed()
    elif args.action == "cleanup":
        result = _cleanup()
    else:
        result = _status()
    import json

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

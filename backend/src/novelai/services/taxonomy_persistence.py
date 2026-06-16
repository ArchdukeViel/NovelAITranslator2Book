"""Taxonomy persistence helpers for catalog service.

Connects scraped source taxonomy metadata to the DB taxonomy schema.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.genre import Genre
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag
from novelai.db.models.genre import novel_genres
from novelai.db.models.tag import novel_tags
from novelai.sources.taxonomy import normalize_keywords

logger = logging.getLogger(__name__)


def _upsert_tag(session: Session, name: str, name_ja: str | None = None) -> int:
    """Upsert a tag by name and return its ID.

    If the tag exists, return its ID. If not, create it.
    """
    tag = session.query(Tag).filter_by(name=name).one_or_none()
    if tag is None:
        tag = Tag(name=name, name_ja=name_ja, is_adult=False)
        session.add(tag)
        session.flush()  # Get the ID
    return tag.id


def _assign_genre(session: Session, novel_id: int, genre_slug: str, assigned_by: str = "scraper") -> None:
    """Assign a genre to a novel, avoiding duplicates.

    Does nothing if the assignment already exists.
    """
    genre = session.query(Genre).filter_by(slug=genre_slug, is_active=True).one_or_none()
    if genre is None:
        logger.debug(f"Genre slug {genre_slug!r} not found or inactive; skipping assignment")
        return

    # Check if assignment already exists
    existing = session.query(novel_genres).filter_by(novel_id=novel_id, genre_id=genre.id).one_or_none()
    if existing is not None:
        logger.debug(f"Novel {novel_id} already assigned to genre {genre_slug!r}")
        return

    # Insert assignment
    session.execute(
        novel_genres.insert().values(
            novel_id=novel_id,
            genre_id=genre.id,
            assigned_by=assigned_by,
        )
    )
    logger.info(f"Assigned novel {novel_id} to genre {genre_slug!r}")


def _assign_tag(
    session: Session,
    novel_id: int,
    tag_name: str,
    origin: str,
    assigned_by: str = "scraper",
) -> None:
    """Assign a tag to a novel, upserting the tag if needed.

    Does nothing if the assignment already exists.
    """
    tag_id = _upsert_tag(session, tag_name)

    # Check if assignment already exists
    existing = session.query(novel_tags).filter_by(novel_id=novel_id, tag_id=tag_id).one_or_none()
    if existing is not None:
        logger.debug(f"Novel {novel_id} already has tag {tag_name!r}")
        return

    # Insert assignment
    session.execute(
        novel_tags.insert().values(
            novel_id=novel_id,
            tag_id=tag_id,
            origin=origin,
            assigned_by=assigned_by,
        )
    )
    logger.debug(f"Assigned novel {novel_id} to tag {tag_name!r} (origin={origin})")


def persist_taxonomy_assignments(
    session: Session,
    novel_id: int,
    metadata: dict[str, Any],
    source_key: str | None = None,
) -> None:
    """Persist taxonomy assignments from scraped metadata to the DB.

    This function:
    - Assigns genre if metadata has genre_slug that matches a seeded genre
    - Creates/assigns tags from source_keywords (Syosetu) or source_tags (Kakuyomu)
    - Is idempotent: running twice does not create duplicates
    - Does not delete existing assignments (admin/manual assignments preserved)

    Args:
        session: Active SQLAlchemy session (caller manages lifecycle)
        novel_id: The DB novel ID (not the slug)
        metadata: Scraped metadata dict from source adapter
        source_key: Optional source key for origin tracking (e.g., "syosetu_ncode")
    """
    # Determine origin for tags
    if source_key:
        origin = source_key
    elif metadata.get("source") in ("syosetu_ncode", "novel18_syosetu"):
        origin = "syosetu"
    elif metadata.get("source") == "kakuyomu":
        origin = "kakuyomu"
    else:
        origin = "unknown"

    # 1. Assign genre if genre_slug is present and valid
    genre_slug = metadata.get("genre_slug")
    if isinstance(genre_slug, str) and genre_slug.strip():
        _assign_genre(session, novel_id, genre_slug.strip(), assigned_by="scraper")
    else:
        logger.debug(f"Novel {novel_id}: no valid genre_slug in metadata (got {genre_slug!r})")

    # 2. Assign tags from source_keywords (Syosetu/Novel18)
    source_keywords = metadata.get("source_keywords")
    if isinstance(source_keywords, list):
        normalized = normalize_keywords(source_keywords)
        for keyword in normalized:
            _assign_tag(session, novel_id, keyword, origin=origin, assigned_by="scraper")
        if normalized:
            logger.info(f"Assigned {len(normalized)} keyword(s) to novel {novel_id}")

    # 3. Assign tags from source_tags (Kakuyomu)
    source_tags = metadata.get("source_tags")
    if isinstance(source_tags, list):
        normalized = normalize_keywords(source_tags)
        for tag_name in normalized:
            _assign_tag(session, novel_id, tag_name, origin=origin, assigned_by="scraper")
        if normalized:
            logger.info(f"Assigned {len(normalized)} tag(s) to novel {novel_id}")

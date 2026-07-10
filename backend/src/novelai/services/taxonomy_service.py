"""Taxonomy service for per-novel genre/tag management.

Handles DB-level taxonomy operations (novel_genres, novel_tags tables).
Routers should call this service instead of importing db.models.* directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag, novel_tags


class TaxonomyService:
    """Service for managing per-novel genre/tag taxonomy assignments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_taxonomy(self, novel_ref: str) -> tuple[list[str], list[str]] | None:
        """Load combined (scraper + admin) genre slugs and tag names for a novel.

        Returns (genre_slugs, tag_names) or None if the novel is not found.
        Genres are ordered by display_order then slug; tags alphabetically.
        """
        novel = self._resolve_novel(novel_ref)
        if novel is None:
            return None

        genre_slugs = [g.slug for g in novel.genres if g.is_active]
        genre_slugs.sort(key=lambda s: next(
            (g.display_order for g in novel.genres if g.slug == s), 999
        ))

        tag_names = sorted({t.name for t in novel.tags})
        return genre_slugs, tag_names

    def set_taxonomy(self, novel_ref: str, genre_slugs: list[str], raw_tags: list[str]) -> tuple[list[str], list[str]] | None:
        """Replace admin-managed taxonomy assignments for a novel.

        Returns (genre_slugs, tag_names) after the change, or None if
        the novel is not found.
        """
        novel = self._resolve_novel(novel_ref)
        if novel is None:
            return None

        validated_genres = self._validate_genres(genre_slugs)
        if validated_genres is None:
            raise ValueError("Unknown or inactive genre slug")

        tags = self._normalize_tags(raw_tags)
        validated_tags = self._upsert_tags(tags)

        self._replace_admin_assignments(novel.id, validated_genres, validated_tags)
        self._session.commit()

        return self.get_taxonomy(novel_ref)

    def _resolve_novel(self, novel_ref: str) -> Novel | None:
        novel = self._session.query(Novel).filter_by(slug=novel_ref).one_or_none()
        if novel is None and novel_ref.isdigit():
            novel = self._session.get(Novel, int(novel_ref))
        return novel

    def _validate_genres(self, genre_slugs: list[str]) -> list[Genre] | None:
        validated: list[Genre] = []
        for slug in genre_slugs:
            genre = self._session.query(Genre).filter_by(slug=slug, is_active=True).one_or_none()
            if genre is None:
                return None
            validated.append(genre)
        return validated

    @staticmethod
    def _normalize_tags(raw: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for t in raw:
            cleaned = t.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    def _upsert_tags(self, tag_names: list[str]) -> list[Tag]:
        validated: list[Tag] = []
        for name in tag_names:
            tag = self._session.query(Tag).filter_by(name=name).one_or_none()
            if tag is None:
                tag = Tag(name=name)
                self._session.add(tag)
                self._session.flush()
            validated.append(tag)
        return validated

    def _replace_admin_assignments(self, novel_id: int, genres: list[Genre], tags: list[Tag]) -> None:
        self._delete_admin_rows(novel_id)
        existing_genre_rows = self._existing_genre_rows(novel_id)
        existing_tag_rows = self._existing_tag_rows(novel_id)
        now = _utcnow()

        for genre in genres:
            if genre.id in existing_genre_rows:
                if existing_genre_rows[genre.id] == "scraper":
                    self._session.execute(
                        update(novel_genres)
                        .where(
                            novel_genres.c.novel_id == novel_id,
                            novel_genres.c.genre_id == genre.id,
                        )
                        .values(assigned_by="admin", assigned_at=now)
                    )
                continue
            self._session.execute(
                novel_genres.insert().values(
                    novel_id=novel_id,
                    genre_id=genre.id,
                    assigned_by="admin",
                    assigned_at=now,
                )
            )

        for tag in tags:
            if tag.id in existing_tag_rows:
                if existing_tag_rows[tag.id] == "scraper":
                    self._session.execute(
                        update(novel_tags)
                        .where(
                            novel_tags.c.novel_id == novel_id,
                            novel_tags.c.tag_id == tag.id,
                        )
                        .values(
                            assigned_by="admin",
                            origin="admin",
                            assigned_at=now,
                        )
                    )
                continue
            self._session.execute(
                novel_tags.insert().values(
                    novel_id=novel_id,
                    tag_id=tag.id,
                    origin="admin",
                    assigned_by="admin",
                    assigned_at=now,
                )
            )

    def _delete_admin_rows(self, novel_id: int) -> None:
        self._session.execute(
            novel_genres.delete().where(
                novel_genres.c.novel_id == novel_id,
                novel_genres.c.assigned_by == "admin",
            )
        )
        self._session.execute(
            novel_tags.delete().where(
                novel_tags.c.novel_id == novel_id,
                novel_tags.c.assigned_by == "admin",
            )
        )

    def _existing_genre_rows(self, novel_id: int) -> dict[int, str]:
        return {
            row.genre_id: row.assigned_by
            for row in self._session.execute(
                select(novel_genres.c.genre_id, novel_genres.c.assigned_by).where(
                    novel_genres.c.novel_id == novel_id
                )
            )
        }

    def _existing_tag_rows(self, novel_id: int) -> dict[int, str]:
        return {
            row.tag_id: row.assigned_by
            for row in self._session.execute(
                select(novel_tags.c.tag_id, novel_tags.c.assigned_by).where(
                    novel_tags.c.novel_id == novel_id
                )
            )
        }


def _utcnow() -> datetime:
    return datetime.now(UTC)

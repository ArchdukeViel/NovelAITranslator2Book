"""Admin taxonomy endpoints for per-novel genre/tag management.

Only accessible to owner role. Operates on the DB taxonomy tables
(novel_genres, novel_tags), NOT file-backed storage metadata.

Admin save replaces admin-managed assignments and promotes any
selected scraper rows to admin ownership. This ensures selections
survive re-scrape.

The composite PK (novel_id, genre_id) / (novel_id, tag_id) prevents
dual rows for the same assignment. When a genre/tag is already assigned
by the scraper and the admin selects it, the row is promoted to
assigned_by="admin". Admin cannot remove scraper-only assignments
through this endpoint — only admin-owned rows are deleted during save.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session
from novelai.db.models.genre import Genre, novel_genres
from novelai.db.models.novel import Novel
from novelai.db.models.tag import Tag, novel_tags

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TaxonomyRequest(BaseModel):
    genre_slugs: list[str] = []
    tags: list[str] = []


class TaxonomyResponse(BaseModel):
    novel_id: str
    genres: list[str]
    tags: list[str]


class TaxonomyErrorDetail(BaseModel):
    """Match existing admin error response style."""

    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_tags(raw: list[str]) -> list[str]:
    """Trim whitespace, drop empties, deduplicate preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for t in raw:
        cleaned = t.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _load_taxonomy(db_session, novel_id: str) -> tuple[list[str], list[str]]:
    """Load combined (scraper + admin) genre slugs and tag names for a novel.

    Returns (genre_slugs, tag_names) matching the public router's ordering:
    - genres: by Genre.display_order then Genre.slug
    - tags: alphabetical by Tag.name
    """
    novel = db_session.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is None:
        return [], []

    genre_slugs = [g.slug for g in novel.genres if g.is_active]
    genre_slugs.sort(key=lambda s: next(
        (g.display_order for g in novel.genres if g.slug == s), 999
    ))

    tag_names = sorted({t.name for t in novel.tags})
    return genre_slugs, tag_names


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/{novel_id}/taxonomy", response_model=TaxonomyResponse)
async def get_novel_taxonomy(
    novel_id: str,
    db_session=Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Return current taxonomy (genres + tags) for one novel.

    Returns combined scraper + admin assignments.
    """
    novel = db_session.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    genres, tags = _load_taxonomy(db_session, novel_id)
    return {"novel_id": novel_id, "genres": genres, "tags": tags}


@router.put("/{novel_id}/taxonomy", response_model=TaxonomyResponse)
async def set_novel_taxonomy(
    novel_id: str,
    body: TaxonomyRequest,
    db_session=Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> dict[str, Any]:
    """Replace admin-managed taxonomy assignments for one novel.

    Semantics:
    - Validate novel exists in DB.
    - Validate genre slugs exist and are active.
    - Normalize tags: trim, deduplicate, drop empty.
    - Upsert tags by name if they do not exist.
    - Delete existing novel_genres rows for this novel where
      assigned_by="admin".
    - Delete existing novel_tags rows for this novel where
      assigned_by="admin".
    - For each selected genre:
      - If a scraper row already exists for this novel+genre,
        promote it: UPDATE assigned_by to "admin" (durable intent).
      - Else INSERT with assigned_by="admin".
    - For each selected tag:
      - If a scraper row already exists for this novel+tag,
        promote it: UPDATE assigned_by to "admin" and origin to "admin".
      - Else INSERT with assigned_by="admin" and origin="admin".
    - Scraper-only rows not selected by admin remain untouched.
    - Promoted rows survive re-scrape (scraper deletes only
      assigned_by="scraper" rows).
    - Idempotent: repeat calls with same body produce same result.
    - Returns combined scraper + admin assignments after the change.
    """
    novel = db_session.query(Novel).filter_by(slug=novel_id).one_or_none()
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    # --- Validate genre slugs ---
    validated_genres: list[Genre] = []
    for slug in body.genre_slugs:
        genre = db_session.query(Genre).filter_by(slug=slug, is_active=True).one_or_none()
        if genre is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown or inactive genre slug: {slug!r}",
            )
        validated_genres.append(genre)

    # --- Normalize tags ---
    tags = _normalize_tags(body.tags)

    # --- Upsert tags by name ---
    validated_tags: list[Tag] = []
    for name in tags:
        tag = db_session.query(Tag).filter_by(name=name).one_or_none()
        if tag is None:
            tag = Tag(name=name)
            db_session.add(tag)
            db_session.flush()
        validated_tags.append(tag)

    # --- Get existing assignments for this novel ---
    _existing_genre_ids = {
        row.genre_id
        for row in db_session.execute(
            select(novel_genres.c.genre_id).where(novel_genres.c.novel_id == novel.id)
        )
    }
    _existing_tag_ids = {
        row.tag_id
        for row in db_session.execute(
            select(novel_tags.c.tag_id).where(novel_tags.c.novel_id == novel.id)
        )
    }

    # --- Delete admin-assigned rows ---
    db_session.execute(
        novel_genres.delete().where(
            novel_genres.c.novel_id == novel.id,
            novel_genres.c.assigned_by == "admin",
        )
    )
    db_session.execute(
        novel_tags.delete().where(
            novel_tags.c.novel_id == novel.id,
            novel_tags.c.assigned_by == "admin",
        )
    )

    # Re-query existing IDs after admin row deletion so we don't
    # skip inserts for genres/tags that were only in the admin layer.
    # Also collect current assigned_by values so we can distinguish
    # scraper rows (promote) from admin rows (already deleted above).
    existing_genre_rows = {
        row.genre_id: row.assigned_by
        for row in db_session.execute(
            select(novel_genres.c.genre_id, novel_genres.c.assigned_by).where(
                novel_genres.c.novel_id == novel.id
            )
        )
    }
    existing_tag_rows = {
        row.tag_id: row.assigned_by
        for row in db_session.execute(
            select(novel_tags.c.tag_id, novel_tags.c.assigned_by).where(
                novel_tags.c.novel_id == novel.id
            )
        )
    }

    # --- Apply genre assignments (insert or promote) ---
    now = _utcnow()
    for genre in validated_genres:
        if genre.id in existing_genre_rows:
            if existing_genre_rows[genre.id] == "scraper":
                # Promote scraper row to admin ownership so it survives
                # re-scrape even if the source stops listing this genre.
                db_session.execute(
                    update(novel_genres)
                    .where(
                        novel_genres.c.novel_id == novel.id,
                        novel_genres.c.genre_id == genre.id,
                    )
                    .values(assigned_by="admin", assigned_at=now)
                )
            # Already admin (post-delete: impossible since we deleted
            # admin rows above; but safe for idempotency: if called
            # twice without commit, the row is already promoted).
            continue
        db_session.execute(
            novel_genres.insert().values(
                novel_id=novel.id,
                genre_id=genre.id,
                assigned_by="admin",
                assigned_at=now,
            )
        )

    # --- Apply tag assignments (insert or promote) ---
    for tag in validated_tags:
        if tag.id in existing_tag_rows:
            if existing_tag_rows[tag.id] == "scraper":
                # Promote scraper row: admin now claims ownership.
                # Also set origin="admin" — the admin is the new
                # authoritative source for this tag assignment.
                db_session.execute(
                    update(novel_tags)
                    .where(
                        novel_tags.c.novel_id == novel.id,
                        novel_tags.c.tag_id == tag.id,
                    )
                    .values(
                        assigned_by="admin",
                        origin="admin",
                        assigned_at=now,
                    )
                )
            continue
        db_session.execute(
            novel_tags.insert().values(
                novel_id=novel.id,
                tag_id=tag.id,
                origin="admin",
                assigned_by="admin",
                assigned_at=now,
            )
        )

    db_session.commit()

    # --- Return combined state ---
    genre_slugs, tag_names = _load_taxonomy(db_session, novel_id)
    return {"novel_id": novel_id, "genres": genre_slugs, "tags": tag_names}

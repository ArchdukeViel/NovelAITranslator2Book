"""Public chapter reader and tag-search endpoints.

Chapter reader, tags search, reader text helpers, and availability helpers.
Catalog browse and genres are in ``public_catalog.py``.
Novel detail and chapter list are in ``public_novel.py``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import case
from sqlalchemy.orm import Session

from novelai.api.routers.dependencies import (
    get_db_session,
    get_public_catalog_service,
    metadata_chapters,
    reader_title,
)
from novelai.api.routers.public_contracts import (
    DEFAULT_UNAVAILABLE_POLICY,
    PUBLIC_PARAGRAPH_MARKER_RE,
    PUBLIC_PROTOCOL_MARKER_RE,
    VALID_UNAVAILABLE_POLICIES,
    PublicTagSearchResult,
    _optional_str,
)
from novelai.config.settings import settings
from novelai.services.public_catalog_service import PublicCatalogService

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reader text helpers
# ---------------------------------------------------------------------------


def _public_reader_text(text: str) -> str:
    """Remove internal translation protocol markers from public reader text."""
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        current = line
        had_marker = False
        while True:
            current, replacements = PUBLIC_PROTOCOL_MARKER_RE.subn("", current, count=1)
            if replacements == 0:
                break
            had_marker = True
        if had_marker and not current.strip():
            continue
        cleaned_lines.append(current)
    return "\n".join(cleaned_lines).strip("\n")


def _reader_line_block(text: str) -> dict[str, str]:
    return {"type": "line", "text": text}


def _reader_break_block() -> dict[str, str]:
    return {"type": "break"}


def _append_reader_break(blocks: list[dict[str, str]]) -> None:
    if blocks and blocks[-1].get("type") != "break":
        blocks.append(_reader_break_block())


def _with_conservative_reader_breaks(blocks: list[dict[str, str]]) -> list[dict[str, str]]:
    """Add readable group breaks when old storage has line order but no group metadata."""
    if any(block.get("type") == "break" for block in blocks):
        return blocks

    line_blocks = [block for block in blocks if block.get("type") == "line"]
    if len(line_blocks) < 8:
        return blocks

    grouped: list[dict[str, str]] = []
    line_index = 0
    for block in blocks:
        grouped.append(block)
        if block.get("type") != "line":
            continue
        line_index += 1
        if line_index % 4 == 0 and line_index < len(line_blocks):
            grouped.append(_reader_break_block())
    return grouped


def _translated_paragraph_map(text: str) -> dict[str, str]:
    translations: dict[str, str] = {}
    current_id: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_id
        if current_id is not None:
            translated = "\n".join(current_lines).strip("\n")
            if translated.strip():
                translations[current_id] = translated
        current_id = None
        current_lines.clear()

    for line in text.splitlines():
        if re.match(r"^\s*\[CHAPTER[^\]]*\]\s*$", line, flags=re.IGNORECASE):
            flush_current()
            continue
        marker_match = re.match(r"^\s*\[P\s+(p\d{4})\]\s*(.*)$", line, flags=re.IGNORECASE)
        if marker_match:
            flush_current()
            current_id = marker_match.group(1).lower()
            remainder = marker_match.group(2)
            if remainder.strip():
                current_lines.append(remainder)
            continue
        if current_id is not None:
            current_lines.append(line)

    flush_current()
    return translations


def _source_layout_reader_blocks(text: str, source_blocks: Any) -> list[dict[str, str]]:
    if not isinstance(source_blocks, list):
        return []

    translations = _translated_paragraph_map(text)
    if not translations:
        return []

    blocks: list[dict[str, str]] = []
    for source_block in source_blocks:
        if not isinstance(source_block, dict):
            continue
        block_type = source_block.get("type")
        if block_type == "break":
            _append_reader_break(blocks)
            continue
        if block_type != "line":
            continue
        paragraph_id = source_block.get("paragraph_id")
        if not isinstance(paragraph_id, str):
            continue
        translated = translations.get(paragraph_id.lower())
        if translated and translated.strip():
            blocks.append(_reader_line_block(_public_reader_text(translated)))

    if blocks:
        return _with_conservative_reader_breaks(blocks)
    return []


def _public_reader_blocks(text: str, source_blocks: Any = None) -> list[dict[str, str]]:
    """Return source-layout-aware blocks without internal protocol markers."""
    layout_blocks = _source_layout_reader_blocks(text, source_blocks)
    if layout_blocks:
        return layout_blocks

    blocks: list[dict[str, str]] = []
    current_lines: list[str] = []
    saw_paragraph_marker = False
    pending_blank_lines = 0

    def flush_current() -> None:
        block = "\n".join(line for line in current_lines).strip("\n")
        current_lines.clear()
        if block.strip():
            blocks.append(_reader_line_block(block))

    for line in text.splitlines():
        stripped_line = line.strip()
        if re.match(r"^\s*\[CHAPTER[^\]]*\]\s*$", line, flags=re.IGNORECASE):
            flush_current()
            continue

        is_paragraph_marker = PUBLIC_PARAGRAPH_MARKER_RE.match(line) is not None
        if is_paragraph_marker:
            flush_current()
            if saw_paragraph_marker and pending_blank_lines >= 2:
                _append_reader_break(blocks)
            saw_paragraph_marker = True
            pending_blank_lines = 0

        current = line
        had_marker = False
        while True:
            current, replacements = PUBLIC_PROTOCOL_MARKER_RE.subn("", current, count=1)
            if replacements == 0:
                break
            had_marker = True

        if had_marker and not current.strip():
            continue
        if not stripped_line:
            flush_current()
            pending_blank_lines += 1
            if not saw_paragraph_marker and pending_blank_lines >= 1:
                _append_reader_break(blocks)
            continue
        pending_blank_lines = 0
        current_lines.append(current)

    flush_current()
    if blocks:
        return _with_conservative_reader_breaks(blocks)

    clean_text = _public_reader_text(text)
    fallback_blocks: list[dict[str, str]] = []
    for index, block in enumerate(block.strip("\n") for block in re.split(r"\n{2,}", clean_text) if block.strip()):
        if index > 0:
            fallback_blocks.append(_reader_break_block())
        fallback_blocks.append(_reader_line_block(block))
    return fallback_blocks


# ---------------------------------------------------------------------------
# Availability helpers
# ---------------------------------------------------------------------------


def _resolve_unavailable_policy(meta: dict[str, Any]) -> str:
    """Resolve the unavailable-chapter policy for a novel.

    Per-novel ``public_reader_unavailable_policy`` in metadata takes
    precedence over the global ``PUBLIC_READER_UNAVAILABLE_POLICY``
    setting. Invalid values fall back to ``hard_404`` and log a warning.
    Missing values are not warned about.
    """
    per_novel = meta.get("public_reader_unavailable_policy")
    if isinstance(per_novel, str) and per_novel.strip():
        if per_novel in VALID_UNAVAILABLE_POLICIES:
            return per_novel
        logger.warning(
            "Invalid per-novel public_reader_unavailable_policy %r; using hard_404",
            per_novel,
        )
        return DEFAULT_UNAVAILABLE_POLICY

    global_policy = settings.PUBLIC_READER_UNAVAILABLE_POLICY
    if isinstance(global_policy, str) and global_policy in VALID_UNAVAILABLE_POLICIES:
        return global_policy
    if isinstance(global_policy, str) and global_policy.strip():
        logger.warning(
            "Invalid PUBLIC_READER_UNAVAILABLE_POLICY %r; using hard_404",
            global_policy,
        )
    return DEFAULT_UNAVAILABLE_POLICY


async def _try_get_owner(request: Request | None) -> Any | None:
    """Best-effort, non-raising owner check for optional public preview.

    Returns the owner session user when authenticated as owner, otherwise
    ``None``. Swallows expected auth failures so public ``?version_id=``
    requests continue normally.
    """
    if request is None:
        return None
    try:
        from novelai.api.auth.session import get_current_user

        scope = getattr(request, "scope", None) or {}
        app = scope.get("app") if isinstance(scope, dict) else None
        override = None
        if app is not None:
            overrides = getattr(app, "dependency_overrides", None)
            if isinstance(overrides, dict):
                override = overrides.get(get_current_user)
        if override is not None:
            user = override()
        else:
            user = get_current_user(request)
        if getattr(user, "is_owner", False):
            return user
        return None
    except Exception:
        return None


def _has_reader_text(translated: dict[str, Any] | None) -> bool:
    return isinstance((translated or {}).get("text"), str)


def _latest_version_with_text(
    versions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the newest version that has usable string text."""
    candidates = [version for version in versions if isinstance(version, dict) and isinstance(version.get("text"), str)]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda version: version.get("created_at") or version.get("translated_at") or "",
        reverse=True,
    )[0]


def _translated_from_version(
    chapter_id: str,
    version: dict[str, Any],
) -> dict[str, Any]:
    """Build a normalized translated-chapter dict from a raw version entry."""
    created_at = version.get("created_at") or version.get("translated_at")
    translated_at = version.get("translated_at") or version.get("created_at")
    return {
        "chapter_id": chapter_id,
        "version_id": version.get("version_id"),
        "version_kind": version.get("version_kind"),
        "provider_key": version.get("provider_key"),
        "provider_model": version.get("provider_model"),
        "translated_at": translated_at,
        "created_at": created_at,
        "text": version.get("text"),
        "editor": version.get("editor"),
        "note": version.get("note"),
        "confidence_score": version.get("confidence_score"),
        "glossary_revision": version.get("glossary_revision", 0)
        if isinstance(version.get("glossary_revision"), int)
        else 0,
    }


def _chapter_shell_response(
    *,
    novel_id: str,
    meta: dict[str, Any],
    public_slug: str,
    chapter_id: str,
    chapter: dict[str, Any],
    chapters: list[dict[str, Any]],
    storage: Any,
) -> dict[str, Any]:
    """Build a reader-safe chapter shell response with no translated text."""
    chapter_ids = [str(ch.get("id", "")) for ch in chapters]
    if chapter_id in chapter_ids:
        index = chapter_ids.index(chapter_id)
    else:
        index = 0
    translated_ids = set(storage.list_translated_chapters(novel_id))

    prev_id = chapter_ids[index - 1] if index > 0 else None
    next_id = chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None

    return {
        "novel_id": novel_id,
        "slug": public_slug,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("num") or (index + 1),
        "novel_title": reader_title(meta),
        "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
        "text": None,
        "reader_blocks": [],
        "previous_chapter_id": prev_id if prev_id in translated_ids else None,
        "next_chapter_id": next_id if next_id in translated_ids else None,
        "previous_chapter_unavailable": prev_id is not None and prev_id not in translated_ids,
        "next_chapter_unavailable": next_id is not None and next_id not in translated_ids,
        "availability_status": "not_translated",
        "availability_message": "This chapter has not been translated yet.",
        "version_id": None,
        "version_kind": None,
        "is_active_version": False,
        "provider_key": None,
        "provider_model": None,
        "translated_at": None,
    }


def _availability_fields(
    translated: dict[str, Any] | None,
    *,
    is_active_version: bool,
) -> dict[str, Any]:
    """Build additive availability/version fields for a translated response."""
    if not isinstance(translated, dict):
        return {
            "availability_status": "available",
            "availability_message": None,
            "version_id": None,
            "version_kind": None,
            "is_active_version": is_active_version,
            "provider_key": None,
            "provider_model": None,
            "translated_at": None,
        }
    return {
        "availability_status": "available",
        "availability_message": None,
        "version_id": translated.get("version_id"),
        "version_kind": translated.get("version_kind"),
        "is_active_version": is_active_version,
        "provider_key": translated.get("provider_key"),
        "provider_model": translated.get("provider_model"),
        "translated_at": translated.get("translated_at"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/novels/{slug}/chapters/{chapter_id}")
async def get_chapter(
    slug: str,
    chapter_id: str,
    version_id: str | None = Query(default=None),
    request: Request = None,  # type: ignore[assignment]
    service: PublicCatalogService = Depends(get_public_catalog_service),
) -> dict[str, Any]:
    """Public translated chapter reader."""
    resolved = service._resolve_public_novel(slug)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Novel not found.")
    novel_id, meta, public_slug = resolved

    chapters = metadata_chapters(meta)
    chapter_ids = [str(ch.get("id", "")) for ch in chapters]
    if chapter_id not in chapter_ids:
        raise HTTPException(status_code=404, detail="Chapter not found.")

    effective_version_id: str | None = None
    if version_id is not None:
        owner = await _try_get_owner(request)
        if owner is not None:
            effective_version_id = version_id

    translated: dict[str, Any] | None = None
    is_active_version = True

    if effective_version_id is not None:
        translated = service.storage.load_translated_chapter_by_version_id(
            novel_id,
            chapter_id,
            effective_version_id,
        )
        if translated is None:
            raise HTTPException(status_code=404, detail="Version not found.")
        active = service.storage.load_translated_chapter(novel_id, chapter_id)
        active_version_id = active.get("version_id") if isinstance(active, dict) else None
        is_active_version = active_version_id == effective_version_id
    else:
        translated = service.storage.load_translated_chapter(novel_id, chapter_id)
        is_active_version = True

    if not _has_reader_text(translated):
        policy = _resolve_unavailable_policy(meta)

        if policy == "latest_version":
            versions = service.storage.list_translated_chapter_versions(novel_id, chapter_id)
            latest = _latest_version_with_text(versions)
            if latest is not None:
                translated = _translated_from_version(chapter_id, latest)
                is_active_version = False
            else:
                policy = "chapter_shell"

        if policy == "chapter_shell":
            index = chapter_ids.index(chapter_id)
            chapter = chapters[index]
            return _chapter_shell_response(
                novel_id=novel_id,
                meta=meta,
                public_slug=public_slug,
                chapter_id=chapter_id,
                chapter=chapter,
                chapters=chapters,
                storage=service.storage,
            )

        if policy == "hard_404":
            raise HTTPException(
                status_code=404,
                detail="Translated chapter not available.",
            )

    assert isinstance(translated, dict)
    translated_text = translated.get("text")  # type: ignore[no-untyped-call]
    if not isinstance(translated_text, str):
        raise HTTPException(
            status_code=404,
            detail="Translated chapter not available.",
        )
    paragraph_map = translated.get("paragraph_map")
    raw_chapter: dict[str, Any] = {}
    if not paragraph_map or not isinstance(paragraph_map, list) or not paragraph_map:
        raw_chapter = service.storage.load_chapter(novel_id, chapter_id) or {}

    index = chapter_ids.index(chapter_id)
    chapter = chapters[index]
    translated_ids = set(service.storage.list_translated_chapters(novel_id))
    previous_adjacent_id = chapter_ids[index - 1] if index > 0 else None
    next_adjacent_id = chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None
    previous_chapter_id = previous_adjacent_id if previous_adjacent_id in translated_ids else None
    next_chapter_id = next_adjacent_id if next_adjacent_id in translated_ids else None
    response = {
        "novel_id": novel_id,
        "slug": public_slug,
        "chapter_id": chapter_id,
        "chapter_number": chapter.get("num") or (index + 1),
        "novel_title": reader_title(meta),
        "title": _optional_str(chapter.get("translated_title")) or _optional_str(chapter.get("title")),
        "text": _public_reader_text(translated_text),
        "reader_blocks": _public_reader_blocks(translated_text, raw_chapter.get("source_blocks")),
        "previous_chapter_id": previous_chapter_id,
        "next_chapter_id": next_chapter_id,
        "previous_chapter_unavailable": previous_adjacent_id is not None and previous_chapter_id is None,
        "next_chapter_unavailable": next_adjacent_id is not None and next_chapter_id is None,
    }
    response.update(_availability_fields(translated, is_active_version=is_active_version))

    if settings.PUBLIC_GLOSSARY_ANNOTATIONS_ENABLED:
        try:
            annotations = service.public_glossary_annotations(
                novel_id=novel_id,
                metadata=meta,
                translated_text=response["text"],
                reader_blocks=response["reader_blocks"],
            )
            if annotations:
                response["glossary_annotations"] = annotations
        except Exception as exc:
            logger.debug("Glossary annotations failed (%s).", type(exc).__name__)

    return response


@router.get("/tags/search", response_model=list[PublicTagSearchResult])
async def search_tags(
    q: str = Query(min_length=1, description="Search query — at least 2 non-whitespace characters"),
    include_adult: bool = Query(default=False, description="Include adult tags"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    db: Session = Depends(get_db_session),
) -> list[PublicTagSearchResult]:
    """Search tags by name (case-insensitive). No tags are created."""
    from novelai.db.models.tag import Tag

    query_str = q.strip()
    if len(query_str) < 2:
        return []

    pattern = f"%{query_str}%"
    base = db.query(Tag).filter(Tag.name.ilike(pattern) | Tag.name_ja.ilike(pattern))
    if not include_adult:
        base = base.filter(Tag.is_adult.is_(False))

    prefix_case = case(
        (Tag.name.ilike(f"{query_str}%"), 0),
        (Tag.name_ja.ilike(f"{query_str}%"), 0),
        else_=1,
    )
    results = base.order_by(prefix_case, Tag.name).limit(limit).all()

    return [
        PublicTagSearchResult(
            name=t.name,
            name_ja=t.name_ja,
        )
        for t in results
    ]

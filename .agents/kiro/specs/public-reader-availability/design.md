# Design: Public Reader Availability

## Overview

Targeted changes to the public router and storage translations module. No new DB migrations. No new storage file formats. The availability policy is a string field read from settings and optionally overridden per-novel in `metadata.json`.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/config/settings.py` | Add `PUBLIC_READER_UNAVAILABLE_POLICY` |
| `backend/src/novelai/storage/translations.py` | Add `load_translated_chapter_by_version_id` |
| `backend/src/novelai/api/routers/public.py` | Update `get_chapter` handler; update `list_chapters` response |
| `backend/tests/test_public_reader_availability.py` | New |

### Files Not Touched

- DB models — no schema change
- Storage file formats — no change
- Admin chapter routes — unchanged
- Frontend — additive response fields only

## Component Design

### 1. `settings.py`

```python
PUBLIC_READER_UNAVAILABLE_POLICY: str = os.getenv(
    "PUBLIC_READER_UNAVAILABLE_POLICY", "hard_404"
)
```

Valid values: `"hard_404"`, `"chapter_shell"`, `"latest_version"`.

### 2. `load_translated_chapter_by_version_id` in `translations.py`

```python
def load_translated_chapter_by_version_id(
    self: Any,
    novel_id: str,
    chapter_id: str,
    version_id: str,
) -> dict[str, Any] | None:
    payload = self._load_chapter_bundle(novel_id, chapter_id)
    if payload is None:
        return None
    versions = self._translation_versions_from_payload(payload)
    for version in versions:
        if version.get("id") == version_id:
            return {
                "id": chapter_id,
                "version_id": version.get("id"),
                "version_kind": self._normalize_version_kind(version.get("kind")),
                "provider": version.get("provider"),
                "model": version.get("model"),
                "translated_at": version.get("translated_at") or version.get("created_at"),
                "created_at": version.get("created_at") or version.get("translated_at"),
                "text": version.get("text"),
                "editor": version.get("editor"),
                "note": version.get("note"),
                "confidence_score": version.get("confidence_score"),
                "glossary_revision": version.get("glossary_revision", 0),
            }
    return None
```

### 3. `get_chapter` Handler — Policy Logic

```python
@router.get("/novels/{slug}/chapters/{chapter_id}")
async def get_chapter(
    slug: str,
    chapter_id: str,
    version_id: str | None = Query(default=None),  # NEW
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    request: Request = None,                        # NEW for auth check
) -> dict[str, Any]:
```

**Policy resolution:**
```python
def _resolve_unavailable_policy(meta: dict) -> str:
    per_novel = meta.get("public_reader_unavailable_policy")
    if per_novel in {"hard_404", "chapter_shell", "latest_version"}:
        return per_novel
    global_policy = settings.PUBLIC_READER_UNAVAILABLE_POLICY
    if global_policy not in {"hard_404", "chapter_shell", "latest_version"}:
        logger.warning("Invalid PUBLIC_READER_UNAVAILABLE_POLICY '%s', using hard_404", global_policy)
        return "hard_404"
    return global_policy
```

**Version ID param auth check:**
```python
# version_id param: only honor for authenticated owner
effective_version_id: str | None = None
if version_id is not None:
    try:
        # Check owner role from request — optional auth, don't fail on absence
        owner = await _try_get_owner(request)
        if owner is not None:
            effective_version_id = version_id
        # else: silently ignore version_id for public requests
    except Exception:
        pass  # silently ignore
```

**Translation loading:**
```python
translated: dict | None = None
is_active_version = True

if effective_version_id is not None:
    translated = storage.load_translated_chapter_by_version_id(
        novel_id, chapter_id, effective_version_id
    )
    if translated is None:
        raise HTTPException(status_code=404, detail="Version not found.")
    active = storage.load_translated_chapter(novel_id, chapter_id)
    active_version_id = active.get("version_id") if active else None
    is_active_version = (active_version_id == effective_version_id)
else:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    is_active_version = True
```

**Unavailability handling:**
```python
if translated is None or not isinstance(translated.get("text"), str):
    policy = _resolve_unavailable_policy(meta)
    if policy == "latest_version":
        versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
        if versions:
            # Sort by created_at descending, pick most recent
            latest = sorted(
                versions,
                key=lambda v: v.get("created_at", "") or "",
                reverse=True,
            )[0]
            translated = {"text": latest.get("text"), "version_id": latest.get("id"), ...}
            is_active_version = False
        else:
            # No versions at all — fall through to chapter_shell
            policy = "chapter_shell"
    if policy == "chapter_shell" or translated is None or not isinstance(translated.get("text"), str):
        return _chapter_shell_response(novel_id, meta, public_slug, chapter_id, chapter, chapters, chapter_ids, storage)
    if policy == "hard_404":
        raise HTTPException(status_code=404, detail="Translated chapter not available.")
```

**`_chapter_shell_response` helper:**
```python
def _chapter_shell_response(
    novel_id, meta, public_slug, chapter_id, chapter, chapters, chapter_ids, storage
) -> dict:
    index = chapter_ids.index(chapter_id)
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
        "is_active_version": False,
    }
```

**Normal response — add new fields:**
```python
return {
    ...existing fields...,
    "availability_status": "available",
    "version_id": translated.get("version_id"),
    "is_active_version": is_active_version,
    "version_kind": translated.get("version_kind"),
    "provider": translated.get("provider"),
    "model": translated.get("model"),
    "translated_at": translated.get("translated_at"),
}
```

### 4. `list_chapters` — Add `availability_status`

In the chapter list handler, the chapter list response currently returns an array of chapter metadata dicts. Add `availability_status` per chapter:

```python
translated_ids = set(storage.list_translated_chapters(novel_id))
chapter_list = [
    {
        ...existing chapter fields...,
        "availability_status": "available" if str(ch.get("id", "")) in translated_ids else "not_translated",
    }
    for ch in chapters
]
```

### 5. Owner Auth Check Helper

```python
async def _try_get_owner(request: Request) -> Any | None:
    """Non-raising owner auth check for optional version_id gate."""
    try:
        from novelai.api.auth.roles import require_role
        checker = require_role("owner")
        return await checker.__call__(request)
    except Exception:
        return None
```

If the auth infrastructure doesn't cleanly support an optional check this way, the fallback is to always ignore `version_id` for non-authenticated requests by checking `request.headers.get("Cookie")` or the session token presence before attempting the role check.

## Migration and Backward Compatibility

- Default policy is `"hard_404"` — no change in behavior for existing deployments.
- New fields (`availability_status`, `version_id`, `is_active_version`) are additive — clients that don't read them are unaffected.
- `text: null` in chapter_shell responses is safe for clients that check `if text` before rendering.
- `list_chapters` `availability_status` field is additive.

## Acceptance Criteria

1. With default policy `"hard_404"`, missing translation still returns HTTP 404.
2. With policy `"chapter_shell"`, missing translation returns HTTP 200 with `text=null` and `availability_status="not_translated"`.
3. With policy `"latest_version"`, missing active translation but a saved version returns that version's text with `is_active_version=false`.
4. An authenticated owner can load any specific version via `?version_id=`.
5. Public unauthenticated requests ignore `version_id` silently.
6. Chapter list includes `availability_status` per chapter.
7. All 10 tests pass.

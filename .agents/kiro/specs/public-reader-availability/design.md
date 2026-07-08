# Design: Public Reader Availability

## Overview

This design adds explicit public-reader availability behavior for translated chapters while preserving the current default behavior.

The public reader currently assumes a translated chapter is available only when the active translated bundle can be loaded. When a chapter is missing a translation, has no active version, or has an invalid active version, behavior is not configurable. This design adds a small availability policy layer to the public chapter route.

Scope is intentionally narrow:

- Add a global unavailable-content policy setting.
- Allow optional per-novel policy override in `metadata.json`.
- Add a storage helper to load a specific translation version by ID.
- Add additive availability fields to public chapter and chapter-list responses.
- Allow authenticated owners to preview a specific translation version via `?version_id=`.
- Keep unauthenticated public readers on safe public behavior.

No database migrations, storage format changes, new endpoints, or frontend rewrites are required.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/config/settings.py` | Add `PUBLIC_READER_UNAVAILABLE_POLICY` |
| `backend/src/novelai/storage/translations.py` | Add `load_translated_chapter_by_version_id` |
| `backend/src/novelai/api/routers/public.py` | Update `get_chapter`; add availability fields to `list_chapters` |
| `backend/tests/test_public_reader_availability.py` | Add focused tests |

### Files Not Touched

- Database models.
- Storage file formats.
- Admin chapter routes.
- Translation pipeline.
- Crawl/fetch pipeline.
- Public reader frontend, except optional consumption of additive fields.

## Availability Policies

Add a string setting:

```python
PUBLIC_READER_UNAVAILABLE_POLICY: str = os.getenv(
    "PUBLIC_READER_UNAVAILABLE_POLICY",
    "hard_404",
)
```

Valid values:

| Policy | Behavior |
|---|---|
| `hard_404` | Missing/unavailable translated chapter returns HTTP 404. This is the default. |
| `chapter_shell` | Missing/unavailable translated chapter returns HTTP 200 with metadata/navigation but `text=null`. |
| `latest_version` | If active translation is missing but saved versions exist, return the latest saved translated version with `is_active_version=false`; otherwise fall back to `chapter_shell`. |

Per-novel override is read from `metadata.json`:

```json
{
  "public_reader_unavailable_policy": "chapter_shell"
}
```

Invalid global or per-novel values fall back to `hard_404`.

## Component Design

### 1. Policy Resolution

Add a helper in `public.py`:

```python
VALID_UNAVAILABLE_POLICIES = {"hard_404", "chapter_shell", "latest_version"}

def _resolve_unavailable_policy(meta: dict[str, Any]) -> str:
    per_novel = meta.get("public_reader_unavailable_policy")
    if per_novel in VALID_UNAVAILABLE_POLICIES:
        return per_novel

    global_policy = settings.PUBLIC_READER_UNAVAILABLE_POLICY
    if global_policy in VALID_UNAVAILABLE_POLICIES:
        return global_policy

    logger.warning(
        "Invalid PUBLIC_READER_UNAVAILABLE_POLICY %r; using hard_404",
        global_policy,
    )
    return "hard_404"
```

### 2. Load Translation Version by ID

Add to `backend/src/novelai/storage/translations.py`:

```python
def load_translated_chapter_by_version_id(
    self,
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
            created_at = version.get("created_at") or version.get("translated_at")
            translated_at = version.get("translated_at") or version.get("created_at")

            return {
                "id": chapter_id,
                "version_id": version.get("id"),
                "version_kind": self._normalize_version_kind(version.get("kind")),
                "provider": version.get("provider"),
                "model": version.get("model"),
                "created_at": created_at,
                "translated_at": translated_at,
                "text": version.get("text"),
                "editor": version.get("editor"),
                "note": version.get("note"),
                "confidence_score": version.get("confidence_score"),
                "glossary_revision": version.get("glossary_revision", 0),
            }

    return None
```

This helper reads existing translated chapter bundles only. It does not change the storage schema.

### 3. Optional Owner Version Preview

Update public `get_chapter` to accept `version_id`:

```python
@router.get("/novels/{slug}/chapters/{chapter_id}")
async def get_chapter(
    slug: str,
    chapter_id: str,
    version_id: str | None = Query(default=None),
    storage: StorageService = Depends(get_storage),
    db: Session = Depends(get_db_session),
    request: Request = None,
) -> dict[str, Any]:
    ...
```

Rules:

- `version_id` is honored only for authenticated owners.
- Public unauthenticated requests silently ignore `version_id`.
- Failed optional auth must not break normal public reads.
- Do not infer ownership from cookie/header presence alone; use existing auth helpers if available.

Helper:

```python
async def _try_get_owner(request: Request) -> Any | None:
    """Best-effort, non-raising owner check for optional public preview."""
    if request is None:
        return None

    try:
        from novelai.api.auth.roles import require_role

        checker = require_role("owner")
        return await checker(request)
    except Exception:
        return None
```

If local auth helpers require a different call shape, use the project’s existing optional-auth pattern.

### 4. Translation Loading Logic

```python
translated: dict[str, Any] | None = None
is_active_version = True

effective_version_id: str | None = None
if version_id is not None:
    owner = await _try_get_owner(request)
    if owner is not None:
        effective_version_id = version_id

if effective_version_id is not None:
    translated = storage.load_translated_chapter_by_version_id(
        novel_id,
        chapter_id,
        effective_version_id,
    )
    if translated is None:
        raise HTTPException(status_code=404, detail="Version not found.")

    active = storage.load_translated_chapter(novel_id, chapter_id)
    active_version_id = active.get("version_id") if active else None
    is_active_version = active_version_id == effective_version_id
else:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    is_active_version = True
```

Public readers without owner auth always receive the normal active-version path.

### 5. Unavailable Chapter Handling

```python
def _has_reader_text(translated: dict[str, Any] | None) -> bool:
    return isinstance((translated or {}).get("text"), str)
```

Policy handling:

```python
if not _has_reader_text(translated):
    policy = _resolve_unavailable_policy(meta)

    if policy == "latest_version":
        versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
        latest = _latest_version_with_text(versions)

        if latest is not None:
            translated = _translated_from_version(chapter_id, latest)
            is_active_version = False
        else:
            policy = "chapter_shell"

    if policy == "chapter_shell" or not _has_reader_text(translated):
        return _chapter_shell_response(
            novel_id=novel_id,
            meta=meta,
            public_slug=public_slug,
            chapter_id=chapter_id,
            chapter=chapter,
            chapters=chapters,
            chapter_ids=chapter_ids,
            storage=storage,
        )

    if policy == "hard_404":
        raise HTTPException(
            status_code=404,
            detail="Translated chapter not available.",
        )
```

Latest-version helper:

```python
def _latest_version_with_text(
    versions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        version
        for version in versions
        if isinstance(version.get("text"), str)
    ]

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda version: version.get("created_at") or version.get("translated_at") or "",
        reverse=True,
    )[0]
```

### 6. Chapter Shell Response

`chapter_shell` returns chapter metadata and navigation without translated text.

```python
def _chapter_shell_response(
    *,
    novel_id: str,
    meta: dict[str, Any],
    public_slug: str,
    chapter_id: str,
    chapter: dict[str, Any],
    chapters: list[dict[str, Any]],
    chapter_ids: list[str],
    storage: StorageService,
) -> dict[str, Any]:
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
        "title": _optional_str(chapter.get("translated_title"))
        or _optional_str(chapter.get("title")),
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
        "provider": None,
        "model": None,
        "translated_at": None,
    }
```

### 7. Normal Chapter Response Fields

Add these fields to the existing successful chapter response:

```python
{
    "availability_status": "available",
    "availability_message": None,
    "version_id": translated.get("version_id"),
    "version_kind": translated.get("version_kind"),
    "is_active_version": is_active_version,
    "provider": translated.get("provider"),
    "model": translated.get("model"),
    "translated_at": translated.get("translated_at"),
}
```

These fields are additive.

### 8. Chapter List Availability

Update the public chapter-list response to include per-chapter availability:

```python
translated_ids = set(storage.list_translated_chapters(novel_id))

chapter_list = [
    {
        **existing_chapter_fields,
        "availability_status": (
            "available"
            if str(ch.get("id", "")) in translated_ids
            else "not_translated"
        ),
    }
    for ch in chapters
]
```

No existing chapter-list fields should be removed.

## Migration and Backward Compatibility

- Default policy is `hard_404`, preserving current behavior.
- New response fields are additive.
- No database migration is required.
- No storage file format changes are required.
- Existing public routes remain unchanged.
- Existing clients that ignore new fields continue working.
- Public unauthenticated requests cannot select arbitrary historical versions.
- `chapter_shell` responses use `text: null` and `reader_blocks: []`.

## Test Plan

Create `backend/tests/test_public_reader_availability.py`.

Required tests:

1. Default `hard_404` returns HTTP 404 when translation is missing.
2. Global `chapter_shell` returns HTTP 200 with `text=null` and `availability_status="not_translated"`.
3. Per-novel `public_reader_unavailable_policy` overrides the global policy.
4. Invalid global policy falls back to `hard_404`.
5. `latest_version` returns latest saved version when active translation is unavailable.
6. `latest_version` sets `is_active_version=false`.
7. `latest_version` falls back to `chapter_shell` when no saved version has text.
8. Authenticated owner can load a specific version via `?version_id=`.
9. Public unauthenticated request ignores `?version_id=` and serves normal active-version behavior.
10. Unknown owner-requested `version_id` returns HTTP 404.
11. Chapter list includes `availability_status` for translated and untranslated chapters.
12. New fields are additive and existing response fields remain present.

## Acceptance Criteria

1. With default `hard_404`, missing translations still return HTTP 404.
2. With `chapter_shell`, missing translations return HTTP 200 with `text=null` and `availability_status="not_translated"`.
3. With `latest_version`, missing active translation but existing saved translated version returns that version with `is_active_version=false`.
4. Authenticated owners can load a specific translation version via `?version_id=`.
5. Public unauthenticated requests ignore `?version_id=`.
6. Public chapter responses include additive availability/version fields.
7. Public chapter list includes `availability_status` per chapter.
8. No DB migrations, storage format changes, or new endpoints are introduced.
9. Focused tests pass.
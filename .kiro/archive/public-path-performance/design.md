# Design: Public-Path and Storage Projection Hardening

## Overview

All changes stay within the router and service layers. No storage file formats change, no DB migrations are required, and the public API response shape is preserved (with one additive field). The work is in three areas:

1. Eliminating the `load_translated_chapter` N+1 in `recompute_catalog_projection` and `_latest_translated_chapter`
2. Making the public chapter endpoint's raw chapter read conditional
3. Improving observability of projection health without breaking existing workflows

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/services/catalog_service.py` | Remove N+1 in `_latest_translated_chapter`; add single-novel health endpoint logic |
| `backend/src/novelai/api/routers/public.py` | Remove N+1 in `_latest_translated_chapter`; conditional raw chapter read; DB slug lookup before scan |
| `backend/src/novelai/api/routers/library.py` | Add `GET /catalog-health`, `GET /{novel_id}/catalog-projection-health`; expose projection refresh error counter |
| `backend/src/novelai/services/catalog_service.py` | (continued) add `projection_refresh_failure_counter` module-level state; update `safely_refresh_catalog_projection_after_storage_write` |
| `backend/tests/test_catalog_projection_performance.py` | New |

### Files Not Touched

- `storage/` — no storage format changes
- `db/models/` — no schema changes (no migration)
- `api/routers/public.py` public response models — additive only
- `prompts/`, `translation/` — unrelated to this spec

## Component Design

### 1. `CatalogService._latest_translated_chapter` — Remove N+1

Current (problematic):
```python
translated = self._storage.load_translated_chapter(novel_id, chapter_id)
if translated is None or not isinstance(translated.get("text"), str):
    continue
latest = {"id": chapter_id, ..., "updated_at": translated.get("translated_at")}
```

New (no artifact load):
```python
def _latest_translated_chapter(
    self,
    novel_id: str,
    metadata_chapters: list[dict],
) -> dict[str, object] | None:
    translated_ids = set(self._storage.list_translated_chapters(novel_id))
    if not translated_ids:
        return None

    latest: dict[str, object] | None = None
    for index, chapter in enumerate(metadata_chapters):
        chapter_id = str(chapter.get("id", "")).strip()
        if not chapter_id or chapter_id not in translated_ids:
            continue
        # Source updated_at from chapter metadata, not from the artifact
        updated_at = (
            _optional_string(chapter.get("translated_at"))
            or _optional_string(chapter.get("updated_at"))
            or _optional_string(chapter.get("scraped_at"))
        )
        latest = {
            "id": chapter_id,
            "number": chapter.get("num") or (index + 1),
            "title": _optional_string(chapter.get("translated_title"))
                     or _optional_string(chapter.get("title")),
            "updated_at": _metadata_datetime(updated_at),
        }
    return latest
```

The `updated_at` sourcing changes from "read from the translated artifact timestamp" to "read from the chapter metadata dict." Chapter metadata dicts are already loaded as part of `metadata_chapters` — no extra I/O. For cases where `translated_at` in the chapter metadata is missing, the projection will show `null`, which is already the fallback behavior.

Apply the same change to the equivalent function in `public.py`.

### 2. Conditional Raw Chapter Read in `public.py`

Current:
```python
translated = storage.load_translated_chapter(novel_id, chapter_id)
raw_chapter = storage.load_chapter(novel_id, chapter_id) or {}
```

New:
```python
translated = storage.load_translated_chapter(novel_id, chapter_id)
# Only load raw chapter if translated chapter lacks a paragraph_map
# (paragraph_map is present in JSON-output mode and provides layout info)
paragraph_map = translated.get("paragraph_map") if isinstance(translated, dict) else None
needs_raw = not isinstance(paragraph_map, list) or len(paragraph_map) == 0
raw_chapter: dict[str, Any] = storage.load_chapter(novel_id, chapter_id) if needs_raw else {}
```

`_public_reader_blocks` must remain unchanged — it already handles `raw_chapter = {}` gracefully by falling back to block-splitting on the translated text. No response shape change.

### 3. DB Slug Lookup in `_resolve_public_novel`

The function signature gains an optional `db: Session | None = None` parameter:

```python
def _resolve_public_novel(
    slug: str,
    storage: StorageService,
    db: Session | None = None,
) -> tuple[str, dict[str, Any], str] | None:
    # Step 1: direct storage key hit (unchanged)
    meta = storage.load_metadata(slug)
    if meta is not None:
        source_id = _optional_str(meta.get("novel_id")) or slug
        return source_id, meta, _public_slug_from_metadata(source_id, meta)

    # Step 2: DB slug lookup (new)
    if db is not None:
        novel = db.query(Novel).filter_by(slug=slug).one_or_none()
        if novel is not None:
            meta = storage.load_metadata(novel.slug) or {}
            source_id = _optional_str(meta.get("novel_id")) or novel.slug
            return source_id, meta, _public_slug_from_metadata(source_id, meta)

    # Step 3: storage scan fallback (unchanged)
    for novel_id in storage.list_novels():
        ...
```

The public chapter endpoint handler passes `db` to `_resolve_public_novel`. No other change to the public chapter endpoint signature.

### 4. `projection_refresh_failure_counter` Module-Level State

In `catalog_service.py`:

```python
from collections import deque
from datetime import datetime, UTC

_PROJECTION_REFRESH_FAILURES: deque[dict[str, Any]] = deque(maxlen=50)

def _record_projection_refresh_failure(
    novel_id: str,
    error: str,
    context: str,
) -> None:
    """Non-raising — called from exception handler."""
    try:
        _PROJECTION_REFRESH_FAILURES.append({
            "novel_id": novel_id,
            "error": error[:200],
            "context": context,
            "failed_at": datetime.now(UTC).isoformat(),
        })
    except Exception:  # noqa: BLE001
        pass

def _clear_projection_refresh_failure(novel_id: str) -> None:
    """Called on success — remove entries for this novel."""
    try:
        # deque doesn't support in-place filtering; rebuild
        to_keep = [e for e in _PROJECTION_REFRESH_FAILURES if e.get("novel_id") != novel_id]
        _PROJECTION_REFRESH_FAILURES.clear()
        _PROJECTION_REFRESH_FAILURES.extend(to_keep)
    except Exception:  # noqa: BLE001
        pass

def get_projection_refresh_failures() -> list[dict[str, Any]]:
    return list(_PROJECTION_REFRESH_FAILURES)
```

Update `safely_refresh_catalog_projection_after_storage_write`:
```python
except Exception as exc:
    _record_projection_refresh_failure(novel_id, str(exc), context)
    logger.warning(...)
    return False
# On success path:
_clear_projection_refresh_failure(novel_id)
return True
```

### 5. Admin Endpoints

#### `GET /catalog-health` (library.py)

```python
@router.get("/catalog-health", response_model=CatalogHealthResponse)
async def catalog_health(
    storage: StorageService = Depends(get_storage),
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> CatalogHealthResponse:
```

```python
class CatalogHealthResponse(BaseModel):
    total_novels: int
    projection_stale_count: int
    missing_projection_count: int
    last_bulk_reconciliation_at: str | None
    recommendations: list[str]
    projection_refresh_errors: list[dict]  # from failure counter
```

Implementation:
```python
total_novels = session.query(Novel).count()
stale_threshold = datetime.now(UTC) - timedelta(hours=24)
projection_stale_count = session.query(Novel).filter(
    Novel.updated_at < stale_threshold
).count()
db_slugs = {slug for (slug,) in session.query(Novel.slug).all()}
storage_ids = set(storage.list_novels())
missing_projection_count = len(storage_ids - db_slugs)
recommendations = []
if missing_projection_count > 0:
    recommendations.append("run_bulk_reconciliation")
if projection_stale_count > 0:
    recommendations.append("refresh_stale_projections")
if not recommendations:
    recommendations.append("all_projections_healthy")
```

`last_bulk_reconciliation_at` — track this in a module-level variable updated by the bulk reconciliation endpoint handler when a non-dry-run completes.

#### `GET /{novel_id}/catalog-projection-health` (library.py)

```python
class NovelProjectionHealthResponse(BaseModel):
    novel_id: str
    db_translated_count: int | None
    storage_translated_count: int
    in_sync: bool
    last_refreshed_at: str | None
    recommended_action: str
```

Implementation: load `Novel` row for `novel_id`, read `novel.translated_count` and `novel.updated_at`. Call `storage.count_translated_chapters(novel_id)`. Compare. Return.

### 6. `degraded` Flag on Storage Fallback Catalog Response

`PublicCatalogResponse` gains an optional additive field:

```python
class PublicCatalogResponse(BaseModel):
    novels: list[PublicNovelSummary]
    total: int
    page: int
    page_size: int
    degraded: bool = False   # NEW — True when storage fallback fired
```

`_catalog_from_storage` sets `degraded=True` on the returned response. `_catalog_from_db_page` always returns `degraded=False` (the default).

The `WARNING` log is emitted in the `catalog()` route handler when `db_response` is `None` and before calling `_catalog_from_storage`.

### 7. Test Design

`tests/test_catalog_projection_performance.py`:

**N+1 tests (using `unittest.mock.MagicMock` on storage):**
- `test_recompute_projection_does_not_load_chapter_artifacts` — mock `storage.load_translated_chapter`, assert `assert_not_called()` after `recompute_catalog_projection`
- `test_latest_chapter_determined_from_id_set_only` — `list_translated_chapters` returns `{"ch2"}`, metadata has `[ch1, ch2, ch3]`, assert result is `ch2`
- `test_latest_chapter_empty_when_no_translated_ids` — empty set → `None` returned

**Conditional raw read tests:**
- `test_public_chapter_skips_raw_read_when_paragraph_map_present` — translated artifact has `paragraph_map=[...]`, `load_chapter` mock asserts `assert_not_called()`
- `test_public_chapter_loads_raw_when_paragraph_map_absent` — translated artifact has no `paragraph_map`, `load_chapter` is called

**Slug resolver tests:**
- `test_slug_resolver_uses_db_before_storage_scan` — DB returns a novel, `list_novels` mock asserts `assert_not_called()`
- `test_slug_resolver_falls_back_when_db_misses` — DB returns `None`, `list_novels` is called, slug found in scan

**Health endpoint tests:**
- `test_catalog_health_counts_missing_projections` — 3 storage novels, 2 in DB → `missing_projection_count=1`
- `test_catalog_health_counts_stale_projections` — 1 novel with `updated_at` 48h ago → `projection_stale_count=1`
- `test_catalog_health_recommendations_all_healthy` — all in sync → `["all_projections_healthy"]`
- `test_projection_refresh_failure_recorded_and_cleared`

**Degraded flag test:**
- `test_storage_fallback_degraded_flag` — no published DB novels → storage fallback → `degraded=True`

## Migration and Backward Compatibility

- `PublicCatalogResponse.degraded` is an additive optional field (default `False`). Existing clients that don't read it are unaffected.
- `_resolve_public_novel` gains `db=None` with a safe default — all existing call sites that don't pass `db` continue to work via the storage scan fallback.
- `_latest_translated_chapter` no longer reads artifact timestamps. For already-projected novels, the `latest_chapter_updated_at` DB field will be `null` for chapters where chapter metadata doesn't carry a `translated_at` field. This is already the projection's actual behavior for many novels. No regression.
- No DB migration needed.

## Acceptance Criteria

1. `recompute_catalog_projection` makes zero calls to `storage.load_translated_chapter()`.
2. The public chapter endpoint does not call `storage.load_chapter()` when the translated artifact contains a non-empty `paragraph_map`.
3. `_resolve_public_novel` does not call `storage.list_novels()` when the DB has a matching slug.
4. `GET /catalog-health` returns `missing_projection_count` and `projection_stale_count` without triggering any storage writes.
5. When the public catalog storage fallback fires, the response contains `degraded: true` and a `WARNING` log is emitted.
6. All new tests pass.

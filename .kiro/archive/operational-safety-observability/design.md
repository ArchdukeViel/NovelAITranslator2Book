# Design: Operational Safety and Observability

## Overview

This spec makes targeted fixes to concrete safety regressions (backup manifest write, silent JSON parse errors, missing catalog refresh after restore) and adds focused observability improvements (expanded runtime-state endpoint, correlation IDs, checkpoint inventory endpoint, malformed-artifact tests). All changes are backward-compatible and confined to the service and storage layers.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/services/backup_manager.py` | Use `atomic_write` for manifest; add optional `storage` param and catalog refresh call to `restore_backup` |
| `backend/src/novelai/storage/runtime_contracts.py` | Add `WARNING` log in `_read_json_file` on `JSONDecodeError`; add `DEBUG` log on empty file |
| `backend/src/novelai/services/admin_service.py` | Expand `RUNTIME_STATE_DEFINITIONS` with translation runtime files + backup manifest |
| `backend/src/novelai/api/routers/admin.py` | Block `DELETE /admin/runtime-state/backup_manifest`; ensure new keys behave correctly |
| `backend/src/novelai/translation/pipeline/stages/translate.py` | Generate/propagate `request_id`; include in chunk/attempt records |
| `backend/src/novelai/api/routers/library.py` | Add `GET /novels/{novel_id}/checkpoints` endpoint |
| `backend/tests/test_malformed_artifact_recovery.py` | New — malformed-artifact recovery tests |
| `backend/tests/test_backup_restore_catalog_refresh.py` | New — catalog refresh after restore tests |

### Files Not Touched

- `storage/chapters.py` — existing recovery patterns are already correct
- `storage/glossary.py` — existing recovery is already correct
- `storage/jobs.py` — existing recovery is already correct
- `public.py` — public router unchanged
- `prompts/` — unrelated to this spec

## Component Design

### 1. `BackupManager._save_manifest` — Atomic Write

```python
# Before
def _save_manifest(self, manifest: dict[str, BackupManifestEntry]) -> None:
    self._backup_manifest.write_text(
        json.dumps(serialized, ...), encoding="utf-8"
    )

# After
from novelai.utils import atomic_write

def _save_manifest(self, manifest: dict[str, BackupManifestEntry]) -> None:
    atomic_write(
        self._backup_manifest,
        json.dumps(serialized, ensure_ascii=False, indent=2),
    )
```

No schema change. `_load_manifest` unchanged.

### 2. `_read_json_file` — Logging

```python
def _read_json_file(path: Path, default: T) -> T:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            logger.debug("Empty JSON file: %s — returning default.", path.name)
            return default
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Corrupt JSON file: %s — returning default.", path.name)
        return default
    except OSError:
        return default
```

The `path.name` (not full path) is logged to avoid exposing filesystem structure in log output. `path.name` is the bare filename (e.g. `chunks.json`), which is sufficient for debugging without leaking storage root paths.

### 3. `BackupManager.restore_backup` — Catalog Refresh

```python
def __init__(
    self,
    base_dir: Path,
    *,
    storage: StorageService | None = None,      # NEW optional
    session_scope_factory: Callable | None = None,  # NEW optional
) -> None:
    self._storage = storage
    self._session_scope_factory = session_scope_factory or session_scope
    ...
```

In `restore_backup`, after successful extraction:
```python
if self._storage is not None:
    from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
    safely_refresh_catalog_projection_after_storage_write(
        novel_id=novel_id,
        storage=self._storage,
        context="backup_restore",
        session_scope_factory=self._session_scope_factory,
    )
```

`novel_id` is derived from the backup manifest entry or the backup info structure — it must be an existing field in `BackupInfo`.

Existing callers that do `BackupManager(base_dir)` without `storage` continue to work. The refresh is silently skipped.

### 4. Correlation ID in `TranslateStage`

At the start of `TranslateStage.run()`:
```python
import uuid

request_id = str(context.metadata.get("request_id") or "").strip()
if not request_id:
    request_id = str(uuid.uuid4())
    context.metadata["request_id"] = request_id
```

When writing a chunk record (in `_save_chunk_records` or equivalent), include:
```python
record["request_id"] = request_id
```

When writing a chunk attempt record, include the same `request_id`.

When raising the max-attempts-exceeded error, include `request_id` in the error detail dict.

`request_id` must not be logged at any level — it is stored in JSON files only. This avoids log volume concerns and keeps observability in the artifact layer.

### 5. Expanded `RUNTIME_STATE_DEFINITIONS`

```python
RUNTIME_STATE_DEFINITIONS = {
    # Existing
    "preferences": { ... },
    "translation_cache": { ... },
    "usage": { ... },

    # New — translation runtime tracking
    "runtime_chunks": {
        "label": "Translation Chunks",
        "filename": "runtime/translation/chunks.json",
        "description": "Per-chunk translation tracking records for active and recent translation runs.",
        "affects_process": True,
    },
    "runtime_chunk_attempts": {
        "label": "Translation Chunk Attempts",
        "filename": "runtime/translation/chunk_attempts.json",
        "description": "Per-attempt records for each chunk translation, including retry history.",
        "affects_process": True,
    },
    "runtime_bundles": {
        "label": "Translation Bundles",
        "filename": "runtime/translation/bundles.json",
        "description": "Bundle-level translation state for active runs.",
        "affects_process": True,
    },
    "runtime_outputs": {
        "label": "Translation Outputs",
        "filename": "runtime/translation/outputs.json",
        "description": "Completed translation output records.",
        "affects_process": True,
    },
    # Backup manifest — read-only in this surface
    "backup_manifest": {
        "label": "Backup Manifest",
        "filename": "backups/manifest.json",
        "description": "Inventory of all backup archives. Do not clear via this endpoint.",
        "affects_process": False,
    },
}
```

### 6. Block `DELETE /admin/runtime-state/backup_manifest`

In `DELETE /admin/runtime-state/{key}` handler:
```python
if key == "backup_manifest":
    raise HTTPException(
        status_code=422,
        detail="backup_manifest cannot be cleared via this endpoint. Use backup management endpoints.",
    )
```

### 7. `GET /novels/{novel_id}/checkpoints` Endpoint

```python
class ChapterCheckpointFile(BaseModel):
    name: str
    timestamp: str | None
    size_bytes: int

class ChapterCheckpoints(BaseModel):
    chapter_id: str
    checkpoint_files: list[ChapterCheckpointFile]

class NovelCheckpointsResponse(BaseModel):
    novel_id: str
    chapters: list[ChapterCheckpoints]
    total_checkpoint_files: int

@router.get("/{novel_id}/checkpoints", response_model=NovelCheckpointsResponse)
async def list_novel_checkpoints(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> NovelCheckpointsResponse:
    chapter_ids = storage.list_stored_chapters(novel_id)
    chapters: list[ChapterCheckpoints] = []
    total = 0
    for chapter_id in chapter_ids:
        checkpoints = storage.list_checkpoints(novel_id, chapter_id)
        if not checkpoints:
            continue
        files = [
            ChapterCheckpointFile(
                name=cp.name,           # from CheckpointInfo
                timestamp=cp.timestamp,
                size_bytes=cp.size_bytes if hasattr(cp, "size_bytes") else 0,
            )
            for cp in checkpoints
        ]
        total += len(files)
        chapters.append(ChapterCheckpoints(chapter_id=chapter_id, checkpoint_files=files))
    return NovelCheckpointsResponse(novel_id=novel_id, chapters=chapters, total_checkpoint_files=total)
```

The response must use the checkpoint `name` field (e.g. `"ch001__20240601_120000"`) — not a filesystem path.

### 8. Test Design

#### `tests/test_malformed_artifact_recovery.py`

Uses `tmp_path` pytest fixture for real temp files:

```python
def _write(path, content):
    path.write_text(content, encoding="utf-8")

# _load_chapter_bundle
def test_chapter_bundle_truncated_json(tmp_path, storage):
    bundle_path = ...  # construct valid path under tmp_path
    _write(bundle_path, '{"id": "ch001", "translation_versions":')  # truncated
    result = storage._load_chapter_bundle("novel1", "ch001")
    assert result is None

def test_chapter_bundle_empty_file(tmp_path, storage): ...
def test_chapter_bundle_array_instead_of_dict(tmp_path, storage): ...

# load_chapter_state
def test_chapter_state_malformed(tmp_path, storage): ...
def test_chapter_state_empty(tmp_path, storage): ...

# load_glossary
def test_glossary_malformed(tmp_path, storage): ...

# _read_json_file
def test_read_json_file_malformed_emits_warning(tmp_path, caplog):
    import logging
    path = tmp_path / "chunks.json"
    path.write_text("{broken", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        result = _read_json_file(path, {})
    assert result == {}
    assert "Corrupt JSON file" in caplog.text

def test_read_json_file_empty_emits_debug(tmp_path, caplog):
    path = tmp_path / "bundles.json"
    path.write_text("   ", encoding="utf-8")
    with caplog.at_level(logging.DEBUG):
        result = _read_json_file(path, {})
    assert result == {}
    # DEBUG log present
```

#### `tests/test_backup_restore_catalog_refresh.py`

```python
def test_restore_backup_calls_catalog_refresh_when_storage_supplied(tmp_path, mocker):
    manager = BackupManager(tmp_path, storage=mock_storage)
    refresh_mock = mocker.patch("novelai.services.catalog_service.safely_refresh_catalog_projection_after_storage_write")
    manager.restore_backup(backup_id="b1", ...)
    refresh_mock.assert_called_once()

def test_restore_backup_succeeds_even_if_refresh_raises(tmp_path, mocker):
    # safely_refresh_... already swallows exceptions; this test confirms the
    # restore result is still success when the refresh itself is problematic
    manager = BackupManager(tmp_path, storage=mock_storage)
    mocker.patch("...", side_effect=Exception("refresh failed"))
    result = manager.restore_backup(backup_id="b1", ...)
    assert result.success is True  # adjust to actual return type

def test_restore_backup_skips_refresh_when_storage_is_none(tmp_path, mocker):
    manager = BackupManager(tmp_path)  # no storage
    refresh_mock = mocker.patch("...")
    manager.restore_backup(backup_id="b1", ...)
    refresh_mock.assert_not_called()
```

## Migration and Backward Compatibility

- `BackupManager.__init__` gains optional `storage` and `session_scope_factory` — existing callers without these args continue to work.
- `_save_manifest` change: `atomic_write` writes to the same path. The manifest schema is unchanged.
- `_read_json_file` change: adds logging only — return behavior is identical.
- `RUNTIME_STATE_DEFINITIONS` expansion: `GET /admin/runtime-state` returns more entries. Clients that iterate the list are unaffected; clients that look up a specific key by name gain new keys.
- New checkpoint endpoint: additive.
- Correlation ID in chunk records: new field in JSON files; existing readers that don't expect `request_id` are unaffected.

## Acceptance Criteria

1. `BackupManager._save_manifest` uses `atomic_write`. A test confirms backup manifest is written atomically.
2. `_read_json_file` logs `WARNING` when `JSONDecodeError` is caught; test confirms log message.
3. `BackupManager.restore_backup` calls `safely_refresh_catalog_projection_after_storage_write` when `storage` is supplied; test confirms.
4. `GET /admin/runtime-state` returns entries for `runtime_chunks`, `runtime_chunk_attempts`, `runtime_bundles`, `runtime_outputs`, and `backup_manifest`.
5. `DELETE /admin/runtime-state/backup_manifest` returns HTTP 422.
6. `GET /novels/{novel_id}/checkpoints` returns chapter checkpoint inventory without filesystem paths.
7. All malformed-artifact recovery tests pass.
8. All catalog-refresh-after-restore tests pass.

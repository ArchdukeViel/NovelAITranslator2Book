# Design: Glossary Sync Bridge

## Overview

The sync bridge is a single-direction pipeline: file glossary (source of truth for extraction/review) → DB glossary (source of truth for prompt injection). It introduces one new service class, one new orchestration hook, two new admin endpoints, and one `TranslateStage` fix. No existing DB schema changes are needed. No storage file format changes are needed.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/services/glossary_sync_service.py` | New — `GlossarySyncService` and `GlossarySyncResult` |
| `backend/src/novelai/services/orchestration/glossary.py` | Add sync call after `review_glossary_terms` saves to file |
| `backend/src/novelai/translation/pipeline/stages/translate.py` | Add `platform_novel_id` resolution at start of `run()` |
| `backend/src/novelai/api/routers/admin_glossary.py` | Add `POST /glossary/sync-to-db` and `GET /glossary/sync-status` |
| `backend/tests/test_glossary_sync_bridge.py` | New |

### Files Not Touched

- `storage/glossary.py` — file glossary read/write unchanged
- `services/glossary_prompt_injection.py` — prompt rendering unchanged (owned by `prompt-translation-hardening`)
- `services/glossary_repository.py` — `create_glossary_entry` used as-is
- `db/models/glossary.py` — no schema change
- Any migration files — no new columns

## Component Design

### 1. `GlossarySyncService`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository
from novelai.storage.service import StorageService


@dataclass
class GlossarySyncResult:
    novel_id: str
    dry_run: bool
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    synced_terms: list[str] = field(default_factory=list)


class GlossarySyncService:
    def __init__(self, repository: GlossaryRepository, storage: StorageService) -> None:
        self.repository = repository
        self.storage = storage

    def sync_from_file(
        self,
        novel_id: str,
        *,
        actor_user_id: int | None = None,
        dry_run: bool = False,
    ) -> GlossarySyncResult:
        ...
```

#### `sync_from_file` algorithm

1. Load file entries: `entries = self.storage.load_glossary(novel_id)`
2. Resolve `platform_novel_id`: query `db.query(Novel).filter_by(slug=novel_id).one_or_none()` → if `None`, raise `ValueError("novel_not_in_db")`
3. Filter eligible entries: `status in {"approved", "needs_manual_review"}` and `source` is non-empty
4. For each eligible entry:
   a. Try `repository.list_glossary_entries_for_novel(platform_novel_id)` — find existing by `canonical_term == entry["source"]`
   b. If not found and not `dry_run`: call `repository.create_glossary_entry(...)` with mapped fields
   c. If found and not `dry_run`: call `repository.update_glossary_entry(...)` with allowed field updates; skip `status` update if existing status is `"approved"` and file status maps to `"candidate"`
   d. If `dry_run`: count what would happen
   e. On any exception: append `{"term": source, "error": str(exc)}` to `errors`, continue
5. If not `dry_run` and `created + updated > 0`: call `repository._increment_glossary_revision(platform_novel_id)` once
6. Return `GlossarySyncResult`

**Field mapping table:**

| File glossary field | DB `NovelGlossaryEntry` field | Notes |
|---|---|---|
| `source` | `canonical_term` | Required |
| `target` | `approved_translation` | Optional; skip if empty |
| `status == "approved"` | `status = "approved"` | |
| `status == "needs_manual_review"` | `status = "candidate"` | |
| `confidence` | `confidence` | Optional float |
| `notes` | `admin_notes` | Optional |
| (fixed) | `term_type = "extracted"` | Provenance marker |
| (fixed) | `decision_source = "file_glossary_sync"` | |
| (fixed) | `rationale = "Promoted from file glossary review"` | |

**Upsert logic for `update_glossary_entry`:**

Only these fields are updated:
- `approved_translation` (always, if non-empty in file)
- `admin_notes` (always, from `notes`)
- `confidence` (always, if present)
- `status`: only update if current DB status is `"candidate"` — never downgrade from `"approved"` to `"candidate"`

### 2. `review_glossary_terms` Hook

At the end of `review_glossary_terms`, after `self.storage.save_glossary(novel_id, entries)`:

```python
try:
    from novelai.services.glossary_sync_service import GlossarySyncService
    from novelai.db.engine import session_scope
    from novelai.services.glossary_repository import GlossaryRepository

    with session_scope() as session:
        repo = GlossaryRepository(session)
        sync_result = GlossarySyncService(repo, self.storage).sync_from_file(
            novel_id, actor_user_id=None
        )
    db_sync = {
        "created": sync_result.created,
        "updated": sync_result.updated,
        "skipped": sync_result.skipped,
        "error_count": len(sync_result.errors),
    }
except ValueError as exc:
    if "novel_not_in_db" in str(exc):
        db_sync = {"skipped": True, "reason": "novel_not_in_db"}
    else:
        logger.warning("Glossary DB sync failed: %s", exc)
        db_sync = {"skipped": True, "reason": "sync_error"}
except Exception as exc:
    logger.warning("Glossary DB sync failed after review: %s", exc.__class__.__name__)
    db_sync = {"skipped": True, "reason": "sync_error"}
```

Add `"db_sync": db_sync` to the return dict.

### 3. `TranslateStage.run()` — `platform_novel_id` Resolution

Add at the start of `run()`, before the worker/scheduler loop:

```python
# Resolve platform_novel_id if not already in context
if self._platform_novel_id(context) is None and isinstance(context.novel_id, str) and context.novel_id.strip():
    try:
        from novelai.db.engine import session_scope
        from novelai.db.models.novel import Novel as NovelModel
        with session_scope() as session:
            novel_row = session.query(NovelModel).filter_by(slug=context.novel_id.strip()).one_or_none()
            if novel_row is not None:
                context.metadata["platform_novel_id"] = novel_row.id
    except Exception as exc:
        logger.debug("Could not resolve platform_novel_id for %s: %s", context.novel_id, exc.__class__.__name__)
```

This runs once per `run()` call. `_platform_novel_id()` is the existing static method that checks three context keys.

### 4. Router Endpoints

#### `POST /novels/{novel_id}/glossary/sync-to-db`

```python
class GlossarySyncRequest(BaseModel):
    dry_run: bool = False

class GlossarySyncResponse(BaseModel):
    novel_id: str
    dry_run: bool
    created: int
    updated: int
    skipped: int
    errors: list[dict[str, str]]
    synced_terms: list[str]

@router.post("/novels/{novel_id}/glossary/sync-to-db", response_model=GlossarySyncResponse)
async def sync_glossary_to_db(
    novel_id: str,
    body: GlossarySyncRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossarySyncResponse:
```

Calls `GlossarySyncService(GlossaryRepository(session), storage).sync_from_file(novel_id, dry_run=body.dry_run)`.

Returns HTTP 404 when `storage.load_metadata(novel_id)` is `None`.
Returns HTTP 422 with `"novel_not_in_db"` message when `GlossarySyncService` raises `ValueError("novel_not_in_db")`.

#### `GET /novels/{novel_id}/glossary/sync-status`

```python
# Module-level: tracks last sync timestamp per novel_id
_LAST_SYNC_TIMESTAMPS: dict[str, str] = {}

class GlossarySyncStatusResponse(BaseModel):
    novel_id: str
    file_approved_count: int
    db_approved_count: int
    in_sync: bool
    last_sync_at: str | None
    recommendation: str  # "sync_required" | "healthy" | "empty"

@router.get("/novels/{novel_id}/glossary/sync-status", response_model=GlossarySyncStatusResponse)
async def glossary_sync_status(...) -> GlossarySyncStatusResponse:
```

Implementation:
- `file_entries = storage.load_glossary(novel_id)`
- `file_approved_count = sum(1 for e in file_entries if e.get("status") == "approved")`
- `novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()` — if `None`, return all zeros
- `db_approved_count = repository.list_glossary_entries_for_novel(novel.id, status="approved")` count
- Build `recommendation` and `in_sync` from counts

`_LAST_SYNC_TIMESTAMPS` is updated in the `sync_glossary_to_db` handler on successful non-dry-run sync, and also in the `review_glossary_terms` hook path.

### 5. Test Design

`backend/tests/test_glossary_sync_bridge.py` uses pytest with SQLAlchemy in-memory SQLite (same pattern as existing glossary tests):

- All `GlossarySyncService` tests mock `StorageService.load_glossary` to return fake entries
- DB operations use the test session fixture
- `TranslateStage` tests mock the session scope and `Novel` query

## Migration and Backward Compatibility

- `GlossarySyncService` is a new module — no existing code breaks
- `review_glossary_terms` change: adds `"db_sync"` to the return dict. Callers that don't read this key are unaffected
- `TranslateStage.run()` change: adds a DB query at start of run if `platform_novel_id` is missing. If the DB is unavailable, the `except` branch logs `DEBUG` and continues — same behavior as before but with an attempt
- No DB migration required
- No storage file format change

## Acceptance Criteria

1. A novel with a reviewed `glossary.json` containing 5 approved entries and a DB row can have those entries promoted to `NovelGlossaryEntry` via `sync_from_file`. After sync, `TranslateStage` will receive a non-empty glossary prompt block.
2. Calling `review_glossary_terms` on a novel that exists in the DB triggers a sync automatically; `"db_sync"` key is present in the return value.
3. `TranslateStage` resolves `platform_novel_id` from the DB when it is not in context, and glossary injection fires for that run.
4. `POST /glossary/sync-to-db` with `dry_run=true` returns counts without writing to DB.
5. Syncing 3 entries increments `glossary_revision` exactly once.
6. A `"needs_manual_review"` file entry promotes to a `"candidate"` DB entry; an already-`"approved"` DB entry is not downgraded when the file entry is `"needs_manual_review"`.
7. All 13 tests pass.

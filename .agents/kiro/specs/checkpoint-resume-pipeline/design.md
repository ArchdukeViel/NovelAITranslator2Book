# Design: Checkpoint and Resume Pipeline

## Overview

Add chapter-level state tracking in the database and segment-level checkpoint files on disk. Modify `TranslationService` to write checkpoints at each stage transition and after each segment. Add resume logic that reads checkpoints at job start and skips completed work. Add a translation status endpoint for querying progress.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/db/models/chapter.py` | Update — add `translation_state`, `translation_error` columns |
| Alembic migration | New — add columns to `chapters` table |
| `backend/src/novelai/services/pipeline/translation_service.py` | Refactor — add checkpoint write/read, resume logic, state updates |
| `backend/src/novelai/services/pipeline/checkpoint.py` | New — `CheckpointManager` for file-based checkpoint I/O |
| `backend/src/novelai/api/routers/operations.py` | Update — add `translate-status` endpoint, `force` param, concurrency guard |

### Files Not Touched

- Pipeline stage implementations — no logic changes
- Storage layer — no change (checkpoints use same storage)
- Source adapters — no change
- Provider modules — no change

## Component Design

### 1. `TranslationState` and DB Migration

```python
# novelai/db/models/chapter.py
from enum import Enum

class TranslationState(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    PARSING = "parsing"
    SEGMENTING = "segmenting"
    TRANSLATING = "translating"
    QA = "qa"
    POST_PROCESSING = "post_processing"
    COMPLETE = "complete"
    FAILED = "failed"

# In Chapter model:
class Chapter(Base):
    ...
    translation_state = Column(
        String(32), nullable=False, default=TranslationState.PENDING
    )
    translation_error = Column(String(1024), nullable=True)
```

### 2. `CheckpointManager` (`services/pipeline/checkpoint.py`)

```python
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel

from novelai.services.pipeline.translation_service import TranslationState

CHECKPOINT_MAX_AGE_DAYS = int(os.environ.get("CHECKPOINT_MAX_AGE_DAYS", "7"))


class Checkpoint(BaseModel):
    chapter_id: str
    state: TranslationState
    completed_stages: list[str] = []
    current_stage: str | None = None
    segments_completed: int = 0
    segments_total: int = 0
    last_updated: str = ""
    error: str | None = None


class CheckpointManager:
    def __init__(self, novel_path: Path):
        self.checkpoint_dir = novel_path / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, chapter_id: str) -> Path:
        return self.checkpoint_dir / f"{chapter_id}.json"

    def load(self, chapter_id: str) -> Checkpoint | None:
        path = self._path(chapter_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cp = Checkpoint(**data)
            # Check staleness
            last_updated = datetime.fromisoformat(cp.last_updated)
            age = datetime.now(timezone.utc) - last_updated
            if age > timedelta(days=CHECKPOINT_MAX_AGE_DAYS):
                path.unlink()
                return None
            return cp
        except (json.JSONDecodeError, KeyError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def save(self, checkpoint: Checkpoint) -> None:
        checkpoint.last_updated = datetime.now(timezone.utc).isoformat()
        path = self._path(checkpoint.chapter_id)
        try:
            fd, tmp_name = tempfile.mkstemp(dir=str(self.checkpoint_dir))
            with os.fdopen(fd, "w") as f:
                json.dump(checkpoint.model_dump(), f, ensure_ascii=False)
            os.replace(tmp_name, str(path))
        except OSError:
            # Best-effort: don't block translation on checkpoint failure
            pass

    def delete(self, chapter_id: str) -> None:
        self._path(chapter_id).unlink(missing_ok=True)
```

### 3. TranslationService Resume Logic

```python
async def translate_novel(self, novel_id: str, force: bool = False) -> dict:
    chapters = self._get_chapters(novel_id)

    # Concurrency guard
    if any(c.translation_state not in (
        TranslationState.COMPLETE, TranslationState.FAILED, TranslationState.PENDING
    ) for c in chapters):
        raise OperationError(409, f"Translation already in progress for novel {novel_id}")

    for chapter in chapters:
        if force:
            chapter.translation_state = TranslationState.PENDING
        await self._translate_chapter(chapter)

    ...

async def _translate_chapter(self, chapter: Chapter) -> None:
    if chapter.translation_state == TranslationState.COMPLETE:
        return  # Skip

    if chapter.translation_state == TranslationState.FAILED:
        chapter.translation_state = TranslationState.PENDING  # Reset for retry

    checkpoint_mgr = CheckpointManager(self._novel_path(chapter.novel_id))
    cp = checkpoint_mgr.load(chapter.id)

    if cp:
        start_stage_idx = self._get_stage_index(cp)
        start_segment = cp.segments_completed
    else:
        start_stage_idx = 0
        start_segment = 0
        cp = Checkpoint(
            chapter_id=chapter.id,
            state=TranslationState.PENDING,
            segments_total=self._count_segments(chapter),
        )

    stages = [Fetching, Parsing, Segmenting, Translating, QA, PostProcessing]
    for idx in range(start_stage_idx, len(stages)):
        stage = stages[idx](chapter, start_segment if idx == start_stage_idx else 0)
        try:
            stage.execute()
            cp.completed_stages.append(stage.name)
            cp.current_stage = None
            cp.segments_completed = cp.segments_total  # Stage complete
            checkpoint_mgr.save(cp)
        except Exception as exc:
            cp.state = TranslationState.FAILED
            cp.error = str(exc)[:1024]
            checkpoint_mgr.save(cp)
            raise

    # All stages complete
    cp.state = TranslationState.COMPLETE
    cp.completed_stages.append("translate")
    checkpoint_mgr.save(cp)
    checkpoint_mgr.delete(chapter.id)  # Clean up completed checkpoint
```

### 4. Translation Status Endpoint

```python
@router.get("/{novel_id}/translate-status")
async def get_translate_status(
    novel_id: str,
    db: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
):
    chapters = db.query(Chapter).filter_by(novel_id=novel_id).all()
    total = len(chapters)
    completed = sum(1 for c in chapters if c.translation_state == TranslationState.COMPLETE)
    failed = sum(1 for c in chapters if c.translation_state == TranslationState.FAILED)
    in_progress = sum(1 for c in chapters if c.translation_state not in (
        TranslationState.COMPLETE, TranslationState.FAILED, TranslationState.PENDING
    ))

    if completed == total:
        overall = "complete"
    elif failed > 0 and completed + failed == total:
        overall = "failed"
    elif in_progress > 0:
        overall = "in_progress"
    else:
        overall = "pending"

    return {
        "novel_id": novel_id,
        "total_chapters": total,
        "completed_chapters": completed,
        "failed_chapters": failed,
        "in_progress_chapters": in_progress,
        "overall_state": overall,
    }
```

### 5. Force Translate Parameter

```python
@router.post("/{novel_id}/translate")
async def translate_novel(
    novel_id: str,
    force: bool = Query(False, description="Restart translation from scratch"),
    ...
):
    result = await translation_service.translate_novel(novel_id, force=force)
    return result
```

## Migration and Backward Compatibility

- New columns have defaults (`pending` and `null`), so existing chapters are unaffected.
- If no checkpoint files exist, behavior is identical to current (starts from scratch).
- The `force` parameter defaults to `False`, preserving existing behavior.
- Checkpoint files use the existing storage path structure.

## Acceptance Criteria

1. Translating a novel creates checkpoint files with segment counts.
2. Killing the process mid-translation and re-running resumes from the last checkpoint.
3. Chapters marked `COMPLETE` are skipped on re-run.
4. `GET /{novel_id}/translate-status` returns correct counts by state.
5. Concurrent translation attempts return HTTP 409.
6. `?force=true` restarts all chapters from scratch.
7. Corrupt checkpoint files are treated as `PENDING` (restart chapter).
8. Stale checkpoints (>7 days) are invalidated.

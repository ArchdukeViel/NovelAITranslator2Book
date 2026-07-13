# Requirements: Checkpoint and Resume Pipeline

## Introduction

If a translation job crashes or is interrupted midway (due to API errors, process restart, or network failure), all progress is lost and the job must restart from the beginning. There is no state tracking at the chapter or segment level, no checkpointing between pipeline stages, and no mechanism to skip already-completed work on retry. This wastes provider API quota, increases translation time, and creates a poor operator experience.

This spec adds chapter-level and segment-level progress tracking, checkpoint files that record completed stages, and resume logic that skips already-processed work when a translation job is re-triggered.

## Requirements

### REQ-1: Chapter-Level Translation State

Each chapter must have a trackable translation state.

- REQ-1.1: Define a `TranslationState` enum with values: `PENDING`, `FETCHING`, `PARSING`, `SEGMENTING`, `TRANSLATING`, `QA`, `POST_PROCESSING`, `COMPLETE`, `FAILED`.
- REQ-1.2: Add a `translation_state` column (str, default `PENDING`) to the `chapters` table via Alembic migration.
- REQ-1.3: Add a `translation_error` column (str, nullable) to record the last error message for `FAILED` chapters.
- REQ-1.4: The `TranslationService` must update the chapter's `translation_state` before and after each pipeline stage.
- REQ-1.5: The state transition must be visible via `GET /api/admin/novels/{id}` — include `translation_state` and `translation_error` per chapter.

### REQ-2: Segment-Level Checkpoints

Within a chapter, progress must be tracked at the segment level.

- REQ-2.1: Define a `Checkpoint` model stored as a JSON file: `storage/novel_library/novel/{slug}/checkpoints/{chapter_id}.json`.
- REQ-2.2: The checkpoint must record:
  - `chapter_id`
  - `state: TranslationState`
  - `completed_stages: list[str]` — stages that finished successfully
  - `current_stage: str` — the stage currently in progress
  - `segments_completed: int` — number of segments completed in the current stage
  - `segments_total: int` — total segments in the chapter
  - `last_updated: str` (ISO timestamp)
  - `error: str | null`
- REQ-2.3: The checkpoint must be written after every segment completes (during Translate and QA stages) and after every stage transition.
- REQ-2.4: Checkpoint writes must be atomic (write to temp file, then rename) to prevent corruption.

### REQ-3: Resume Logic

When a translation job is re-triggered, completed work must be skipped.

- REQ-3.1: On `translate_novel` call, the `TranslationService` must iterate over all chapters. For each chapter:
  - If `translation_state == COMPLETE`: skip entirely.
  - If `translation_state == FAILED`: reset to `PENDING` (retry from scratch).
  - If `translation_state` is any other value: resume from the checkpoint.
- REQ-3.2: When resuming from a checkpoint, the service must skip completed segments and continue from `segments_completed + 1`.
- REQ-3.3: If a checkpoint file exists but is corrupt or unreadable, log a `WARNING` and restart the chapter from the beginning.
- REQ-3.4: Resume behavior must be the default. An optional query parameter `?force=true` on the translate endpoint must bypass resume and restart all chapters from scratch.

### REQ-4: Job-Level Progress

Overall translation progress must be queryable.

- REQ-4.1: `GET /api/admin/novels/{id}/translate-status` must return:
  ```json
  {
    "novel_id": "...",
    "total_chapters": 10,
    "completed_chapters": 7,
    "failed_chapters": 1,
    "in_progress_chapters": 2,
    "overall_state": "in_progress",
    "chapters": [
      {"chapter_id": "ch1", "state": "COMPLETE", "segments_done": 15, "segments_total": 15},
      {"chapter_id": "ch2", "state": "TRANSLATING", "segments_done": 8, "segments_total": 15}
    ]
  }
  ```
- REQ-4.2: The status must be computed from the database `translation_state` columns and checkpoint files.

### REQ-5: Fault Tolerance

The checkpoint system must handle edge cases.

- REQ-5.1: If a checkpoint write fails, the translation must continue without blocking. Log the failure at `WARNING` level.
- REQ-5.2: Stale checkpoints (older than 7 days, configurable via `CHECKPOINT_MAX_AGE_DAYS`) must be automatically invalidated and treated as `PENDING` on resume.
- REQ-5.3: Concurrent translation attempts on the same novel must be prevented: if a chapter is `IN_PROGRESS`, a second translate request must return HTTP 409 `"Translation already in progress for novel {id}"`.

## Non-Goals

- This spec does not add distributed worker coordination (single-process only).
- This spec does not add automatic retry on failure (manual re-trigger only).
- This spec does not change how the pipeline stages work internally.
- This spec does not add a UI for viewing checkpoint progress (API-only).

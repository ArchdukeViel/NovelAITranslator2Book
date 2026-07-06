# Design: Chapter Parallelization

## Overview

Add bounded chapter-level concurrency inside backend worker/orchestration code. Use existing scheduler for provider limits. Keep writes chapter-scoped and preserve final ordering by sorting source chapter index at read/export time.

## Architecture

### Affected Areas

| Area | Expected change |
|---|---|
| `backend/src/novelai/services/` | Orchestration submits chapter work with bounded concurrency |
| `backend/src/novelai/worker/` | Worker activity progress supports per-chapter state |
| `backend/src/novelai/translation/` | Existing chunk pipeline remains unchanged |
| `backend/src/novelai/storage/` | Ensure chapter-scoped writes are safe |
| `backend/tests/` | Fake-provider concurrency tests |

## Component Design

### 1. Concurrency Control

Use stdlib `asyncio.Semaphore` if current flow is async; otherwise use `concurrent.futures.ThreadPoolExecutor` with bounded `max_workers`. Do not add a queue dependency.

ponytail: local bounded concurrency only; add distributed queue when single-process worker cannot meet throughput.

### 2. Chapter Task Contract

Each chapter task receives immutable inputs:

- `novel_id`
- `chapter_id`
- source chapter index
- provider/profile settings
- resolved glossary or glossary resolver inputs

Each task returns:

- `chapter_id`
- source chapter index
- status
- output reference
- error envelope if failed

### 3. Failure Model

Use per-chapter result collection. One failed chapter marks job partial/failed according to existing policy, but does not delete other outputs. Retries operate on failed chapter/chunks only.

### 4. Scheduler Interaction

Each chunk still passes through scheduler/provider flow. Scheduler remains source of truth for cooldowns and quotas.

## Acceptance Criteria

1. Configured concurrency >1 runs chapter tasks in parallel under fake provider timing tests.
2. Concurrency 1 matches sequential output.
3. One failed chapter does not remove successful chapter outputs.
4. Activity progress shows per-chapter state.
# Requirements: Chapter Parallelization

## Introduction

Technical audit 5 flags sequential chapter translation. Current architecture already has background activity workers, scheduler/provider rate limits, chunk states, and activity progress. This spec adds configurable chapter-level concurrency without bypassing scheduler, QA, cache, or storage boundaries.

## Requirements

### REQ-1: Configurable Concurrency

Owner translation jobs must support bounded chapter concurrency.

- REQ-1.1: Concurrency must default to current safe sequential behavior unless configured.
- REQ-1.2: Maximum parallel chapters must be configurable through backend settings/profile, not React-only flags.
- REQ-1.3: Concurrency must never exceed provider scheduler rate/quota limits.
- REQ-1.4: Setting concurrency to `1` must preserve existing behavior.

### REQ-2: Order and State Safety

Parallel work must not corrupt output.

- REQ-2.1: Final chapter order must match source chapter order.
- REQ-2.2: Each chapter must write to its own storage key/path through storage service.
- REQ-2.3: Chunk/chapter state updates must be idempotent enough for retries.
- REQ-2.4: One chapter failure must not erase successful outputs from other chapters.

### REQ-3: Scheduler and QA Preservation

Parallelization must not bypass existing pipeline rules.

- REQ-3.1: Every chunk must still use prompt builder, glossary resolution, cache key rules, scheduler/provider selection, QA, and post-processing.
- REQ-3.2: Provider cooldown/daily exhaustion must pause or throttle workers instead of spawning unbounded retries.
- REQ-3.3: Activity progress must expose per-chapter success/failure/running states.

### REQ-4: Tests

Concurrency behavior must have deterministic tests.

- REQ-4.1: Tests must prove multiple chapters can run concurrently with a fake provider.
- REQ-4.2: Tests must prove output order remains stable.
- REQ-4.3: Tests must prove one chapter failure leaves other successful chapter outputs intact.
- REQ-4.4: Tests must prove concurrency `1` matches sequential behavior.

## Non-Goals

- No Celery/RabbitMQ/Kubernetes worker split.
- No frontend scheduler policy.
- No provider-rate-limit bypass.
# Async call-graph and blocking-operation inventory

Run: `pac-8a109a5ad1cd`
Captured: `2026-08-23T18:56:01.456Z` UTC
Source: current working-tree source inspected with CodeGraph and targeted
line-numbered searches. This is an inventory, not a claim that the worker is
safe to resume.

## Call graph observed

```text
ActivityDatabaseBackend.claim_next_activity
  -> ActivityWorkerService.run_claimed_activity
  -> ActivityWorkerService._run_translation_activity
  -> NovelOrchestrationService.translate_chapters
  -> translate_chapters
  -> chapter semaphore / asyncio.gather
  -> _run_chapter
  -> synchronous storage, checkpoint, and SQLAlchemy operations
  -> awaited provider/QA work
  -> synchronous artifact/state/reference operations
  -> activity terminal transaction
```

The required CodeGraph query completed successfully and reported the direct
flow `_run_chapter -> _update_db_translation_state -> session_scope`. The
current implementation has no explicit async-facing persistence port or
bounded executor at this boundary.

## Operation inventory

| Operation / source | Current execution context | Classification | Ownership/risk | Required boundary |
| --- | --- | --- | --- | --- |
| `translate_chapters` chapter task creation and `asyncio.gather` (`translation.py:1209-1214`, `1692`) | Event loop | Async-safe scheduling but task-count unbounded by input size | The chapter semaphore bounds active work, not the number of created tasks | Bounded admission plus bounded task creation/backpressure |
| `_load_cached_chapter` and chapter preflight storage reads (`translation.py:57-65`, `556`, `700`) | Event loop | Synchronous I/O | R2/serialization latency can block every chapter coroutine | `DB_READ_*`/`R2_READ` command through owned bounded I/O boundary |
| Metadata, glossary, media, active-generation and source-state reads (`translation.py:1032`, `1087`, `1147`, `166`, `674`) | Event loop | Synchronous R2/DB/runtime reads | Storage facade may perform exact-key R2 and projection work; returned mutable dicts are not DTOs | Immutable scalar/DTO results from per-operation sessions and owned storage client |
| `_update_db_translation_state`, `_load_db_translation_state`, platform/glossary revision lookups (`translation.py:289-418`) | Event loop | Synchronous SQLAlchemy transaction | `session_scope()` checks out/commits synchronously; repeated novel/chapter lookups multiply pool occupancy | Short `DB_READ_SCALAR`/`DB_WRITE_STATE` operations with session created and closed inside executor |
| Checkpoint manager and runtime checkpoint methods (`translation_resume.py:138-189`, `translation.py:1294`, `1432-1434`, `1593`, `1674`) | Event loop | Synchronous filesystem, JSON serialization, and storage I/O | Runtime files are disposable but can block and must not become canonical content | Bounded `CHECKPOINT_WRITE`/`CHECKPOINT_READ` operation with versioned plain result |
| Translation artifact, lineage, chunk-state, pipeline-event and active-reference writes (`translation.py:1376`, `1528`, `1582-1594`, `1632-1676`) | Event loop | Synchronous R2 plus DB/projection work | Terminal ordering and idempotency are correctness-critical; a partial move could report false completion | Separate non-terminal progress commands from one atomic terminal command |
| `self.translation.translate_chapter` (`translation.py:1463`) | Event loop | Awaited provider/CPU pipeline | Provider wait is asynchronous, but pipeline stages currently call synchronous storage persistence while chunk work overlaps | Provider semaphore remains separate; QA/provider waits never hold DB connections or persistence executor slots |
| Chunk persistence inside translation/QA stages (`translate.py:1409-1410`, `1472-1484`; `translation_qa.py:305`) | Event loop | Synchronous persistence during async chunk workers | Per-chunk writes can multiply transactions and task contention | Coalesced bounded progress queue; terminal results use idempotent command keys |
| Activity worker metadata and state paths (`activity/worker.py:199-220`, `314-319`, `836-840`) | Event loop | Synchronous storage/SQLAlchemy | Worker can block heartbeat-adjacent work and shares process resources with reader only when enabled together | Worker lifecycle operations use short owned DB operations; translation coordinator uses the persistence boundary |
| Activity heartbeat/lease calls (`activity/worker.py`, `activity/database.py`) | Event loop with separate heartbeat task | Bounded async orchestration over synchronous DB operation | Lease renewal is independent but still checks out a synchronous session; lease loss must cancel new work and flush critical commands | Keep independent short transactions and add measured queue/checkout wait |
| `BackgroundActivityRunner` (`activity/runner.py:86-115`) | Event loop | Async-safe polling | Stop cancels the task but has no bounded executor drain/critical-command flush contract | Shutdown policy must stop admission, drain critical commands, and record timeout |
| R2 backend `head`, `load`, `put_immutable`, `delete`, and list-capable maintenance methods (`storage/backends/r2.py:197-464`) | Caller context | Synchronous network; list methods are maintenance-only | Mutable client ownership is implicit; hot paths must never call `LIST` | Exact-key operations through an owned boundary; preserve list only for inventory/GC/cleanup |

## Classification summary

- Async-safe: provider calls that are genuinely awaited, semaphore/event
  coordination, and runner polling.
- Synchronous but bounded: current short activity claim/heartbeat/state
  transactions when isolated; they still need measured checkout/commit time.
- Synchronous and blocking: all direct SQLAlchemy sessions, R2 facade calls,
  runtime checkpoint reads/writes, JSON serialization, and storage-backed
  chunk/event persistence reachable from chapter coroutines.
- CPU-heavy or potentially CPU-heavy: checkpoint serialization/compression,
  QA computation, and translation result assembly; these must not occupy a DB
  connection while waiting for unrelated provider/R2 work.
- Unavailable from static inspection: provider-side quota headroom, hosted
  billed bytes, real event-loop lag, and production pooler attribution.

No session, ORM instance, provider response, raw content, credential, or
connection string was copied into this inventory.

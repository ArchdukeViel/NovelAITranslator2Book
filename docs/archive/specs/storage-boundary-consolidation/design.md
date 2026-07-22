# Design: Storage Boundary Consolidation

## Overview

Consolidate storage by enforcing one access path, not one physical backend. Postgres remains source of truth for queryable records. Private file storage remains source of truth for heavy chapter content. Services and routers use repository/storage abstractions only.

## Architecture

### Affected Areas

| Area | Expected change |
|---|---|
| `backend/src/novelai/storage/` | Add/extend canonical chapter content operations |
| `backend/src/novelai/db/` | Keep metadata records behind repositories/session dependencies |
| `backend/src/novelai/services/` | Replace direct path reads/writes with storage calls |
| `backend/src/novelai/api/` | Remove any raw path response leaks |
| `backend/tests/` | Add storage boundary and path-leak regression tests |

### Files Not Touched

- `storage/novel_library/` runtime data, except test fixtures under temp dirs
- Frontend storage code, because frontend must not access runtime files
- Deployment object-storage config

## Component Design

### 1. Storage Inventory

Use static search for `Path(`, `open(`, `storage/novel_library`, `DATA_DIR`, `raw`, and `translated` references. Classify each result:

- Canonical storage implementation
- Test fixture/helper
- Legacy compatibility loader
- Boundary violation needing replacement

### 2. Chapter Content Gateway

Expose small storage methods only where needed:

- `get_raw_chapter(novel_id, chapter_id)`
- `save_raw_chapter(novel_id, chapter_id, content)`
- `get_translated_chapter(novel_id, chapter_id)`
- `save_translated_chapter(novel_id, chapter_id, content)`
- `list_chapter_content(novel_id)`

ponytail: keep API minimal; add streaming/object-store variants only when deployment needs large remote blobs.

### 3. API Path Leak Guard

Add tests around public and admin chapter endpoints that assert response JSON has no absolute paths and no `storage/novel_library` substrings.

### 4. Migration Compatibility

Prefer read-through compatibility over eager migration. If a legacy path has content, storage service reads it and returns canonical content object. Writes go to canonical layout only.

## Acceptance Criteria

1. Direct runtime path access exists only inside `storage/`, `db/`, migration scripts, and tests.
2. Public/admin APIs never expose raw filesystem paths.
3. Existing legacy chapter content remains readable through storage services.
4. No raw scraped chapters are deleted by translation or migration flows.
# Tasks: Advanced Translation Caching

## Task List

- [x] 1. Create `TranslationCacheService`
  - [x] 1.1 Create `backend/src/novelai/services/cache/translation_cache.py` (REQ-3)
  - [x] 1.2 Implement `make_cache_key` with SHA-256 hashing (REQ-1)
  - [x] 1.3 Implement `CacheEntry` Pydantic model (REQ-2.2)
  - [x] 1.4 Implement sharded file storage (`storage/novel_library/translation_cache/`) (REQ-2.1)
  - [x] 1.5 Implement `get(key)` with TTL expiry (REQ-3.1)
  - [x] 1.6 Implement `set(key, entry)` with atomic write (REQ-3.2)
  - [x] 1.7 Implement `invalidate(novel_id)` (REQ-3.3)
  - [x] 1.8 Implement `stats()` (REQ-3.4)
  - [x] 1.9 Wire env var configuration (`TRANSLATION_CACHE_ENABLED`, `_MAX_ENTRIES`, `_TTL_SECONDS`) (REQ-3.5)

- [x] 2. Integrate cache into pipeline Stage 4
  - [x] 2.1 Update `backend/src/novelai/services/pipeline/stages/translate.py` to check cache before provider call (REQ-4.1)
  - [x] 2.2 On cache hit: skip provider, use cached text, log `cache_hit=True` (REQ-4.2)
  - [x] 2.3 On cache miss: call provider, store result, log `cache_hit=False` (REQ-4.3)
  - [x] 2.4 Respect `TRANSLATION_CACHE_ENABLED=false` bypass (REQ-4.4)
  - [x] 2.5 Handle cache errors gracefully (WARNING log, proceed without cache) (REQ-4.5)

- [x] 3. Add glossary-change invalidation
  - [x] 3.1 Update `GlossaryService` to call `TranslationCacheService.invalidate(novel_id)` after glossary update (REQ-5.1)
  - [x] 3.2 Wrap invalidation in try/except with WARNING log (REQ-5.2)

- [x] 4. Add manual invalidation endpoint
  - [x] 4.1 Add `POST /api/admin/novels/{novel_id}/cache/invalidate` (REQ-5.3)

- [x] 5. Write tests
  - [x] 5.1 Test `make_cache_key` produces deterministic, unique keys
  - [x] 5.2 Test `get` returns entry on cache hit and `None` on miss
  - [x] 5.3 Test TTL expiry causes cache miss
  - [x] 5.4 Test cache bypass when disabled
  - [x] 5.5 Test glossary invalidation triggers cache miss
  - [x] 5.6 Test manual invalidation endpoint

- [x] 6. Verify, lint, and type-check
  - [x] 6.1 Run `pytest backend/tests/ --tb=short -q` and confirm all pass
  - [x] 6.2 Run `ruff check backend/src/novelai/services/cache/` and fix issues
  - [x] 6.3 Run `pyright` and fix type errors

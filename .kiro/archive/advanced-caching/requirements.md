# Requirements: Advanced Translation Caching

## Introduction

The current translation cache operates at the chapter level: if the same novel is retranslated, the entire chapter bundle is reused. However, identical or near-identical segments frequently appear across chapters — repeated character names, common phrases, boilerplate narration, and structural elements. Each retranslation of a segment that has been translated before wastes API calls, increases latency, and incurs provider costs.

This spec adds a segment-level translation cache. Each translated segment is keyed by a hash of its source text plus glossary context. When the translation pipeline processes a new segment, it first checks the cache for an existing result. On cache hit, the API call is skipped. On cache miss, the result is stored for future reuse.

## Requirements

### REQ-1: Cache Key Design

Cache keys must uniquely identify a translatable segment.

- REQ-1.1: Each cache key must be a SHA-256 hash of `source_text + source_language + target_language + glossary_hash`, where `glossary_hash` is a SHA-256 hash of the concatenated glossary terms applied at translation time.
- REQ-1.2: The `glossary_hash` component ensures that cache entries are invalidated when glossary terms change.
- REQ-1.3: The cache key must be representable as a hexadecimal string (64 chars for SHA-256).
- REQ-1.4: A helper function `make_cache_key(source_text, source_lang, target_lang, glossary_hash) -> str` must be exposed.

### REQ-2: Cache Storage

Cache entries must be stored durably and survive process restarts.

- REQ-2.1: Cache entries must be stored as a JSON file (`translation_cache.json`) under `storage/novel_library/translation_cache/`, sharded by the first two characters of the cache key to avoid a single huge directory (e.g. `ab/abcdef...json`).
- REQ-2.2: Each cache entry must contain: `key`, `source_text`, `translated_text`, `source_language`, `target_language`, `glossary_hash`, `provider_key`, `provider_model`, `created_at` (ISO timestamp), `ttl_seconds` (optional, default 0 = no expiry).
- REQ-2.3: The storage module must handle concurrent reads and writes safely via file locking or atomic write patterns.

### REQ-3: Cache Service Interface

A dedicated `TranslationCacheService` must manage all cache operations.

- REQ-3.1: `TranslationCacheService.get(key: str) -> CacheEntry | None` — returns the cached entry if present and not expired.
- REQ-3.2: `TranslationCacheService.set(key: str, entry: CacheEntry) -> None` — stores a cache entry.
- REQ-3.3: `TranslationCacheService.invalidate(novel_id: str) -> int` — invalidates all cache entries associated with a novel when its glossary changes. Returns count of invalidated entries.
- REQ-3.4: `TranslationCacheService.stats() -> dict` — returns cache hit count, miss count, total entries, and total size in bytes.
- REQ-3.5: The service must be configurable via environment variables: `TRANSLATION_CACHE_ENABLED` (default `true`), `TRANSLATION_CACHE_MAX_ENTRIES` (default `100000`), `TRANSLATION_CACHE_TTL_SECONDS` (default `0` = no expiry).

### REQ-4: Integration with Translation Pipeline

The cache must be checked before calling the translation provider and written after a successful translation.

- REQ-4.1: In pipeline Stage 4 (Translate), before calling the provider for each segment, compute the cache key and call `TranslationCacheService.get(key)`.
- REQ-4.2: On cache hit, skip the provider call and use the cached `translated_text` directly. Log at `DEBUG` level with `cache_hit=True`.
- REQ-4.3: On cache miss, proceed with the provider call. After successful translation, call `TranslationCacheService.set(key, entry)`. Log at `DEBUG` level with `cache_hit=False`.
- REQ-4.4: The cache must be optional and bypassable: if `TRANSLATION_CACHE_ENABLED=false`, the pipeline must skip all cache lookups and writes.
- REQ-4.5: Cache failures (read/write errors) must not block translation. Log the failure at `WARNING` level and proceed without cache.

### REQ-5: Cache Invalidation on Glossary Change

When a novel's glossary is updated, relevant cache entries must be invalidated.

- REQ-5.1: The `GlossaryService` must call `TranslationCacheService.invalidate(novel_id)` after any glossary update operation.
- REQ-5.2: Invalidation must be best-effort: if the cache cannot be read or written, log the failure at `WARNING` level and proceed.
- REQ-5.3: A manual invalidation endpoint `POST /api/admin/novels/{novel_id}/cache/invalidate` must be available for owner use.

## Non-Goals

- This spec does not add an in-memory (Redis/Memcached) cache layer. All caching is file-based.
- This spec does not change the segment identification or segmentation algorithm.
- This spec does not add distributed cache invalidation.
- This spec does not change how glossary terms are defined or managed.
- This spec does not add a frontend UI for cache management.

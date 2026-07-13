# Requirements: Public-Path and Storage Projection Hardening

## Introduction

The public catalog endpoint has a two-path strategy: DB-first (fast, paginated SQL) and a storage fallback that fires when no published DB rows exist. The storage fallback path performs a full linear scan — `list_novels()` plus N metadata file reads plus N×M translated chapter reads to find the latest translated chapter. The DB-first path is correct and scalable, but it is only as reliable as the projection data backing it.

Three concrete N+1 hotspots exist: (1) `_latest_translated_chapter()` in `catalog_service.py` and `public.py` iterates all chapters and calls `load_translated_chapter()` per candidate — the DB `latest_chapter_*` projection fields exist but are recomputed from file reads instead of being trusted; (2) the public chapter endpoint unconditionally reads both the translated chapter and the raw chapter on every request, even when raw `source_blocks` are never used; (3) the public slug resolver falls back to iterating all novels when the slug is not a direct storage key.

The broader risk is projection staleness: if the DB projection becomes stale (a translation run completes but `safely_refresh_catalog_projection_after_storage_write` silently failed), the public catalog serves wrong `translated_count`, wrong `latest_chapter_*`, and potentially wrong `is_published` — and there is no operator-visible health indicator.

This spec closes those gaps. It does not change the storage layout, does not change the public API response shapes (except additive fields), and does not introduce a new caching layer.

## Requirements

### REQ-1: Trust Projected `latest_chapter_*` Fields in `recompute_catalog_projection`

The catalog projection recomputation must use the `list_translated_chapters` set and already-known chapter ordering without loading individual translated chapter payloads.

- REQ-1.1: `CatalogService._latest_translated_chapter()` must not call `storage.load_translated_chapter()` for each candidate chapter. It must determine the latest translated chapter ID solely from `storage.list_translated_chapters(novel_id)` (which returns a set of IDs) and the chapter order from `metadata_chapters`.
- REQ-1.2: The method must return the chapter whose position is latest in the metadata chapter list and whose ID is in the translated ID set. It must not verify text content by loading the artifact — the ID being in the translated set is sufficient evidence the chapter is translated.
- REQ-1.3: The `updated_at` field of the latest chapter projection must be sourced from the chapter metadata dict (fields `translated_at`, `updated_at`, or `scraped_at` in that order), not from loading the translated chapter artifact.
- REQ-1.4: The same pattern must be applied to the equivalent helper in `public.py` (`_latest_translated_chapter`) when it is called during projection recompute. For the public API response it already uses the DB projection, so this requirement applies to any code path where `_latest_translated_chapter` is called outside of a DB-backed response.
- REQ-1.5: After this change, `recompute_catalog_projection` must not call `storage.load_translated_chapter()` for any chapter. A test must confirm no such call is made.

### REQ-2: Conditional Raw Chapter Read in Public Chapter Endpoint

The public chapter endpoint must not unconditionally load the raw chapter artifact.

- REQ-2.1: The public chapter endpoint (`GET /api/public/novels/{slug}/chapters/{chapter_id}`) must first determine whether the translated chapter's `paragraph_map` is non-empty (available from the translated artifact) before loading the raw chapter.
- REQ-2.2: If the translated chapter contains a non-empty `paragraph_map`, the raw chapter read must be skipped. The response must be built from the translated artifact alone.
- REQ-2.3: If the translated chapter does not contain a `paragraph_map` (plain-text mode), the raw chapter may be loaded to access `source_blocks` for layout assistance. The raw chapter read remains conditional, not default.
- REQ-2.4: The public response shape must not change. If the raw chapter was previously contributing fields to the response that are now not loaded, those fields must be omitted gracefully (return `null` / empty list, not an error).

### REQ-3: DB Slug Lookup Before Storage Scan in Slug Resolver

The `_resolve_public_novel` slug resolver must query the DB before falling back to the full storage scan.

- REQ-3.1: `_resolve_public_novel(slug, storage)` must first attempt `storage.load_metadata(slug)` (direct key hit). If that succeeds, return immediately (existing behavior, unchanged).
- REQ-3.2: On miss, before scanning `storage.list_novels()`, the resolver must query the DB for a `Novel` row whose `slug` column matches the input slug. If found, return that novel's slug, load its metadata once, and return.
- REQ-3.3: On DB miss, fall back to the existing `storage.list_novels()` scan. This fallback must remain functional.
- REQ-3.4: The DB query in REQ-3.2 must use the existing `db` session. The public chapter endpoint handler must accept and pass a `db` session dependency for this purpose.
- REQ-3.5: The resolver must not expose any `HTTPException` or router-layer logic. It remains a pure data helper returning `tuple[str, dict, str] | None`.

### REQ-4: Projection Staleness Visibility

Stale or missing catalog projections must be visible to the admin without requiring a manual reconciliation run.

- REQ-4.1: A new admin endpoint `GET /novels/catalog-health` must be added to the library router. It must be owner-only.
- REQ-4.2: The endpoint must return a summary with: `total_novels` (count of DB `Novel` rows), `projection_stale_count` (count of rows where `updated_at` is older than a configurable threshold, default 24 hours), `missing_projection_count` (count of storage novels with no DB row), `last_bulk_reconciliation_at` (timestamp of most recent bulk reconcile run, or `null`), `recommendations` (list of string advisory messages when counts are above zero).
- REQ-4.3: `missing_projection_count` must be computed by comparing `storage.list_novels()` against DB `Novel.slug` values. Novels in storage that have no DB row are "missing."
- REQ-4.4: The `recommendations` list must include: `"run_bulk_reconciliation"` when `missing_projection_count > 0`, `"refresh_stale_projections"` when `projection_stale_count > 0`, `"all_projections_healthy"` when both counts are zero.
- REQ-4.5: The endpoint must not trigger any storage writes or projection updates. It is read-only.
- REQ-4.6: The response must not expose internal filesystem paths.

### REQ-5: Projection Refresh Failure Visibility

Silent projection refresh failures must be surfaced to the admin.

- REQ-5.1: `safely_refresh_catalog_projection_after_storage_write` must record the failure in a dedicated in-process counter (a module-level dict keyed by `novel_id`) when it catches an exception. This does not require persistent storage.
- REQ-5.2: A new field `projection_refresh_errors` (list of `{novel_id, error, context, failed_at}` dicts, capped at 50 entries) must be exposed on the existing admin runtime-state or worker status endpoint.
- REQ-5.3: The counter must be cleared for a given `novel_id` when a subsequent projection refresh for that novel succeeds.
- REQ-5.4: The failure counter must not raise exceptions itself; if the counter update fails for any reason, it must be silently ignored.

### REQ-6: Storage Fallback Path — Ensure Published Novels Have Projections

The storage fallback in the public catalog must remain functional but must be flagged as a degraded state.

- REQ-6.1: When `_catalog_from_db_page` returns `None` (no published DB rows), the response from `_catalog_from_storage` must include a `degraded: true` field in the catalog response (additive field, existing clients can ignore).
- REQ-6.2: A warning log entry at `WARNING` level must be emitted every time the storage fallback fires: `"Public catalog using storage fallback — no published DB rows. Run reconciliation to restore DB-backed performance."`.
- REQ-6.3: The storage fallback path must not be removed. It is a reliability backstop for new installations before any novel is published.

### REQ-7: `translated_count` Accuracy in Projection

The `translated_count` projection field must not diverge from the actual count of translated chapter artifacts.

- REQ-7.1: `recompute_catalog_projection` already calls `storage.count_translated_chapters(novel_id)`. This must remain the authoritative source — no SQL-only count may override it unless a future spec explicitly migrates chapter artifact keys to DB.
- REQ-7.2: An admin endpoint `GET /novels/{novel_id}/catalog-projection-health` must be added (owner-only) that returns: `db_translated_count` (from `Novel.translated_count`), `storage_translated_count` (from `storage.count_translated_chapters`), `in_sync: bool`, `last_refreshed_at` (from `Novel.updated_at`), and `recommended_action` (`"refresh"` when `in_sync=False`, `"healthy"` otherwise).
- REQ-7.3: The endpoint must be read-only. It must not trigger a refresh.

### REQ-8: Tests

- REQ-8.1: A new test file `tests/test_catalog_projection_performance.py` must contain tests for the N+1 fixes.
- REQ-8.2: `test_recompute_projection_does_not_load_chapter_artifacts` — mock `storage.load_translated_chapter` and assert it is never called during `recompute_catalog_projection`.
- REQ-8.3: `test_latest_chapter_determined_from_id_set_only` — assert `_latest_translated_chapter` returns the correct chapter using only the translated ID set and metadata chapter order.
- REQ-8.4: `test_public_chapter_skips_raw_read_when_paragraph_map_present` — mock `storage.load_chapter` and assert it is not called when the translated artifact has a non-empty `paragraph_map`.
- REQ-8.5: `test_public_chapter_loads_raw_when_paragraph_map_absent` — assert raw chapter is loaded when `paragraph_map` is absent or empty.
- REQ-8.6: `test_slug_resolver_uses_db_before_storage_scan` — mock `storage.list_novels` and assert it is not called when the DB slug match succeeds.
- REQ-8.7: `test_slug_resolver_falls_back_to_storage_scan_on_db_miss` — assert storage scan is used when DB has no matching slug.
- REQ-8.8: `test_catalog_health_endpoint_returns_correct_counts` — assert `missing_projection_count` and `projection_stale_count` are computed correctly.
- REQ-8.9: `test_projection_refresh_failure_is_recorded` — assert the in-process counter captures a failure and clears on subsequent success.
- REQ-8.10: `test_storage_fallback_emits_degraded_flag` — assert the `degraded` field is `true` in the storage fallback response.

## Non-Goals

- This spec does not add HTTP-layer response caching (Redis, CDN headers, etc.).
- This spec does not move chapter artifact storage to a DB-backed blob or object store.
- This spec does not change the public API response shapes in a breaking way.
- This spec does not add a search index or full-text search capability.
- This spec does not paginate the admin library listing (that is a separate UX concern).

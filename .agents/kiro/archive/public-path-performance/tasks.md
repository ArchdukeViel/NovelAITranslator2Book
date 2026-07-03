# Tasks: Public-Path and Storage Projection Hardening

## Task List

- [x] 1. Remove N+1 from `CatalogService._latest_translated_chapter`
  - [x] 1.1 Rewrite `CatalogService._latest_translated_chapter` in `backend/src/novelai/services/catalog_service.py` to use only `storage.list_translated_chapters()` and the chapter metadata list — no call to `storage.load_translated_chapter()` (REQ-1.1, REQ-1.2)
  - [x] 1.2 Source `updated_at` from chapter metadata dict fields (`translated_at`, `updated_at`, `scraped_at`) in priority order (REQ-1.3)
  - [x] 1.3 Verify `recompute_catalog_projection` makes no call to `storage.load_translated_chapter` after the change (REQ-1.5)

- [x] 2. Remove N+1 from `_latest_translated_chapter` in `public.py`
  - [x] 2.1 Apply the same rewrite to `_latest_translated_chapter` in `backend/src/novelai/api/routers/public.py` — use ID set + metadata chapter order, no artifact load (REQ-1.4)

- [x] 3. Make raw chapter read conditional in public chapter endpoint
  - [x] 3.1 In the public chapter route handler in `public.py`, read `paragraph_map` from the translated artifact before deciding whether to load the raw chapter (REQ-2.1, REQ-2.2)
  - [x] 3.2 Skip `storage.load_chapter()` when `paragraph_map` is a non-empty list; load it only when `paragraph_map` is absent or empty (REQ-2.3)
  - [x] 3.3 Confirm the response shape and `_public_reader_blocks` behavior are unchanged when `raw_chapter = {}` (REQ-2.4)

- [x] 4. Add DB slug lookup to `_resolve_public_novel`
  - [x] 4.1 Add optional `db: Session | None = None` parameter to `_resolve_public_novel` in `public.py` (REQ-3.1, REQ-3.5)
  - [x] 4.2 After the direct storage key hit attempt, add a DB slug query: `db.query(Novel).filter_by(slug=slug).one_or_none()` when `db` is provided (REQ-3.2)
  - [x] 4.3 Fall through to existing storage scan when both direct hit and DB query miss (REQ-3.3)
  - [x] 4.4 Pass `db` from the public chapter endpoint handler into `_resolve_public_novel`; add `db: Session = Depends(get_db_session)` to the handler signature (REQ-3.4)

- [x] 5. Add projection refresh failure counter to `catalog_service.py`
  - [x] 5.1 Add `_PROJECTION_REFRESH_FAILURES: deque[dict]` module-level deque (maxlen=50) to `catalog_service.py` (REQ-5.1)
  - [x] 5.2 Add `_record_projection_refresh_failure(novel_id, error, context)` non-raising helper (REQ-5.1)
  - [x] 5.3 Add `_clear_projection_refresh_failure(novel_id)` helper (REQ-5.3)
  - [x] 5.4 Add `get_projection_refresh_failures() -> list[dict]` public function (REQ-5.2)
  - [x] 5.5 Update `safely_refresh_catalog_projection_after_storage_write`: call `_record_projection_refresh_failure` in the except branch and `_clear_projection_refresh_failure` on success (REQ-5.1, REQ-5.3)
  - [x] 5.6 Confirm the counter update is silent on its own failure (REQ-5.4)

- [x] 6. Add `degraded` flag to public catalog storage fallback
  - [x] 6.1 Add `degraded: bool = False` field to `PublicCatalogResponse` in `public.py` (REQ-6.1)
  - [x] 6.2 Set `degraded=True` in `_catalog_from_storage` return value (REQ-6.1)
  - [x] 6.3 Emit `WARNING` level log in `catalog()` handler when `db_response is None` before calling `_catalog_from_storage` (REQ-6.2)

- [x] 7. Add `GET /catalog-health` admin endpoint
  - [x] 7.1 Define `CatalogHealthResponse` Pydantic model with `total_novels`, `projection_stale_count`, `missing_projection_count`, `last_bulk_reconciliation_at`, `recommendations`, `projection_refresh_errors` fields (REQ-4.1, REQ-4.2)
  - [x] 7.2 Add module-level `_last_bulk_reconciliation_at: str | None = None` variable to `library.py`; update it when a non-dry-run bulk reconciliation completes (REQ-4.2)
  - [x] 7.3 Implement `GET /catalog-health` endpoint (owner-only): count total DB novels, stale novels (updated_at < 24h ago), missing projections (storage IDs not in DB slugs), build recommendations list, include failure counter from `get_projection_refresh_failures()` (REQ-4.1–REQ-4.6)
  - [x] 7.4 Confirm endpoint is read-only — no storage writes (REQ-4.5)

- [x] 8. Add `GET /{novel_id}/catalog-projection-health` admin endpoint
  - [x] 8.1 Define `NovelProjectionHealthResponse` Pydantic model (REQ-7.2)
  - [x] 8.2 Implement endpoint: load `Novel` row, call `storage.count_translated_chapters`, compare, return `in_sync`, `recommended_action` (REQ-7.2, REQ-7.3)
  - [x] 8.3 Return HTTP 404 when the novel is not found in the DB

- [x] 9. Write tests
  - [x] 9.1 Create `backend/tests/test_catalog_projection_performance.py`
  - [x] 9.2 Write `test_recompute_projection_does_not_load_chapter_artifacts` (REQ-8.2)
  - [x] 9.3 Write `test_latest_chapter_determined_from_id_set_only` and `test_latest_chapter_empty_when_no_translated_ids` (REQ-8.3)
  - [x] 9.4 Write `test_public_chapter_skips_raw_read_when_paragraph_map_present` (REQ-8.4)
  - [x] 9.5 Write `test_public_chapter_loads_raw_when_paragraph_map_absent` (REQ-8.5)
  - [x] 9.6 Write `test_slug_resolver_uses_db_before_storage_scan` (REQ-8.6)
  - [x] 9.7 Write `test_slug_resolver_falls_back_to_storage_scan_on_db_miss` (REQ-8.7)
  - [x] 9.8 Write `test_catalog_health_counts_missing_projections`, `test_catalog_health_counts_stale_projections`, `test_catalog_health_recommendations_all_healthy` (REQ-8.8)
  - [x] 9.9 Write `test_projection_refresh_failure_recorded_and_cleared` (REQ-8.9)
  - [x] 9.10 Write `test_storage_fallback_degraded_flag` (REQ-8.10)
  - [x] 9.11 Run `pytest backend/tests/test_catalog_projection_performance.py --tb=short -q` and confirm all pass
  - [x] 9.12 Run `ruff check backend/src/novelai/services/catalog_service.py backend/src/novelai/api/routers/public.py backend/src/novelai/api/routers/library.py` and fix issues
  - [x] 9.13 Run `pyright backend/src/novelai/services/catalog_service.py backend/src/novelai/api/routers/public.py` and fix type errors

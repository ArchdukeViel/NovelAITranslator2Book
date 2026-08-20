# Performance Audit: Public Read and Translation Stack

**Initial audit:** 2026-08-19
**Phase 0 update:** 2026-08-20
**Phase 2 update:** 2026-08-20
**Phase 3 update:** 2026-08-20
**Phase 4 update:** 2026-08-20
**Baseline revision before Phase 6:** `0f9c82b` (`docs(perf): record phase five worker evidence`)
**Scope:** browser-to-Caddy traffic, the public reader API, database access, object storage, Redis/queues, translation workers/providers, and the public Next.js client.

## Executive conclusion

The initial runtime was behind the checkout and allowed public storage waterfalls. Phase 0 rebuilt and deployed the current checkout locally; Phase 1 made the public catalog/detail metadata path projection-first; Phase 2 now server-hydrates the guest home view and bounds public browser reads. The current local runtime is healthy with the base Compose configuration, but the live serving projection still needs storage-backed chapter reconciliation. The largest remaining risks are:

1. The original runtime was older than the checkout; the local Phase 0 deployment now uses freshly built local images, but those tags do not carry an immutable source revision.
2. Live projection repair is storage-latency-bound: the bounded reconciliation attempt exceeded 180 seconds, and the current live database still has zero chapter projection rows. Public chapter metadata therefore returns a truthful unavailable response until maintenance succeeds.
3. Caddy repeatedly attempted stale backend container addresses during container replacement, producing connection-refused errors and making availability look like latency.
4. The home SSR boundary now hydrates the catalog and weekly ranking, but its local server response was about 2.6 seconds and production-scale TTFB/LCP/INP remain unmeasured. The browser no longer makes duplicate initial catalog/ranking/genre requests.
5. Phase 3 now uses one joined ranking/projection query, composite analytics indexes, and a bounded process-local success cache. Focused tests prove distinct-viewer periods, chapter exclusion, bounded SQL work, and cache metrics; production-volume query plans, seeded latency, and cross-replica cache behavior remain unmeasured.
6. Phase 4 now makes readiness cacheable/single-flight, removes the mutating storage probe from public readiness, adds bounded origin projection caching, and queues analytics writes off the request path. The local one-second probe configuration now passes without an override; populated analytics load and cross-replica cache behavior remain unmeasured.
7. Translation work can occupy a web request for up to the configured 120-second timeout. Provider calls also use blocking SDK calls in worker threads, bounded concurrency, retries, and quota reservation, so provider latency can create sustained backpressure.
8. Phase 6 now has a repeatable local fixture and measured public/browser sample. Catalog, detail, chapter, and search p95 values were still above the proposed warm budgets in this small local run. Direct-mode owner enqueue exposed an aggregate database-session capacity failure; recognized capacity failures are now classified as sanitized retryable responses, transaction mode avoided them in an isolated control, and controlled storage delay produced visible bounded degradation. Production object-storage telemetry and provider-capacity evidence remain unmeasured, so no runtime sign-off is claimed.

The remaining release/operations problems are chapter-projection completeness, production-scale browser/ranking budgets, and multi-instance cache economics. Phase 4 source and Compose defaults now make public readiness cheap and cached, preserve a full owner diagnostic path, cache only safe public projections, and apply explicit bounded analytics loss semantics. The live local stack passed the base Compose readiness check without a temporary override.

## Evidence and confidence rules

This document separates three kinds of evidence:

- **Measured runtime:** the initial baseline was observed against the local Compose stack on 2026-08-19 with image revision `8c8c109c...`; the Phase 0 rerun was observed against freshly built `:local` images on 2026-08-20.
- **Current-source trace:** control flow read from the checkout. It describes what the current source can do after it is built and deployed; it does not claim that the old runtime contains those changes.
- **Design risk:** a likely scaling or latency problem that needs a benchmark before a production threshold is assigned.

No secret, complete credential, private host, bucket name, IP address, process identifier, or raw storage key is included in this report.

## Measured runtime snapshot

| Probe | Observation | What it means |
| --- | --- | --- |
| Public liveness through the local proxy | `200` in about `8 ms` | The proxy and process can answer a cheap liveness check. This does not prove database, storage, or route readiness. |
| Public readiness through the local proxy | `503` in about `1.6 s` | The stack is not ready. The response reported unhealthy storage while database, worker, disk, and storage-usage checks were healthy. |
| Public rankings through the local proxy | `404` in about `7 ms` | The old running reader image does not contain the current ranking route. This is deployment drift, not a ranking-query latency result. |
| Public catalog through the local proxy | timed out at about `6 s` with no response | The request was not merely a slow browser render; it did not complete at the proxy timeout. |
| Direct catalog call inside the reader container | timed out after about `35 s` | The reader itself was blocked, independently of Caddy. |
| Direct reader health and API calls during the catalog load | each timed out at about `6 s` | The reader workers were saturated or blocked by the catalog work. |
| Reader container health state | reported healthy while recent health checks exceeded their timeout | The health state was stale relative to observed responsiveness. |
| One observed storage-backed catalog load | serial chapter-object reads for one 148-chapter novel took roughly 10 seconds for the observed portion | The storage path performs a request-time object waterfall that can monopolize a reader worker. |
| Runtime analytics | disabled; live analytics table had zero rows | No live ranking performance can be inferred from production-like data in this environment. |
| Runtime database migration | database at `d7e4f9a1c2b3`; latest contributor migration not applied | The deployed database is behind the current source contract. |
| Migration attempt | failed because the database role lacked permission to create tables in the application schema | This is an operational readiness blocker, not something to hide behind a longer timeout. |
| Redis | `PING` succeeded; no RQ queue keys were observed; rejected connections were zero | Redis was not the measured bottleneck in this sample. This does not validate worker throughput under load. |

The proxy request was made with the configured site host. Requests sent with an unrelated loopback `Host` header returned a fast, empty frontend response, so browser and synthetic checks must use the configured host or an explicit host override.

## Phase 0 execution update — 2026-08-20

Phase 0 was executed against the local Compose environment and is **complete as the local baseline**. The Phase 1 and Phase 2 execution updates below record the subsequent public-read changes and browser request-graph work.

| Gate | Result | Evidence |
| --- | --- | --- |
| Current application build | Passed | Backend, reader, and frontend images built from the checkout. The frontend build generated 49 routes. |
| Migration | Passed | The migration runner exited successfully and the database reports `a8c4e2f7b901` as the current head. |
| Current route deployment | Passed | `/api/public/rankings?period=weekly&limit=10` returned `200` in about `43 ms`; the catalog page of 10 returned `200` in about `254 ms`. |
| Application containers | Passed | Backend, reader, and frontend reported healthy after recreation using the base Compose file. |
| Caddy replacement behavior | Improved but not signed off | After recreation, no matching recent connection-refused/upstream errors were observed. Caddy remains unhealthy because its readiness check receives `503`. |
| Liveness | Passed | `/health/live` returned `200` in about `9 ms` through Caddy. |
| Readiness | Failed | `/health/ready` returned `503` in about `1.5 s`; the public body reports storage unhealthy. |
| Storage probe diagnosis | Failed at readiness budget, not at storage correctness | Ten isolated `StorageService.probe()` calls all returned true in roughly `486–640 ms`. The actual concurrent `HealthService._run_probes()` run returned `storage: Probe timed out` at `1,000 ms`, while storage-usage work took about `1,559 ms`. |
| Development overlay | Failed for production-style startup | The development bind mount replaced the frontend standalone bundle, causing `node /app/frontend/server.js` to fail. The base Compose file was used for the valid current-image verification. |

The final local baseline rerun used an explicit `HEALTH_PROBE_TIMEOUT_MS=2000` process override because `deploy/.env` explicitly contains the old one-second value and was intentionally not edited. With that override, Caddy became healthy; readiness returned `200` in about `1.29 s`, liveness returned `200` in about `7 ms`, rankings returned `200` in about `25 ms`, and the ten-item catalog returned `200` in about `425 ms`. This proves the immediate Phase 0 failure is the readiness timeout budget, not an unavailable storage backend.

The current local deployment therefore proves that the migration and current public routes can run, and that the catalog path is fast for the present nine-novel dataset. It does not prove production-scale catalog behavior. A durable deployment/configuration change is still required so a restart does not revert to the one-second readiness failure.

## Phase 1 execution update — 2026-08-20

Phase 1 implementation is complete in the checkout and the focused backend acceptance suite passes. Phase 2 was subsequently executed; the current Phase 2 review gate is recorded below.

| Area | Result | Evidence |
| --- | --- | --- |
| Public catalog source | Passed in source/tests | `public_catalog.py` now uses the published `Novel` projection only, with no request-time `list_novels()`, metadata scan, chapter count, or storage fallback. Missing projection returns an empty `degraded=true` response. |
| Catalog count work | Passed in source/tests | The page query uses one window count instead of the previous existence count plus total count sequence. Page size remains bounded by the existing API limit. |
| Public slug projection | Passed | Migration `b7c1e2d3f4a5` adds `Novel.public_slug`; projection writes derive the canonical title slug, and DB-only detail/read-context lookup accepts source or canonical public slug. |
| Chapter metadata projection | Passed in source/tests | Migration `b7c1e2d3f4a5` adds section fields to `Chapter`; write/reconciliation paths persist ordering, titles, section metadata, and translation availability. Public chapter-list and reader metadata use DB rows. |
| Public content reads | Passed in source/tests | Chapter text/version/raw-layout reads remain storage-backed only after the DB read context succeeds; adjacency and availability no longer call `list_translated_chapters()` on public reads. |
| Focused backend validation | Passed | `tools/pytest.ps1 backend/tests/test_catalog_projection_performance.py backend/tests/test_public_router.py -q`: `147 passed`; `tools/pyright.ps1`: `0 errors`; targeted Ruff: passed. |
| Compose migration | Passed | The Compose migration runner applied `a8c4e2f7b901 → b7c1e2d3f4a5`; the Compose `current` check reports `b7c1e2d3f4a5 (head)`. |
| Live service health | Passed with carried override | Backend, reader, frontend, and Caddy are healthy; liveness `200` in about `17 ms`, readiness `200` in about `1,006 ms`, using `HEALTH_PROBE_TIMEOUT_MS=2000`. |
| Live public routes | Partially passed | Catalog `200` in about `2,434 ms`, weekly rankings `200` in about `21 ms`, canonical-slug detail `200` in about `228 ms`. The catalog completed without a storage fallback. |
| Live projection repair | Incomplete, truthful | Live DB counts are 9 novels, 2 published rows, 0 chapter rows, 0 published chapter rows, 0 published placeholders, and 2 published public-slug rows. Two bounded storage-backed reconciliation attempts exceeded 180 seconds; no chapter identities were fabricated. Chapter-list requests return `404` until the maintenance path can read and persist canonical metadata. |
| Docker image cleanup | Scoped | Current `novelai-admin:local`, `novelai-reader:local`, and `novelai-frontend:local` images were rebuilt. Superseded explicitly tagged application/test images were removed; base Caddy/Redis/Postgres dependencies were retained. |

### Phase 1 findings and resolutions

### F-21 — P0 — Public catalog storage fallback removed; projection freshness is now an explicit serving dependency

**Evidence:** The normal catalog route no longer calls `_catalog_from_storage`. The no-projection regression test asserts an empty `degraded=true` result and fails if `list_novels()` is called. The live catalog returned `200` without a storage scan for the current dataset.

**Impact:** Public catalog latency is bounded by the database page query, but stale or missing projection data is visible as unavailable content instead of silently repaired during a user request. That is the intended honest tradeoff; reconciliation must be reliable and observable.

**Recommendation:** Keep storage enumeration in maintenance/reconciliation only. Add scheduled retry/alerting for failed projection repair, and expose projection age/failure counts to operators before Phase 6 sign-off.

**Confidence:** Source, focused tests, and live route measured.

### F-22 — P0 — Chapter projection was empty for published live rows

**Evidence:** Before and after Phase 1 live checks found 0 `Chapter` rows for 2 published novels whose `Novel.chapter_count` values indicate content exists. The bounded reconciliation attempts timed out while reading configured object storage. The public chapter-list route returned `404`, not a fabricated list.

**Impact:** Novel detail summaries and catalog cards can be served, but chapter navigation cannot be truthfully served for underfed rows. Publishing or readiness policy must prevent a novel from appearing fully readable until its chapter projection is complete, or the UI must show the unavailable state explicitly.

**Recommendation:** Run reconciliation with an operator-capable storage path and bounded per-novel retries. Add a projection-completeness gate to publication/readiness and alert when `Novel.chapter_count > count(Chapter)` for a published row.

**Confidence:** Live database counts, live route response, and timed maintenance commands.

### F-23 — P1 — Canonical public slugs must be persisted, not recomputed from request-time storage metadata

**Evidence:** The DB-only summary already emitted title-derived slugs, while detail routes previously resolved them through storage metadata. Phase 1 adds `Novel.public_slug`, writes it during projection reconciliation, and the live canonical-slug detail route returned `200` after a DB-only public-slug repair.

**Impact:** Without this projection field, homepage links could point to a canonical slug that the DB-only detail route could not resolve after storage fallback removal.

**Recommendation:** Keep `public_slug` as a projection field, reject ambiguous duplicate slugs safely, and rebuild it whenever display-title metadata changes.

**Confidence:** Source, migration, focused test, and live route measured.

### F-24 — P1 — Projection reconciliation can exceed the maintenance time budget

**Evidence:** The bulk reconciliation command and a published-row-only reconciliation command each exceeded the 180-second command timeout while using the configured object-storage backend. No partial result was reported, and the live chapter projection remained empty.

**Impact:** Removing public fallback makes a failed reconciliation visible rather than catastrophic to reader workers, but it also means release/readiness must not claim full public-read readiness while projection repair is incomplete.

**Recommendation:** Instrument each storage operation and per-novel reconciliation phase, use resumable checkpoints, and run maintenance from the operator role/path that has reliable object-storage latency. Do not increase public request timeouts to mask this maintenance problem.

**Confidence:** Measured live maintenance behavior.

## Phase 2 execution update - 2026-08-20

Phase 2 implementation is complete in the checkout and the browser/frontend acceptance checks pass. The phase was **stopped for review before Phase 3**; Phase 3 was subsequently executed and is recorded below.

| Area | Result | Evidence |
| --- | --- | --- |
| Guest home hydration | Passed in source/build/live HTML | `frontend/app/(public)/home/layout.tsx` prefetches only the catalog page of 24 and the weekly ranking, then hydrates the existing client queries. The production build marks `/home` dynamic and succeeded. |
| Initial catalog volume | Passed | `HOME_CATALOG_PARAMS.page_size` is 24 instead of the previous 100; additional catalog pages remain a client navigation concern. |
| Ranking request graph | Passed in source/browser trace | The home ranking tab defaults to weekly, the weekly Trending query is disabled while the selected tab is weekly, and the browser request trace showed no initial `/api/public/catalog` or `/api/public/rankings` request because both were server-hydrated. |
| Non-critical data | Passed in source/browser trace | Genre data is no longer requested by the home page; auth/history are enabled through deferred personalization after the catalog settles. The trace showed only the deferred `/api/auth/me` request and no initial genre request. |
| Public cancellation | Passed in tests/source | `publicFetch` uses a shared 10-second timeout, preserves React Query signals, and exposes separate caller-cancelled and timeout error reasons. Catalog, ranking, novel, chapter-list, and chapter hooks pass the query signal and disable unbounded retries. |
| Frontend validation | Passed | Targeted Phase 2 tests: `21 passed`; full frontend suite: `857 passed` in `219.66s`; `npm run lint`, `npm run typecheck`, and `npm run build` passed. |
| Live SSR route | Passed with measured caveat | Rebuilt `novelai-frontend:local`; `GET /home` returned `200` in about `2,604 ms`, with a `61,501`-byte HTML response containing the live title `That Time I Got Reincarnated as a World Tree`, `unique_novel_views`, and `analytics_disabled`. |
| Browser performance sample | Partial, honest | One Playwright sample reported navigation response end about `363 ms`, DOMContentLoaded about `411 ms`, load about `910 ms`, 54 resources, and about `3.23 MB` transfer. LCP and INP were not exposed by the available buffered entries; this is not a production p95. |
| Runtime topology | Passed after correction | The first SSR probe used admin port 8000 and returned 404 for public routes; adding `READER_API_URL=http://reader:8001` corrected the boundary. All five Compose services remained healthy after recreation. |

### Phase 2 findings and resolutions

### F-25 - P1 - Server prefetch must target the reader service boundary

**Evidence:** The first live server-prefetch attempt used `BACKEND_API_URL=http://backend:8000`; both public catalog and ranking requests returned `404` because public routes are served by the reader service. The corrected `READER_API_URL=http://reader:8001` returned catalog `200` with 2 live novels and ranking `200` with the truthful `analytics_disabled` response.

**Impact:** A server-rendered home can silently fall back to client loading if its internal service boundary is wrong, restoring the request waterfall while the build remains green.

**Recommendation:** Keep `READER_API_URL` explicit in Compose and align `BACKEND_API_HOST` with the backend/reader allowed-host contract. Add an SSR smoke check to deployment validation.

**Confidence:** Measured live behavior and corrected source/configuration.

### F-26 - P1 - SSR removes browser waterfalls but does not yet prove end-to-end latency budget

**Evidence:** The browser received useful catalog HTML and made no initial public catalog/ranking/genre requests, but a PowerShell request to `/home` took about `2.6 s` on the current local stack. The browser timing sample had response end about `363 ms` after navigation, while LCP and INP were unavailable from the available entries.

**Impact:** Server hydration improves time to useful content and request fan-out, but it can move backend latency into TTFB. Without repeated cold/warm samples and real LCP/INP, no production budget claim is justified.

**Recommendation:** Measure cold/warm TTFB, LCP, INP, transfer size, and API timings across representative catalog volume before Phase 6 sign-off. Keep the server prefetch timeout bounded and continue to allow honest client fallback when the reader is unavailable.

**Confidence:** One live runtime sample and one browser trace; insufficient for p95 capacity claims.

## Phase 3 execution update - 2026-08-20

Phase 3 implementation is complete in the checkout and the ranking/metrics
acceptance checks pass. The phase is **stopped for review before Phase 4**.

| Area | Result | Evidence |
| --- | --- | --- |
| Distinct-view aggregation | Passed in source and tests | One `CASE` identity expression counts authenticated user ids and signed anonymous viewer digests. The query is limited to `public_novel.view`, excludes chapter events, filters published projection rows, and preserves daily/weekly/monthly windows. |
| Ranking indexes | Applied locally | Migration `c8d2e4f6a1b3` adds `ix_analytics_events_rank_event_time_novel_user` and `ix_analytics_events_rank_event_time_novel_session`; both names are present in the live PostgreSQL database. Production-volume `EXPLAIN (ANALYZE, BUFFERS)` remains open. |
| Enrichment fan-out | Passed in source and tests | Ranking joins the published `Novel` projection and uses bounded taxonomy `selectinload` queries. It no longer calls `get_public_novel_summary` once per result and performs no object-storage summary fallback. |
| Result cache | Passed in source and tests | A bounded process-local TTL/LRU cache keys on period, public projection schema/update version, and limit. It caches successful non-empty responses only; the default is 60 seconds and 64 entries. |
| Cache observability | Passed | `/metrics` exposes `novelai_public_ranking_cache_hits_total`, `novelai_public_ranking_cache_misses_total`, and `novelai_public_ranking_cache_entries`. |
| Focused validation | Passed | Ranking, metrics, public-router, and catalog-projection suites passed with `157 passed`; targeted Ruff and Pyright passed. |
| Live deployment | Passed with honest limitation | Rebuilt backend/reader images were migrated to `c8d2e4f6a1b3`, recreated healthy, and served the weekly ranking through Caddy in about `606 ms`. Analytics is disabled and empty, so the response was `available=false`, `reason=analytics_disabled`, with zero items; no populated ranking latency claim is made. |

### Phase 3 findings and resolutions

### F-27 - P1 - Ranking production plan and cardinality evidence remain open

**Evidence:** SQLite-backed tests prove period boundaries, duplicate-viewer
deduplication, chapter exclusion, index creation, and a small query count. The
live deployment has analytics disabled and no retained events, so it cannot
exercise the PostgreSQL plan at representative event volume.

**Impact:** The implementation removes the known query and enrichment
waterfalls, but a large raw-event table may still outgrow an online aggregation
before a rollup is warranted.

**Recommendation:** Seed an isolated representative event set and record
`EXPLAIN (ANALYZE, BUFFERS)`, p50/p95/p99 latency, pool wait, and distinct-viewer
cardinality for all three periods. Add a durable rollup/reconciliation path if
the measured raw-event plan misses the ranking budget.

**Confidence:** Current-source and focused-test corroborated; production
capacity is unmeasured.

### F-28 - P1 - Ranking cache is process-local and not shared across replicas

**Evidence:** `PublicRankingCache` is a bounded in-process TTL/LRU cache. Its
key includes the public projection schema/version and latest published-row
update timestamp, and it never caches disabled or empty responses. Separate
reader workers therefore have separate hit ratios and may briefly compute the
same successful result.

**Impact:** The cache bounds repeated work within one process but does not
provide cross-instance hit sharing or immediate invalidation across workers.

**Recommendation:** Measure the current topology first. If multiple reader
replicas make ranking origin work material, move the same versioned success-only
contract to Redis or an equivalent shared cache with explicit TTL and
invalidation behavior. Do not cache disabled/no-data responses as fabricated
popularity.

**Confidence:** Current-source corroborated; multi-replica impact is unmeasured.

## Phase 4 execution update - 2026-08-20

Phase 4 implementation is complete in the checkout and local Compose validation
passed. The phase was stopped for review before Phase 5.

| Area | Result | Evidence |
| --- | --- | --- |
| Readiness cache | Passed in source/tests | `HealthService` now uses the configured `HEALTH_CACHE_TTL_SECONDS` (default 5 seconds), deep-copies cached public-safe results, and single-flights concurrent refreshes. Admin diagnostics remain fresh and uncached. |
| Readiness storage work | Passed in source/tests | Public readiness uses a non-mutating backend reachability probe and no longer runs S3/storage-usage work. Full write/read/delete verification and storage-usage checks remain in owner diagnostics. Liveness remains process-only. |
| Public projection cache | Passed in source/tests | Catalog base pages, DB-backed novel summaries, and bounded chapter metadata use a process-local TTL/LRU cache with a 30-second default TTL and 256-entry bound. Keys include the database/projection version where applicable; catalog publication/reconciliation and takedown review invalidate the cache. User identity, progress, raw query text, and analytics cookies are excluded. |
| Analytics ingestion | Passed in source/tests | Public/server events now enqueue sanitized fields to a bounded asynchronous writer (default queue size 1,000). Queue-full events are counted as dropped; worker database failures are counted and suppressed. Shutdown drains briefly. No raw IP, prompt, authorization header, or unsanitized metadata crosses the queue boundary. |
| Focused backend validation | Passed | `tools/pytest.ps1` changed-path suites passed with `209 passed`; storage/backend, microservice split, health, analytics, and cache suites passed with `161 passed`. Ruff and Pyright passed. |
| Live readiness without override | Passed | Fresh backend/reader images were rebuilt and recreated without `HEALTH_PROBE_TIMEOUT_MS=2000`. With `Host: localhost`, Caddy readiness returned `200` in `0.559 s` cold and `0.046 s` warm; the public response contained only database, storage, worker, and disk statuses and no `storage_usage` check. |
| Live public routes | Passed with honest limitation | Through Caddy with the configured host, weekly rankings returned `200` in `0.072 s` with the existing `analytics_disabled` state; catalog returned `200` in `0.490 s` cold and `0.222 s` warm. No populated ranking latency claim is made. |
| Metrics and images | Passed | Direct backend `/metrics` exposed readiness-cache, projection-cache, and analytics-writer metrics. Current app image tags are `novelai-admin:local` (`dd80e37c1202`), `novelai-reader:local` (`fdf702bc9be4`), and the existing `novelai-frontend:local` (`d4c87ff798c9`); no older tagged Novel AI app images were retained. |

### Phase 4 findings and resolutions

### F-29 - P1 - Readiness probe amplification is resolved locally; percentile evidence remains open

**Evidence:** Public readiness now has a short process-local TTL and one in-flight
refresh, uses a non-mutating storage reachability probe, and excludes the
expensive S3 usage scan. The live one-second configuration passed without the
previous two-second process override. The two measured Caddy samples were
`0.559 s` cold and `0.046 s` warm.

**Impact:** Reverse-proxy health checks no longer create a storage object on
every readiness request or repeat the full storage-usage scan. A delayed
storage provider can still make the cached result unhealthy until the next
refresh, which is visible and bounded rather than hidden.

**Remaining work:** Measure p50/p95/p99 readiness under concurrent storage delay,
container replacement, and multi-process deployment. Keep the full diagnostic
probe scheduled/owner-only and alert on sustained unhealthy results.

**Confidence:** Source, focused tests, fresh images, and live no-override route.

### F-30 - P1 - Safe public projections are cached per process, not shared

**Evidence:** Catalog pages, novel summaries, and chapter metadata now use the
bounded `PublicProjectionCache`; ranking uses the existing bounded ranking
cache. Cache values are copied, disabled/empty catalog results are not stored,
and publication/reconciliation/takedown paths invalidate the projection cache.
The reader process does not expose the admin `/metrics` route, so populated
reader-side cache ratios still need a direct operator telemetry path.

**Impact:** Warm reads avoid repeated projection assembly and chapter metadata
queries within one process, but separate reader workers can duplicate origin
work and the current local analytics-disabled dataset cannot measure a useful
ranking hit ratio.

**Remaining work:** Run a populated multi-reader benchmark and decide whether
Redis/shared origin caching is justified. Preserve versioned keys and explicit
invalidation if that migration is made.

**Confidence:** Source and focused tests; live route behavior is measured but
not a populated cache-ratio benchmark.

### F-31 - P1 - Analytics writes no longer share the public request session

**Evidence:** The public ingestion route no longer depends on `get_db_session`.
It sanitizes metadata before enqueue, returns `recorded` for accepted queue
items and `dropped` for queue-full/worker-unavailable admission, and the
worker owns a fresh transaction. Server-side novel/chapter events use the same
bounded writer. Writer lifecycle is wired into monolith, admin, and reader
lifespans.

**Impact:** Analytics database latency or failure no longer holds the public
detail/chapter request open. Events can be intentionally lost under sustained
backpressure; the drop counter and queue depth make that policy observable.

**Remaining work:** Measure enqueue overhead and event loss under a deliberately
slow database, then tune queue size and worker count from evidence. Do not turn
the queue into an unbounded memory buffer.

**Confidence:** Source and focused tests; slow-writer live load remains open.

### F-32 - Resolved - Public reader availability coverage now seeds the projection

**Evidence:** The fixture now creates the published `Novel`/`Chapter`
projection through `CatalogService`, and translation helpers reconcile the
projected availability state. `backend/tests/test_public_reader_availability.py`
passes all `22` tests. The existing per-novel policy contract is also preserved
in the DB projection by migration `e5f7a9c1d3b2`.

**Impact:** Chapter-policy, owner-preview, version, and availability-list
regressions now execute against the same projection-first contract as the
public reader. Request-time storage fallback was not restored.

**Confidence:** Focused test output, catalog regression tests, migration
upgrade/downgrade smoke, and current Phase 1 source contract.

## Phase 5 execution update - 2026-08-20

Phase 5 implementation and focused local validation are complete in the
checkout. Work is stopped for review before Phase 6. This phase resolves the
request-path and file-control-plane findings F-12 through F-15 in source and
tests; runtime percentile/load evidence remains an explicit limitation.

| Area | Result | Evidence |
| --- | --- | --- |
| Translation enqueue | Passed in source/tests | `POST /api/admin/{novel_id}/translate` now creates a durable translation activity and returns `202` with `activity_id`/`pending`; optional `Idempotency-Key` and deterministic non-secret fallback prevent duplicate active work. |
| Worker isolation | Passed in source/Compose | Added the dedicated `worker` service running `novelaibook worker`; web services keep `JOB_WORKER_ENABLED=false`, and the public reader has no activity-runner lifespan. |
| Activity control plane | Passed in source/tests | Added `activity_records`, migration `d9f3a1b7c5e2`, row-locked claims, lease recovery, idempotency uniqueness, bounded metadata/retry history, and queue timing/age metrics. Two queue instances passed the no-double-claim test. |
| Provider bounds | Passed in source/tests | Owner/contributor Gemini admission has separate in-flight limits plus RPM/TPM/RPD budgets; provider deadlines, bounded retry backoff, reusable credential-isolated clients, sanitized usage timing, and runtime metrics are implemented. |
| Translation cache maintenance | Passed in source/tests | SQLite WAL metadata sidecar indexes entries for invalidation, statistics, and LRU eviction. Only initialization backfill scans JSON files; request-path maintenance does not recurse through the directory. |
| Focused validation | Passed | `tools/ruff.ps1 check .`, `tools/pyright.ps1`, the prior affected set (`63 passed`), the expanded Phase 5 set (`102 passed`), activity/router/health coverage (`69 passed`), and focused frontend coverage (`40 passed` across 5 files) all passed. |
| Frontend release checks | Passed with full-suite limitation | `npm run lint`, `npm run typecheck`, and `npm run build` passed. The full `npm run test` command timed out after about `243 s`; the focused route/ranking/admin Vitest set passed. |
| Migration and Compose | Passed locally | Targeted SQLite upgrade/downgrade passed; the real local PostgreSQL migration profile applied `d9f3a1b7c5e2`. Fresh admin/reader/frontend images built, the production Compose stack was recreated, and backend, reader, frontend, Redis, Caddy, and worker were healthy/running. |
| Route and Markdown audit | Passed | No active `/contribute`, `/request-novel`, or singular `/novel/...` references remain. Current request route, historical notes, truthful All Time exclusions, and `TableOfContentsV2` source identifier are intentional. |
| Runtime gate | Open | The full backend command timed out after `904 s`; the availability contract now passes `22` focused tests. Enqueue p95 under concurrent public probes and production-like provider failure/load evidence remain unmeasured. |

### Phase 5 finding resolutions

F-12 is resolved locally: translation no longer waits inside the owner web
request, and the worker receives the activity id as both `job_id` and
`activity_id`. F-13 is resolved locally for admission and retry policy: global
provider/credential reservations, deadlines, bounded backoff, and timing
metrics are present; real provider-volume capacity is not claimed. F-14 is
resolved locally: the database owns activity state and leases, with a one-time
legacy queue import. F-15 is resolved locally: indexed cache metadata replaces
recursive maintenance scans; the one-time backfill is visible in cache stats.

F-32 is resolved locally. Its reader fixture now creates the published
`Novel`/`Chapter` projection, and the per-novel unavailable policy is projected
into `Novel.public_reader_unavailable_policy` by migration `e5f7a9c1d3b2`.
The fixture passes without restoring request-time storage fallback.

## Phase 6 execution update - 2026-08-20

The initial Phase 6 run was executed against an isolated local Compose overlay
and stopped for review with the runtime gate open. A continuation run then
tested transaction-mode connection mitigation and controlled delayed storage.
The source and acceptance harness are repeatable, but the combined evidence
does not claim production-scale capacity or complete the provider/storage fault
matrix. Temporary overlays, fixture rows, and volumes are removed after each
run; the base Compose topology is restored.

### Fixture and HTTP workload

`backend/tests/run_phase6_acceptance.py` seeds and removes only the
`phase6-load-` namespace. The run used 48 published novels, 1,428 projected
chapters (one novel with 300 chapters and 47 novels with 24 chapters each),
and 1,200 privacy-safe `public_novel.view` events across authenticated and
anonymous viewer identities. Storage used an isolated filesystem volume for
the run so the existing object-storage data was not touched. Each route had
20 measured samples at concurrency 8 after a per-route warmup request.

| Route | p50 | p95 | p99 | Result |
| --- | ---: | ---: | ---: | --- |
| `/health/live` | 6.220 ms | 293.287 ms | 293.595 ms | 20/20 `200` |
| `/health/ready` | 24.444 ms | 55.197 ms | 55.519 ms | 20/20 `200` |
| `/api/public/catalog` | 1,099.367 ms | 1,951.122 ms | 2,071.137 ms | 20/20 `200` |
| public novel detail | 1,541.714 ms | 1,829.161 ms | 2,007.659 ms | 20/20 `200` |
| public chapter | 2,312.717 ms | 3,053.049 ms | 3,801.925 ms | 20/20 `200` |
| public search | 1,970.445 ms | 2,660.428 ms | 2,765.409 ms | 20/20 `200` |
| daily ranking | 117.895 ms | 292.914 ms | 322.484 ms | 20/20 `200` |
| weekly ranking | 125.517 ms | 355.838 ms | 367.510 ms | 20/20 `200` |
| monthly ranking | 149.160 ms | 298.064 ms | 343.298 ms | 20/20 `200` |
| `/home` | 259.181 ms | 659.779 ms | 668.904 ms | 20/20 `200` |

All measured routes had zero client timeouts and zero transport errors. A
temporary local owner session was generated entirely inside the backend
container, refreshed through the CSRF endpoint, and never printed or persisted
as test output. An eight-request concurrent enqueue attempt through Caddy
returned two `202`, four expected translation rate-limit `429` responses, and
two `500` responses. The two `500` responses were database connection-capacity
failures while checking for an active translation, not provider responses. The
translation limiter is five requests per 60 seconds per client in this local
configuration. After restarting only the temporary backend process to clear
that in-memory limiter, a lower-concurrency control returned `3/3` `202`
responses at concurrency 3, with p50 `1,008.526 ms` and maximum
`1,210.110 ms`. A follow-up transaction-mode overlay control sent the same
owner burst at concurrency 8 and returned five `202` responses and three
configured translation-limit `429` responses, with no database-capacity `500`
responses; p50 was `3,139.887 ms` and the maximum was `3,196.577 ms`. A
five-sample public workload at concurrency 8 through the corrected internal
proxy `Host` header returned `200` for every route with zero timeouts and
transport errors. A disposable public `role=user` browser session also loaded
`/account/contributions` with `200` and was removed after the check.

### Proxy, database, queue, and provider evidence

- Caddy remained healthy during the initial public run. Recent logs contained
  zero `502` responses, zero connection-refused events, and zero `5xx`
  responses. The delayed-storage control intentionally made Caddy's readiness
  check unhealthy without causing a container restart loop; the base stack was
  restored and healthy afterward.
- Backend `/metrics` was available only on the internal admin boundary;
  public `/metrics` correctly returned `404` through Caddy. The backend sample
  recorded readiness cache hits/misses and no provider calls because no owner
  translation was submitted. Reader-process cache counters therefore cannot be
  inferred from this endpoint.
- PostgreSQL reported 22 active connections, pool size 5, no pool overflow
  (`overflow=-5` means the pool was below its configured ceiling), and zero
  checked-out connections at the sample point. The broad PostgreSQL
  `waiting_connections` value included non-checkout wait events, so it is not
  reported as pool checkout wait. `pg_stat_statements` query statistics were
  unavailable in this local profile; slowest-query and query-count evidence
  remain open. During the direct-mode owner burst, the managed session pool
  rejected a connection because its aggregate client cap was reached. This
  produced the two API `500` responses above. A transaction-mode overlay using
  the same database and workload avoided those `500`s, but the protected base
  runtime configuration remains `DB_CONNECTION_MODE=direct` and was not
  changed.
- After that run, recognized SQLAlchemy DBAPI pool/server-capacity failures
  were classified as sanitized retryable responses. The rebuilt admin and
  reader images were exercised in a direct-mode filesystem control: an
  eight-request authenticated enqueue burst returned five `202` and three
  configured translation-limit `429` responses, with zero capacity `500`s.
  Unrelated database errors remain generic `500` responses. Deployment-wide
  pooler budget verification is still open.
- A later safe database snapshot reported `max_connections=60`,
  `superuser_reserved_connections=3`, `active_connections=19`, and
  `application_connections=13`; `pg_stat_statements` is not installed in this
  profile. Compose still has three long-running SQLAlchemy pool processes
  (backend, reader, worker), each configured for a theoretical ten connections,
  while the current budget is `20`. The production validator currently checks
  only the two web pools, so worker/migration/operator reserve is a documented
  review item rather than an enforced aggregate invariant.
- Redis remained healthy, but the public workload created no queue keys and
  did not materially exercise the translation worker. Worker CPU was idle in
  this guest-only sample, so queue depth/job age/provider throughput are not
  capacity evidence.
- A namespaced durable activity with a deliberately missing provider
  configuration failed truthfully with `status=failed`,
  `provider_error_code=provider_configuration_error`, and `retry_count=1`.
  The six accepted owner-enqueue activities in the combined diagnostic and
  control samples reached the same expected provider-configuration failure
  path with `retry_count=1`. No provider key, prompt, authorization header, or
  response secret was used.
- The controlled storage-delay run used an in-memory S3-protocol stub with a
  1.2-second response delay and no production credentials or bucket. Ten
  concurrent `/health/ready` requests returned `503` with
  `storage=unhealthy`; p50 was `1,351.488 ms`, p95 `1,382.913 ms`, and maximum
  `1,541.684 ms`. This proves bounded, visible degradation behavior only;
  production R2/S3 call count, operation latency, bytes, and fallback count
  remain unmeasured.

### Browser evidence and hydration correction

Playwright verified the guest `/home`, `/ranking?period=weekly`, seeded novel
detail, and seeded chapter routes. The measured navigation/LCP/CLS samples
were:

| Page | Navigation end | LCP | INP sample | CLS | Resources / transfer |
| --- | ---: | ---: | ---: | ---: | --- |
| `/home` | 1,388 ms | 2,012 ms | 80-88 ms tab click | 0 | 61 / 3,243,473 bytes |
| `/ranking?period=weekly` | 169 ms | 196 ms | 80-88 ms tab click | 0 | 58 / 45,990 bytes |
| novel detail | 174 ms | 1,288 ms | not exercised | 0 | 67 / 86,610 bytes |
| chapter reader | 165 ms | 740 ms | not exercised | 0 | 27 / 16,552 bytes |

The first browser run found React hydration error `#418` on `/home`. Source
review identified `Date.now()` in relative-time and freshness rendering. The
home page now uses a hydration-aware cached client timestamp via
`useSyncExternalStore`; the initial server/client markup is deterministic.
The rebuilt frontend has zero application console errors on all four checked
routes, and the focused home suite passes 29 tests. The deprecated
performance-entry warnings were emitted by the measurement script, not by the
application.

### Phase 6 gate status and remaining work

The fixture, route, proxy-health, seeded-analytics, provider-failure,
guest/authenticated-browser, hydration, focused frontend, controlled
storage-delay, and classified-capacity-response gates pass for this local
sample. The protected base runtime still needs an operator-approved
connection-mode/budget change and production pooler verification. The Phase 6
runtime gate remains open because production object-storage telemetry,
PostgreSQL query-plan statistics, and representative multi-worker/provider
capacity evidence are still missing. The earlier full-suite timeouts remain
open; the former F-32 projection-fixture failures were repaired in the current
continuation and are no longer counted as current failures.

### F-33 - P1 - Home clock-dependent labels caused a hydration mismatch

**Evidence:** The first Phase 6 browser check reported React error `#418`.
`frontend/app/(public)/home/page.tsx` used `Date.now()` during the initial
render for relative timestamps and `New` badges.

**Resolution:** The home page now supplies a stable server snapshot and a
cached client timestamp through `useSyncExternalStore`. Lint, typecheck,
focused home tests, production build, and the post-rebuild browser check pass
with zero application console errors.

**Confidence:** Source review, focused tests, production build, and browser
verification.

### F-34 - P1 - Aggregate database session capacity can turn enqueue bursts into 500s

**Evidence:** An owner-authenticated eight-request translation enqueue burst
through Caddy returned two `202`, four translation rate-limit `429` responses,
and two `500` responses. Backend logs classified the `500` responses as
database `OperationalError` failures caused by the managed session pool
reaching its aggregate client cap while `find_active_translation` acquired a
connection. After restarting only the temporary backend process, a concurrency
3 control returned `3/3` `202` responses with p50 `1,008.526 ms` and maximum
`1,210.110 ms`. The configured application limiter remained visible as four
`429` responses in the burst; the provider-failure path separately produced
durable failed activities with one retry.

**Impact:** A short owner burst can produce server errors before the activity
queue absorbs the work. The current local sample does not establish a safe
aggregate concurrency budget across backend, reader, worker, and managed
database-pooler sessions.

**Recommendation:** Set and verify one aggregate connection budget across all
Compose services and managed-pooler modes, reserve capacity for readiness and
operator traffic, and add a burst test that asserts no database-capacity `500`
responses. If capacity is exhausted, keep returning a classified retryable
response and preserve the enqueue/worker boundary rather than exposing an
unhandled database exception. The local application classification is now in
place; deployment-wide budget verification remains open.

**Confidence:** Direct local runtime logs and repeated control run; the
production pooler limit and multi-instance budget remain unverified.

## Public request waterfalls

### Home page

The home route now has a server layout that prefetches the two guest-visible datasets and hydrates the client page. A guest home load is now:

```text
server home layout
  ├─ catalog: 24 newest novels (reader service)
  └─ ranking: weekly, limit 5 (reader service)
       ↓ hydrate existing client queries
browser after useful content is available
  └─ deferred auth/session
       └─ authenticated users: history after auth is known
```

React Query still revalidates hydrated data after its bounded stale window. The home page sorts the 24-item catalog and computes genre counts in the browser, while the shared search overlay remains responsible for its own debounced catalog/tag requests when opened. This reduces initial data volume and fan-out without inventing catalog or ranking data when the reader service is unavailable.

### Ranking page and widget

`frontend/app/(public)/ranking/ranking-client.tsx` requests up to 50 rows for the selected period. The home page starts on weekly so its ranking widget and Trending state share the hydrated weekly query; after a user selects another tab, the selected period and weekly widget can be active together. The ranking API is cacheable for 60 seconds at the HTTP layer and now has a bounded success-only process-local result cache. The superseded pre-Phase 3 ranking response was:

```text
two distinct-viewer aggregation queries
  → published-novel lookup
  → up to limit public-summary calls
       → database projection or object-storage fallback
```

The current cold ranking response is:

```text
projection-version check
  -> one distinct-viewer aggregation joined to published projection rows
       -> bounded taxonomy selectinload queries
            -> success-only cache write
```

A cache hit still performs the projection-version check so publish, takedown,
or projection updates naturally move the request to a new key. The cache is
process-local, and disabled/no-data responses remain uncached and explicit.

### Novel detail and chapter list

`frontend/app/(public)/novels/[slug]/page.tsx` requests the novel summary, chapter list, taxonomy, and authenticated progress. The detail handler records an analytics event and deliberately uses private caching for a newly issued anonymous identity. The chapter-list handler resolves the published DB projection, checks takedown state, and maps cached chapter metadata; it does not enumerate object storage. Chapter text/version/raw-layout reads remain storage-backed only after the projection succeeds.

### Chapter reader

The reader page requests a translated chapter, public auth, and progress state. The current chapter handler can resolve metadata, load a translated object, list available versions, load a raw fallback, list translated chapters again, and optionally query glossary annotations. Authenticated readers also create history/progress mutations. These operations are reasonable individually, but they are not a single bounded read and should be measured as a complete request waterfall.

### Translation

The owner translation operation in `services/orchestration/operations.py` waits for `orchestrator.translate_chapters` inside the web request with `WEB_REQUEST_TIMEOUT_SECONDS` (observed runtime value: 120 seconds). The worker path also runs translation activities. Each activity can launch up to `TRANSLATION_CONCURRENCY` provider calls (observed value: 4), retry failed chunks up to the configured attempts, write generated artifacts, update activity state, and record contributor usage. If web and worker execution are enabled together, the same host can spend resources on both request handling and long-running translation work.

## Findings

### F-01 — P0 — The deployed revision is behind the current contract

**Evidence:** The initial Compose inspection identified the running backend, reader, and frontend images as revision `8c8c109c...`; the checkout was `8048306`. The live ranking route returned `404`, and the database was behind the latest contributor migration. Phase 0 rebuilt the three application images locally, applied the migration, and the current ranking route now returns `200`; the local `:local` tags do not themselves prove an immutable source revision.

**Impact:** A performance test against the live URL can report behavior that no longer exists in source. It also prevents the contributor and ranking contracts from being exercised and makes route-health conclusions misleading.

**Recommendation:** For release deployments, replace mutable local tags with immutable image digests or embedded source-revision labels. Record image revision, migration revision, and route inventory as part of every performance run. The local Phase 0 migration/current-route portion is complete.

**Confidence:** Measured.

### F-02 — P0 — Caddy can retain stale backend addresses during container replacement

**Evidence:** The initial run showed repeated connection-refused attempts to old backend container addresses while backend containers were replaced, and Caddy had a large failing streak. After the Phase 0/1 base-Compose recreation, no matching recent connection-refused/upstream errors were observed and Caddy is healthy when the explicit two-second health-probe override is present. A fresh restart with the protected one-second runtime value can still regress.

**Impact:** Requests fail as `502` or wait through connection retries. This is an availability failure that users experience as a slow page or an intermittent API, and it can obscure the application bottleneck behind proxy errors.

**Recommendation:** Validate service-discovery behavior on restart and replacement, reload Caddy after upstream changes when required by the chosen deployment topology, and add a restart/replace acceptance test. Do not treat a healthy container process as proof that the proxy has a live upstream.

**Confidence:** Measured; the post-recreation absence of errors is a single local sample, not a restart acceptance test.

### F-03 — P0 — Storage-backed catalog loads can block every reader worker

**Evidence:** A direct catalog request exceeded 35 seconds. Reader health and API calls also timed out during the load. Logs showed serial object reads for a 148-chapter novel, followed by metadata and key-list operations. The reader had multiple server workers, so a small number of concurrent catalog requests can consume all of them.

**Impact:** Home, search, and any endpoint that depends on catalog availability become unavailable or slow. Low CPU with high elapsed time indicates I/O blocking rather than insufficient JavaScript or CPU capacity.

**Recommendation:** Keep the Phase 1 projection-only public path. The request-time fallback has been removed locally; complete and monitor asynchronous projection reconciliation before declaring the public catalog fully ready at production scale.

**Confidence:** Measured and current-source corroborated.

### F-04 — P0 — The catalog fallback is O(n) storage work plus database work per novel

**Evidence:** The initial source and runtime path looped over `storage.list_novels()`, checked database eligibility per item, loaded metadata, resolved taxonomy, built summaries, sorted the complete list, and sliced afterward. Phase 1 removed `_catalog_from_storage` from the public route and added no-fallback regression coverage.

**Impact:** Latency grows with the catalog, object count, and metadata size even when the caller asks for a small page. The fallback also creates an N+1 database/object-storage pattern and has no reliable upper bound for a public request.

**Recommendation:** Treat the projection as a required serving index. Reconcile it asynchronously from storage, expose the implemented truthful degraded state while it is stale, and keep the regression test that asserts catalog requests do not invoke `list_novels()` or per-item storage summary calls.

**Confidence:** Current-source corroborated; runtime behavior observed.

### F-05 — P1 — The database catalog path performs unnecessary count work

**Evidence:** The initial source called `query.count()` to test whether rows exist and then called `query.count()` again for the total before selecting the page. Phase 1 replaced this with a page query carrying one window count and a bounded projection-existence check only when the page is empty. The default home request still asks for 100 rows.

**Impact:** A page request can perform two count queries in addition to the page query. Exact counts become increasingly expensive as filters and joins grow, and the oversized default page increases serialization, transfer, and browser work.

**Recommendation:** Retain the single-window-count implementation and add query-plan/latency evidence at realistic catalog volume. Set a smaller home page size and paginate or stream additional items in Phase 2.

**Confidence:** Initial source corroborated; Phase 1 resolution verified by source and focused tests.

### F-06 — P1 — Home has client-side request fan-out and no initial-data hydration

**Evidence:** `HomePage` starts catalog, selected ranking, weekly ranking, genre, and auth queries. `frontend/lib/query-client.tsx` sets a 20-second stale time but there is no public-page server prefetch or `HydrationBoundary` path. The home page requests 100 catalog items and sorts/counts them in the browser.

**Impact:** Time to useful content is bounded by the slowest API dependency, particularly catalog. A cold visitor pays the full network round trip before React Query can display data; a slow ranking or auth request can also keep dependent UI in loading states.

**Recommendation:** Render an initial public shell and first catalog projection from the server or a route-level prefetch, then hydrate client queries for interactivity. Share the weekly ranking request between the widget and the selected tab, fetch only the active tab, reduce the initial catalog page, and defer non-critical taxonomy/auth/history work.

**Confidence:** Current-source corroborated.

### F-07 — P1 — Public query hooks do not forward cancellation signals or enforce client timeouts

**Evidence:** `publicFetch` has no request timeout. The catalog and ranking API methods accept an `AbortSignal`, but `use-catalog.ts` and `use-rankings.ts` do not pass React Query's signal into those methods. The novel/chapter hooks have the same pattern.

**Impact:** Navigating away does not reliably cancel a slow reader/storage request. Stale requests can continue consuming reader workers and sockets after the user has left the page, worsening saturation during an outage.

**Recommendation:** Thread `signal` through every public query function and add an explicit timeout using `AbortSignal.timeout` or the project HTTP abstraction. Distinguish cancellation from server errors in UI state and add a test that unmounting a query aborts the request.

**Confidence:** Current-source corroborated; saturation mechanism is inferred.

### F-08 — P1 — Novel detail and chapter-list reads are origin-bound and storage-heavy

**Evidence:** The initial source used storage metadata and translated-key enumeration for detail/chapter metadata. Phase 1 now resolves detail, review existence, chapter lists, and reader adjacency from the DB projection; chapter content/version/raw-layout objects remain storage-backed after the read context succeeds. Detail still sets private/no-store for a newly issued anonymous identity and records an event.

**Impact:** First views cannot be absorbed by a shared cache, and each visitor can cause origin database/storage work. The design is privacy-preserving, but it makes origin efficiency and object-call count critical.

**Recommendation:** Keep the Phase 1 projection boundary and complete reconciliation before publishing underfed rows. Separate identity issuance and analytics ingestion from the critical content read where possible, then measure object calls and bytes per content request in Phase 4/6.

**Confidence:** Current-source corroborated.

### F-09 — P1 — Ranking aggregation is not aligned with the live indexes

**Phase 3 status:** Resolved locally; production-volume plan and cardinality evidence remain open.

**Evidence:** Before Phase 3, `PublicRankingService` ran separate authenticated and anonymous distinct-viewer aggregations, merged them in Python, and enriched results with up to `limit` catalog summaries. Phase 3 now uses one `CASE`-based distinct-viewer aggregation joined to published projection rows, and migration `c8d2e4f6a1b3` adds composite indexes for authenticated and anonymous identity fields.

**Impact:** The known query and summary/storage fan-out is removed locally, but the raw-event aggregation still needs representative PostgreSQL volume evidence before a rollup table is justified. Current analytics is disabled and empty, so production ranking capacity is not visible in the current runtime.

**Recommendation:** Run seeded PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` and p50/p95/p99 measurements for all three windows. Prefer a rollup table or scheduled hourly/daily aggregates once event volume warrants it. Keep the current disabled/no-data contract and measure the bounded success-only cache across the deployed reader topology.

**Confidence:** Current-source and live query-plan corroborated.

### F-10 — P1 — Readiness performed a storage write/read/delete probe without an effective cache

**Phase 4 status:** Resolved locally for public readiness; the full diagnostic
probe remains intentionally available to owner health and scheduled checks.

**Updated evidence:** Phase 4 wires `HEALTH_CACHE_TTL_SECONDS` into a
single-flight readiness cache, uses a non-mutating backend reachability probe
for public readiness, and moves `StorageService.probe()` plus S3
storage-usage work to owner diagnostics. Fresh images passed the protected
one-second probe configuration: Caddy readiness returned `200` in
`0.559 s` cold and `0.046 s` warm, with only database, storage, worker,
and disk in the public checks.

**Historical evidence:** Before Phase 4, `HealthService` contained unused
cache fields and `StorageService.probe()` ran a random write/read/delete
object check. During Phase 0, ten isolated probes all returned true in roughly
`486–640 ms`, but the concurrent health run timed storage out at its
`1,000 ms` per-probe limit while storage-usage work took about `1,559 ms`;
the readiness endpoint returned `503`. The two-second override was the
temporary pre-Phase-4 workaround.


**Impact:** A transient object-store delay can make readiness fail and can also consume storage operations on every probe. Proxy health checks then amplify the issue. A slow provider or storage service can cause deploy/restart churn.

**Recommendation:** Retain the short cache and cheap probe, measure percentile behavior under delayed storage and multi-process replacement, and alert on sustained unhealthy cached results. Preserve the 3-second total budget and keep internal timestamps/metrics redacted. Do not move the full write/read/delete probe back onto the public readiness path.

**Confidence:** Measured and current-source corroborated.

### F-11 — P1 — Database pool capacity is per process, while web and worker processes are multiplied

**Evidence:** The configured Postgres pool is size 5 with max overflow 5 and a 30-second pool timeout. Backend and reader containers were observed with multiple server processes. Each process creates its own engine/pool; contributor usage, analytics, health, and catalog work can all request connections.

**Impact:** Aggregate database connections can exceed the budget calculated from one process. Under concurrent catalog/ranking/analytics traffic, requests may wait for a pool slot even while each individual process appears correctly configured.

**Recommendation:** Budget connections as `processes × (pool size + overflow)` across backend, reader, worker, migrations, and operator jobs. Set an explicit deployment-wide maximum, measure pool checkout wait time, and reduce unnecessary per-request sessions such as synchronous analytics writes.

**Confidence:** Current-source/runtime topology corroborated; exact aggregate connection count requires deployment configuration.

### F-12 — P1 — Translation is still a synchronous web-request operation

**Evidence:** `services/orchestration/operations.py` wraps `translate_chapters` in `asyncio.wait_for` using the 120-second web request timeout. Translation is also run by the activity worker. The current architecture therefore has both a long-running request path and a background path.

**Impact:** A few large translations can occupy web workers for minutes, compete with public reads, hold locks, and cause client/proxy timeouts. A web timeout does not necessarily stop work already handed to a provider or storage layer.

**Recommendation:** Change the public/owner operation to enqueue and return an activity identifier, with polling or streaming progress. Keep long work in a separately scaled worker deployment and enforce cancellation/lease semantics. The acceptance test should prove that a translation request returns quickly while public liveness and catalog latency remain within budget.

**Confidence:** Current-source corroborated.

### F-13 — P1 — Provider retries and bounded concurrency can create sustained backpressure

**Evidence:** `TranslateStage` uses a semaphore with runtime concurrency 4 and gathers chunk workers. `GeminiProvider` executes a blocking provider SDK call in a thread, reserves quota, records usage, and retries classified failures. The stage can retry chunks and the QA policy can cause another translation pass when configured to block.

**Impact:** Provider latency is multiplied by chunk count and retries. Concurrent activities or processes can exceed provider quotas even when each activity respects its own semaphore. Thread-pool occupancy and usage-ledger writes add local contention.

**Recommendation:** Make concurrency and retry budgets global per provider/credential, reserve capacity before scheduling a chunk, use exponential backoff with a bounded deadline, and expose queue wait/provider wait separately. Test invalid-key and quota failures as fast state transitions rather than repeated long retries.

**Confidence:** Current-source corroborated; production magnitude requires provider telemetry.

### F-14 — P1 — Activity state is a serialized full-file control plane

**Evidence:** `ActivityQueueService` stores activity state in one JSON file. Create, claim, heartbeat, update, and list operations acquire locks, load/parse the complete file, and rewrite the complete file. The background runner polls every two seconds by default.

**Impact:** Progress updates and concurrent workers serialize on file I/O. Work grows with activity history, and a slow filesystem operation delays claims and heartbeats. This can make a healthy provider look like a queue stall.

**Recommendation:** Move durable activity state to the application database or a properly bounded Redis/job store, retaining a migration/audit path. Until then, cap history reads, reduce heartbeat write frequency, instrument lock wait and rewrite duration, and ensure only one execution model owns a given queue.

**Confidence:** Current-source corroborated.

### F-15 — P1 — The translation cache performs directory-wide scans during maintenance operations

**Evidence:** `TranslationCacheService` uses file-per-entry JSON. Invalidation, statistics, and eviction scan the cache directory recursively, open entries, stat files, or sort all files by modification time.

**Impact:** Cache maintenance latency grows with cache size and competes with translation reads/writes on the same local disk. On Windows or a network-mounted volume, metadata operations can be especially expensive.


**Recommendation:** Use an indexed metadata store, sharded bounded directories, or a cache backend with native TTL/LRU. Keep invalidation keyed by canonical content/model/prompt identity and measure maintenance work independently from provider time.

**Confidence:** Current-source corroborated.

### F-16 — P1 — Server cache headers existed without origin memoization

**Phase 4 status:** Safe catalog, summary, and chapter-projection memoization is
implemented locally; shared-reader behavior and populated hit ratios remain
open.

**Evidence:** Catalog base pages, DB-backed novel summaries, and bounded chapter
metadata now use `PublicProjectionCache`, while ranking uses its own bounded
success-only cache. Projection keys include the current database/projection
version where a response can become stale; publication/reconciliation and
takedown review invalidate the projection cache. Private identity/progress
responses remain outside shared caching.

**Impact:** Warm public projection reads avoid repeated assembly and metadata
work within one process, but cache entries are not shared across replicas and
the cache hit ratio is not yet measured under populated analytics. HTTP headers
alone remain insufficient for an unbounded origin path.

**Recommendation:** Measure hit ratio, stale window, origin query count, and
reader-worker topology. If multiple replicas make duplicate work material,
move the same bounded, versioned contract to Redis or another shared cache with
explicit invalidation; do not cache disabled/no-data responses.

**Confidence:** Current-source corroborated; cache effectiveness requires deployment measurements.

### F-17 — P2 — The frontend bundle is not the primary measured bottleneck

**Evidence:** The existing `.next/static` output was about 4.46 MB across 63 files; the largest observed JavaScript chunk was about 229 KB and CSS about 95 KB. The severe failures occurred on API/catalog calls and direct reader responsiveness, with low reader CPU.

**Impact:** Focusing first on bundle splitting would not address the observed 6–35-second public-read failures.

**Recommendation:** Keep normal bundle budgets and inspect route-level imports, but prioritize deployment, storage, database, cancellation, and request fan-out. Re-measure browser LCP/INP after the API path is healthy.

**Confidence:** Measured for the local build artifact; not a substitute for a clean production build profile.

### F-18 — P2 — Redis is currently not the observed bottleneck, but queue load is unproven

**Evidence:** Redis responded to `PING`, rejected connections were zero, memory use was low, and no RQ queue keys were observed in the sampled key scan.

**Impact:** Redis tuning would be premature for the observed outage. Conversely, the absence of queue keys means there was no meaningful worker-load sample.

**Recommendation:** Add queue-depth, job-wait, Redis command latency, and connection-pool metrics before changing Redis settings. Use a controlled translation workload to measure queue behavior.

**Confidence:** Measured for the sample; load conclusion is limited.

### F-19 — P2 — Synthetic checks can produce false-fast results when the Host header is wrong

**Evidence:** Caddy is configured for the site host. A request sent with a loopback host returned a fast empty frontend response, while a request with the configured host exercised the backend/reader routes and exposed readiness/catalog failures.

**Impact:** Browser automation, uptime checks, and local profiling can report success while bypassing the API routing path.

**Recommendation:** Make the host header/base URL an explicit test fixture, assert route ownership, and include response identity headers or a route marker in diagnostics. Never compare timings from different host-routing conditions.

**Confidence:** Measured.

### F-20 — P0 — The development overlay cannot start the production frontend bundle

**Evidence:** `deploy/compose.dev.yml` bind-mounts the source `frontend/` directory into `/app/frontend`, while the built standalone image starts `node frontend/server.js`. Recreating the application with the development overlay caused the frontend container to restart with `MODULE_NOT_FOUND`; rebuilding itself succeeded. Recreating with the base Compose file, without that mount, produced a healthy frontend.

**Impact:** A developer or deployment check can report a failed current-image rollout even though the frontend build is valid. It also encourages testing an overlay with different runtime semantics from the production image.

**Recommendation:** Separate the development server configuration from the standalone production image: either run the mounted source with the Next development command and its required dependencies, or remove the source mount for production-like verification. Add a Compose smoke test for both modes and make the selected mode explicit in Phase 0 commands.

**Confidence:** Measured.

## Positive observations to preserve

- The public ranking contract correctly returns unavailable when analytics is disabled rather than fabricating popularity.
- Chapter views are excluded from the ranking service's source query, avoiding an obvious chapter-navigation inflation path.
- Provider credentials are isolated by credential scope in the current translation/provider code, and usage is recorded per credential/job path.
- HTTP connection limits and database statement/lock/idle timeouts are configured rather than left entirely unbounded.
- The public search overlay debounces input, uses `Promise.allSettled`, and forwards an abort signal; that pattern should be reused by the remaining public hooks.
- Redis is available and responsive in the current environment, so it can support a later queue/cache design after the serving path is corrected.

## Recommended performance budgets

These are proposed acceptance budgets for a healthy, current-revision deployment, not claims about the present runtime:

| Path | Target | Required measurement |
| --- | --- | --- |
| `/health/live` | p95 under 100 ms | Proxy and direct reader/backend separately |
| `/health/ready` | p95 under 500 ms with cached readiness | Breakdown by database, storage, worker, and total |
| Home initial public data | p95 under 1.5 s on a warm region | Browser LCP plus catalog API and ranking API timings |
| Catalog page | p95 under 300 ms warm, under 800 ms cold | DB plan, projection hit ratio, object calls/request |
| Ranking page | p95 under 500 ms warm, under 1 s cold | aggregation time, cache hit ratio, summary enrichment count |
| Novel detail | p95 under 500 ms warm, under 1.2 s cold | DB/object calls, analytics enqueue time, response bytes |
| Chapter read | p95 under 800 ms warm, under 1.5 s cold | object calls, raw fallback count, glossary time |
| Translation enqueue | p95 under 300 ms | API response time independent of provider completion |
| Translation completion | tracked by size percentile | queue wait, provider time, retries, storage write time |

The budgets should be validated with at least 50 warm and 50 cold requests per route, a realistic published catalog, analytics enabled for ranking tests, and concurrent translation load. Report p50/p95/p99, error rate, timeout rate, database pool wait, storage call count, and reader worker utilization.

## Validation limitations

- The initial live stack was running an older image; the local Phase 0 rerun now uses freshly built images, but no remote/production deployment was validated and local `:local` tags are not immutable revision evidence.
- Analytics was disabled and contained no events, so ranking latency and cardinality behavior need a seeded benchmark after deployment.
- Ranking/cache tests use an isolated SQLite dataset and prove bounded query behavior, but no production-volume PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` or cross-replica cache hit ratio has been measured.
- The ranking cache is process-local with a bounded 60-second default stale window and 64-entry default limit; shared-cache economics and invalidation across reader replicas remain unverified.
- The contributor/ranking migration is now applied locally; production-equivalent permissions and deployment migration procedure remain unverified.
- Phase 4 readiness and Caddy passed locally with the protected one-second probe value and no process override. Percentile behavior under concurrent delayed storage and multi-process replacement remains unmeasured.
- `backend/tests/test_public_reader_availability.py` now passes all 22 tests against a published DB projection; migration `e5f7a9c1d3b2` persists the per-novel unavailable policy needed by the projection-first reader.
- Object-storage timing was measured in the existing deployment, but no destructive or production data operation was performed.
- The browser check with the wrong host was intentionally treated as invalid for API performance; only configured-host proxy timings were used.
- No claim is made here about provider-side latency without a controlled provider workload and provider telemetry.

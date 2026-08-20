# Performance Action Plan: Public Reads, Rankings, and Translation

**Prepared:** 2026-08-19
**Companion report:** `docs/PERFORMANCE_AUDIT.md`
**Phase 6 update:** 2026-08-20
**Objective:** make the deployed stack measurable, responsive, and resilient under public-read traffic while keeping the existing privacy, credential-isolation, ranking, and artifact-preservation contracts.

## How to use this plan

The order matters. Runtime/release correctness comes before application benchmarks; serving-path fixes come before frontend polish; and worker/provider tuning comes after queue and origin metrics exist. Each phase has an exit gate. Do not declare a phase complete from a code diff alone.

## Phase 0 — establish a truthful baseline

### 0.1 Deploy one known revision

**Owner area:** release/deployment
**Relevant areas:** Compose image references, Caddy, migration runner, route inventory.

Actions:

- Build and deploy the current repository revision to an isolated environment.
- Verify backend, reader, frontend, and Caddy report the same image revision.
- Apply the contributor/ranking migration using an application schema role with the required create/alter permissions. Do not grant broad permissions without an explicit security review.
- Confirm the current public ranking route returns the contract's disabled/unavailable response when analytics is disabled; it must not return the old-image `404`.
- Make the configured site host a required variable in health and browser tests.

Exit gate:

- Image revision, migration revision, and route inventory are recorded together.
- `/health/live` is 200, `/health/ready` is healthy, and Caddy reaches the correct backend/reader after container replacement.
- A deployment restart/replace test produces no stale-upstream connection failures.

### 0.2 Separate outage from latency in telemetry

Add request metrics with route, status, duration, and upstream component. At minimum record:

- Caddy upstream connect failures and proxy retries.
- Backend/reader request p50/p95/p99 and timeout/error counts.
- Database pool checkout wait and query duration.
- Object-storage operation count, operation type, duration, bytes, and error class.
- Cache hit/miss and projection fallback count.

Do not log credentials, authorization headers, prompt text, raw provider responses, storage keys, or IP addresses.

Exit gate: a single trace or structured timing record can identify whether time was spent in proxy connection, database, object storage, provider, queue, or serialization.

### Phase 0 execution log — 2026-08-20

**Status: local baseline complete. Phase 1 was subsequently implemented and is recorded below.**

Completed in the local Compose environment:

- Built current backend, reader, and frontend images from the checkout; the frontend build generated 49 routes.
- Applied the contributor credential/usage-ledger migration successfully; the database is at head `a8c4e2f7b901`.
- Recreated the services with the base Compose file, which uses the built standalone frontend image without the development source bind mount.
- Verified current public routes: liveness `200` in about `9 ms`, rankings `200` in about `43 ms`, and a ten-item catalog page `200` in about `254 ms` through Caddy.
- Observed backend, reader, and frontend containers healthy after recreation.
- Observed no matching recent Caddy connection-refused/upstream errors after recreation.
- Recreated backend, reader, and Caddy once more with an explicit `HEALTH_PROBE_TIMEOUT_MS=2000` runtime override; all services became healthy and Caddy readiness passed.
- Verified the final proxy timings: liveness about `7 ms`, readiness about `1.29 s`, rankings about `25 ms`, and a ten-item catalog page about `425 ms`.

Remaining gate requiring review:

- The original `/health/ready` failure was reproduced at the configured `1,000 ms` per-probe limit. Ten isolated storage probes succeeded in roughly `486–640 ms`, but the real concurrent health run timed out storage while storage-usage work took about `1,559 ms`.
- `deploy/.env` explicitly contains the one-second value and was intentionally not edited because it is a protected runtime/secrets file. A durable operator-approved configuration or Phase 4 health implementation is still required to prevent regression on restart.
- The development overlay is not a valid production-style startup: its frontend bind mount hides the standalone server and causes `MODULE_NOT_FOUND`. The base Compose file was used for the valid current-image check.
- The local `:local` image tags do not embed an immutable source revision, so a release deployment still needs digest/revision evidence.

The local Phase 0 baseline is signed off: current images, migration, routes, application health, readiness, and one replacement cycle were verified. The durable configuration caveat is carried into Phase 4. Phase 1 and Phase 2 implementation are complete locally; Phase 3 execution and review evidence is recorded below.

## Phase 1 — remove public-read request waterfalls

### 1.1 Make the published projection authoritative for public catalog reads

**Owner area:** backend public catalog and storage reconciliation
**Relevant source:** `backend/src/novelai/api/routers/public_catalog.py`, `backend/src/novelai/services/public_catalog_service.py`.

Actions:

- Define the minimum complete public projection: slug, title, status, taxonomy labels, cover/reference metadata, translated chapter count, latest activity, and generation identity required by the public cards.
- Populate/reconcile that projection asynchronously when a novel or generation changes.
- Make the public request path query the projection only. If the projection is missing or stale, return a bounded unavailable/degraded state rather than enumerate object storage.
- Keep storage enumeration as an operator/reconciliation operation, not as a public fallback.
- Add a test that fails if a normal catalog request invokes `list_novels()`, per-novel metadata loading, or per-novel chapter counting.

Phase 1 result: the public catalog now uses the published database projection only, returns a bounded degraded response when that projection is unavailable, and has regression coverage proving that normal reads do not scan object storage.

Exit gate: a catalog request performs one bounded database page query and zero object-storage calls in the normal path; cold and warm p95 meet the proposed budget.

### 1.2 Bound catalog query work

Actions:

- Replace the existence `count()` plus total `count()` pattern with a measured bounded strategy.
- Cap public page size to a deliberate value; use pagination for more items.
- Confirm indexes support published status, sort order, slug, and the common taxonomy filters.
- Use query plans in tests or a repeatable benchmark so a future filter cannot silently reintroduce a sequential scan.

Phase 1 result: the page query now uses a single window count and retains the existing bounded page-size contract. Query-plan/load benchmarking remains a later acceptance task.

Exit gate: the common home/catalog query has a stable plan, no redundant count query, bounded response size, and no N+1 database calls.

### 1.3 Make detail and chapter metadata projection-first

Actions:

- Store or derive immutable public chapter-list metadata in a serving projection/manifest.
- Use one versioned manifest for chapter availability and generation identity instead of listing object-storage keys on every request.
- Keep raw and translated artifacts immutable and preserve takedown checks before serving.
- Measure and reduce normal chapter reads to one content object plus only the metadata needed for the response.

Phase 1 result: `Novel.public_slug` and projected chapter/section metadata are persisted by migration `b7c1e2d3f4a5`; public detail and chapter metadata reads use the projection, while translated chapter content remains storage-backed. Incomplete chapter projections return an honest unavailable response.

Exit gate: novel detail and chapter-list requests remain responsive when a novel has hundreds of chapters and do not perform a chapter-count/list waterfall.

### Phase 1 execution log - 2026-08-20

**Status: implementation complete; stopped for review before Phase 2.**

Completed in the local checkout and Compose environment:

- Removed public catalog storage fallback and request-time metadata/chapter enumeration. Missing or incomplete projections now produce bounded degraded/404 responses rather than fabricated public data.
- Replaced redundant catalog count work with one window count and added regression tests for storage-call avoidance, projection completeness, persisted slugs, and projected chapter section fields.
- Added `Novel.public_slug`, projected chapter/section metadata, and migration `b7c1e2d3f4a5`; the Compose migration runner applied it and reported that revision as head.
- Focused backend tests passed: `147 passed`; `tools/pyright.ps1` reported zero errors; targeted Ruff checks passed; `graphify update . --no-cluster` completed successfully.
- Live services remained healthy with the explicit `HEALTH_PROBE_TIMEOUT_MS=2000` runtime override. Liveness, readiness, catalog, detail, and ranking routes responded successfully; the live chapter-list route returned `404` because the two published novels currently have zero projected `Chapter` rows.
- Live DB-only counts were 9 total novels, 2 published novels, 0 chapter rows, and 2 published public-slug rows. Two bounded reconciliation attempts exceeded the 180-second maintenance command timeout while reading object storage, so live chapter projection completeness is not yet proven.
- The failed host-side migration was due to database table-ownership privileges and rolled back. The deployment-authoritative Compose migration succeeded; no `.env` or secret file was changed.
- Superseded project/test Docker images were removed only after checking the current healthy containers; base Postgres, Redis, Caddy, and build/runtime dependency images were retained.

Phase 1 exit gate status: source-level and focused-test gates passed, and live catalog/detail/ranking behavior passed. The live chapter projection gate remains open because reconciliation timed out; this remains a Phase 4/production-readiness follow-up rather than a reason to discard the completed projection-first read path.

## Phase 2 — make the browser start with useful data and stop obsolete work

### 2.1 Server-render or prefetch the public first view

**Owner area:** Next.js public routes and public API client
**Relevant source:** `frontend/app/(public)/home/page.tsx`, `frontend/lib/query-client.tsx`, `frontend/lib/public-api.ts`, public query hooks.

Actions:

- Provide initial catalog and weekly ranking data from the route/server boundary or an equivalent prefetch/dehydrate path.
- Keep the interactive client query for revalidation, but do not make first content wait for every non-critical query.
- Fetch only the visible ranking period. If the home widget is weekly, share that query with the weekly tab instead of always starting two ranking requests.
- Defer genres, auth, history, notification, and search data until they affect visible UI.
- Reduce the initial catalog page and load additional pages on demand.

Exit gate: a guest receives useful catalog content without waiting for auth or taxonomy; the home request graph has no duplicate ranking request for the same period.

### 2.2 Add cancellation and bounded browser timeouts

Actions:

- Pass React Query's `signal` into catalog, ranking, novel, chapter-list, and chapter API calls.
- Add a consistent request timeout in `publicFetch` and classify aborts separately from server errors.
- Verify navigation away from a slow page cancels the underlying request and does not leave a reader worker occupied.
- Keep the search overlay's debounce/abort behavior as the reference implementation.

Exit gate: browser tests show aborted requests on route change, no unbounded fetch remains in the public API client, and error UI does not claim a preview is real catalog data.

Phase 2 result: `home/layout.tsx` prefetches only the 24-item catalog and weekly ranking through the reader service, then hydrates the existing client queries. `publicFetch` now has a 10-second timeout, preserves caller cancellation, classifies timeout versus caller abort, and all public content hooks forward React Query signals with retries disabled. Auth/history are deferred until the initial home content settles. Targeted tests cover the request and hydration contracts.

### 2.3 Keep bundle work proportional to evidence

Actions:

- Retain a normal bundle budget and inspect route-level imports after API latency is fixed.
- Do not prioritize broad bundle splitting over catalog/readiness/reader saturation work unless browser LCP measurements identify JavaScript as the limiting component.

Exit gate: browser traces include LCP, INP, transfer size, and API timings so bundle decisions are evidence-based.

### Phase 2 execution log - 2026-08-20

**Status: implementation and local validation complete; stopped for review before Phase 3.**

Completed in the local checkout and Compose environment:

- Added a server home layout that prefetches 24 newest catalog items and the weekly ranking, with a 20-second hydrated-query stale window and a three-second server prefetch bound. The browser trace showed no initial public catalog, ranking, or genre requests.
- Corrected the internal SSR topology after the first probe used the admin service: public prefetch now targets `READER_API_URL=http://reader:8001`, while `BACKEND_API_URL` remains the admin/rewrite boundary. The live reader calls returned catalog `200` and a truthful ranking `200` with `analytics_disabled`.
- Deferred auth/history personalization, added React Query cancellation propagation and bounded public request timeouts, and removed unbounded public-query retries.
- Frontend validation passed: 21 targeted tests; the full suite passed with 857 tests across 78 files in 219.66 seconds; lint, typecheck, and production build passed. The rebuilt frontend image was recreated with all five Compose services healthy.
- Live `/home` returned `200` with useful catalog HTML, the current live title, and honest unavailable ranking markup. One browser sample measured response end about 363 ms, DOMContentLoaded about 411 ms, load about 910 ms, 54 resources, and about 3.23 MB transferred.
- Added the non-secret `READER_API_URL` and `BACKEND_API_HOST` configuration documentation without changing protected `.env` files.

Phase 2 exit gate status: source, focused tests, full frontend checks, live SSR, and browser request-graph checks passed. Production-scale repeated TTFB, LCP, and INP budgets remain unmeasured, and the local chapter projection completeness issue from Phase 1 remains open. Review is required before Phase 3.

## Phase 3 — make rankings cheap, truthful, and cacheable

### 3.1 Align analytics indexes with the ranking query

**Owner area:** analytics schema and ranking service
**Relevant source:** `backend/src/novelai/services/public_ranking_service.py`, `backend/src/novelai/db/models/analytics_event.py`.

Actions:

- Add the index or indexes justified by `EXPLAIN (ANALYZE, BUFFERS)` for event name, time window, novel, and authenticated/anonymous viewer identity.
- Include the anonymous identity field actually used by the current source contract; do not silently substitute IP addresses.
- Seed representative authenticated and anonymous events and test daily, weekly, and monthly boundaries.
- Exclude chapter events and preserve distinct-viewer semantics.

Exit gate: ranking aggregation uses the intended indexes, has bounded query time at the target event volume, and has tests for duplicate events from one viewer.

### 3.2 Remove ranking enrichment fan-out

Actions:

- Join ranking rows to the public projection in one bounded query, or return projection fields already present in the aggregation/rollup.
- Avoid calling `get_public_novel_summary` once per result.
- Introduce a scheduled rollup table when raw-event aggregation no longer meets the budget. Keep raw events for the configured retention period and define rollup rebuild/reconciliation behavior.

Exit gate: a limit-50 ranking response has a fixed small number of database queries and zero object-storage calls.

### 3.3 Cache results without fabricating data

Actions:

- Cache successful ranking results by period, projection version, and limit for a short bounded TTL.
- Return an explicit unavailable/empty state when analytics is disabled or no data exists.
- Invalidate or version cached rows after publish, takedown, or projection changes.

Exit gate: cache hit ratio and stale-data window are observable, and disabled analytics never renders fabricated popularity.

### Phase 3 execution log - 2026-08-20

**Status: implementation and local validation complete; stopped for review before Phase 4.**

Completed in the checkout and the local Compose environment:

- Replaced the two-query authenticated/anonymous ranking merge with one distinct-viewer aggregation joined to the published `Novel` projection. Chapter events remain excluded, and taxonomy is loaded with bounded `selectinload` queries rather than per-result summary/storage calls.
- Added the two ranking indexes used by the event predicate and viewer identities: `ix_analytics_events_rank_event_time_novel_user` and `ix_analytics_events_rank_event_time_novel_session`, migration `c8d2e4f6a1b3`.
- Added a bounded process-local ranking cache keyed by period, public projection version, and limit. It stores successful non-empty responses only, uses a 60-second default TTL and 64-entry LRU bound, and exposes hit/miss/entry metrics without exposing ranking contents.
- Backend implementation committed as `615bb0d` (`perf(public): bound ranking aggregation and cache results`).
- Preserved truthful disabled and no-data responses. The live analytics-disabled route returned `available=false`, `reason=analytics_disabled`, and zero items; no popularity data was fabricated.
- Built the current backend and reader images, applied the migration through the Compose migration service, recreated backend and reader with the already documented `HEALTH_PROBE_TIMEOUT_MS=2000` runtime override, and verified all five services healthy. The live database reported migration head `c8d2e4f6a1b3` and both composite indexes present.

Validation:

- Affected backend tests passed: `157 passed` across ranking, metrics, public-router, and catalog-projection suites.
- Ranking/cache tests passed with bounded database work: the uncached path stayed within four SQL statements and the cached path required only the projection-version check; duplicate authenticated/anonymous viewer and period behavior remain covered.
- Targeted Ruff and Pyright passed. The full backend suite and unit-only suite each exceeded a 10-minute allowance without returning a result; they are recorded as validation limitations, not passes.
- Live `/api/public/rankings?period=weekly&limit=10` returned `200` in about `606 ms` through Caddy with the truthful disabled response. `/metrics` exposed the three ranking-cache metrics. This is not a populated ranking latency benchmark because live analytics is disabled and empty.

Phase 3 exit gate status: source-level query-count, privacy, cache-state, index, and focused-test gates passed. Production-volume `EXPLAIN (ANALYZE, BUFFERS)`, seeded ranking latency/cardinality, and cross-replica cache behavior remain open. Review is required before Phase 4.

## Phase 4 — reduce health and cache amplification

### 4.1 Make readiness cheap and stable

**Owner area:** health service and operations
**Relevant source:** `backend/src/novelai/services/health_service.py`, `backend/src/novelai/api/routers/health.py`, Compose healthchecks.

Actions:

- Carry forward the Phase 0 finding: the current explicit one-second per-probe setting fails under concurrent storage checks; do not rely on a temporary runtime override as the release configuration.
- Implement the intended short readiness cache with an explicit TTL and timestamp.
- Keep liveness process-only.
- Use a bounded readiness storage check; move full write/read/delete verification to a scheduled or owner-only diagnostic.
- Ensure Caddy's readiness check is not allowed to churn containers because of a transient storage probe.

Exit gate: readiness p95 meets its budget, transient storage delay does not cause restart loops, and the response remains redacted/public-safe.

### 4.2 Make public cacheability effective

Actions:

- Cache immutable/versioned catalog, ranking, and chapter metadata at the origin or Redis layer, not only through response headers.
- Track cache hits, misses, invalidations, and origin storage calls.
- Preserve private identity and progress semantics; never put user-specific history/progress in a shared cache.

Exit gate: warm public reads do not repeat object-storage enumeration and cache invalidation is tied to publish/takedown/generation changes.

### 4.3 Decouple analytics ingestion from the critical read

Actions:

- Enqueue best-effort analytics events or use a bounded async writer instead of opening a synchronous database session inside the public detail/chapter request.
- Define backpressure and loss policy; analytics failure must not fail or materially delay a content read.
- Preserve the signed opaque anonymous identity contract and retention/privacy rules.

Exit gate: disabling analytics or slowing the analytics writer does not change public content latency beyond the agreed budget.

## Phase 4 execution log - 2026-08-20

**Status: implementation and local validation complete; stopped for review before Phase 5.**

Completed in the local checkout and Compose environment:

- Wired the existing five-second health-cache setting into a single-flight
  readiness cache. Public readiness now performs only database, lightweight
  storage reachability, worker, and disk checks; the full storage
  write/read/delete probe and S3 usage scan remain owner diagnostics.
- Added bounded process-local public projection caching for safe catalog pages,
  DB-backed summaries, and chapter metadata. The default is a 30-second TTL
  with 256 entries. Database/projection version keys and publish/reconcile/
  takedown invalidation prevent normal stale-publication reuse. Identity,
  progress, raw query text, and analytics cookies remain outside the cache.
- Replaced synchronous public analytics ingestion with a sanitized bounded
  asynchronous writer. Queue-full events are dropped and counted, worker
  failures are suppressed and counted, and lifecycle shutdown drains briefly.
- Added readiness, projection-cache, and analytics-writer metrics plus explicit
  Compose/example settings.
- Built fresh backend/reader images and recreated the stack without the former
  `HEALTH_PROBE_TIMEOUT_MS=2000` override. Caddy readiness passed with the
  one-second setting: `0.559 s` cold and `0.046 s` warm. Weekly ranking and
  catalog routes returned `200`; analytics remained honestly disabled/empty.
- Focused changed-path validation passed: 209 tests in the public/health/
  ranking/cache group and 161 tests in storage, split-topology, health,
  analytics, and cache groups. Ruff and Pyright passed.

Phase 4 exit gate status: the source, focused-test, no-override readiness, and
redaction gates passed locally. Percentile readiness under delayed storage,
slow-writer loss behavior, populated ranking load, and multi-reader/shared
cache economics remain open. The Phase 4 checkpoint recorded a storage-only
`backend/tests/test_public_reader_availability.py` fixture; the continuation
later repaired it against the required Phase 1 DB projection without restoring
request-time storage fallback.

## Phase 5 — isolate worker and provider latency

### 5.1 Return an activity immediately for long translations

**Owner area:** translation API, activity orchestration, deployment topology
**Relevant source:** `backend/src/novelai/services/orchestration/operations.py`, `backend/src/novelai/activity/runner.py`, worker tasks.

Actions:

- Change long-running translation endpoints to enqueue work and return an activity/job identifier.
- Run provider workers separately from public web workers and disable the in-process background runner in public reader processes.
- Preserve owner/contributor credential isolation, quotas, usage ledger, and revocation behavior.
- Make activity state transitions durable and idempotent.

Exit gate: translation enqueue p95 is under the API budget while concurrent public catalog/detail probes remain healthy.

### 5.2 Replace the JSON activity control plane

Actions:

- Move activity state/claim/heartbeat/list operations from full-file JSON rewrites to the database or a durable queue store.
- Add lease expiry, retry state, idempotency keys, and bounded history queries.
- Instrument claim wait, heartbeat wait, update duration, and queue age.

Exit gate: queue throughput and update latency remain stable as activity history grows and two workers cannot claim the same activity.

### 5.3 Bound provider work across all processes

Actions:

- Enforce global per-provider/per-credential concurrency and token/request budgets, not only a per-activity semaphore.
- Use a deadline across retries, bounded exponential backoff, and fast invalid-key/quota state transitions.
- Reuse safe provider clients where supported instead of creating a client for every request, while preserving explicit key isolation.
- Record provider wait, provider execution, retry count, quota reservation, and usage-ledger write duration without logging prompt/key data.

Exit gate: provider overload increases queue time predictably rather than consuming all web/worker threads, and contributor credentials never appear in owner-only work.

### 5.4 Replace directory-wide translation-cache maintenance

Actions:

- Add indexed metadata or a bounded cache backend for invalidation, statistics, and eviction.
- Shard file-backed entries if a migration is needed, and avoid scanning the entire cache directory on a request path.
- Measure cache hit rate, read/write latency, eviction duration, and disk contention.

Exit gate: cache maintenance has a bounded schedule and does not increase translation or public-read p95 as cache size grows.

## Phase 5 execution log - 2026-08-20

**Status: implementation and focused local validation complete; stopped for
review before Phase 6.**

### 5.1 result

- Owner translation requests now validate the novel, create a durable
  translation activity, and return `202 Accepted` with `activity_id` and
  `status=pending`; they no longer await provider-backed orchestration.
- `Idempotency-Key` is accepted on the enqueue route. Without a supplied key,
  the service derives a stable hash from non-secret operation parameters.
- Compose now has a dedicated `worker` service running `novelaibook worker`.
  Web services keep `JOB_WORKER_ENABLED=false`; the reader already has no
  in-process activity runner. Existing credential isolation, usage ledger,
  quota, revocation, and activity cancellation paths remain worker-owned.

### 5.2 result

- Added `activity_records` and migration `d9f3a1b7c5e2`. The production queue
  uses row-locked status/lease transitions, expired-lease recovery,
  `skip_locked` claims where supported, idempotency uniqueness, bounded list
  queries, retry state, and sanitized metadata size/history limits.
- The legacy `queue.json` is imported once when the database backend starts;
  explicit file-backed instances remain available for isolated tests and
  maintenance compatibility.
- Queue operation timing, pending age, and status gauges are available through
  the metrics boundary. A two-queue test proved that a second worker cannot
  claim an already-running activity.

### 5.3 result

- Gemini quota admission now supports global in-flight limits in addition to
  RPM/TPM/RPD reservation. Owner and contributor controllers receive separate
  limits, and abandoned reservations expire after the configured TTL.
- Provider calls use reusable credential-isolated Gemini clients, per-chunk
  deadlines, bounded exponential retry delay, and truthful timeout/quota
  failure transitions. Provider timing counters and sanitized usage records
  capture wait, execution, retries, quota reservation, and usage-ledger write
  duration without prompts or secrets.

### 5.4 result

- `TranslationCacheService` now maintains an SQLite WAL metadata sidecar for
  key, novel, access-time, and size indexes. Invalidation, statistics, and LRU
  eviction use indexed rows. A recursive JSON scan is limited to one
  initialization/backfill and is not used on request-path maintenance.

### Focused evidence

- `tools/ruff.ps1 check .`: passed.
- `tools/pyright.ps1`: passed with zero errors.
- The affected queue, operation, provider, cache, usage, metrics, and quota
  suites passed (`63 passed` in the pre-Phase-5 regression set).
- New durable-queue, enqueue/idempotency, cache-index, and quota-concurrency
  tests passed (`12 passed`).
- The expanded Phase 5 backend set passed (`102 passed` in `13.63 s`), and
  activity-router, admin-translation, split-topology, and health coverage
  passed (`69 passed` in `12.22 s`).
- The contract set passed `40` tests at the Phase 5 checkpoint; its two
  failures were the then-known stale public-reader projection fixture failures,
  not enqueue, idempotency, or worker failures. The continuation repaired the
  separate availability fixture and now passes all `22` tests.
- Frontend lint, typecheck, production build, and focused route/ranking/admin
  coverage passed. The focused Vitest run passed `40 tests` across `5 files`
  in `14.32 s`.
- The targeted migration smoke upgraded `c8d2e4f6a1b3` to
  `d9f3a1b7c5e2` and downgraded back successfully. The real local PostgreSQL
  migration profile applied the new migration successfully, and the final
  production Compose topology reported healthy backend, reader, frontend,
  Redis, Caddy, and running worker services.
- The all-Markdown route audit found no active `/contribute`, `/request-novel`,
  or singular `/novel/...` references. Remaining matches are intentional
  current routes, historical notes, the truthful absence of All Time ranking,
  or the unrelated `TableOfContentsV2` source identifier.
- `graphify update . --no-cluster` refreshed the graph after the implementation
  edits.

### Phase 5 gate status

The source, focused-test, migration, Compose, and route/document gates pass.
The full backend command timed out after `904 s` without returning a result;
the full frontend Vitest command timed out after about `243 s`. The stale
availability fixture was repaired after this checkpoint and passes `22` tests.
Enqueue p95 under concurrent public probes and production-like multi-worker/
provider load evidence remain unavailable. Do not treat this section as Phase
6 approval; review the completed implementation and these runtime limitations
first.

## Phase 6 — load testing and operational acceptance

Create a repeatable scenario with:

- a realistic published catalog, including a novel with hundreds of chapters;
- analytics enabled with seeded authenticated and anonymous viewers;
- cold and warm public cache states;
- guest and authenticated browser sessions;
- concurrent catalog, detail, chapter, search, ranking, and translation-enqueue traffic;
- at least one provider failure/quota event and one storage delay event.

Record for every run:

- p50/p95/p99 latency, status, timeout, and retry rate per route;
- Caddy upstream connect/error counts;
- database query count, slowest query, pool checkout wait, and total connections;
- object-storage call count, operation latency, bytes, and fallback count;
- Redis command latency, queue depth, job age, and worker utilization;
- provider queue wait, execution time, retries, token usage, and quota failures;
- browser LCP/INP/CLS, request waterfall, transferred bytes, and aborted requests.

### Acceptance matrix

| Area | Must be true before sign-off |
| --- | --- |
| Deployment | All services run the same revision; migrations are applied; route inventory matches current source. |
| Proxy | Container replacement does not leave stale upstreams; Caddy health is stable. |
| Readiness | Liveness is cheap; readiness is bounded/cached; storage degradation is visible without restart churn. |
| Catalog | Normal public catalog is projection/database-only, bounded, and free of N+1 storage work. |
| Detail/chapter | Metadata is manifest/projection-first; normal reads have measured object-call bounds. |
| Home | Initial useful content does not wait for auth/taxonomy; duplicate ranking requests are removed. |
| Browser | Public queries forward cancellation signals and enforce timeouts. |
| Rankings | Distinct viewer semantics, period boundaries, disabled/empty behavior, indexes, rollups/cache, and privacy rules are tested. |
| Analytics | Event ingestion cannot materially delay a content read and never stores IP addresses. |
| Translation | Enqueue is fast; long work is isolated; quotas/retries/credential scope/usage ledger are observable. |
| Queue/cache | Activity and translation-cache operations do not rewrite/scan unbounded files on hot paths. |
| Capacity | Aggregate database connections and provider concurrency are budgeted across all processes. |
| Documentation | Architecture, configuration, operations, translation, privacy/legal, route inventory, and public design briefs describe the measured implementation. |

## Phase 6 execution log - 2026-08-20

**Status: repeatable local acceptance and continuation controls executed; the
runtime gate remains open.**

The new `backend/tests/run_phase6_acceptance.py` harness creates a namespaced,
reversible local fixture and runs public traffic through Caddy. The executed
fixture contained 48 published novels, 1,428 chapters, and 1,200 seeded
authenticated/anonymous novel-view events. One novel contained 300 chapters;
the remaining 47 contained 24 chapters each. The run used 20 samples per
route at concurrency 8, with a warmup request before each route.

Measured p50/p95/p99 results were:

| Route | p50 | p95 | p99 | Status |
| --- | ---: | ---: | ---: | --- |
| liveness | 6.220 ms | 293.287 ms | 293.595 ms | 20 `200` |
| readiness | 24.444 ms | 55.197 ms | 55.519 ms | 20 `200` |
| catalog | 1,099.367 ms | 1,951.122 ms | 2,071.137 ms | 20 `200` |
| detail | 1,541.714 ms | 1,829.161 ms | 2,007.659 ms | 20 `200` |
| chapter | 2,312.717 ms | 3,053.049 ms | 3,801.925 ms | 20 `200` |
| search | 1,970.445 ms | 2,660.428 ms | 2,765.409 ms | 20 `200` |
| daily ranking | 117.895 ms | 292.914 ms | 322.484 ms | 20 `200` |
| weekly ranking | 125.517 ms | 355.838 ms | 367.510 ms | 20 `200` |
| monthly ranking | 149.160 ms | 298.064 ms | 343.298 ms | 20 `200` |
| home | 259.181 ms | 659.779 ms | 668.904 ms | 20 `200` |

The table values are ordered `p50 / p95 / p99`; all routes had zero client
timeouts and zero transport errors. Caddy recorded zero `502`, connection
refused, and `5xx` events during the public sample. A temporary local owner
session was generated inside the backend container, refreshed through the CSRF
endpoint, and never printed or persisted as test output. An eight-request
concurrent translation enqueue burst returned two `202`, four configured
translation-rate-limit `429` responses, and two `500` responses. Backend logs
classified the `500` responses as managed database session-capacity failures
while checking for active translation work. After restarting only the
temporary backend process to clear its in-memory limiter, a concurrency-3
control returned `3/3` `202` responses with p50 `1,008.526 ms` and maximum
`1,210.110 ms`. A deliberately missing provider configuration then produced
durable failed activities with the expected sanitized provider-configuration
error and one retry. A disposable public authenticated browser session loaded
`/account/contributions` and was deleted after the check.

The Phase 6 continuation tested the measured connection-capacity mitigation in
an isolated transaction-mode overlay. An eight-request owner burst returned
five `202` and three configured translation-limit `429` responses, with no
database-capacity `500` responses; p50 was `3,139.887 ms` and maximum
`3,196.577 ms`. A five-sample public workload at concurrency 8 returned `200`
for every route with zero timeouts or transport errors. The harness now accepts
an explicit `--host-header` for internal Caddy targets; no-host internal proxy
responses were rejected as invalid because they had empty `200` bodies.

Controlled storage fault injection used a local in-memory S3-protocol stub with
a 1.2-second delay. Ten concurrent readiness requests returned `503` with
`storage=unhealthy`; p50 was `1,351.488 ms`, p95 `1,382.913 ms`, and maximum
`1,541.684 ms`. The application containers stayed running and the base Compose
stack was restored afterward. This does not substitute for production R2/S3
telemetry.

The application-side capacity response was then implemented and rebuilt into
the admin and reader images. A direct-mode filesystem control repeated the
eight-request authenticated enqueue burst and returned five `202` responses
and three configured translation-limit `429` responses, with zero capacity
`500`s. Recognized SQLAlchemy DBAPI pool/server-capacity failures now return a
sanitized `503 DATABASE_CAPACITY_EXHAUSTED`; unrelated database errors remain
generic `500`s. The web API regression file passes in full (`163 passed`).
This closes the local unhandled-error path, while deployment-wide pooler and
production capacity evidence remain open.

The browser sample measured home LCP `2,012 ms`, ranking LCP `196 ms`, detail
LCP `1,288 ms`, chapter LCP `740 ms`, CLS `0` on all pages, and an 80-88 ms
ranking-tab interaction event sample. The first home run exposed a hydration
error caused by `Date.now()`-derived labels; the home page now uses a stable
hydration-aware timestamp, and the rebuilt browser routes report zero
application console errors. Focused home tests pass (`29 tests`).

The original direct-mode owner burst reproduced two database-capacity `500`
responses before the application classification change. The rebuilt runtime
control now returns no capacity `500`s, but the protected base runtime
configuration remains direct and was not changed. Production R2/S3
call/latency/byte telemetry, PostgreSQL slowest-query and query-count
statistics (`pg_stat_statements` was unavailable), and multi-worker/provider
capacity remain unmeasured. Public `/metrics` is not routed through Caddy;
internal backend metrics were collected separately. The base Compose stack is
restored after cleanup, and no Phase 6 overlay or fixture data is part of the
deployment configuration.

A safe database snapshot from the restored base reported
`max_connections=60`, `superuser_reserved_connections=3`,
`active_connections=19`, and `application_connections=13`; `pg_stat_statements`
is unavailable in this profile. Compose has three long-running pool processes
(backend, reader, worker), each with a theoretical ten-connection ceiling,
while the snapshot's configured budget was `20`. At that checkpoint, the
deployed validator still accounted for only the two web pools, so the
worker/migration/operator aggregate remained an operator review item rather
than a proven invariant.

The rebuilt migration image then applied `d9f3a1b7c5e2 -> e5f7a9c1d3b2`; the
live local schema contains the per-novel reader-policy projection and both
ranking indexes. Sanitized `EXPLAIN (ANALYZE, BUFFERS)` samples measured the
projection catalog page at `0.041 ms` with three shared-hit blocks and the
weekly distinct-view ranking at `1.36 ms` with ten shared-hit blocks. Analytics
is disabled and the ranking result was empty, so this validates query shape and
the honest empty path only, not production-volume ranking capacity.

A second safe connection snapshot reported `max_connections=60`,
`superuser_reserved_connections=3`, `active_connections=1`, and
`application_connections=7`. Point-in-time activity is not a capacity proof:
direct-mode theoretical ceilings remain ten connections each for backend,
reader, and worker against budget `20`; this remains historical runtime
evidence, not a substitute for the explicit source guard or pooler verification.

### Phase 6 continuation: current-image public rerun

A fresh run used the current application images and an isolated named
filesystem volume. It seeded 48 published novels, 1,428 projected chapters,
and 1,200 privacy-safe authenticated/anonymous view events. Five samples per
route at concurrency 8 returned `200` for every public route with zero
timeouts or transport errors. The p95 values were `281.925 ms` for liveness,
`19.736 ms` for readiness, `1,348.466 ms` for catalog, `1,708.672 ms` for
detail, `1,844.762 ms` for chapter, `1,172.054 ms` for search, `30.516 ms`,
`24.123 ms`, and `28.468 ms` for daily/weekly/monthly ranking, and
`400.261 ms` for home.

The populated local PostgreSQL plans measured the projection catalog page at
`1.528 ms` with 8 shared-hit blocks and 24 rows, and weekly distinct-view
ranking at `2.704 ms` with 22 shared-hit blocks and 10 rows. This closes the
local seeded-query-plan gap for the current-image sample, not the production
capacity gate. Translation enqueue was skipped because no disposable owner
session and CSRF token were supplied. Cleanup verified zero remaining fixture
novels, chapters, and analytics events; the temporary volume and containers
were removed and the base Compose stack was restored healthy. R2/S3 telemetry,
production pooler/query-plan evidence, and worker/provider capacity remain
open.

The focused production-configuration validator suite now passes `38` tests.
The source guard computes
`DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
DB_CONNECTION_RESERVE` for direct/session mode and fails closed when it exceeds
`DB_CONNECTION_BUDGET`. The committed split-topology examples use three pool
owners, a two-connection reserve, and budget `32`. The rebuilt admin/worker and
reader images now run in the local base Compose stack with that direct-mode
budget. Configuration-only validation of the real production environment passes
for both admin and reader roles with zero fatal issues and one backup warning;
the real production database and object storage were not contacted by that
probe. Production pooler verification, R2/S3 telemetry, and provider capacity
remain open.

### Phase 6 gate status

The harness, public route, seeded analytics, proxy-health, provider-failure,
browser, hydration, focused frontend, cleanup, controlled storage-delay, and
classified-capacity-response checks pass for the local sample. Transaction
mode provides a tested local mitigation for the direct-mode database-session
failure, and the local base runtime now uses the explicit direct-mode budget of
`32`. Production pooler verification remains open. Phase 6 remains open because
production storage telemetry, database query-plan evidence, and representative
worker/provider capacity remain sign-off requirements. Do not convert these
local p95 values into production SLOs.

### Phase 6 continuation: projection-fixture and policy repair

The former F-32 fixture gap is resolved. Availability tests now seed the
published `Novel`/`Chapter` projection through `CatalogService` and pass all
`22` tests. Projection-first public reads retain the existing per-novel
`public_reader_unavailable_policy` contract through migration
`e5f7a9c1d3b2`; its SQLite upgrade/downgrade smoke also passes. This closes the
local stale-fixture gate, but does not close the separate production storage,
database-plan, pooler-budget, or worker/provider-capacity gates.

## Suggested implementation sequence

1. Complete Phase 0 and rerun the same runtime probes against the current revision. (Complete.)
2. Implement the projection-first catalog/detail path and add request-level object/query-count tests. (Complete locally; chapter projection reconciliation remains open.)
3. Review Phase 1 evidence; the projection-first read path is complete locally while chapter projection completeness and durable readiness remain open follow-ups.
4. Add browser cancellation/timeouts and reduce home critical fan-out. (Complete locally in Phase 2.)
5. Review Phase 2 evidence and approve the ranking/index/cache work before starting Phase 3. (Complete.)
6. Align ranking indexes, remove summary enrichment fan-out, and add bounded result caching. (Complete locally in Phase 3; production-volume and multi-replica evidence remain open.)
7. Review Phase 3 evidence and approve readiness/cache amplification work before starting Phase 4. (Complete.)
8. Stabilize readiness, cache safe public projections, and decouple analytics writes. (Complete locally in Phase 4; percentile, populated-load, and shared-cache evidence remain open.)
9. Review Phase 4 evidence and approve worker/provider isolation before starting Phase 5.
10. Move translation to enqueue/worker-only execution, then replace file-backed activity/cache hot paths.
11. Run the repeatable Phase 6 load scenario and update the budgets using
    measured capacity. (Local sample executed; review gate remains open.)
12. Apply and verify the transaction-mode/aggregate connection budget against
    the target pooler, then rerun Phase 6 with production-equivalent object
    storage and worker/provider telemetry before launch sign-off.

The first practical gate is not a frontend optimization: it is a current-revision deployment with a healthy reader, healthy readiness, current migrations, and a catalog request that cannot fall back to a serial object-storage scan.

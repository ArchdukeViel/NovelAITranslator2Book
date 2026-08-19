# Performance Action Plan: Public Reads, Rankings, and Translation

**Prepared:** 2026-08-19
**Companion report:** `docs/PERFORMANCE_AUDIT.md`
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

The local Phase 0 baseline is signed off: current images, migration, routes, application health, readiness, and one replacement cycle were verified. The durable configuration caveat is carried into Phase 4. Phase 1 implementation is now complete locally; review is required before Phase 2.

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

Phase 1 exit gate status: source-level and focused-test gates passed, and live catalog/detail/ranking behavior passed. The live chapter projection gate remains open because reconciliation timed out; review is required before Phase 2.

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

### 2.3 Keep bundle work proportional to evidence

Actions:

- Retain a normal bundle budget and inspect route-level imports after API latency is fixed.
- Do not prioritize broad bundle splitting over catalog/readiness/reader saturation work unless browser LCP measurements identify JavaScript as the limiting component.

Exit gate: browser traces include LCP, INP, transfer size, and API timings so bundle decisions are evidence-based.

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

## Suggested implementation sequence

1. Complete Phase 0 and rerun the same runtime probes against the current revision. (Complete.)
2. Implement the projection-first catalog/detail path and add request-level object/query-count tests. (Complete locally; chapter projection reconciliation remains open.)
3. Review Phase 1 evidence and approve the chapter-projection/readiness gate before starting Phase 2.
4. Add browser cancellation/timeouts and reduce home critical fan-out.
5. Align ranking indexes, remove summary enrichment fan-out, and add bounded result caching.
6. Stabilize readiness and decouple analytics writes.
7. Move translation to enqueue/worker-only execution, then replace file-backed activity/cache hot paths.
8. Run the full load scenario and update the budgets using measured capacity.

The first practical gate is not a frontend optimization: it is a current-revision deployment with a healthy reader, healthy readiness, current migrations, and a catalog request that cannot fall back to a serial object-storage scan.

# Performance Action Plan: Public Reads, Rankings, and Translation

**Prepared:** 2026-08-19
**Companion report:** `docs/PERFORMANCE_AUDIT.md`
**Phase 6 update:** 2026-08-20
**Objective:** make the deployed stack measurable, responsive, and resilient under public-read traffic while keeping the existing privacy, credential-isolation, ranking, and artifact-preservation contracts.

## R2-only cutover note — 2026-08-21

Canonical novel, chapter, translation, media, asset, and generation content
now belongs to Cloudflare R2 with PostgreSQL exact-reference truth. Earlier
phase entries that mention filesystem volumes, S3-protocol fixtures, or
request-time object scans describe historical controlled runs before the hard
cutover; they are not the current production storage architecture. Current
performance work must measure exact R2 operations, PostgreSQL projections, and
disposable local-runtime state separately.

## Risk-resolution checkpoint - 2026-08-23 07:33 UTC

The unresolved audit risks were rechecked against current primary provider
documentation and one bounded application run:

This is a historical risk snapshot. The 2026-08-24 async execution and
capacity handoff below is authoritative for current completion status.

| Risk | Current evidence or uncertainty | Resolution plan | Status |
| --- | --- | --- | --- |
| Supabase egress attribution | `pg_stat_statements` supplies cumulative call/row indicators, not billed bytes. The operator's custom report shows `66,683,432,737` bytes of Shared Pooler Egress, matching the reported billing-period spike; Logs Explorer does not currently expose response-byte data. | Keep the operator Usage/Observability report as billing authority and compare it with sanitized local counters during the bounded canary. | Confirmed: Shared Pooler Egress |
| Connection route | Sanitized backend and worker probes resolve a pooler host on port `5432`. The runtime uses Supabase Session Pooler; `DB_CONNECTION_MODE=direct` controls the application-side SQLAlchemy pool behavior and does not select the Supabase endpoint. | Keep Session Pooler for the current IPv4 deployment. Reduce payloads and repeated queries; do not run an A/B route test solely to change the egress category. | Confirmed; no config change |
| Gemini capacity | Gemini RPM/TPM/RPD limits are project-wide rather than key-wide, vary by model/tier, and active limits are visible in AI Studio. More keys from the same project do not multiply that project quota. | Record the owning project and active model limits in the operator runbook, then enforce a project-aware budget before production-volume work. | Complete: project/model limit evidence recorded |
| R2 request cost | R2 egress is free, but `LIST`/`PUT` are Class A and `HEAD`/`GET` are Class B operations. | Preserve exact-key hot paths and bucket `HEAD` readiness; keep inventory/GC listing off hot paths. | Complete: code gate and evidence boundary recorded |
| Expired activity recovery | Targeted recovery changed the expired NCode row to pending but initially failed to claim it because the recovery mutation was not flushed before `UPDATE ... RETURNING`. | Flush the recovery transaction before the targeted claim and keep a regression test. | Fixed and focused-tested |
| Worker/provider behavior | Three bounded one-chapter samples reached terminal completion through the application service with raw/translated R2 readback; the original full queue remains paused by the safety decision. | Keep the worker stopped after the safety window; resume one target at a time only with database, provider, memory, network, and lease stop gates recorded. | Complete: bounded canary and full-queue safety decision |

The official references used for this checkpoint are [Supabase egress usage](https://supabase.com/docs/guides/platform/manage-your-usage/egress), [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres), [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), and [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/).

### Historical next bounded execution sequence (superseded by the 2026-08-24 continuation)

1. Keep the original full-queue activities paused through the application service; do not restart the unbounded queue as a capacity test.
2. Preserve the completed one-chapter-per-source sample and its application-service artifact readback as the bounded validation baseline.
3. Before any larger run, capture a fresh `pg_stat_statements` aggregate and operator-side Supabase egress report baseline. Treat cumulative database counters as workload indicators only.
4. Measure and remove the synchronous database/storage work inside concurrent async chapter tasks, then repeat a small staged sample with provider, query, R2, and lease metrics.
5. Verify Gemini project/model limits in AI Studio and set a project-level budget lower than the provider limits. Do not infer capacity from the number of API keys.
6. Only after the staged workload is stable, run 1k/10k/100k-DAU-equivalent reader load and separately authorize application-service chapter repair, backup/restore, and production-scale telemetry.

### Operator egress and route evidence - 2026-08-23

The operator-provided Supabase custom report now supplies the missing billing
attribution. Its current window shows `API Egress=0` and a
`Shared Pooler Egress` peak of `66,683,432,737` bytes, approximately 66.68 GB
decimal (62.1 GiB). That is consistent with the organization Usage page's
67.20 GB total and identifies the pooler path as the dominant observed source.
The report's bucket label is offset by approximately one day from the Usage
chart; the exact hover timestamp should be recorded in the next evidence
capture rather than inferred from the axis label.

The sanitized runtime probes show both the backend and worker using a pooler
host on port `5432`. This is Session Pooler mode for the current IPv4
deployment. `DB_CONNECTION_MODE=direct` is an application pool-topology
setting in this repository; the `DATABASE_URL` endpoint determines whether
the connection is direct, session-pooler, or transaction-pooler. No endpoint
or environment value was changed at this checkpoint.

### Session Pooler canary follow-up - 2026-08-23

The rebuilt `novelai-admin:local` image was used for one NCode-only
application-service canary. Temporary process overrides capped Gemini at
12 RPM with provider and chapter concurrency set to 1; no project `.env` value
was changed. The canary selected NCode at retry count 4, renewed its lease, and
remained `running` without a visible chapter-progress transition during the
bounded window.

The sanitized database baseline moved from 1,333,488 cumulative calls and
16,580,767 rows to 1,339,354 calls and 16,585,220 rows. These counters include
the verification queries and are not billed-byte measurements. Container
memory rose from about 117 MiB to 174 MiB, network totals reached about
13.2 MB received and 1.63 MB sent, and `OOMKilled=false` remained true. The
temporary canary was stopped and removed at the safety checkpoint; the
dedicated worker remains stopped. No PostgreSQL row, runtime JSON, canonical
R2 prefix, or endpoint was manually edited.

This run confirms that the Session Pooler route and the rebuilt worker can be
observed under the lower provider cap, but it does not prove terminal
translation or a safe full-queue rate. Further queue execution remains gated
on reducing the repeated database work and obtaining a fresh report hover
timestamp for the next before/after comparison.

### Full-queue stop and 100k-user scale decision - 2026-08-23 15:34 UTC

A later application-service run used temporary provider and chapter concurrency
of `4` against the existing NCode activity. It was deliberately stopped at a
checkpoint after the queue continued to spend an hour-scale window on one
source. The final sanitized chapter projection at the stop was:

| Source | Complete | Failed | Pending | Fetching | Translating | Nonterminal |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NCode | 75 | 19 | 49 | 1 | 4 | 54 |
| Kakuyomu | 9 | 78 | 0 | 0 | 1 | 1 |
| Novel18 | 29 | 2 | 0 | 0 | 0 | 0 |

The worker sample at the final observation was about `224 MiB` resident,
`256 MB` received, `27.4 MB` sent, and up to about `57%` CPU. These are
container-session indicators, not Supabase billed-byte attribution. Graceful
stop did not complete within the stop window, so the dedicated one-shot
container was force-terminated and removed; no PostgreSQL row, runtime JSON,
canonical R2 object, or endpoint was manually edited. The remaining fetching
and translating states must be recovered by the normal expired-lease/application
claim path before another run.

This result is a capacity warning, not evidence that R2 content placement is
wrong. The intended boundary remains: PostgreSQL stores compact catalog/state,
hashes, pointers, queue leases, and projections; R2 stores immutable raw,
translated, and media artifacts. The immediate cost driver is repeated
database-row hydration and synchronous database/storage work inside concurrent
async chapter tasks. Large legacy JSON columns still need a measured migration
or reference-only follow-up where they remain on routine paths; the new
`defer()`/`load_only()` projections reduce hydration but do not by themselves
prove billed-byte savings.

Do not use the full queue as the next acceptance workload. The next execution
gate is a bounded one-to-three-chapter sample for each source, with fresh
before/after `pg_stat_statements` counters, provider timing/token fields, R2
operation counters, queue/lease transitions, and a fixed stop window. Only
after that sample is stable should the workload expand in steps.

For a 100k-daily-user planning model, DAU alone is insufficient. Record active
readers, requests per session, cache-hit ratio, average catalog/detail bytes,
chapters read, translated chapters per day, provider tokens, and concurrent
worker jobs. Keep public reads on cached compact PostgreSQL projections and
exact-key R2/CDN reads; isolate translation workers from the reader connection
budget; batch state writes; and add load tests at 1k, 10k, and 100k DAU-equivalent
traffic before claiming capacity. Supabase's current pricing page lists Pro
at `$25/month` with `250 GB` egress included and `$0.09/GB` overage, while R2
charges storage and Class A/B operations but no direct R2 egress. These figures
must be rechecked at launch and do not include compute, provider, CDN, or
observability costs.

### Bounded three-source sample follow-up - 2026-08-23 15:59 UTC

The three original full-queue activities were paused through
`ActivityQueueService`. Three new one-chapter sample activities were then
created through the same service and executed sequentially at provider and
chapter concurrency `1`. NCode, Novel18, and Kakuyomu each reached
`completed`; application-service readback confirmed raw and translated content
was present for each selected chapter. The sample containers exited cleanly and
the original full queues remain paused. This closes bounded validation only; it
does not claim that the remaining full queues are economical or terminal.

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
- At this Phase 0 checkpoint, `deploy/.env` explicitly contained the one-second value and was intentionally not edited because it was a protected runtime/secrets file. The later Phase 4 health implementation resolved the restart regression without changing that timeout value.
- The development overlay is not a valid production-style startup: its frontend bind mount hides the standalone server and causes `MODULE_NOT_FOUND`. The base Compose file was used for the valid current-image check.
- The local `:local` image tags do not embed an immutable source revision, so a release deployment still needs digest/revision evidence.

The local Phase 0 baseline is signed off: current images, migration, routes, application health, readiness, and one replacement cycle were verified. The timeout caveat was carried into Phase 4, where the no-override readiness path was validated. Phase 1 and Phase 2 implementation are complete locally; Phase 3 execution and review evidence is recorded below.

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

- Carry forward the Phase 0 finding as the pre-Phase 4 diagnosis: the explicit one-second per-probe setting failed under concurrent storage checks; the Phase 4 cache/single-flight implementation then removed the need for a temporary runtime override.
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
  write/read/delete probe and R2 usage scan remain owner diagnostics.
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
- Shard disposable local-runtime entries if a migration is needed, and avoid scanning the entire cache directory on a request path.
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
local runtime gate passes, while production telemetry sign-off remains open.**

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
the admin and reader images. A direct-mode local-runtime control repeated the
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
pre-cutover disposable storage fixture. It seeded 48 published novels, 1,428 projected chapters,
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
were removed and the base Compose stack was restored healthy. A subsequent
sanitized read-only object-storage readiness probe using the real production
environment completed successfully in `0.302 s` (`list_objects_v2` with
`MaxKeys=1`). This proves bounded reachability only, not production-volume
object-storage call, latency, or byte telemetry. Production pooler/query-plan
evidence and worker/provider capacity remain open.

The focused production-configuration validator suite now passes `38` tests.
The source guard computes
`DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
DB_CONNECTION_RESERVE` for direct/session mode and fails closed when it exceeds
`DB_CONNECTION_BUDGET`. The committed split-topology examples use three pool
owners, a two-connection reserve, and budget `32`. The rebuilt admin/worker and
reader images now run in the local base Compose stack with that direct-mode
budget. Configuration-only validation of the real production environment passes
for both admin and reader roles with zero fatal issues and one backup warning;
that validator intentionally does not contact the real production database or
object storage. A separate bounded read-only object-storage probe using the
same production environment returned `ready` in `0.302 s`; representative
storage telemetry, production pooler verification, and provider capacity
remain open.

### Phase 6 gate status

The harness, public route, seeded analytics, proxy-health, provider-failure,
browser, hydration, focused frontend, cleanup, controlled storage-delay, and
classified-capacity-response checks pass for the local sample. Transaction
mode provides a tested local mitigation for the direct-mode database-session
failure, and the local base runtime now uses the explicit direct-mode budget of
`32`. A bounded production object-storage readiness probe also passes, but it
does not provide representative call, latency, or byte telemetry. Production
pooler verification, database query-plan evidence, and representative
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

### Phase 6 continuation: current contract audit - 2026-08-20

The broader contract audit resolved several current-checkout failures. The
production environment example now matches the other environment templates in
non-secret setting order and includes the cache, readiness, translation-limit,
contributor-limit, and activity-bound settings. The home server-prefetch path
now uses the approved public API client while preserving its internal reader
base URL, Host header, revalidation, and bounded cancellation. The review test
fixture now matches the projection-first summary seam, raw-chapter writes
preserve authoritative or existing ordering through projection recomputation,
and catalog reconciliation now accepts numeric source chapter IDs through the
canonical chapter-ID normalizer. The E2E fixture refreshes the real projection
inside the isolated SQLite database rather than bypassing it.

The full frontend suite passed `857` tests across `78` files; frontend lint,
typecheck, and production build passed. The repaired backend contract tests and
public-review/PR41 files passed `56` tests. The complete E2E file passed `5`
tests, and the full slow shard passed `302` tests with `19` skipped. The first
four-worker backend attempt reached `3,240 passed, 26 skipped, 29 failed`; all
failures were in the shared-state `test_web_api.py` module and included
activity-lock contention. That fixture now scopes its filesystem root by
`PYTEST_XDIST_WORKER`, and the module passes both serially (`163 passed in
84.03 s`) and under four-worker xdist (`163 passed in 38.71 s`). The
orchestration fixture now uses a disposable SQLite file inside its unique test
directory instead of a Windows-invalid shared-memory URI. The exact current
full command, launched with an in-repository basetemp after the host temp root
returned `PermissionError`, passes `3,270` tests with `26` skipped in `552.92 s`;
the non-slow and slow shards pass `2,968/7` and `302/19`, respectively. This is
local test evidence only; production pooler/query-plan and representative
worker/provider capacity evidence remain the external Phase 6 gates.

A current read-only proxy recheck confirms port `80` is reachable and returns
`200` for the health, public catalog, weekly rankings, robots, sitemap, privacy,
terms, and legal routes when sent with `Host: localhost`. The local env files do
not define `SITE_DOMAIN`, so Caddy uses its documented `localhost` fallback;
this is local routing evidence only. Supply and recheck the production
hostname before public launch.

The final Compose recheck initially found the `worker` service restarting with
exit code `1` (`23` restarts observed). It runs as `novelai` UID/GID `100:101`,
but the mounted legacy content root was `root:root` mode `755`, so
the worker could not create `activity_log` or temporary provider
credential-hydration files. After explicit authorization, an ownership-only
change assigned the mounted directory to `novelai:novelai`; no storage files
were deleted or rewritten. After a 12-second stability window, all six Compose
services were running, the worker had exit code `0`, no restart loop, and both
the storage root and `activity_log` were writable. Exactly three current Novel
AI application images remain. The local Phase 6 runtime gate now passes;
production hostname, pooler/query-plan, and provider-capacity evidence remain
external launch gates.

## Suggested implementation sequence

1. Complete Phase 0 and rerun the same runtime probes against the current revision. (Complete.)
2. Implement the projection-first catalog/detail path and add request-level object/query-count tests. (Complete locally; numeric chapter-ID reconciliation and the isolated E2E projection fixture are now covered.)
3. Review Phase 1 evidence; the projection-first read path and local chapter projection completeness are now covered, while durable readiness remains an open follow-up.
4. Add browser cancellation/timeouts and reduce home critical fan-out. (Complete locally in Phase 2.)
5. Review Phase 2 evidence and approve the ranking/index/cache work before starting Phase 3. (Complete.)
6. Align ranking indexes, remove summary enrichment fan-out, and add bounded result caching. (Complete locally in Phase 3; production-volume and multi-replica evidence remain open.)
7. Review Phase 3 evidence and approve readiness/cache amplification work before starting Phase 4. (Complete.)
8. Stabilize readiness, cache safe public projections, and decouple analytics writes. (Complete locally in Phase 4; percentile, populated-load, and shared-cache evidence remain open.)
9. Review Phase 4 evidence and approve worker/provider isolation before starting Phase 5. (Complete.)
10. Move translation to enqueue/worker-only execution, then replace file-backed activity/cache hot paths. (Complete locally in Phase 5; provider-volume evidence remains open.)
11. Run the repeatable Phase 6 load scenario and update the budgets using
    measured capacity. (Complete locally; the measured sample and full local suite pass, while production telemetry remains open.)
12. Apply and verify the transaction-mode/aggregate connection budget against
    the target pooler, then rerun Phase 6 with production-equivalent object
    storage and worker/provider telemetry before launch sign-off. (Open external launch gate.)

## Worker egress containment checkpoint — 2026-08-23 (historical; superseded by the 2026-08-24 handoff)

The worker was stopped after the operator reported `57.434 GB / 5 GB` egress
for the billing cycle. That dashboard value is operator-supplied and was not
refreshed through the available database connector. The worker was intentionally
left stopped while the rebuilt query paths were reviewed; no live activity or
chapter row was manually rewritten. The last interrupted activity remains
subject to normal lease expiry and application-level recovery.

Read-only PostgreSQL statistics identified the dominant query families: full
Novel-by-slug reads with `metadata_history_json`, full Chapter reads with media
and translation-version JSON, and repeated activity polling. These statistics
are cumulative database counters rather than billing-cycle byte telemetry, so
they explain the likely egress mechanism but do not prove the exact billed
worker share. Supabase Reports remains the authority for Database/Pooler egress
attribution.

The locally selected corrections are:

- defers `Novel.metadata_history_json` on routine catalog reconciliation and
  defers chapter media/version/edit-history JSON on existing chapter lookups;
- projects translation platform-novel and glossary-revision lookups with
  `load_only()`;
- reuses selected novel metadata, approved glossary entries, and raw chapter
  bundles only within one translation job;
- reuses the activity row returned by the atomic claim in `run-next`;
- uses bucket-level `HEAD` for R2 readiness rather than a probe `LIST`;
- keeps atomic claims, timestamp-only heartbeat updates, and 5-to-30-second
  empty polling, which were already correct; and
- keeps the normal five-minute-lease heartbeat in the 15–30 second window,
  with a shorter-lease branch only for explicitly shortened local/test leases.

The bounded per-job novel/glossary/raw-bundle cache is now implemented with an
invocation lifetime and no cross-job reuse. Its byte impact remains unmeasured
until a terminal workload canary; a process-global or cross-job cache remains
deferred because it would require a separate invalidation contract.

Focused validation passed after the change, followed by the post-patch full
backend suite (`2,904 passed, 16 skipped`), Ruff, Pyright, Compose validation,
and the repository Markdown/link checks. A rebuilt-worker canary was then run against
only the existing NCode activity. It retained a fresh lease but showed no
chapter-state transition during the bounded observations; Kakuyomu remained
pending. The worker was stopped after cumulative statement volume rose from
1,308,671 to 1,322,596 and container traffic rose from 21.6 MB to 59.1 MB
received. These are resource indicators, not billed-byte attribution. Docker
reported exit 137 after the stop timeout, and the activity remains for normal
application-level lease recovery. Production pooler/query-plan, billed egress
attribution, terminal queue outcomes, and representative provider-volume
telemetry remain open.

The first practical gate is not a frontend optimization: it is a current-revision deployment with a healthy reader, healthy readiness, current migrations, and a catalog request that cannot fall back to a serial object-storage scan.

### Post-canary query-payload projection hardening - 2026-08-23 (historical; superseded by the 2026-08-24 handoff)

The translation path now projects only the fields needed for platform-novel
and glossary-revision lookups. Routine catalog saves/reconciliation defer
`Novel.metadata_history_json`; existing chapter lookups defer
`media_state_json`, `translation_versions_json`, and
`translation_edit_history_json`. The bounded per-job cache reuses selected
metadata, approved glossary entries, and raw chapter bundles across discovery,
preflight, and translation, then is discarded with the job.

Focused projection/translation/worker/glossary coverage passed `145` tests,
Ruff and Pyright passed, and the full backend suite passed `2,904` tests with
`16` skips. No environment value changed and the dedicated worker remains
stopped. The latest canary remains nonterminal, so the byte-level egress effect
of these projections still requires a later terminal workload comparison.

## Async execution and capacity handoff - 2026-08-24 (historical checkpoint)

Completed local slices:

- bounded persistence boundary with ownership guards, progress batching,
  idempotent event/chunk replay, queue lease/cancellation/shutdown coverage,
  and explicit rollback configuration;
- bounded runtime telemetry and redaction/provenance tests;
- conservative contributor-pool admission with shared-project quota accounting,
  fair selection, reservation reconciliation/expiry, and secret-free ledger
  attribution;
- fixture-only reader/capacity harness, public correctness matrix, checkpoint
  footprint measurement, and hosted-versus-modeled cost envelope.

Current gate outcomes:

- isolated R2 PUT/GET/HEAD/DELETE benchmark: complete against the separate test
  bucket with 6 live tests and a final paginated zero-object cleanup sweep;
- independent R2 object snapshot and recovery readback: complete with a verified
  980-object, 4,022,175-byte snapshot; encrypted PostgreSQL backup and
  isolated restore also passed with 37 public tables and 0 invalid constraints
  (`artifacts/capacity/pac-8a109a5ad1cd-recovery-evidence.md`);
- bounded source canary: complete with one terminal application-service sample,
  one provider usage-ledger success, and exact raw/translated R2 readback
  (`artifacts/capacity/pac-8a109a5ad1cd-live-canary-gate.md`);
- 1k reader stage: complete execution with a quantified SLO and telemetry stop
  after 50 samples per route, zero transport errors, and non-empty content
  responses (`artifacts/capacity/pac-8a109a5ad1cd-reader-stage-1000.md`);
- 10k and 100k reader stages: complete dependency-safety decision; higher-stage
  traffic was not admitted after the 1k stop, and no provider, R2, or canonical
  content operation was performed (`artifacts/capacity/pac-8a109a5ad1cd-reader-stages-10000-100000.md`).

The current evidence boundary is complete: the local runner recorded the
provider/R2 counter and hosted-billing fields that it could not observe, so
these results do not claim production billing, provider quota, or capacity
success. The worker remains stopped and the original full queue remains
paused by the recorded safety decision.

The recovery drill was repeated after `DATABASE_BACKUP_URL` was synchronized
exactly once into both real deployment environments from the configured
migration connection. The persisted configuration created and restored the
encrypted backup without a process override.

Rollback remains configuration-first: disable
`TRANSLATION_PERSISTENCE_EXPANSION_ENABLED`, stop new admission, drain critical
terminal work within the deadline, and verify state through the application.
Do not claim production SLO, billing, egress, provider quota, or reader
capacity from the local artifacts.

### Reader capacity and recovery follow-up — current checkpoint 2026-08-25

The follow-up specification's execution package is structurally validated, but
its operational disposition is blocked. The latest generated report contains
the complete 3-topology x 5-required-route x warm/unknown-cache matrix; all
cells are explicitly unavailable because no approved fixture/target or
controlled cold-cache method was supplied. `reader_slo_status=blocked` and
`path_profile_status=blocked`; no live 1k sample result is claimed.

All attribution layers and hosted telemetry snapshots are explicitly
unavailable, so no largest contributor or hosted R2/provider billing/quota
value is established and no speculative remediation was applied. Recovery
control tests pass locally, but current backup freshness, alert delivery, and
isolated hosted restore evidence remain unavailable/blocked. The managed
services workflow also references a missing integration-test path. The worker,
original full queue, 10k/100k stages, and production-capacity admission remain
stopped or unadmitted. See
`artifacts/operations/reader-capacity-follow-up/handoff.md` and
`artifacts/operations/reader-capacity-follow-up/validation.md` for exact
blockers and next actions.

### Reader capacity and recovery runtime recheck — retired topology checkpoint 2026-08-27

The local Compose baseline was restored after Docker Desktop had been stopped.
Backend, reader, Caddy, frontend, Redis, and restore-db were healthy, and local
Caddy returned HTTP 200 with an empty body for both `/health/live` and
`/health/ready`. This is a local runtime recovery observation, not production
availability or Cloudflare-edge evidence. This private-network topology is
retired.

The historical campaign `camp-20260827T130658Z` selected `private_network` as
the only reader SLO gate. Its bounded 1k runner invocation produced no live
samples because no approved fixture/target binding or controlled cold-cache
method was available. The 60 route/cache cells are explicit unavailable evidence;
`reader_slo_status=blocked`, `path_profile_status=blocked`,
`telemetry_status=unavailable`, and `production_capacity_claim=not_established`.
The worker stayed absent, while original-queue and other-writer state remain
unobservable. No remediation is selected without non-overlapping layer timing.

The T-011 local quality gates passed, including Pyright, affected Ruff,
focused tests, workflow-path and router checks, semantic artifact validators,
and Graphify. Hosted pooler/R2/provider telemetry, recovery freshness/alert/
restore evidence, release configuration parity, cross-source acceptance,
provider/bulk readiness, production CDN/takedown propagation, actual
credential rotation, and dedicated-host availability remain external gates.

### Reader capacity and recovery runtime recheck - retired topology checkpoint 2026-08-28

The historical campaign is `camp-20260828T042235Z`, with `private_network` as
the selected reader gate. The historical stage artifact
`reader-stage-1000/reader-stage-1000-20260828T042533Z.json` records 60 required
route/cache cells, 30 quantified blockers, and no live samples. The 38
pre-remediation and stage-1000 telemetry records are joinable but explicitly
unavailable. The worker/full queue remain stopped or paused, and the approved
fixture/target, queue/writer observation, controlled cold-cache method,
hosted telemetry, and isolated recovery evidence remain unavailable. The
dispositions are still `reader_slo_status=blocked`,
`path_profile_status=blocked`, `telemetry_status=unavailable`, and
`production_capacity_claim=not_established`. This private-network topology is
retired; see the Cloudflare checkpoint below.

## Reader capacity access decision - current checkpoint 2026-08-29

The active reader-capacity contract now selects `cloudflare_tunnel` as the
non-production Caddy-routed SLO surface. The direct service and Caddy loopback
paths remain diagnostic comparisons. Earlier private-network measurements are
historical and are not a current prerequisite. The supplied fixture is absent
from the Cloudflare development origin. The bounded read-only run recorded
50 warm samples per required route, with liveness/catalog/search over budget
and detail/chapter returning HTTP 404; controlled cold-cache evidence remains
unavailable and no production-capacity claim is established.

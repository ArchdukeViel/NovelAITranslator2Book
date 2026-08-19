# Performance Audit: Public Read and Translation Stack

**Initial audit:** 2026-08-19
**Phase 0 update:** 2026-08-20
**Repository revision:** `8048306` (`perf/debt-079d-public-path-hardening`)
**Scope:** browser-to-Caddy traffic, the public reader API, database access, object storage, Redis/queues, translation workers/providers, and the public Next.js client.

## Executive conclusion

The initial runtime was behind the checkout and allowed public storage waterfalls. Phase 0 rebuilt and deployed the current checkout locally; Phase 1 now makes the public catalog/detail metadata path projection-first. The current local runtime is healthy with the documented readiness override, but the live serving projection still needs storage-backed chapter reconciliation. The largest remaining risks are:

1. The original runtime was older than the checkout; the local Phase 0 deployment now uses freshly built local images, but those tags do not carry an immutable source revision.
2. Live projection repair is storage-latency-bound: the bounded reconciliation attempt exceeded 180 seconds, and the current live database still has zero chapter projection rows. Public chapter metadata therefore returns a truthful unavailable response until maintenance succeeds.
3. Caddy repeatedly attempted stale backend container addresses during container replacement, producing connection-refused errors and making availability look like latency.
4. The public home page still starts several client-side requests before it can render useful catalog content. There is no server-side initial-data hydration for these public queries, and the catalog request asks for 100 novels.
5. Rankings and novel summaries can combine database aggregation with per-novel summary/storage calls. The current analytics indexes do not match the ranking filters and distinct-viewer grouping.
6. Translation work can occupy a web request for up to the configured 120-second timeout. Provider calls also use blocking SDK calls in worker threads, bounded concurrency, retries, and quota reservation, so provider latency can create sustained backpressure.

The remaining release/operations problem is durable readiness configuration: the application and Caddy are healthy locally only with an explicit two-second probe override because the protected runtime file still carries the one-second budget. The highest-value Phase 1 application change is complete locally: published public reads now use the database projection and do not enumerate object storage on normal requests.

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

Phase 0 was executed against the local Compose environment and is **complete as the local baseline**. The Phase 1 execution update below records the subsequent public-read changes and review gate.

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

Phase 1 implementation is complete in the checkout and the focused backend acceptance suite passes. The phase is **stopped for review before Phase 2**.

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

## Public request waterfalls

### Home page

The current `frontend/app/(public)/home/page.tsx` is a client component. A guest home load can request:

```text
home shell
  ├─ catalog: 100 newest novels
  ├─ rankings: selected period, limit 5
  ├─ rankings: weekly widget, limit 5
  ├─ genres/taxonomy
  └─ public auth/session
       └─ authenticated users: history after auth is known
```

React Query deduplicates calls that share a query key, including the repeated auth calls from shell components, but it does not remove the catalog, genre, and two ranking dependencies. There is no server-side prefetch/dehydrate path for the public page. The home page then sorts the 100-item catalog and computes genre counts in the browser. That CPU work is small compared with the API and storage waits, but the data volume and request fan-out increase the time to useful content.

### Ranking page and widget

`frontend/app/(public)/ranking/ranking-client.tsx` requests up to 50 rows for the selected period. The home page separately requests the selected period and weekly results. The ranking API is cacheable for 60 seconds at the HTTP layer, but `PublicRankingService` has no server-side result cache and enriches each result with a public novel summary. A ranking response can therefore be:

```text
two distinct-viewer aggregation queries
  → published-novel lookup
  → up to limit public-summary calls
       → database projection or object-storage fallback
```

### Novel detail and chapter list

`frontend/app/(public)/novels/[slug]/page.tsx` requests the novel summary, chapter list, taxonomy, and authenticated progress. The detail handler records an analytics event and deliberately uses private caching for a newly issued anonymous identity. The chapter-list handler resolves the novel, checks takedown state, lists translated chapters in object storage, and maps metadata. This is a storage-bound path even when the page itself is mostly metadata.

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

**Evidence:** `PublicRankingService` runs separate authenticated and anonymous distinct-viewer aggregations, filters by event name and time, groups by novel, merges in Python, then enriches results with up to `limit` catalog summaries. Live analytics indexes were single-column indexes; there was no session identity index or composite index covering event name, time, novel, and viewer identity.

**Impact:** As analytics grows, the database must filter and sort more rows before grouping. Summary enrichment adds storage/database work after aggregation. Current analytics is disabled and empty, so this risk is not visible in the current runtime.

**Recommendation:** Add and validate a composite index matching the actual ranking predicate and grouping, plus an index for the anonymous identity column used by the source. Prefer a rollup table or scheduled hourly/daily aggregates once event volume warrants it. Return unavailable when analytics is disabled, as the current contract requires, and cache successful ranking results for a bounded period.

**Confidence:** Current-source and live query-plan corroborated.

### F-10 — P1 — Readiness performs a storage write/read/delete probe without an effective cache

**Evidence:** `HealthService` contains cache fields but the current implementation does not use them to cache the readiness result. `StorageService.probe()` writes a random health-check object, reads it back, compares it, and deletes it through object storage. During Phase 0, ten isolated probes all returned true in roughly `486–640 ms`, but the actual concurrent health run timed the storage probe out at its `1,000 ms` per-probe limit while storage-usage work took about `1,559 ms`; the readiness endpoint returned `503`. With an explicit `HEALTH_PROBE_TIMEOUT_MS=2000` process override during the Phase 1 runtime check, readiness returned `200` and Caddy became healthy; the protected one-second configuration remains a restart-regression risk.

**Impact:** A transient object-store delay can make readiness fail and can also consume storage operations on every probe. Proxy health checks then amplify the issue. A slow provider or storage service can cause deploy/restart churn.

**Recommendation:** Treat this as a Phase 0 release gate and Phase 4 implementation item: persist a readiness budget that covers the observed concurrent storage work, cache readiness for a short bounded TTL, avoid running two expensive storage operations in the same readiness window, use a cheap bounded probe for liveness/readiness, and keep the full write/read/delete diagnostic in an owner-only or scheduled diagnostic path. Preserve the 3-second total budget and expose the last-known state with a timestamp internally, without leaking paths or credentials. The 2,000 ms runtime override made the current local gate pass, but the protected `deploy/.env` still requires an operator-approved durable update.

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

### F-16 — P1 — Server cache headers exist, but result computation is not memoized

**Evidence:** Catalog, ranking, and chapter responses emit short public cache headers. `PublicRankingService` has no service-level cache, and catalog/detail summaries can still compute storage-derived values before the response is cacheable.

**Impact:** Cache misses and cache revalidation repeatedly pay the full database/storage cost. A 60-second header is not a substitute for a bounded origin cache when the origin path can exceed the request timeout.

**Recommendation:** Add a small bounded server/Redis cache for immutable or versioned public projections, invalidate on publish/takedown/generation changes, and include projection version in cache keys. Measure hit ratio and origin calls, not just response headers.

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
- The contributor/ranking migration is now applied locally; production-equivalent permissions and deployment migration procedure remain unverified.
- Readiness and Caddy pass locally only with the explicit 2,000 ms runtime override; the protected `deploy/.env` still contains the one-second value, so a fresh restart can regress until the durable configuration/health implementation is approved.
- Object-storage timing was measured in the existing deployment, but no destructive or production data operation was performed.
- The browser check with the wrong host was intentionally treated as invalid for API performance; only configured-host proxy timings were used.
- No claim is made here about provider-side latency without a controlled provider workload and provider telemetry.

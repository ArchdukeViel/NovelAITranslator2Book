---
title: Operations
document_role: procedural
authority: canonical
scope: health queue control maintenance backup restore cleanup incident response and operational evidence procedure
audience:
  - agents
  - operators
  - developers
update_triggers:
  - runbook changes
  - health or queue-control changes
  - backup restore or cleanup procedure changes
owned_concerns:
  - operations-runbooks-and-recovery
---

# Operations

This document owns authorized operational procedures, safety gates, health checks, queue control, backup/restore, cleanup, and incident coordination. It does not own deployment topology, application architecture, secret values, or dated result claims.

Current state: destructive and recovery procedures are test-target guarded, fail closed on missing evidence, and require sanitized evidence capture; worker and full translation queue state remains independently controlled.

Related contracts: [`DEPLOYMENT.md`](DEPLOYMENT.md), [`CONFIGURATION.md`](CONFIGURATION.md), [`STORAGE.md`](STORAGE.md), [`STATUS.md`](STATUS.md), and [`EVIDENCE.md`](EVIDENCE.md).

Maintenance: every destructive procedure must retain target isolation, preconditions, abort conditions, cleanup, verification, and evidence requirements.

Solo-owner runbook for health, maintenance, backup, recovery, incidents, and reader budgets. For topology, environment setup, and release procedures, see [`DEPLOYMENT.md`](DEPLOYMENT.md). Never record secret values in evidence.

## Managed test database verification

`MANAGED_DATABASE_TEST_URL` is reserved for the disposable Supabase project
named `testdatabase=dokushodo`. It may use the Supabase session pooler, but it
must never point at the active application database. The strict hosted
verification workflow does not apply migrations automatically; this preserves
stale-schema detection.

When the candidate schema must be created or refreshed, run the manual
confirmation-gated `nonproduction-managed-services.yml` workflow with
`migrate_test_database=true` and `confirm_test_database=true`. It calls
`.github/workflows/reusable-test-database-migration.yml`, which runs Alembic once
with the privileged `MIGRATION_DATABASE_URL` variable and does not start an
application or worker. After it succeeds, run the same verification workflow
again with migration disabled for the observed database and R2 checks, then
leave `MANAGED_SERVICE_TESTS_ENABLED=false`.
Record only the workflow URL, commit, UTC timestamp, pass/skip/fail counts,
and sanitized schema evidence; never record the URL or its credentials.

The candidate migration `f8a2c4e6b0d1` also conditionally revokes Data API
execution on the optional Supabase `public.rls_auto_enable()` security-definer
helper. It does not create the helper, alter application rows, or restore broad
execution on downgrade. After a test-database migration, rerun the Supabase
security advisor and record only the sanitized lint result; do not paste ACL
or connection-string details into evidence.

## Managed non-production recovery verification

`nonproduction-managed-services.yml` is the manual, confirmation-gated entry
workflow for the disposable `testdatabase=dokushodo` project and the dedicated
test R2 target. Its recovery job calls
`.github/workflows/reusable-test-recovery.yml`, which creates a temporary
backup-capable database role for the run, generates the database-backup
encryption key in the runner, uses the existing `DatabaseBackupService`, and
restores into an ephemeral local PostgreSQL service. The run uses a unique R2
prefix and removes the temporary role and test objects before recording
sanitized evidence.

The recovery runner uses a pinned PostgreSQL 17 client container so the dump
client matches the managed database major version. Its generated encryption
key is masked at the runner boundary and is never part of the evidence. A
restore archive is mounted read-only into that client container. A failed
restore records only a fixed diagnostic class and deletes raw client
diagnostics before evidence publication.

Run the registered workflow only with `confirm_test_recovery=true`; there is no
repository-variable fallback. The workflow refuses the canonical production
bucket names and refuses a non-local restore target.
Its success proves one current isolated backup/restore path and representative
schema/public-isolation checks; it does not prove recurring production backup
freshness, operator alert delivery, or production recovery readiness. Keep the
worker/full queue paused and leave `MANAGED_SERVICE_TESTS_ENABLED=false`.

## Disposable reader-capacity evidence

`.github/workflows/nonproduction-reader-evidence.yml` is the confirmation-gated
path for the bounded reader-capacity follow-up. It uses the existing
`MANAGED_DATABASE_TEST_URL` Supabase session-pooler secret and the test R2
application credentials, while binding the application fixture to the dedicated
`test-dokushodo` bucket. `test-dokushodo-backup` remains reserved for recovery
verification; the reader run does not write the canonical `dokushodo` or
`dokushodo-backup` buckets.

The workflow applies candidate migrations, seeds the explicit synthetic
`reader-fixture-test-v1` fixture (`test-novel`, chapters `456` and `457`), and
always cleans the exact fixture rows and R2 namespace. It starts an isolated
Compose project with worker, provider, analytics, and translation expansion
disabled, exposes only its internal Caddy listener through an ephemeral
Cloudflare quick tunnel, waits for that tunnel to return HTTP 200 from the
isolated `/health/live` route, and runs the bounded reader profile. The profile
records the Cloudflare SLO-gate cells plus a Caddy-loopback diagnostic target
with an explicit `localhost` Host binding, 50-count warm cells, and 50-count
cold cells; each cold cell is
preceded by `reset_reader_cache.ps1`, which flushes only that project's Redis
database, restarts only its reader service, waits for reader health, and emits a
sanitized reset proof. The reset receives the same disposable `deploy/.env` as
the Compose stack, and fixture cleanup is retained as a separate sanitized
artifact record.

Each route cell also records coarse sanitized error-class counts (`connect`,
`transport`, `timeout`, `redirect`, and `other`) when the underlying runner
exposes an error name. These counts are diagnostic only; they never convert an
unavailable or incomplete Cloudflare gate cell into a passing result.

### B7 MCP observation boundary

The external Supabase and Cloudflare MCP servers are read-only observation
surfaces for B7. After calling the approved MCP endpoints, pass only bounded
scalar results to:

```powershell
\.venv\Scripts\python.exe tools\capacity\capture_b7_mcp_snapshot.py ...
\.venv\Scripts\python.exe tools\capacity\validate_b7_mcp_snapshot.py artifacts\operations\reader-capacity-follow-up\b7-mcp-snapshot.json
```

The bridge requires the exact candidate/baseline join, zero fixture rows,
zero objects under the approved application and recovery prefixes, and both
test bucket classes. It stores no project or tunnel identifiers, URLs, SQL,
object names, provider responses, credentials, or request data. Security and
performance advisor counts, RLS/activity aggregates, DNS/TLS/tunnel posture,
and bounded R2 prefix counts remain distinct from reader timing and billing.
Unavailable MCP permissions or provider granularity are recorded as `unavailable`; they never become zero measurements or a capacity pass. The current snapshot is blocked until an authorized test identity is available and accepted by the protected gateway, queue/writer state and isolated runtime are independently proven, and the disposable quick-tunnel liveness gate is ready.

### B7 blocked-evidence completeness

When B7 stops before fixture creation because its safety or hosted-runtime
prerequisites are unavailable, create the complete local, candidate-bound
blocked bundle with:

```powershell
\.venv\Scripts\python.exe tools\capacity\capture_b7_blocked_bundle.py
\.venv\Scripts\python.exe tools\capacity\validate_b7_blocked_bundle.py --root artifacts\operations\reader-capacity-follow-up
```

The generator is provider-free and write-free. It emits explicit zero-attempt,
unavailable, or not-run records for the frontend, load generator, pipeline,
database/R2 microprofiles, security lane, writer state, recovery, cleanup,
final validation, artifact manifest, and JSON handoff. It binds every record to
the current baseline campaign and candidate revision, retains the exact reader
and frontend arithmetic, and keeps `production_capacity_claim` at
`not_established`. This bundle is completeness evidence only; it does not
replace the hosted B7 run or prove capacity, recovery, billing, or production
readiness.

The uploaded artifact is retained for seven days and contains sanitized route,
cache-state, reset-proof, and disposition data only. A successful workflow or
valid blocked report is non-production evidence: it does not change the named
`dev.dokushodo.online` tunnel, prove hosted billing/queue telemetry, or establish
production reader capacity.

### Current B7/B1 read-only reconciliation - 2026-09-01

The current read-only refresh is bound to candidate SHA 1fd16737e1485a7117e11d45019a78212597ee59. The exact non-production gateway hostname is attached to the test Worker and the latest Playwright MCP request at 2026-08-31T23:22:42Z again returned HTTP 403 from Cloudflare Access. The authenticated Cloudflare dashboard showed the named test Access application selecting the test Worker production/preview destination and service-auth policy labels for the R2 and recovery classes; its Worker Domains view also showed the exact public custom-domain mapping. This proves edge enforcement and the application-to-Worker mapping only; the available browser session is not an application or recovery service identity, and the exact four workflow credential values/scopes were not inspected or verified.

The exact test Supabase project is active and healthy. Its current inventory has two migrations, 37 public tables with RLS enabled, zero security-advisor findings, 101 informational external performance findings, 12 aggregate sessions with one active, four idle, and seven null-state sessions, and pg_stat_statements enabled with 2,741 visible statement rows. Current aggregate table statistics are 246 estimated live rows and 107 estimated dead rows; they are not fixture-cleanliness evidence.

Both exact test R2 bucket classes are present and each currently lists zero objects, one lifecycle rule, and no custom domains. CORS reads were unavailable. The single account tunnel is down. A later local runtime recheck found Docker engine 29.7.2 reachable, local Caddy and direct-reader liveness at HTTP 200, the dedicated worker stopped, and bounded local RQ queue aggregates at zero. The running Compose environment is nevertheless development-bound to the production application R2 bucket class and lacks the fixture guard and both test gateway identities, so it cannot be used for test fixture writes or hosted timing. Queue/writer quiescence for the approved isolated test campaign, disposable Quick Tunnel liveness, exact provider telemetry, and cleanup or recovery evidence remain blocked. One explicitly authorized test-only recovery workflow dispatch is recorded below; no provider setting, credential, or production resource was mutated.

The B7 read-only preflight and MCP snapshot were subsequently recaptured at
candidate SHA 1fd16737e1485a7117e11d45019a78212597ee59, followed by the
provider-free blocked-bundle generator. The preflight, MCP snapshot, and
blocked-bundle validators exited 0, and the aggregate quality-gate runner
exited 0 for the specification, static checks, focused profile/recovery/restore
tests, router/workflow/path guards, every B7 artifact validator, and Graphify.
The generated handoff contains zero profile samples and keeps reader SLO,
path, frontend, pipeline, security, recovery, cleanup, and overall status
`blocked`; telemetry is `unavailable`. This is a valid blocked completeness
bundle and does not authorize fixture creation or imply hosted capacity.

### Current hosted test-only recovery attempt - 2026-09-01

The authenticated GitHub UI dispatched `Non-production Managed Services` once
at candidate SHA 1fd16737e1485a7117e11d45019a78212597ee59 with only the exact
test-recovery confirmation enabled. Run [33452702858](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33452702858)
failed in `isolated-managed-recovery`; its hosted-postgres-and-R2 job was
skipped because the database-migration confirmation was disabled.

The sanitized uploaded artifact records `failure_stage=create_backup`,
`failure_class=R2GatewayError`, and `production_mutation=none`. Backup,
manifest/checksum/freshness verification, restore, representative queries,
and public isolation were not run. Temporary database-role cleanup passed;
R2 cleanup and overall cleanup failed with `R2GatewayError`. The hosted log
shows the required secret names as masked environment entries, but that is
only nonempty propagation evidence and does not validate values, scopes, or
the application/recovery policy path. Treat recovery as `failed` for this
run and keep all dependent B7/B8 lanes blocked until the gateway failure is
diagnosed and a fresh test-only result passes.

### Latest hosted test-only recovery rerun - 2026-09-01

The authenticated GitHub UI dispatched the recovery-only workflow at candidate
SHA `bf1ecb2b103362078da057a861af728bd4d9cb97`. Run
[33467821883](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33467821883)
failed after 1m27s in `isolated-managed-recovery`; the
`hosted-postgres-and-r2` job was skipped. The sanitized artifact reports
`failure_stage=create_backup`, `failure_class=R2GatewayError`,
`failure_status=403`, `failure_error_code=http_error`, and
`production_mutation=none`. Backup, manifest, checksum, freshness, restore,
representative-query, and public-isolation were not run. Temporary role
cleanup passed; R2 and overall cleanup failed with the same error.

The GitHub staging page shows the four test client-id/secret names, each last
updated about 14 hours ago. The selected Cloudflare recovery token is enabled,
was created/updated about 2 hours ago, and reports `Last Seen: 2 hours ago`.
This is not valid credential-pair evidence; do not rerun until the current
test pair is securely re-saved. Keep B7/B8 recovery and all dependent lanes
blocked, and keep `production_capacity_claim=not_established`.

### Prior disposable profile checkpoint - 2026-08-29

The follow-up rerun [33259176327](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33259176327)
completed after the workflow added a tunnel-readiness smoke check and a
loopback Caddy diagnostic target. The readiness check returned HTTP 200 before
sampling. Its 20 Cloudflare cells attempted 1,000 requests with 850 valid
samples, zero transport errors, 144 timeouts, nine passing cells, eight failed
cells, and three unavailable cells. Its 20 Caddy diagnostic cells attempted
1,000 requests with 800 valid samples, zero transport errors, 189 timeouts, ten
passing cells, six failed cells, and four unavailable cells. The Cloudflare gate
remained blocked because the required health/catalog/detail budgets were
exceeded and chapter/search cells were incomplete; the Caddy comparison shows
the same origin-side latency/timeout pattern.

The run recorded 20 controlled cold-reset proofs and completed guarded cleanup.
Independent Supabase and Cloudflare MCP checks confirmed zero fixture rows in
the disposable managed database, zero objects under `novels/123/` in
`test-dokushodo`, and zero `recovery-` objects in `test-dokushodo-backup`.
The worker remained stopped, queue/writer state remained unknown, hosted
reader-window telemetry was unavailable, recovery was not assessed in this run,
and production capacity remains unestablished. The named durable development
tunnel was down with zero connectors at the control-plane check; the disposable
quick Tunnel passed independently. The readiness fix removes the earlier
tunnel-startup transport ambiguity; it does not make the slow or incomplete
reader routes a capacity pass.

The Supabase test-project advisor and aggregate SQL checks were read-only. The
Cloudflare zone analytics call was unavailable, zone latency had no usable
payload, and account-level R2 metrics lacked exact test-bucket/window
granularity. These provider limitations remain explicit unavailable evidence.

### Current reader workflow disposition - 2026-08-30

The latest complete bounded reader workflow [33293251855](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33293251855)
completed the 1k matrix, controlled cold resets, and guarded cleanup at the
candidate revision. The isolated Cloudflare quick Tunnel reached the liveness
endpoint, but its SLO cells remained blocked: health p95 was 143.075/377.958
ms warm/cold, catalog p95 was 4578.523/5276.454 ms, detail p95 was
6763.523/7352.754 ms, search p95 was 7558.691/8908.098 ms, and chapter
warm/cold cells were unavailable. All artifact validators passed, but the
sanitized result remains quantified non-production evidence with
`reader_slo_status=blocked`, `path_profile_status=blocked`,
`telemetry_status=unavailable`, `recovery_status=not_assessed`, and
`production_capacity_claim=not_established`.

Earlier telemetry-enabled attempts [33286324252](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33286324252),
[33286713872](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33286713872),
and [33287228638](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33287228638)
stopped before a complete profile: one hit the Linux PowerShell telemetry
boundary and two exhausted bounded anonymous quick-tunnel readiness retries.
The Cloudflare MCP can verify the durable named development tunnel and DNS
route, but it cannot repair an anonymous quick-tunnel session. Do not replace
the required isolated quick tunnel with the durable route or treat readiness as
capacity evidence. Keep the worker and original full translation queue
stopped/paused.

The current workflow pins `actions/upload-artifact` to v7.0.1, so the earlier
Node.js 20 deprecation warning belongs to the old run and is not a current
workflow configuration issue.

## B4 timing and authorization diagnostics

Phase B4 uses the fixed internal timing contract in
`backend/src/novelai/services/timing_contract.py`. It keeps application,
database, R2, cache, proxy, and pipeline observations separate, records
parent/child intervals, and subtracts child unions only when the same
monotonic clock proves safe nesting. Public responses and public metrics do
not expose these spans. Framework serialization and managed-pool checkout
remain unavailable unless a measurement boundary can observe them without
mislabeling server or network time.

The local diagnostic command generates only sanitized evidence and performs no
provider or runtime writes:

```powershell
python tools/capacity/run_b4_local_diagnostics.py
python tools/capacity/validate_b4_diagnostics.py --self-test
python tools/capacity/validate_b4_diagnostics.py
```

The required evidence files, including the machine-validated `checkpoint-B4.json`,
are written under the ignored `artifacts/public-hosted-execution/` directory.
The run contains the fixed
guest/user/owner/runtime/migration/R2/MCP/workflow authorization matrix, the
15 reader timing cells, four database cells, 18 native-R2 cells, and a
fixture-only pipeline diagnostic with three warmups plus 30 measured
two-chapter runs. The local pipeline uses a mock provider and in-memory
objects only; it is not hosted capacity evidence. The worker is stopped and
the full translation queue is paused in the evidence contract.

The current B4 disposition is blocked: test database runtime-role reads and
writes were not separately authorized, the protected R2 gateway was not
authorized/configured for microprofiling, exact-window provider telemetry is
unavailable, and four security cases require a separately authorized hosted
identity probe. Do not apply a performance fix from this diagnostic alone.
Promote the required test-only authorizations and isolated endpoints before
running hosted microprofiles; keep production resources untouched.

## B5 Dependency Reconciliation and Candidate Checkpoint - 2026-08-31

The dependency reconciliation audited all 58 Dependabot proposals currently
visible for the repository: 14 open, 44 closed, and 38 closed without a merge.
Each proposal has a disposition in the sanitized
`artifacts/public-hosted-execution/dependabot-ledger.json`; closed status was
not treated as proof that an update had landed. The obsolete boto3/moto/S3
proposals are classified as superseded by the hard R2-only cutover.

The candidate uses the regenerated Python locks, frontend and Worker npm
locks, Python 3.14.7, Node.js 26.8.1, immutable workflow action references,
and immutable container image references. TypeScript 6.0.3 and ESLint 9.39.5
remain explicit compatibility holds because their current peer constraints do
not admit the next major releases. No provider, production resource, secret,
or repository variable was changed. The Worker dry run is test-environment
only, and the worker/full translation queue remains stopped/paused.

The sanitized B5 evidence set is `dependency-validation.json`,
`candidate-manifest.json`, and `publication-audit-candidate.json` alongside
the Dependabot ledger (the validator uses the repository's established
artifact names). The candidate is eligible for the next private hosted phase
only after the exact candidate commit is verified; dependency changes after
that point invalidate affected B4 evidence and return the work to B5.

## B6 Private Hosted Audit and Publication Gate - 2026-08-31

The private hosted audit is a read-only GitHub-control and candidate-run
evidence step. It queries the exact candidate SHA for required workflow runs,
job/step timing, branch protection, rulesets, Actions policy, runner inventory,
fork approval, environments, Pages/packages, OIDC, Apps, hooks, and deployment
inventory. The audit stores only bounded statuses, counts, booleans, labels,
durations, and URLs; command failures and raw provider responses are discarded.

Generate and validate the sanitized set from the repository root:

```powershell
& .venv\Scripts\python.exe tools\capacity\run_b6_private_hosted_audit.py `
  --repo ArchdukeViel/NovelAITranslator2Book `
  --pr <private-candidate-pr> `
  --candidate-sha <exact-candidate-sha>
& .venv\Scripts\python.exe tools\capacity\validate_b6_private_hosted_audit.py --self-test
& .venv\Scripts\python.exe tools\capacity\validate_b6_private_hosted_audit.py
```

The required candidate workflows must execute on GitHub-hosted Ubuntu. A run
that fails before runner assignment or has zero steps is blocked evidence, not a
workflow pass. A zero registered self-hosted runner count is recorded separately
and does not prove hosted availability. Do not reroute these workflows to a
persistent self-hosted runner.

Keep the repository private unless a separate visibility authorization names this
repository and authorizes the transition. Without that authority, leave the
visibility transition, protection-after verification, public-main reruns, and
external-fork proof as `not_run`; do not use a green independent security scan
as a substitute. The B6 gate does not establish reader capacity, hosted
telemetry, recovery completeness, or production readiness.

## Health

| Endpoint                | Expected behavior                                                                                                            |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `GET /health/live`      | Process-only, unauthenticated, always 200; no dependency calls.                                                              |
| `GET /health/ready`     | Redacted, short-TTL cached/single-flight DB/lightweight-storage/worker/disk probes; 503 when the cached result is unhealthy. |
| `GET /api/admin/health` | Owner-only detailed but redacted probe status and latency.                                                                   |

States: `healthy`, `degraded`, `unhealthy`. Investigate stale worker heartbeat,
DB connectivity, storage reachability/capacity, and disk before restart. Public
readiness does not perform a mutating storage probe or R2 usage enumeration;
`/api/admin/health` remains the fresh owner diagnostic for those checks.
Public health output never includes paths, hosts, credentials, or traces.

### Database connection capacity

Treat `DB_CONNECTION_BUDGET` as a deployment-wide limit, not only a single
web-process setting. Account for every backend, reader, worker, migration, and
operator process using `DB_POOL_SIZE + DB_MAX_OVERFLOW`, then reserve capacity
for readiness and emergency access. Verify the resulting aggregate against the
managed pooler before changing `DB_CONNECTION_MODE` or scaling a service.
Set `DB_POOL_PROCESS_COUNT` to the number of long-lived pool owners and
`DB_CONNECTION_RESERVE` to the migration/readiness/operator reserve. Direct and
session startup now fails closed when
`DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) +
DB_CONNECTION_RESERVE` exceeds `DB_CONNECTION_BUDGET`. The current split
Compose example therefore requires `32` for three processes with pools of
`5 + 5` and a reserve of `2`; change the count and budget together when
scaling or changing topology. Transaction mode still requires direct pooler
concurrency verification because `NullPool` removes the fixed SQLAlchemy pool
ceiling rather than proving a managed-pooler limit.

When a recognized SQLAlchemy pool/server-capacity failure occurs, the API
returns `503 DATABASE_CAPACITY_EXHAUSTED` with sanitized retryable details.
Unrelated database errors remain internal failures. A capacity response is a
signal to reduce admission or correct the pooler budget; do not hide it by
raising pool timeouts or enabling unbounded overflow. Record the affected
service, UTC window, status counts, and sanitized pooler evidence without
recording connection URLs, credentials, cookies, or raw traces.

Readiness defaults to a five-second cache (`HEALTH_CACHE_TTL_SECONDS`). The
first request after expiry performs one bounded probe run and concurrent
requests join it. Inspect
`novelai_readiness_cache_hits_total`,
`novelai_readiness_cache_misses_total`,
`novelai_readiness_cache_entries`, and
`novelai_readiness_cache_age_seconds` in the owning backend metrics. A
healthy cache result is not proof that storage remains healthy after its
timestamp; investigate repeated refresh failures rather than disabling the
cache or increasing probe timeouts blindly.

## Worker, Scheduler, and Maintenance

- Check owner worker/scheduler status and `SchedulerRuntimeState` heartbeat,
  last result, cooldown/exhaustion, and next eligible run.
- Scheduled jobs use cron/timezone evaluation and renewable PostgreSQL leases.
- Local disk is runtime-only; it is never used for canonical novel content or
  retention. Redis/Valkey owns distributed leases and coordination.
- Generation activation verifies immutable R2 objects and changes the active
  PostgreSQL reference with optimistic concurrency. There is no R2 pointer
  object, filesystem compare-and-swap, or local-generation fallback.
- Explicit operator recovery from a failed generation activation uses
  `commit_generation_recovery(reason=..., evidence=...)` — both arguments are
  required non-empty strings that are logged for audit. This bypasses the
  strict validation gate and must only be invoked after isolated verification.
- Maintenance cleans allowlisted cache/events/activity/runtime-state roots and
  applies backup retention. Use dry-run before changed cleanup policy.
- Never reintroduce APScheduler.

### Long-running scrape and resume

`POST /api/admin/{novel_id}/scrape` is an enqueue operation and returns
`202 Accepted` with an `activity_id`; it does not wait for metadata or chapter
fetching to finish. The durable `scrape` activity runs metadata reconciliation
and chapter acquisition in one worker lease, renewing its heartbeat and
preserving the standard staged-generation validation, activation, and rollback
behavior. Resume of an interrupted onboarding flow queues a durable chapter
activity using the same contract.

Poll `GET /api/admin/activity/{activity_id}` for the redacted status record.
With a worker disabled, an owner can execute one queued record through
`POST /api/admin/activity/{activity_id}/run`; with the worker enabled, the
background runner claims it. A request/network timeout applies to each
individual outbound operation, while the activity lease and heartbeat govern
the total crawl duration.

### Long-running translation

`POST /api/admin/{novel_id}/translate` returns `202 Accepted` with
`activity_id` and `status=pending`; it never waits for provider calls or
translation artifact commits. Supply an `Idempotency-Key` when a client may
retry the enqueue request. Without one, the server derives a stable key from
the non-secret operation parameters. Poll
`GET /api/admin/activity/{activity_id}` and use the existing activity run,
cancel, retry, and lease status controls.

The Compose `worker` service is the normal execution owner. Keep
`JOB_WORKER_ENABLED=false` explicitly on both web services so the admin/reader
processes do not duplicate provider work; do not rely on a shared environment
file to provide that override. Before a repair or image recreation, verify the
effective flag in `backend`, `reader`, and `worker`, and verify that only the
dedicated worker owns the `novelaibook worker` process. The activity queue is
backed by the `activity_records` table; claims are row-locked, expired leases
are recovered, and bounded history/metadata limits prevent queue state from
growing without control. Monitor `novelai_activity_queue_age_seconds`,
`novelai_activity_queue_operation_total_ms`, and the activity status gauges.
The worker heartbeat renews from an independent daemon thread, so synchronous
provider or orchestration work cannot starve lease renewal; the focused worker
test covers this failure mode. After a code rebuild, verify the running worker
image before relying on the correction for multi-worker recovery.

The worker protects managed-database egress on the translation hot path. Claims
use one atomic returning update, the `run-next` path reuses that returned row,
heartbeats write only lease timestamps, and empty-queue polling backs off from
5 to 30 seconds. Routine catalog reconciliation defers the large novel
metadata-history JSON. A broader per-job metadata/glossary/raw-bundle cache was
not selected because the live audit did not establish a safe repetition or
invalidation baseline. If Supabase egress rises unexpectedly, stop the worker
before investigating:

```powershell
docker compose -f deploy/compose.yml stop --timeout 5 worker
docker compose -f deploy/compose.yml ps worker
```

Then inspect Supabase **Reports → Database / Pooler Egress** and compare the
time window with sanitized application query/operation metrics. `pg_stat_*`
views can identify query volume and rows but do not provide an exact billing
byte attribution; do not claim a precise worker share without provider-side
egress evidence. Do not restart the worker until the query-shape fix is built,
validated, and the operator has reviewed the remaining queue state.

When a worker is interrupted, repair chapter state through the activity and
storage services or the documented activity retry controls. Do not hand-edit or
delete `data/runtime/chapter-state` or checkpoint JSON files. A stale lease
should be allowed to expire and be recovered by the queue; a terminal QA or
provider failure should remain visible for review rather than being relabeled
as translated.

Provider overload should surface as queue age, bounded retry delay, or a
truthful paused/failed activity—not as an unbounded web request. Owner Gemini
uses global RPM/TPM/RPD and in-flight limits. Contributor credentials use the
same dimensions per credential and remain isolated from owner-only jobs.
Provider timing counters include admission wait, execution, retries, quota
reservation, and usage-ledger write time; they intentionally contain no
prompt or credential data.

The translation cache's JSON entries are indexed by a SQLite WAL sidecar.
Only initialization/backfill may scan the cache directory. Invalidation,
statistics, and eviction operate on indexed metadata. If the sidecar is
corrupt, stop the worker, preserve the JSON entries, and rebuild it during a
maintenance window rather than deleting cache data blindly.

Owner maintenance status:

```text
GET /api/admin/maintenance/status
Admin UI: /admin/maintenance
```

| Field/state          | Meaning                                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `never_run`          | Registered task has no durable completed attempt. This is not success.                   |
| `running`            | Task recorded a start and has not recorded completion. Check heartbeat/lease when stale. |
| `idle` / `succeeded` | Latest recorded attempt completed successfully.                                          |
| `failed`             | Latest attempt failed. UI exposes generic redacted guidance only.                        |
| `disabled`           | Maintenance scheduling is disabled; no next eligibility is advertised.                   |
| `next_eligible_at`   | Next cron occurrence in UTC from configured cron/timezone and durable completion state.  |

Every allowlisted task records best-effort start/success/failure transitions in
`SchedulerRuntimeState`. Observability-write failure is logged safely and does
not turn successful cleanup into failed cleanup. DB state is durable truth;
absence remains explicit and no local runtime cache may manufacture success.

Manual novel cache invalidation:

```text
POST /api/admin/novels/{novel_id}/cache/invalidate
```

## Backups

### Object storage

- `BACKUP_ENABLED=true` enables scheduled snapshots.
- R2 production snapshots use independent `dokushodo-backup` target
  credentials.
- Application CRUD, snapshot-source read, and backup-target write credentials
  remain separate and least privilege.
- Snapshot success requires a manifest-last commit plus byte-length, checksum,
  and referenced-object verification. Incremental manifests copy only new
  content-addressed objects and reference prior verified snapshots.
- Retention is implemented by `R2IncrementalBackupTarget` and preserves the
  configured newest/minimum successful manifests. It deletes a shared object
  only when no retained manifest references it and its
  `BACKUP_SAFETY_GRACE_DAYS` period has elapsed. Lifecycle rules/locks are
  safeguards, not copies.

Manual trigger:

```text
POST /api/admin/backups
```

### R2-only cutover and migration

The hard cutover is an operator-gated data operation, not a startup migration.
Before any destructive action:

1. Pause crawl, import, translation, worker, and maintenance writers.
2. Record the three PostgreSQL novel IDs, slugs, source URLs, publication
   states, chapter counts, active generations, and exact current references.
3. Inventory `dokushodo` and `dokushodo-backup` with fully paginated listings,
   checksums, byte totals, and sanitized manifests.
4. Verify an independent backup and an isolated restore before reset.
5. Require an explicit confirmation naming both buckets and the migration ID.

The reset tool may delete only the named buckets after the confirmation gate;
it must verify zero objects, keep both buckets, repopulate immutable objects,
upload manifests, commit PostgreSQL references, and verify all three previous
public URLs. It must refuse legacy prefixes, guessed buckets, incomplete
identity evidence, or a live writer. A dry-run is the default. Production
object counts and repopulation are not claimed until sanitized live evidence is
recorded in the conformance ledger.

### Garbage collection

GC is mark-and-sweep over exact PostgreSQL references plus protected rollback,
backup, and in-progress migration manifests. It lists R2 only in the GC job,
archives or verifies backup presence before deletion, applies the configured
grace period (seven days initially), and emits a dry-run report. Active,
current, protected, referenced, or grace-period objects are never deleted.

### Backup Bucket Object Lock & Operator Retention Debt Procedure

The Cloudflare R2 backup bucket `dokushodo-backup` operates with bucket-level Object Lock / retention policies. When automatic retention cleanup (`apply_retention()`) attempts to delete snapshots whose retention period has not expired, Cloudflare R2 rejects `DeleteObject` with `ObjectLockedByBucketPolicy: The object is locked by the bucket policy.`

- **Operator Retention Debt**: Old snapshots (e.g. historical snapshots created before data-resets) remain immutable in `dokushodo-backup` until their lock period expires.
- **Runbook Rule**:
  1. Do not treat `ObjectLockedByBucketPolicy` errors as application backup failures; new snapshots and manifests are committed successfully.
  2. Maintain `BACKUP_MIN_SUCCESSFUL_TO_KEEP` policy in application logic.
  3. Once bucket retention locks expire, run standard retention prune via maintenance tasks or manual admin API call.
  4. Never attempt force-deletion of locked objects; Cloudflare R2 bucket policy enforces compliance.

### Database

- `DATABASE_BACKUP_ENABLED=true` creates PostgreSQL custom-format dumps of
  application-owned schema.
- Dumps are streamed through AES-256-GCM encryption and committed independently.
- No plaintext dump remains after successful or failed handling.
- Restore verification uses a disposable PostgreSQL database whose name
  contains `restore`; never point it at production.

#### Native PostgreSQL 17 administration via secure Desktop GUI over SSH tunnel

To eliminate web attack surfaces and conserve server memory, no web GUI container is deployed. Operators manage the database using modern desktop clients (TablePlus, DBeaver, Beekeeper Studio) connected through an encrypted SSH tunnel.

1. **Strict host loopback binding**: in `deploy/compose.yml`, the `db` service publishes port 5432 bound exclusively to `127.0.0.1:5432:5432`. Port 5432 is never published to `0.0.0.0` or exposed to the public internet.
2. **Built-in Desktop GUI SSH tunnel**: configure Host: `127.0.0.1`, Port: `5432`, User: `dokushodo`, Database: `dokushodo`, with the GUI's SSH Tunnel set to the VPS host, user, and SSH private key.
3. **CLI port forwarding**:
   ```bash
   ssh -N -L 54322:127.0.0.1:5432 user@your-vps-ip -i ~/.ssh/id_ed25519
   ```
   Connect the local GUI to `localhost:54322`.
4. **Instant query performance diagnostics**: `deploy/postgres/init/01-init.sql` enables `pg_stat_statements` and provisions the `v_slow_queries` view:
   ```sql
   SELECT query, calls, total_ms, mean_ms, rows FROM v_slow_queries;
   ```

## Restore Procedure

1. Select a committed backup and verify manifest/checksums.
2. Restore storage into an isolated prefix; inspect counts and representative content.
3. Restore encrypted PostgreSQL dump into a clean isolated database.
4. Verify Alembic head, tables, constraints, row counts, and representative queries.
5. Restore production storage first, then PostgreSQL.
6. Rebuild catalog projections with `POST /api/admin/catalog/rebuild`.
7. Run deployment smoke checks and spot-check public/private boundaries.
8. Record UTC time, candidate version, operator, commands, and sanitized results.

Never restore directly into production before isolated verification. Historical
generated files are preservation-only data and must not be deleted automatically.

## Incident and Rollback

Rollback triggers include private/taken-down content exposure, owner bypass,
secret exposure, corrupt migration/data, uncontrolled queue growth, broad
storage failure, severe reader errors, or failed recovery without safe mitigation.

1. Pause worker and scheduler.
2. Disable public reader or affected feature when possible.
3. Purge affected CDN/application cache.
4. Preserve logs and current data; do not destroy evidence.
5. Redeploy previous immutable image/version.
6. Prefer forward-fix for DB migrations. Snapshot first; downgrade only after
   isolated testing and explicit data-loss acceptance.
7. Re-run health, auth, reader, takedown, storage, and smoke checks.

## Secret Rotation

- Session secret rotation invalidates all sessions.
- Provider credential encryption-key rotation requires re-encryption before old-key removal.
- Rotate R2 application, snapshot-read, and backup-write tokens independently.
- Owner bootstrap secret seeds only fresh owner state; never expose it.
- Keep SMTP disabled (`noop`) until delivery readiness in `STATUS.md` passes.

## SMTP Activation Gate

`AUTH_EMAIL_DELIVERY_MODE=noop` is the safe default. Before switching to `smtp`:

While `noop` is active, public password signup is intentionally a deferred
email-delivery path: account creation and session login can be tested, but
verification and password-reset messages are not sent. Do not treat an
unverified account or a generated but undelivered token as SMTP evidence.

1. Verify sending domain ownership plus SPF, DKIM, and DMARC.
2. Store SMTP credentials only in provider secret storage.
3. Test verification/reset delivery, bounce handling, timeout, and rate limits.
4. Confirm application and provider logs omit tokens, credentials, message body,
   private recipient data, host internals, and traces.
5. Trigger one real stale/failure operator alert and verify cooldown behavior.
6. Revert to `noop`, confirm authentication remains usable, then document rollback.
7. Record candidate commit, UTC time, operator, provider environment, exact safe
   action, sanitized result, and blocker/waiver status.

SMTP construction tests and noop notifications are not delivery evidence.

## Reader Budgets

| Surface                    |                    Budget |
| -------------------------- | ------------------------: |
| Catalog API                | p95 <= 500 ms; <= 250 KiB |
| Novel API                  | p95 <= 300 ms; <= 100 KiB |
| Chapter API                |   p95 <= 750 ms; <= 1 MiB |
| Public route first-load JS |                <= 250 KiB |
| Catalog page size          |   default 24; maximum 100 |
| Public annotations         |                maximum 50 |

Guest-safe catalog/reader GETs may use short shared caching. Auth, account,
admin, intake, errors, unavailable shells, owner previews, and HTTP 451 do not.
Use real-network/browser acceptance before launch; local budgets are not hosted evidence.

## Routine Checks

- Daily: health, queue, worker/scheduler heartbeat, errors, storage capacity.
- After deploy: migrations, liveness/readiness, public route, auth boundary, frontend.
- After takedown: reader 451, sitemap exclusion, cache/CDN propagation.
- After backup: committed manifest, checksum, retention, alert status.
- Periodically: isolated object and DB restore; secret/credential scope review.

## Recovering the Project Venv

The project venv at `.venv/` is the canonical interpreter for all backend
tooling (Python ≥ 3.14). To rebuild after schema changes, dependency
upgrades, or accidental deletions:

```powershell
py -3.14 -m venv .venv
& .venv\Scripts\python.exe -m pip install --upgrade pip
& uv sync --extra dev --extra db --extra auth --extra worker --extra gemini --extra test
```

Then verify tooling resolves the venv (not a PATH shadow):

```powershell
& tools/pytest.ps1 -q backend/tests/test_chapter_identity_codec.py
& tools/ruff.ps1 check backend/src backend/tests
& tools/pyright.ps1
```

Each `tools/*.ps1` wrapper refuses to run when `.venv\Scripts\python.exe`
is missing. The readme at `tools/README.md` lists the canonical extras.

Current unresolved operator gates live in [`STATUS.md`](STATUS.md).

## Unified Provider Credential Operations

For an enabled credential deployment, the owner and user paths operate on the
same `provider_credentials` table. Verify:

1. Confirm `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is present and not the owner
   bootstrap or session secret.
2. Confirm the current `CONTRIBUTOR_CONSENT_VERSION` is the version shown by
   the frontend and record any consent copy change.
3. Confirm per-credential RPM/TPM/RPD limits and the quota-state directory are
   writable only by the backend runtime.
4. Import the configured owner key only through the owner-only
   `POST /api/admin/providers/credentials/import-environment` operation. It
   explicitly validates `PROVIDER_GEMINI_API_KEY`, stores it encrypted, marks
   it owner-job eligible, and never makes it contributor-pool eligible. A
   failed validation is persisted as `invalid`; do not queue owner bulk work
   until the key validates. At the current 2026-08-22 checkpoint the imported
   owner row is `active`/`valid` and owner-job eligible; this does not make it
   contributor-pool eligible.
5. Confirm at least one user contribution is `active` with
   `validation_status=valid` and `contributor_pool_eligible=true` before
   queueing contributor-backed translation. A zero-key pool is an intentional
   preflight stop; never substitute an owner row or environment key.
6. Verify the active Gemini project limits in Google AI Studio. The local
   RPM/TPM/RPD values are defensive ceilings, not proof of independent quota
   per API key; TPD is model-dependent and is not configured separately here.
7. Apply Alembic migrations with the elevated migration role before starting
   the long-running services; the runtime role must have the required DML but
   should not be granted broad schema-DDL privileges.
8. Verify the user route returns masked metadata only, unsafe methods reject
   missing CSRF, validation attempts are rate-limited per user, and a user
   cannot read or mutate another user's credential.

Owners may pause or revoke a credential for emergency abuse remediation. A
revoked credential cannot be resumed by a user. Permanent user deletion removes
the encrypted credential row but preserves sanitized usage-ledger history for
accounting and incident review. Do not delete ledger rows as part of ordinary
credential removal.

Rotation requires a maintenance window: pause contributor work, re-encrypt
stored credentials, verify fingerprints and validation state, switch the
configured key, resume only after a masked read and validation check, and
record the operator/evidence in `EVIDENCE.md`. If re-encryption cannot complete,
keep the old key available and fail closed rather than accepting new keys.

## Ranking and Anonymous Viewer Retention

`/api/public/rankings` is based on published novel-detail events retained by
`ANALYTICS_RETENTION_DAYS`. Daily, Weekly, and Monthly mean 24 hours, 7 days,
and 30 days from query time. Chapter views are excluded. When analytics is
disabled or the retained set is empty, the API and UI expose an unavailable or
no-data state; operators must not seed placeholder rows or describe it as All
Time.

Successful non-empty ranking responses use a bounded process-local TTL/LRU
cache. The default TTL is 60 seconds and the default bound is 64 entries; the
cache is an optimization only and is not shared between reader workers or
replicas. Cache keys include the period, public-projection schema/update
version, and limit, so publication or projection updates select a new key.
Disabled analytics, no-data, and unavailable responses are never cached.
Inspect `novelai_public_ranking_cache_hits_total`,
`novelai_public_ranking_cache_misses_total`, and
`novelai_public_ranking_cache_entries` in `/metrics`. If the deployment scales
to multiple readers, measure duplicate origin work before moving this contract
to a shared Redis cache.

Migration `c8d2e4f6a1b3` adds the two composite analytics indexes used by the
ranking predicate and authenticated/anonymous viewer identities. Verify the
migration head and run a representative PostgreSQL `EXPLAIN (ANALYZE,
BUFFERS)` before treating ranking latency as production-capacity evidence.

### Public projection cache and analytics writer

Catalog base pages, DB-backed summaries, and chapter metadata use a bounded
30-second/256-entry process-local projection cache. Publication/reconciliation
and approved takedown review invalidate it; versioned keys also prevent normal
projection updates from reusing an older payload. Monitor
`novelai_public_projection_cache_hits_total`,
`novelai_public_projection_cache_misses_total`,
`novelai_public_projection_cache_entries`, and
`novelai_public_projection_cache_invalidations_total`. The reader process
does not expose the admin metrics route by default, so collect these metrics
from the owning operator process or add an approved reader telemetry path
before using them for capacity claims.

Public analytics writes use a bounded asynchronous queue (default 1,000). A
request response with `recorded` means queue admission, not durable commit;
`dropped` reports queue-full or unavailable admission. Monitor
`novelai_analytics_writer_accepted_total`,
`novelai_analytics_writer_dropped_total`,
`novelai_analytics_writer_processed_total`,
`novelai_analytics_writer_failures_total`, and
`novelai_analytics_writer_queue_depth`. Sustained drops require capacity
investigation; do not make the queue unbounded. The writer stores only
sanitized fields and never stores raw IP addresses.

Guest detail views may set the signed `novelai_viewer` first-party cookie. The
server stores only a digest of the opaque token, never the raw token or an IP
address. Clear the cookie or disable analytics when investigating identity
collection; do not export raw cookie values into logs or incident evidence.

The contributor usage ledger is pruned by the `contributor_usage_cleanup`
maintenance task according to `CONTRIBUTOR_USAGE_RETENTION_DAYS`. Permanent
credential deletion preserves rows until that retention task removes them;
dry-run the task before changing the policy.

## Reader capacity and recovery follow-up checkpoint — 2026-08-25

The current operational evidence package is blocked, with local validation
complete. The 1k reader report has a complete required matrix but no approved
fixture/target or controlled cold-cache evidence; all cells are therefore
unavailable and `reader_slo_status=blocked`. Layer attribution and hosted
telemetry are explicitly unavailable. Recovery control tests do not prove
current backup freshness, alert delivery, or an isolated hosted restore; the
workflow audit also identifies a missing integration-test path.

Keep the worker and original full queue stopped/paused. Do not run 10k/100k,
provider-volume, or full-queue traffic and do not make a production-capacity,
billing, or quota claim. Before any retry, an owner must supply the approved
opaque fixture and targets, establish a disposable cold-cache control, enable
fixed-label layer telemetry, repair or disposition the workflow path, and
authorize isolated recovery targets. The sanitized handoff and validation
records are under `artifacts/operations/reader-capacity-follow-up/`.

## Reader capacity and recovery runtime recheck — 2026-08-27

The local runtime baseline was re-established after Docker Desktop recovery.
Backend, reader, Caddy, frontend, Redis, and the isolated `restore-db` service
were healthy; the dedicated worker remained absent. Through local Caddy,
`/health/live` and `/health/ready` both returned HTTP 200 with empty bodies.
This closes the previously observed local Docker/Caddy outage only; it is not
private second-peer, hosted, or production availability evidence.

The campaign `camp-20260827T130658Z` and its `private_network` selection are
retired historical evidence. They were superseded on 2026-08-29 by the
Cloudflare-only reader gate described below. Keep the worker/full queue
stopped/paused and preserve the remaining release-configuration, cross-source,
provider/bulk, hosted pool/cache/analytics, CDN propagation, credential
rotation, and dedicated-host gates in `docs/STATUS.md`.

## Reader capacity and recovery runtime recheck - 2026-08-28

The current local split Compose runtime remained healthy for the bounded
recheck: backend, reader, Caddy, frontend, Redis, and restore-db were healthy,
while the dedicated worker was absent. Local Caddy returned HTTP 200 with
empty bodies for `/health/live` and `/health/ready`. This is local runtime
evidence only and does not establish hosted, private second-peer, or
production availability.

The campaign `camp-20260828T042235Z` and its `private_network` selection are
retired historical evidence. The current Cloudflare-only stage report is
recorded in the authorization checkpoint below. Recovery freshness, alert
delivery, and provider/R2 telemetry remain unobserved; `production_capacity_claim`
is `not_established`.

## Reader authorization input check - 2026-08-29

The project owner supplied a non-production, read-only reader-capacity
authorization and an explicit disposable fixture description. This is test
input, not execution evidence. The selected SLO gate is now
`cloudflare_tunnel`; the Cloudflare development hostname is the approved
non-production reader-facing path through the public edge and internal Caddy.

Fresh Cloudflare MCP inspection confirms the development zone is active, the
development DNS route is proxied to the healthy `dokushodo-dev` tunnel, and
the tunnel has one active connector. The public development liveness request
returned HTTP 200, but the supplied fixture was not present at that origin
(the novel and both requested chapter routes returned HTTP 404). The test R2
buckets are present in the Cloudflare account, but the proposed fixture
namespace has no objects in either test bucket; R2 existence alone therefore
does not establish reader-fixture content.

No private-network peer check is required for this Cloudflare-only contract.
The current baseline and route profile use the opaque binding derived from the
supplied fixture. The bounded read-only Cloudflare run completed with 50 warm
samples per required route: liveness p95 was 155.096 ms, catalog p95 was
1518.142 ms, search p95 was 1368.677 ms, and the requested detail/chapter
fixture returned HTTP 404. All controlled-cold cells remain unavailable, so
the operational disposition remains blocked with
`production_capacity_claim=not_established`. No content, secret, worker, or
queue mutation was performed.

## Managed non-production recovery checkpoint - 2026-08-28

The confirmation-gated recovery run
[`33182847311`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33182847311)
ran at candidate commit `30fe82c` against the disposable managed test
database and dedicated non-production R2 target. Its sanitized artifact is
`artifacts/operations/reader-capacity-follow-up/remote-recovery-33182847311/managed-database-recovery-evidence.json`.

The run passed encrypted database backup creation, manifest and checksum
verification, backup freshness, isolated local restore, Alembic-head
verification, representative queries, public isolation, R2-prefix cleanup,
temporary-role cleanup, and overall cleanup. The restored target contained 37
public tables, all 37 had RLS enabled, and there were zero invalid
constraints. The run recorded `production_mutation=none`; the temporary
confirmation variable was removed and `MANAGED_SERVICE_TESTS_ENABLED` remains
`false`.

A later candidate-only check synchronized the disposable test project's
Alembic marker to `f8a2c4e6b0d1` after applying the idempotent RLS-helper
revocation. Its application fixture tables remain empty and the security
advisor reports no lints. This does not change the scope of the recovery run
above or establish reader-fixture, production, or capacity readiness.

At the 2026-08-28 checkpoint, this was current non-production recovery
evidence for one isolated path. It did not establish recurring production
backup freshness, alert delivery, production smoke, reader capacity, hosted
telemetry, or production recovery readiness. Keep the worker and original full
queue stopped/paused.

## Managed non-production recovery rerun - 2026-08-30 (prior candidate run)

The explicitly authorized test-only recovery workflow
[`33270802038`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33270802038)
completed successfully in 1m51s at merged `main` commit
`01f106ade3700405f3f4a998a1c708ed7113505b`. It used only the disposable
managed test database, `test-dokushodo` for application R2,
`test-dokushodo-backup` for recovery material, and an ephemeral local
PostgreSQL restore target. The sanitized artifact is
`managed-database-recovery-evidence-33270802038`.

Backup creation, healthy freshness, manifest/checksum verification, isolated
restore, representative queries, Alembic-head verification, public isolation,
R2 cleanup, temporary-role cleanup, and overall cleanup passed. The restored
target contained 37 public tables, all 37 with RLS enabled, zero invalid
constraints, and `production_mutation=none`.

Independent Supabase MCP SQL confirmed zero fixture novel rows and zero
fixture chapter rows. Cloudflare MCP read-only listings confirmed zero objects
under `novels/123/` in `test-dokushodo` and zero `recovery-` objects in
`test-dokushodo-backup`. The recovery status is `partial`, because recurring
schedule history, retention behavior, stale/failure alert transition and
delivery, production smoke, and production recovery readiness remain
unverified. No production resource, secret, or repository variable changed;
keep the worker and original full queue stopped/paused.

## Managed non-production recovery checkpoint - 2026-08-30 (corrected target)

The corrected explicitly authorized test-only recovery workflow
[`33287970969`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33287970969)
ran from the candidate branch after the recovery target was pinned to
`test-dokushodo-backup`. It used only the disposable managed test database,
`test-dokushodo` for application R2, `test-dokushodo-backup` for recovery
material, and an ephemeral local PostgreSQL restore database. The sanitized
artifact is `managed-database-recovery-evidence-33287970969`.

Backup creation, healthy freshness, manifest/checksum/reference verification,
isolated restore, representative queries, public isolation, temporary-role
cleanup, R2 cleanup, and overall cleanup all passed, with
`production_mutation=none`. The preceding candidate run
[`33287685641`](https://github.com/ArchdukeViel/NovelAITranslator2Book/actions/runs/33287685641)
was correctly stopped at backup creation after the application bucket rejected
the recovery target; it made no production mutation. Independent Supabase MCP
SQL now confirms zero fixture novel/chapter rows, and Cloudflare MCP confirms
zero objects under `novels/123/` and `recovery-` in the two approved test
buckets.

This is one-run test-only recovery evidence. Set `recovery_status=partial`
until recurring schedule/retention history, stale/failure alert transition and
delivery, production smoke, and production recovery readiness are independently
verified. Leave `MANAGED_SERVICE_TESTS_ENABLED=false` and keep the worker/full
queue stopped/paused.

## Pipeline async execution and capacity runbook checkpoint - 2026-08-24

The local audit completed the bounded persistence boundary, fixed-label runtime
telemetry, contributor-pool admission/accounting, fixture-only reader harness,
checkpoint footprint measurement, and modeled cost-envelope work. Evidence is
under `artifacts/capacity/`. Local tests do not authorize a live workload.

Before any live action, confirm the worker is intentionally running, the
original queues are not being used as a benchmark, the migration head and
readiness state are healthy, and an operator has recorded the traffic model,
SLO/error budget, provider/R2/egress ceilings, stop thresholds, telemetry
window, and rollback owner. Do not activate a contributor key or substitute an
owner key for the contributor pool. Keep `translation_provider_rps` and
`reader_http_rps` in separate reports.

Rollback order is: stop new load; stop worker admission; allow critical
terminal writes to settle within the bounded shutdown deadline; disable the
expansion gate; verify queue/lease state through application APIs; and record
the result. Do not edit queue rows, runtime JSON, checkpoint files, R2 objects,
or canonical content by hand. The current audit did not resume the worker or
the original queues.

The isolated R2 benchmark is unavailable when `TEST_R2_GATEWAY_URL` or the
dedicated test Access identity is absent. The source canary and reader stages
are operator/hosted gates; missing hosted telemetry is an unavailable result,
never a pass.

## Cloudflare development tunnel operation - 2026-08-28

The temporary external development origin is
`https://dev.dokushodo.online`. Cloudflare manages the `dokushodo-dev`
tunnel configuration and its single development DNS route; the production
apex and `www` records are not part of this operation. The tunnel forwards to
the existing internal Caddy service at `http://caddy:80` on `novelai-net`.

The connector token is stored only in the ignored local file
`deploy/.cloudflared/dokushodo-dev.token` and is mounted as a Compose secret.
Do not print, commit, copy, or place it in an environment example. If the
token is exposed, rotate it through the Cloudflare control plane before
restarting the connector.

Use the explicit service target below for a restart; a bare Compose `up`
also includes the worker service, which must remain stopped while the reader
capacity and recovery gates are blocked:

```powershell
docker compose --env-file deploy/.env -f deploy/compose.yml up -d --no-build cloudflared
docker compose --env-file deploy/.env -f deploy/compose.yml stop --timeout 0 worker
```

Verify the connector with `docker compose ... ps -a` and the Cloudflare MCP
tunnel/DNS read path, then verify the real development URL. A healthy tunnel
and HTTP smoke result do not authorize provider work, the original full
queue, recovery writes, or a production launch.

## Native PostgreSQL 17 administration, CloudBeaver, and backup/restore runbook

### 1. Database Web GUI (CloudBeaver)

- **Container**: `dokushodo-cloudbeaver` (`dbeaver/cloudbeaver:24.3.0`) in `deploy/compose.yml`.
- **URL**: `http://127.0.0.1:8978`.
- **Network & Host**: Connects over internal `novelai-net` Docker network to host `db` on port `5432`.
- **Security & Governance Configuration**:
  - Bound strictly to `${CLOUDBEAVER_BIND_ADDRESS:-127.0.0.1}`.
  - Anonymous access disabled (`anonymousAccessEnabled: false` in `deploy/postgres/cloudbeaver/cloudbeaver.conf`).
  - Schema filter hides internal `auth` and `private` schemas, exposing only `public`.
  - Query result limit capped to 1,000 rows (`sqlResultSetRowsLimit: 1000`) to prevent frontend OOM.
  - SQL editor configured with `autoSave: true` (autocommit enabled by default) to prevent idle transaction table locks.
  - Data export file limit capped to 10MB (`dataExportFileSizeLimit: 10000000`).
  - Pre-seeded read-only analyst connection profile `PostgreSQL@db-reader` (`novelai_reader` role) in `deploy/postgres/cloudbeaver/initial-data.conf`.
- **Authentication**: Connect with username `dokushodo` or `cbadmin` and configured password.
- **Desktop Alternative**: Desktop clients (TablePlus, DBeaver, Beekeeper Studio) connect via `127.0.0.1:5432` locally or via SSH tunnel in remote environments.

### 2. Database Initialization and Migration Runbook

Run `tools/database/init_native_postgres.ps1` to orchestrate container spin-up, migration, and data seed:

```powershell
powershell -ExecutionPolicy Bypass -File tools/database/init_native_postgres.ps1
```

This script:

1. Validates Docker engine availability.
2. Ensures the `dokushodo-db` container is running and healthy.
3. Dynamically resolves `DATABASE_URL` from `.env` and executes `alembic upgrade head`.
4. Ingests the canonical relational seed from `deploy/postgres/seeds/02-data-seed.sql`.
5. Asserts post-migration row counts across novels, chapters, and glossaries.

### 3. Automated Database Backup Runbook

Run `tools/database/backup_postgres.ps1` to generate a non-blocking, verified snapshot:

```powershell
powershell -ExecutionPolicy Bypass -File tools/database/backup_postgres.ps1 -RetentionDays 14
```

- Performs a custom-format dump (`pg_dump -Fc`) inside the container.
- Copies the binary dump to `deploy/postgres/backups/dokushodo_backup_<timestamp>.dump`.
- Verifies archive integrity and non-zero size.
- Prunes backups older than the retention threshold (defaults to 14 days).

### 4. Database Restore Runbook

Run `tools/database/restore_postgres.ps1` to recover from a backup:

```powershell
# Restore the latest backup automatically:
powershell -ExecutionPolicy Bypass -File tools/database/restore_postgres.ps1

# Or restore a specific backup archive:
powershell -ExecutionPolicy Bypass -File tools/database/restore_postgres.ps1 -BackupFile deploy/postgres/backups/dokushodo_backup_2026-09-04_102004.dump
```

- Safely terminates open client sessions (`pg_terminate_backend`) to eliminate table-lock contention.
- Executes `pg_restore --clean --if-exists --no-owner --no-privileges`.
- Validates row counts in `novels`, `chapters`, and `novel_glossary_entries` to confirm data integrity.

### 5. Performance Diagnostics (`v_slow_queries`)

The PostgreSQL container automatically enables `pg_stat_statements` via `deploy/postgres/init/01-init.sql`.
To diagnose query performance and slow executions:

```sql
SELECT query, calls, total_ms, mean_ms, rows FROM v_slow_queries;
```

### 6. Automated Backup and Restore Drill

Run `tools/database/verify_backup_drill.ps1` to execute an automated validation drill of container liveness, backup catalog consistency, and schema verification:

```powershell
powershell -ExecutionPolicy Bypass -File tools/database/verify_backup_drill.ps1 -DryRun
```

### 7. Alembic Migration Linearity and Reversibility Check

Verify that the Alembic migration DAG remains strictly single-headed and fully reversible:

```powershell
powershell -ExecutionPolicy Bypass -File tools/database/test_alembic_reversibility.ps1
```

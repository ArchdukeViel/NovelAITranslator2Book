# R2-Only Content Storage Rearchitecture

## Status

**Target architecture:** Cloudflare R2-only durable novel artifact storage.

This plan intentionally removes the filesystem content backend and does **not** retain backward compatibility with the old `storage/novel_library` layout.

The migration is a clean architectural cutover.

**Current-status rule:** The latest dated completion checkpoint is authoritative.
Sections dated before `2026-08-24` preserve historical snapshots, including
their unchecked boxes and boundary language; they are not active work items.
The current completion ledger is [67B](#67b-async-capacity-and-r2-completion-checkpoint--2026-08-24).

### Pipeline resource-efficiency checkpoint — 2026-08-23 (superseded by the 2026-08-24 recovery checkpoint)

The approved pipeline-resource-efficiency audit has completed its local gate
while the worker remains intentionally stopped. This checkpoint records the
current state without rewriting the historical runtime checkpoints below.

This is a historical snapshot. Its unchecked items describe the state observed
on 2026-08-23; the current task and gate decisions are recorded in section 67B.

Completed in the audit:

- [x] The stopped-worker, Compose, bucket, environment-key, and protected-data
  baseline was captured without mutating canonical PostgreSQL or R2 content.
- [x] Bounded pipeline timing and redaction fields were added with explicit
  unavailable reasons for stages that cannot be measured until a live worker
  canary runs.
- [x] Worker claim, lease, retry, heartbeat, and idle-poll behavior was
  audited; atomic claims, backoff, and timestamp-only heartbeats were retained
  where already correct.
- [x] Read-only Supabase/PostgreSQL query, pool, and plan evidence identified
  large-history and repeated-activity-read candidates without applying a
  schema/index change.
- [x] R2 operation, compression/reuse, exact-key, and no-hot-path-LIST
  evidence was captured through an isolated audit prefix and cleaned to zero
  objects.
- [x] Five bounded corrections were implemented and regression-tested:
  deferred novel metadata history, deferred chapter media/version JSON,
  projected translation/glossary-revision lookups, reuse of the activity row
  returned by an atomic claim, and bucket-level `HEAD` for R2 readiness. The
  selected metadata/glossary/raw chapter cache is bounded to one job.
- [x] The configuration decision is an evidence-backed no-op; worker enablement,
  pool, concurrency, batch, timeout, polling, lease, and bucket values were not
  changed while production workload evidence was unavailable.
- [x] Focused tests, the post-patch full backend suite, Ruff, Pyright, Compose validation,
  the relative Markdown link audit, architecture guards, task-ledger/conformance
  review, and Graphify passed. The post-patch full backend result was 2,904
  passed and 16 skipped.

Canary checkpoint result — 2026-08-23 05:04 UTC:

- [x] The rebuilt worker image was recreated and the bounded canary started
  through the Compose worker service. It claimed only the existing NCode
  activity; Kakuyomu remained pending and no third activity was claimed.
- [x] The canary was stopped after repeated observations showed no chapter
  state transition while the activity heartbeat remained fresh. The worker
  container ended with Docker exit 137 after the stop timeout. This is a
  safety stop, not a terminal translation result.
- [x] Post-stop application checks preserved the three existing source records
  and their source URL hashes. No PostgreSQL row or runtime JSON was manually
  edited, and no bucket reset, restore, or legacy-prefix operation was run.
- [ ] The NCode activity remains running with its existing lease and the
  Kakuyomu activity remains pending; application-service lease expiry/recovery
  and retryable chapter repair are still required. The observed cumulative
  query increase and container network totals explain why the canary was not
  allowed to advance without a valid workload baseline, but they do not prove
  billed Supabase egress or a canonical R2 artifact delta.

Risk-resolution canary checkpoint - 2026-08-23 07:33 UTC:

- [x] Current Supabase, Gemini, and Cloudflare R2 documentation was reviewed.
  The review confirms that Supabase billing attribution must be read from the
  Usage/Observability report, Gemini limits are project-wide rather than
  key-wide, and R2 `LIST`/`PUT` are Class A while `HEAD`/`GET` are Class B.
- [x] The application-service recovery path was repaired: expired-row
  recovery is flushed before the targeted atomic claim. The regression suite
  `backend/tests/test_activity_database.py` passed 5 tests after the fix.
- [x] A rebuilt one-target worker canary reclaimed NCode at retry count 4,
  renewed its lease, and moved one chapter from failed translation state into
  fetching/translation. Memory stayed below 135 MiB in the observed sample;
  no OOM kill or provider quota failure was observed.
- [x] The canary was stopped at the bounded safety checkpoint and its temporary
  container was removed. Docker exit 137 came from the stop timeout with
  `OOMKilled=false`; this is not a terminal translation result.
- [ ] The NCode row remains leased until normal expiry because no manual
  PostgreSQL or runtime-file edit was used. Kakuyomu remains pending and
  Novel18 remains a truthful terminal failure at its highest retry record.
  The next application claim must perform normal lease recovery.
- [x] Supabase billing-period egress attribution and Gemini AI Studio project
  limit evidence are now supplied by the operator. Cumulative PostgreSQL query
  counters and local R2 counters remain supporting evidence only.

Operator evidence follow-up - 2026-08-23:

- [x] The Supabase custom report shows `API Egress=0` and
  `Shared Pooler Egress=66,683,432,737` bytes, consistent with the
  organization Usage page's 67.20 GB billing-period total. The report's date
  bucket differs from the Usage chart by approximately one day; exact hover
  timestamp capture remains required.
- [x] Sanitized backend and worker probes confirm Session Pooler traffic on
  port `5432`. `DB_CONNECTION_MODE=direct` controls application-side
  SQLAlchemy pooling and does not select the Supabase endpoint; no environment
  or endpoint value was changed.
- [x] The operator-provided Gemini model snapshot records 15 RPM, 250,000
  input TPM, and 500 RPD for the selected model. The next canary must remain
  below those provider limits and must not treat additional keys from the same
  project as additional quota.

Session Pooler canary follow-up - 2026-08-23:

- [x] The rebuilt local worker image ran one NCode-only application-service
  canary with temporary 12 RPM, provider-concurrency 1, and
  chapter-concurrency 1 overrides; no project `.env` value changed.
- [x] The canary retained a running NCode lease, stayed `OOMKilled=false`, and
  was stopped and removed at the safety checkpoint. The dedicated worker
  remains stopped.
- [x] Sanitized cumulative PostgreSQL counters moved from 1,333,488 calls /
  16,580,767 rows to 1,339,354 calls / 16,585,220 rows; container memory rose
  from about 117 MiB to 174 MiB and no visible chapter-progress transition was
  observed. These counters include verification traffic and are not billed
  egress measurements.
- [ ] The canary remains nonterminal. Full-queue execution, terminal outcomes,
  artifact/read acceptance, backup/restore, and production telemetry remain
  gated on further query/payload reduction and a fresh exact report timestamp.

Post-canary query-payload hardening - 2026-08-23:

- [x] Translation platform-novel and glossary-revision lookups now use
  `load_only()`; routine catalog reads defer `Novel.metadata_history_json` and
  existing chapter lookups defer media/version/edit-history JSON.
- [x] The selected metadata, approved glossary, and raw chapter bundle are
  reused only within one translation job and are discarded at job completion;
  no cross-job cache was introduced.
- [x] Focused projection/translation/worker/glossary coverage passed 145 tests,
  and the full backend suite passed 2,904 tests with 16 skips. Ruff and
  Pyright passed. No environment, PostgreSQL row, runtime JSON, or canonical
  R2 object was changed by this hardening.
- [ ] The egress effect still needs a later terminal workload comparison; the
  current NCode canary remains nonterminal and the dedicated worker remains
  stopped.

Still open at this checkpoint:

- [x] Rebuild the worker and run the bounded one-novel-at-a-time canary for the
  preserved source URLs under the approved stop rules; the first activity was
  intentionally stopped before it reached a terminal boundary.
- [ ] Reach truthful terminal outcomes and perform any retryable chapter-state
  repair through application services; do not hand-edit PostgreSQL or runtime
  JSON.
- [ ] Complete final translated-artifact and published chapter-read acceptance
  counts after the queue is terminal/idle.
- [x] Create backup objects and complete an isolated restore drill; the
  2026-08-24 recovery checkpoint below supersedes this item.
- [ ] Capture production-scale telemetry, hosted CDN/origin acceptance, and the
  production readiness gate.
- [ ] Evaluate checkpoint payload compaction/reference storage after the live
  canary; the current local checkpoint format remains disposable and
  service-safe but duplicates content.

### Runtime boundary and repair checkpoint — 2026-08-22 (historical snapshot; superseded by 67B)

This checkpoint revalidated the plan against the current repository and the
running Compose deployment. The host runtime boundary remains
`data/runtime/`; Compose mounts it as `/app/data/runtime` inside the
containers. The host runtime path is disposable and is not a canonical
content location.
The repository configuration and templates now point to this boundary. The
physical relocation is complete: after a safe checkpoint at a translated
checkpoint boundary, the runtime-consuming Compose services were stopped and
the host directory was renamed from `storage/runtime` to `data/runtime`.
Nothing was copied or hand-edited. The rebuilt worker then started with the
new `/app/data/runtime` bind.

Completed or verified at this checkpoint:

- [x] `data/runtime/` is explicitly ignored by Git; runtime JSON was not
  staged, deleted, or treated as canonical content.
- [x] Chapter state and checkpoint layout were inspected through the service
  implementation. State is one stable-chapter JSON record; checkpoints are
  disposable recovery envelopes and currently contain temporary raw,
  translated, and state copies.
- [x] The rebuilt dedicated worker image was recreated, and the reader was
  recreated with an explicit `JOB_WORKER_ENABLED=false` override. The backend,
  reader, and worker effective topology has one provider-work executor.
- [x] Remaining repair work was queued through `Container.activity_log` and
  processed through the application worker; no chapter JSON or database row was
  hand-edited.
- [x] The worker lease heartbeat was moved out of the event loop into a daemon
  thread, with a regression test covering synchronous orchestration that blocks
  the loop. Source Ruff, Pyright, and the focused worker test pass.
- [x] The stale pre-fix worker was stopped after its lease expired while it was
  stuck in synchronous persistence. The rebuilt worker was recreated with the
  heartbeat fix, recovered the expired NCode activity through the durable
  queue, and extended its lease while that activity remained active. That
  attempt later reached a truthful terminal failure caused by a transient
  PostgreSQL SSL EOF during final novel persistence; it was requeued through
  `Container.activity_log` at retry count 4, preserving the failed attempt.
- [x] After the active runtime write reached the safe checkpoint boundary,
  backend, reader, and worker were stopped, `storage/runtime` was renamed to
  `data/runtime`, and the old path was verified absent. The rebuilt backend,
  reader, and worker were then recreated; the worker started at
  `2026-08-22T19:01:50Z` with restart count `0` and the bind
  `data/runtime -> /app/data/runtime`.
- [x] The post-recreation application checks resolved the NCode lease through
  the durable queue. At the 2026-08-22 22:46 UTC refresh, the sole worker is
  active on NCode at retry count 4 with a renewed lease deadline of
  `2026-08-22T22:50:36Z`; Kakuyomu is `pending` after its expired lease, while
  Novel18 remains a truthful terminal failure.
- [x] After the worker reached a safe quiescence boundary, the existing
  writers-frozen namespace migration was executed at the application layer:
  Kakuyomu moved 5 legacy objects and rewrote 1 database reference, while
  Novel18 moved 2 legacy objects and rewrote 2 database references. All 7
  source objects were deleted only after the migration committed. The old
  prefixes are empty, direct PostgreSQL artifact references to them are zero,
  and the complete post-migration inventory contains only numeric
  `novels/11/`, `novels/16/`, and `novels/17/` groups.
- [x] A read-only live R2 inventory at 2026-08-22 20:23 UTC reconfirmed
  exactly `dokushodo` and `dokushodo-backup`; the application bucket contained
  872 objects and 3,299,655 bytes, while the independent backup bucket remained
  empty. The numeric prefix totals were `novels/11/` 424 objects,
  `novels/16/` 248 objects, and `novels/17/` 200 objects.
- [x] A read-only integrity snapshot at 20:23 UTC listed and GET-verified all
  872 objects. It measured 13,391,798 logical bytes, found `logical-sha256`
  metadata and an exact SHA-256 match for every object, and found zero
  namespace violations.
- [x] Runtime/configuration/operations/architecture Markdown now documents the
  host/container path distinction, ignore boundary, state shape, checkpoint
  trade-off, and executor rule.
- [x] `graphify update . --no-cluster`, Ruff, Pyright, focused checkpoint/worker
  tests, the complete backend suite (`2893 passed, 16 skipped`), and the
  repository relative-link audit have been run.

Still open and intentionally not marked complete:

- [ ] The three-novel bulk queue is not terminal (live refresh at 2026-08-22
  22:46 UTC): NCode is running at retry count 4 with a renewed lease deadline
  of `2026-08-22T22:50:36Z`; Kakuyomu is pending after recovery from an
  expired lease; and Novel18 is failed at retry count 3 with
  `paragraph_missing`. The current PostgreSQL chapter projection is Kakuyomu
  9 complete / 78 failed / 1 translating; NCode 66 complete / 23 failed /
  58 pending / 1 translating; and Novel18 29 complete / 2 failed.
- [ ] Novel18, NCode, and Kakuyomu still require terminal outcomes and any
  retryable chapter-state repair through application services. Final terminal
  counts and post-recovery chapter acceptance remain open.
- [ ] Final translated-artifact counts and remaining published chapter-read
  acceptance cannot be claimed until the queue reaches terminal/idle state;
  the counts above are a recorded checkpoint snapshot while NCode continues.
- [ ] Backup creation, restore, and recovery remain deferred by the operator;
  `dokushodo-backup` remains present but no recovery drill is claimed.
- [ ] Production-scale telemetry, hosted CDN/origin acceptance, and the
  production readiness gate remain open as documented launch follow-ups.
- [ ] The current local checkpoint JSON format is service-safe but duplicates
  content; large-catalog checkpoint compaction or reference/R2-backed payloads
  remain a scale follow-up.

### Baseline cutover checkpoint — 2026-08-22 (superseded by later checkpoints)

This checkpoint records the live state of the cutover. It is deliberately not a
completion claim. The earlier environment configuration gate has now been
resolved by migrating the populated legacy `S3_*` application values to the
current `R2_*` names in the active backend environment files. The checkpoint
also audited every discovered `.env`/`.env.*` file and synchronized each active
application pair by key shape without copying secrets. The operator has since
supplied separate source-read and backup-write R2 credentials and rotated the
application credentials in `deploy/.env`; the six active backend assignments
now match in the root `.env` and `deploy/.env`. No secret was copied into an
example or frontend file. Backup remains disabled until recovery is explicitly
authorized and tested. The credential cutover is now unified: owner-managed
keys and user contributions share the encrypted `provider_credentials` table,
with account ownership, source, owner-job eligibility, and contributor-pool
eligibility stored as explicit row properties. The operator authorized an
owner-scoped bulk translation verification, but the explicit environment-key
import was stored and then failed provider validation; no bulk run is claimed.

### Follow-up control-plane checkpoint — 2026-08-22 (historical/superseded)

The live Cloudflare control-plane recheck reports exactly the two required R2
buckets, `dokushodo` and `dokushodo-backup`. A direct Supabase aggregate query
reports one owner row in the unified `provider_credentials` table, zero
user-contribution rows, and no legacy `contributor_credentials` table. The
security advisor reports no findings, while the performance advisor reports
only informational unused-index observations. The owner row is encrypted and
owner-job eligible but currently `invalid` after explicit provider validation
failed; contributor-backed execution remains an unexercised, user-input-
dependent path.

### Contributor pool checkpoint — 2026-08-22 (historical/superseded)

The live unified registry reports zero user-contribution rows and
`active_valid_count=0` for contributor-pool eligibility. This is an
external-input stop for contributor-backed work: a user key must be submitted
and validated through the contribution flow before the pool can run. The
owner's environment key is stored as an owner-owned registry row, but its
failed validation keeps owner bulk work gated too; it is not silently used as
a substitute for the contributor pool.

### Translation execution checkpoint — 2026-08-22

This is the current translation state and supersedes the earlier validation
failure statements above. The replacement `PROVIDER_GEMINI_API_KEY` is
present only in backend runtime files, the root and deployment values match,
and the live unified owner credential is `active`/`valid` and owner-job
eligible. A durable worker probe for NCode chapter 2 completed through the
current activity path, passed deterministic QA, and persisted the artifact to
R2. The provider-classification and glossary-invalid-JSON retry fixes are
covered by focused tests.

The authorized bulk queue was then created for the three preserved novels with
`skip_glossary_gate` explicitly recorded, owner contribution mode, and no
cross-provider fallback. At the live refresh at 2026-08-22 22:46 UTC, NCode is
running at retry count 4 with a renewed lease, Kakuyomu is pending after
expired-lease recovery, and Novel18 is failed at retry count 3 with
`paragraph_missing`. The current PostgreSQL chapter projection is NCode 60
complete / 23 failed / 58 pending / 1 translating; Kakuyomu 9 complete / 78
failed / 1 translating; and Novel18 29 complete / 2 failed.
NCode chapters
35–37 reached complete state during this interval, while chapters 38–39
recorded QA failures and remain subject to the later application-service repair
pass.
Persisted translated-artifact counts remain Kakuyomu 17/88, Novel18 29/31,
and NCode 60/148; those counts include artifacts whose durable state still
requires reconciliation. The last read-only R2 inventory, at 20:23 UTC,
reports 872 application objects / 3,299,655 stored bytes and zero backup
objects, with a zero-mismatch GET/hash verification of all 872 objects and
13,391,798 logical bytes. These counts are partial and do not constitute
bulk-completion evidence.

Completed at this checkpoint:

- the three existing PostgreSQL novel identities and source URLs were verified;
- the R2 artifact-reference migration `f1a7c9e2d4b6`, follow-up security
  migration `b6c8d0e2f4a6`, and later provider-registry migrations were applied
  to the authorized Supabase project; the current local and remote Alembic
  marker is `e7f1a9c3b5d2`;
- `activity_records`, `provider_credentials`, and
  `contributor_usage_ledger` have RLS enabled, only the `novelai_app` runtime
  policy, denied `anon`/`authenticated` table access, and clean Supabase
  security-advisor results;
- the unified provider credential migration was applied remotely as
  `unify_provider_credential_registry` and `secure_unified_credentials`, with
  local Alembic revisions `d4e6f8a2b1c3` and `e7f1a9c3b5d2`; the legacy
  `contributor_credentials` table is absent, the application Alembic marker is
  stamped at `e7f1a9c3b5d2`, and the usage-ledger owner is nullable so
  historical accounting survives permanent credential deletion;
- both existing R2 buckets were retained and fully paginated inventories were
  verified empty after reset;
- the backup bucket's generic 30-day `snapshots/` retention rule was restored
  after the authorized reset;
- Novel18 (`n3266mn`, PostgreSQL ID 17) was repopulated through the repository
  importer: 31 chapters, 63 R2 objects, 191,998 bytes, and an active immutable
  generation reference; its unpublished state and existing identity were
  preserved;
- Kakuyomu (`16817330655991571532`) and NCode (`n2056dn`) were repopulated
  through the authenticated application R2 path with 88 and 148 chapters;
- the canonical namespace rekey was executed with writers frozen through
  `novelai.runtime.cli r2-migrate-novel-ids --execute --writers-frozen`:
  538 immutable objects moved from the historical slug namespaces to
  `novels/11/`, `novels/16/`, and `novels/17/`, all source namespaces were
  deleted after the database transaction committed, and database pointers,
  nested object references, and generation manifests were rewritten;
- the migration snapshot contained 538 paginated objects / 1,323,657 stored
  bytes under the three exact numeric `novels/<novel_id>/` prefixes, and every
  object had a matching logical SHA-256 metadata value; a read-only full-object
  verifier measured 5,586,652 logical uncompressed bytes and 4,262,995 bytes
  of compression savings (76.31%), with one LIST, 538 HEAD, and 538 GET
  operations and zero logical-hash mismatches;
- the post-rekey verifier found zero non-numeric namespace keys, zero embedded
  legacy-prefix references, zero JSON decode errors, zero missing database
  pointers, and zero logical-hash mismatches at the 538-object migration
  snapshot. A later writer-frozen application migration moved the seven
  pre-existing nonnumeric objects, rewrote three database references, deleted
  the seven old source keys after commit, and was followed by a complete audit
  with only numeric namespace groups and zero direct legacy database pointers;
- the Cloudflare R2 control-plane audit confirmed exactly two buckets,
  `dokushodo` and `dokushodo-backup`, both in the APAC location with Standard
  storage and default jurisdiction; application and backup lifecycle rules are
  present, and neither private bucket has a custom domain or CORS policy;
- the live Supabase performance advisor's actionable missing index was fixed by
  migration `c9d1e3f5a7b9`, adding the `novel_requests.chapter_id` foreign-key
  index; the remaining unused-index notices are informational workload
  observations and were not removed speculatively;
- the populated application `S3_*` values were migrated to `R2_*` in the root,
  development-deployment, and production-deployment environment files;
- all active backend environment assignments are now represented by their
  matching example templates, while real credentials remain only in ignored
  files; obsolete `S3_KEY_PREFIX`, `NOVEL_LIBRARY_DIR`, and legacy S3 backup
  assignments were removed;
- non-secret defaults were synchronized from the matching environment
  examples, and the local frontend overlay now documents its backend/reader
  service URLs;
- the active/template environment key audit is exact for `.env` (129/129),
  `deploy/.env` (129/129), and `frontend/.env.local` (4/4); the root and
  deployment templates share one ordered 129-key contract; no local
  `deploy/.env.production` or root `.env.local` runtime file was fabricated;
- the operator-provided application, source-read, and backup-write R2
  assignments are present and equal between the ignored root `.env` and
  `deploy/.env`, with no duplicate R2 credential keys; examples and frontend
  environment files remain secret-free;
- repository-level read-only credential checks succeeded: the migration-time
  `novelaibook r2-inventory` listed 538 application objects and zero backup
  objects through the application and backup-target credentials, and an
  isolated source-read client independently listed those application objects;
  the latest post-migration inventory lists 872 application objects / 3,299,655
  bytes and zero backup objects; the 872-object GET/hash snapshot had zero
  mismatches and 13,391,798 logical bytes; no inventory check writes or deletes
  objects;
- after the operator rotated application credentials, the backend, reader, and
  worker were recreated with the refreshed environment. The public catalog,
  ranking periods, published details, translated NCode chapter 1, unpublished
  Novel18 isolation, and current-only route rejection passed; backend,
  reader, and worker containers are healthy. Readiness remains 503 because the
  existing disk and worker probes are degraded, so production readiness is not
  claimed;
- the filesystem tar/manifest backup manager and the obsolete full-copy
  snapshot implementation were removed; R2 retention now protects retained
  manifest references and applies a configurable object grace period;
- the runtime storage boundary now exposes only explicit R2 names
  (`R2StorageBackend`, `R2Storage`, and `get_r2_storage`); generic backend
  factory/reset names were removed without a compatibility alias;
- the canonical Compose file now passes blank defaults for optional
  comma-separated list settings instead of JSON-array syntax, matching the
  environment parser contract;
- the explicit R2 client now exposes bounded `save_stream()` transfer with
  provider SHA-256 checksums, automatic multipart behavior for large assets,
  committed-length verification, and cleanup on a length mismatch;
- the final repository-wide Markdown audit covered 86 existing files and 30
  resolved local links with no unresolved targets or duplicate level-2
  headings; all 51
  design briefs (33 public and 18 admin) contain exactly one global visual
  snapshot, and the current-only route scan is clean;
- the local `novels/`, `storage/novel_library/`, and temporary repopulation
  staging paths contain no canonical novel artifacts.
- the live duplicate audit found two stale unpublished PostgreSQL rows (IDs 18
  and 19) for the NCode and Kakuyomu source URLs; they had no active
  generation or content/job/user references and were removed. The canonical
  active rows remain IDs 11, 16, and 17, and the stale tag associations were
  removed by cascade.
- per-novel efficiency evidence is now recorded in the conformance ledger;
  repeated live recrawl counters, asset deduplication savings, and backup
  object reuse remain unmeasured because recovery is still operator-deferred;
- the final live shape report records per-novel chapter/object/byte counts,
  active-generation counts, public route paths, and translation counts in
  `docs/R2-ONLY-CONFORMANCE.md`; logical-byte, repeated-crawl, and operation
  counter measurements remain explicitly unavailable.

Paused or not yet complete:

- separate source-read and backup-write credentials are now present in the
  ignored root and deployment environment files after operator provisioning;
  read-only listing succeeds with the application, source-read, and
  backup-target credentials. Backup-target write permission, object snapshot
  creation, and recovery remain unverified because `R2_BACKUP_ENABLED` remains
  false and no backup or recovery operation is being claimed;
- representative NCode chapter 1 and chapter 2 translations now pass through
  the rebuilt durable worker path, with deterministic QA and R2 persistence;
  the three-novel bulk translation remains partial and is still running or
  queued under the current checkpoint above;
- the workload audit and provider-envelope audit are complete, but provider
  quota behavior, chapter-level QA failures, and the final persisted count
  still require the bulk queue to finish before translation completion can be
  claimed;
- the public reader audit passes catalog/detail and unpublished/adult isolation,
  while only the translated NCode chapter has passed the published chapter-read
  path and the remaining published chapter reads remain pending;
- focused takedown enforcement and public isolation now pass the repository
  suite; hosted CDN/public-origin propagation remains unverified alongside
  bulk translation, backup/restore, translated public chapter behavior beyond
  the representative NCode chapter, and production-scale telemetry;
- the R2 prefix-cleanup path now snapshots all paginated keys before deleting
  batches, preventing provider continuation cursors from skipping objects;
  the focused R2 cleanup suite passes 8 tests and the catalog/cutover suite
  passes 10 tests, including unchanged-recrawl no-op and incremental-backup
  reuse coverage. A live synthetic Phase 6 seed was stopped after 193
  temporary objects because the workstation-to-R2 path made the full
  1,428-chapter fixture impractical; the exact namespace cleanup was rerun and
  verified empty, so no production-scale performance claim is made;
- the Supabase performance advisor still reports informational unused-index
  observations (58 after the new foreign-key index was added); these are a
  workload follow-up, not a security blocker for the cutover;

### Resource-audit scale checkpoint - 2026-08-23 15:34 UTC

The fourth application-service worker observation was intentionally stopped at
a safe checkpoint after the full queue proved unsuitable as an efficiency
acceptance workload. The final PostgreSQL chapter projection was NCode 75
complete / 19 failed / 49 pending / 1 fetching / 4 translating; Kakuyomu 9
complete / 78 failed / 1 translating; and Novel18 29 complete / 2 failed.
The worker sample reached approximately 224 MiB resident memory, 256 MB
received, 27.4 MB sent, and a short peak near 57% CPU. These are local
container indicators and are not a billed-byte attribution for the historical
Supabase egress report.

The graceful stop exceeded its window, so the dedicated one-shot container was
force-terminated and removed. No PostgreSQL row, runtime JSON, canonical R2
object, or endpoint was manually edited. The interrupted fetching/translating
states remain subject to normal lease expiry and application-service recovery;
this checkpoint does not claim terminal translation or final chapter readback.

This result does not show that moving immutable novel content to R2 was a
mistake. It reinforces the intended boundary: PostgreSQL should retain compact
catalog/state, pointers, hashes, and queue projections, while R2 retains raw,
translated, and media artifacts. Repeated row hydration and synchronous
database/storage work inside concurrent async chapter tasks remain the primary
scale risks. The next authorized workload should be a one-to-three-chapter
sample for each source with fresh query, provider, and R2 counters, followed by
1k/10k/100k-DAU-equivalent load stages; a full bulk queue must not be treated as
a reader-capacity test.

### Bounded three-source validation follow-up - 2026-08-23 15:59 UTC

The three original full-queue activities were paused through
`ActivityQueueService`. Three new one-chapter sample activities were created
through the same service and executed sequentially at provider/chapter
concurrency 1. NCode, Novel18, and Kakuyomu each reached `completed`, and an
application-service readback confirmed raw and translated artifacts for all
three selected chapters. The sample containers exited cleanly. The original
full queues remain paused; this closes bounded validation only and does not
claim that the remaining bulk queue is terminal, economical, or production
ready.

---

# 1. Locked Decisions

The following decisions are final for this implementation and must not be reopened unless a blocking technical issue is discovered.

### Storage

- Cloudflare R2 is the **only canonical novel artifact store**.
- Remove the filesystem content backend completely.
- Remove storage-backend runtime selection.
- Do not retain compatibility with `NOVEL_LIBRARY_DIR`.
- Do not retain compatibility with `storage/novel_library`.
- Do not retain compatibility with the accidental root `novels/` directory.
- Local disk is allowed only for disposable runtime data.
- PostgreSQL stores mutable application truth.
- Redis/Valkey stores transient distributed coordination.
- R2 stores immutable durable artifacts.

### Buckets

Use the existing buckets:

```text
dokushodo
dokushodo-backup
```

Do not introduce:

```text
-prod
-v1
storage/novel_library/
```

or equivalent compatibility prefixes.

The application bucket begins directly with:

```text
dokushodo/
└── novels/
```

The backup bucket likewise has no schema-version prefix.

### Existing novels

The three currently known novels must retain their existing public identity and URLs.

Before destructive cleanup, preserve and verify their:

- immutable novel ID;
- current public slug;
- public Dokushodo URL;
- original source URL;
- source adapter/source key;
- publication state;
- adult-content state;
- takedown state;
- other PostgreSQL identity required to recreate them.

The current novel objects may then be deleted from R2 and repopulated through the new architecture.

Do not create new novel identities during repopulation.

### Current R2 contents

Start from a clean artifact-storage state.

1. Freeze all novel-content writers.
2. Preserve and verify the three novel identities and source URLs.
3. Empty `dokushodo-backup`.
4. Verify `dokushodo-backup` contains zero objects.
5. Empty `dokushodo`.
6. Verify `dokushodo` contains zero objects.
7. Keep both bucket resources themselves.
8. Implement the new architecture.
9. Repopulate the three novels.
10. Verify their existing public URLs still work.

No existing backup artifact is required to survive this reset.

### Documentation

Documentation synchronization is **Phase 0** and is mandatory.

Before changing implementation code:

1. recursively discover **every `.md` file in the repository**;
2. read every `.md` file completely;
3. identify every statement affected by this architecture;
4. reconcile contradictions;
5. update affected documentation first;
6. establish the synchronized documentation as the implementation contract.

After implementation is complete, perform a second repository-wide documentation review and assess the implementation **against the synchronized documentation**, not against assumptions made during coding.

---

# 2. Architectural Invariants

These invariants define the target architecture.

## 2.1 R2 invariant

> R2 stores immutable durable application artifacts.

Examples:

- scraped chapter bodies;
- generation manifests;
- translation outputs;
- edited translation outputs;
- durable media/OCR overlays;
- downloaded and normalized novel assets.

R2 must not become a database, queue, log store, or temporary workspace.

---

## 2.2 PostgreSQL invariant

> PostgreSQL stores mutable application truth and object references.

Examples:

- novel identity;
- slug;
- source URL;
- catalog metadata;
- public visibility;
- adult-content state;
- takedown state;
- active generation;
- chapter ordering;
- active source artifact key;
- active translation artifact key;
- active media artifact key;
- crawl state;
- translation state;
- glossary;
- glossary revisions;
- user preferences;
- jobs;
- durable usage/accounting information;
- public projections;
- rankings/search data.

Public application state must never depend on discovering objects through R2 listings.

---

## 2.3 Redis/Valkey invariant

> Redis/Valkey stores transient distributed coordination.

Examples:

- queue dispatch;
- short-lived locks;
- rate limits;
- provider quota coordination;
- deduplicated execution leases;
- transient caches;
- worker coordination.

Loss of Redis must not permanently destroy canonical novel data.

---

## 2.4 Local disk invariant

> Local disk stores only disposable or reconstructable runtime data.

A destroyed VPS must be replaceable without restoring local novel-content files.

Permitted local examples:

```text
runtime/
├── cache/
├── staging/
├── tmp/
├── logs/
└── disposable-checkpoints/
```

A local file must not be the sole source of truth for published novel content.

---

## 2.5 Identity invariant

> Canonical R2 paths use immutable internal IDs, never mutable titles or slugs.

Never use a title or public slug as the canonical object namespace.

Use:

```text
novels/<novel_id>/
```

not:

```text
novels/<novel-slug>/
```

Changing a title or slug must require **zero R2 object renames or copies**.

---

## 2.6 Immutability invariant

> Once an R2 content object has been committed under its content-addressed key, its bytes are immutable.

A changed artifact gets a new content hash and therefore a new object key.

Do not overwrite historical content-addressed objects.

---

## 2.7 Reuse invariant

> A recrawl or retranslation writes only content whose canonical bytes changed.

Unchanged chapter bodies, translations, media, and assets must be reused.

---

## 2.8 Query invariant

> Normal reader/API requests perform exact R2 GETs from keys obtained from PostgreSQL.

Normal application traffic must not require:

```text
LIST novels/...
LIST translations/...
LIST generations/...
```

R2 listing is reserved for administrative workflows such as:

- integrity auditing;
- garbage collection;
- backup;
- migration;
- recovery;
- controlled reconciliation.

---

# 3. Target R2 Application Bucket

Bucket:

```text
dokushodo
```

Target layout:

```text
dokushodo/
└── novels/
    └── <novel_id>/
        ├── generations/
        │   └── <generation_id>.json.gz
        │
        ├── chapters/
        │   └── <chapter_id>/
        │       └── <source_hash>.json.gz
        │
        ├── translations/
        │   └── <chapter_id>/
        │       └── <translation_hash>.json.gz
        │
        ├── media/
        │   └── <chapter_id>/
        │       └── <media_hash>.json.gz
        │
        └── assets/
            └── <sha256>.<normalized_extension>
```

No additional top-level application prefix is required.

---

# 4. What Does Not Belong in `dokushodo`

Do not recreate the current filesystem hierarchy in R2.

The following concepts must **not** become R2 application objects:

```text
novels/index.json

preferences.json
usage.json
translation_cache.json

.healthcheck/

logs/

activity_log/
    queue.json
    source_health.json

runtime/
    fetch_cache/
    translation/
    traceability/

state/
checkpoints/

active_generation.lock

translations/active/

metadata_backups/

temporary provider requests
temporary provider responses
retry-attempt files
worker scratch files
scheduler caches
local locks
```

These must either:

- move to PostgreSQL;
- move to Redis/Valkey;
- remain disposable local runtime data;
- or be removed entirely.

---

# 5. Generation Model

A generation is a **small immutable manifest**, not a complete duplicate directory tree.

Example:

```text
novels/<novel_id>/generations/<generation_id>.json.gz
```

Conceptual contents:

```json
{
  "schema_version": 1,
  "generation_id": "...",
  "novel_id": "...",
  "created_at": "...",
  "source": {
    "source_key": "...",
    "source_url": "..."
  },
  "metadata": {
    "title": "...",
    "author": "..."
  },
  "chapters": [
    {
      "chapter_id": "...",
      "position": 1,
      "source_hash": "...",
      "object_key": "novels/.../chapters/.../...json.gz",
      "assets": [
        "novels/.../assets/....webp"
      ]
    }
  ]
}
```

The exact schema should reuse existing domain models wherever practical rather than introducing unnecessary parallel representations.

---

# 6. Generation Deduplication

A generation must reference existing immutable chapter objects when the source content is unchanged.

Example:

Generation A:

```text
chapter 1 → hash AAA
chapter 2 → hash BBB
chapter 3 → hash CCC
```

After recrawl only chapter 2 changed:

```text
chapter 1 → hash AAA  reuse
chapter 2 → hash DDD  new
chapter 3 → hash CCC  reuse
```

Only:

```text
DDD
```

and the new generation manifest are uploaded.

Do not upload duplicate copies of chapters 1 and 3.

---

# 7. No-Op Recrawl Rule

If a recrawl produces no canonical source change:

- do not write duplicate chapter objects;
- do not write duplicate assets;
- do not create a meaningless new generation;
- update only appropriate crawl timestamps/telemetry/state in PostgreSQL.

Compute a deterministic generation/content fingerprint.

If:

```text
candidate_fingerprint == active_fingerprint
```

the operation is a no-op from the artifact-storage perspective.

---

# 8. Chapter Object Model

Source chapters are immutable objects:

```text
novels/<novel_id>/
└── chapters/
    └── <chapter_id>/
        └── <source_hash>.json.gz
```

`source_hash` must derive from the canonical serialized chapter representation.

Hashing must be deterministic.

Canonicalization must account for:

- stable key ordering;
- deterministic encoding;
- normalized line endings;
- deterministic Unicode handling;
- exclusion of volatile timestamps/telemetry that would create false changes.

Do not let operational metadata cause a new source hash.

---

# 9. Translation Object Model

Translations are immutable artifacts:

```text
novels/<novel_id>/
└── translations/
    └── <chapter_id>/
        └── <translation_hash>.json.gz
```

PostgreSQL identifies the active translation.

There is no R2:

```text
translations/active/
```

pointer namespace.

A translation identity/fingerprint should account for relevant inputs such as:

- source chapter hash;
- source language;
- target language;
- glossary revision;
- translation policy/prompt version;
- substantive model/provider parameters;
- translation result content.

Do not incorporate volatile request IDs or timestamps into content identity.

---

# 10. Selective Translation Invalidation

Retranslation must not automatically rewrite an entire novel.

Examples:

### Source chapter changes

Invalidate only translations dependent on the changed source hash.

### Glossary changes

Invalidate only chapters whose translation semantics are affected where the existing glossary-invalidation architecture can determine this safely.

### Translation policy changes

Invalidate only the scope required by the policy change.

### Media-only changes

Do not invalidate text translations unless text translation actually depends on the changed media state.

The target is:

```text
changed dependency
       ↓
smallest safe invalidation set
       ↓
only required translations regenerated
```

---

# 11. Edited Translation Model

Human or administrator edits must not overwrite immutable translation artifacts.

An edited translation produces a new immutable translation object and becomes active through PostgreSQL.

Example:

```text
translation A
      ↓ edit
translation B
```

PostgreSQL changes:

```text
active_translation_key: A → B
```

Object A remains immutable until archive/retention/GC policy permits removal from the application bucket.

---

# 12. Media Overlay Model

Durable OCR/image-derived media state uses:

```text
novels/<novel_id>/
└── media/
    └── <chapter_id>/
        └── <media_hash>.json.gz
```

Like translations:

- objects are immutable;
- PostgreSQL identifies the active artifact;
- unchanged media is reused;
- superseded media becomes eligible for archival/GC.

---

# 13. Asset Model

Assets are content-addressed:

```text
novels/<novel_id>/
└── assets/
    └── <sha256>.<ext>
```

Do not duplicate the same image across:

```text
generation A
generation B
generation C
```

when the bytes are identical.

The same object should be referenced repeatedly.

---

# 14. Asset Normalization

Images are expected to become the largest storage consumer.

Implement one canonical asset pipeline where practical:

```text
download
   ↓
validate
   ↓
normalize orientation
   ↓
normalize format/quality when safe
   ↓
calculate SHA-256
   ↓
check existence
   ↓
upload once
```

Avoid retaining multiple derivatives by default such as:

```text
original.jpg
optimized.webp
small.webp
medium.webp
large.webp
thumbnail.webp
```

unless the application demonstrably requires them.

Do not sacrifice source fidelity required for OCR or reader quality merely to save storage.

Normalization policy must be explicit and covered by tests.

---

# 15. Compression

Text-heavy R2 artifacts should use transparent compression.

Target:

```text
.json.gz
```

for:

- chapters;
- translations;
- media JSON;
- generation manifests.

Persist appropriate object metadata including:

```text
Content-Type: application/json
Content-Encoding: gzip
```

Hashing semantics must be defined clearly.

Prefer hashing the canonical **uncompressed logical representation** so compression implementation changes do not create false logical versions.

Store the logical SHA-256 and, where useful, the uploaded-object checksum separately.

---

# 16. PostgreSQL Object Index

PostgreSQL is the authoritative lookup layer.

Relevant records should contain exact R2 object keys.

Conceptually:

```text
novel
├── novel_id
├── slug
├── source_url
├── active_generation_id
└── ...

chapter
├── chapter_id
├── novel_id
├── source_hash
├── source_object_key
├── active_translation_id/key
├── active_media_id/key
└── ...
```

The exact schema should extend existing tables/models instead of creating redundant projections where current structures already satisfy the requirement.

---

# 17. Activation Model

Remove filesystem-era activation semantics.

Do not use:

```text
active_generation.lock
atomic filesystem rename
R2 active_generation.json
R2 translations/active/*.json
```

Target generation activation:

```text
1. Build candidate generation.
2. Upload all new immutable chapter/assets objects.
3. Verify successful writes/checksums.
4. Upload immutable generation manifest.
5. Begin PostgreSQL transaction.
6. Verify expected current generation / concurrency version.
7. Update active generation and chapter references.
8. Commit transaction.
9. Publish downstream events/cache invalidation.
```

If transaction activation fails, newly uploaded but unreferenced objects remain harmless and are handled later by garbage collection.

---

# 18. Concurrency

Use PostgreSQL and/or Redis semantics for coordination.

R2 is not the coordination database.

Protect against:

- two crawlers activating competing generations;
- translator races;
- stale glossary revisions;
- simultaneous media updates;
- duplicate object uploads;
- worker retries after timeouts;
- stale activation attempts.

Prefer deterministic idempotency keys and database optimistic concurrency where appropriate.

---

# 19. Direct R2 Storage Implementation

Replace generic filesystem/S3 selection with an explicit R2 implementation.

Target concept:

```text
novelai.storage.r2
```

or equivalent repository-appropriate package placement.

The implementation may use the S3-compatible protocol internally, but application semantics should describe it as R2.

Configuration should be R2-specific.

Example conceptual configuration:

```text
R2_ENDPOINT
R2_REGION=auto

R2_BUCKET=dokushodo
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY

R2_BACKUP_BUCKET=dokushodo-backup
R2_BACKUP_ACCESS_KEY_ID
R2_BACKUP_SECRET_ACCESS_KEY
```

Reuse the repository's existing settings conventions and secret-loading patterns.

Do not hard-code credentials.

---

# 20. Remove Filesystem Storage Support

Delete implementation paths that exist solely for canonical filesystem novel storage.

Candidate removals include, after confirming usages:

```text
FilesystemBackend
STORAGE_BACKEND
NOVEL_LIBRARY_DIR
filesystem content backend selection
filesystem content locks
filesystem atomic-renaming abstractions
filesystem novel discovery
filesystem slug index
filesystem generation activation
filesystem translation activation
```

Do not keep dead compatibility adapters.

Tests that genuinely test unrelated services should use mocks/fakes for R2 interfaces rather than reviving a filesystem production backend.

A lightweight in-memory test double is acceptable if needed.

---

# 21. Local Runtime Directory

Create one clearly noncanonical runtime root.

Example:

```text
data/
└── runtime/
    ├── cache/
    │   ├── fetch/
    │   └── translation/
    │
    ├── staging/
    │   ├── downloads/
    │   └── uploads/
    │
    ├── tmp/
    │
    ├── logs/
    │
    └── checkpoints/
```

The exact configured VPS path may differ.

Do not place this under the R2 namespace.

A test should demonstrate that deleting this entire directory cannot remove canonical novel content.

---

# 22. Runtime State Classification

Audit every existing direct `Path` writer.

Classify each one explicitly.

### PostgreSQL

Use PostgreSQL for durable mutable state such as:

- user preferences;
- durable usage history;
- catalog state;
- chapter workflow state;
- durable job state;
- glossary state;
- active artifact references.

### Redis/Valkey

Use Redis/Valkey for:

- queue dispatch;
- transient source health;
- rate limits;
- distributed locks;
- short-lived provider quota coordination;
- caches.

### Local runtime

Use local files only for:

- HTTP fetch cache;
- temporary translation chunks;
- temporary raw provider responses;
- upload staging;
- temporary image transforms;
- logs;
- disposable checkpoints.

### Remove

Delete files/concepts that become redundant after database/Redis migration.

---

# 23. Backup Bucket

Bucket:

```text
dokushodo-backup
```

Target hierarchy:

```text
dokushodo-backup/
├── objects/
│   └── novels/
│       └── <novel_id>/
│           ├── chapters/
│           ├── translations/
│           ├── media/
│           ├── generations/
│           └── assets/
│
├── snapshots/
│   └── <snapshot_id>/
│       └── manifest.json
│
├── database/
│   └── <timestamp>/
│       ├── database.dump.zst.enc
│       └── manifest.json
│
└── migrations/
    └── <migration_id>/
        ├── source-state.json
        ├── application-manifest.json
        ├── backup-manifest.json
        └── verification.json
```

No `v1/` prefix.

---

# 24. Incremental Backup Model

Do not create complete duplicated bucket snapshots.

Backup objects should be immutable and content-addressed.

Snapshot N references objects already present in the backup bucket.

Example:

Snapshot 1 requires:

```text
A
B
C
D
```

Snapshot 2 requires:

```text
A
B
C
E
```

Only:

```text
E
```

is newly copied.

Snapshot 2 adds a small manifest referencing:

```text
A
B
C
E
```

Do not duplicate:

```text
A
B
C
```

under every snapshot directory.

---

# 25. Backup Independence

Application credentials must not have broad destructive access to the backup bucket.

Prefer separate credentials:

### Application credential

Access:

```text
dokushodo
```

only.

### Backup credential

Access required to:

- read application objects;
- create backup objects/manifests.

### Restore credential

Read:

```text
dokushodo-backup
```

as required for recovery.

Avoid allowing an application compromise to trivially delete both live and backup data.

---

# 26. Backup Retention

Begin with a bounded retention policy.

Example initial target:

```text
7 daily
4 weekly
3 monthly
```

The implementation should make retention configurable.

Do not blindly delete backup objects based only on age.

Delete an immutable backup object only when:

1. no retained snapshot references it;
2. no restore/migration process references it;
3. its safety grace period has passed.

---

# 27. Database Dumps

Database dumps remain separate immutable backup artifacts.

Target:

```text
database/
└── <timestamp>/
    ├── database.dump.zst.enc
    └── manifest.json
```

Requirements:

- compression;
- encryption before durable backup storage;
- checksum verification;
- bounded retention;
- isolated restore testing.

Do not put database credentials or encryption keys in the bucket.

---

# 28. Application-Bucket Garbage Collection

Content-addressed storage requires explicit garbage collection.

A source/translation/media object can become unreferenced after:

- recrawl;
- retranslation;
- edit;
- media regeneration;
- novel deletion.

Do not delete immediately.

Implement mark-and-sweep semantics.

Conceptual lifecycle:

```text
active
   ↓
superseded
   ↓
backup confirmed
   ↓
unreferenced
   ↓
grace period
   ↓
delete from application bucket
```

---

# 29. GC Safety

An object must not be deleted from `dokushodo` if referenced by:

- current active generation;
- current active translation;
- current active media state;
- an activation currently in progress;
- a protected rollback generation;
- an unfinished backup snapshot;
- any other canonical PostgreSQL reference.

Use a safety grace period.

Example initial default:

```text
7 days
```

Make the period configurable.

---

# 30. Archival Flow

Superseded application objects should not remain indefinitely in the live bucket.

Target flow:

```text
new artifact activated
        ↓
old artifact becomes superseded
        ↓
backup/archive copy confirmed
        ↓
snapshot references verified
        ↓
grace period
        ↓
remove unreferenced old object from dokushodo
```

This keeps the application bucket close to:

> currently active content + short rollback safety margin.

Historical growth occurs primarily in the backup bucket.

---

# 31. Novel Deletion

Deleting a novel from the application must be a state transition, not an immediate recursive R2 purge.

Sequence:

```text
1. Mark unavailable/deleted in PostgreSQL.
2. Remove public/catalog visibility transactionally.
3. Stop new work.
4. Ensure required backup/archive state exists.
5. Mark application objects as GC candidates.
6. Apply grace period.
7. Sweep safe application objects.
```

Respect takedown/legal deletion requirements when they require different retention semantics.

---

# 32. Storage-Hungry Workloads

The architecture must explicitly control the following growth sources.

## Highest risk: images/assets

Mitigation:

- hash deduplication;
- one canonical normalized object;
- reuse across generations.

## High risk: complete recrawl snapshots

Mitigation:

- immutable shared chapter objects;
- generation manifests;
- upload only changed chapters;
- no-op crawl detection.

## High risk: retranslation history

Mitigation:

- immutable hash-addressed outputs;
- selective invalidation;
- archive superseded output;
- application GC.

## High risk: full duplicated backups

Mitigation:

- incremental backup objects;
- snapshot manifests;
- reference-based retention.

## Moderate risk: provider raw responses

Mitigation:

- keep locally only while operationally necessary;
- persist durable normalized result, not every provider envelope.

## Moderate risk: database dumps

Mitigation:

- compression;
- bounded retention.

## Low risk: generation manifests

These are small and should not materially drive capacity.

---

# 33. Object-Count-Hungry Workloads

Avoid creating R2 objects for tiny operational events such as:

```text
attempt-1.json
attempt-2.json
request-123.json
scheduler-state.json
pipeline-event-456.json
worker-heartbeat.json
lock.json
quota-state.json
```

Even when storage consumption is small, huge object counts create:

- extra operations;
- latency;
- listing complexity;
- backup complexity;
- GC complexity.

Store operational events in PostgreSQL/Redis/logging infrastructure instead.

---

# 34. R2 Listing Requirements

Administrative listings must paginate fully.

Audit every existing R2/S3 listing implementation.

Requirements:

- recursive listings paginate;
- nonrecursive listings paginate;
- continuation tokens handled correctly;
- empty pages handled correctly;
- prefix boundaries tested;
- deletion utilities handle more than one page;
- cleanup never silently processes only the first result page.

---

# 35. Upload Requirements

R2 writes must support:

- streaming uploads where appropriate;
- multipart uploads for large artifacts;
- checksums;
- correct content type;
- correct content encoding;
- timeout handling;
- permission errors;
- partial-upload cleanup;
- safe retry behavior;
- deterministic idempotency.

Do not buffer arbitrarily large images/artifacts completely in memory unless bounded and justified.

---

# 36. Read Requirements

Exact-key reads must distinguish at least:

- object exists;
- object missing;
- permission denied;
- timeout/network failure;
- malformed/corrupt payload;
- checksum/integrity mismatch.

Missing artifact errors must not silently become valid empty chapter content.

---

# 37. Integrity Metadata

For every durable object, retain sufficient metadata to verify integrity.

At minimum:

```text
logical SHA-256
stored byte length
content type
content encoding
creation time
artifact type
```

ETag may also be retained but must not be treated as a universal substitute for SHA-256 semantics.

---

# 38. Observability

Add/retain telemetry for:

- R2 GET count;
- R2 PUT count;
- R2 DELETE count;
- R2 LIST count;
- uploaded bytes;
- downloaded bytes;
- deduplication hits;
- deduplication misses;
- no-op crawls;
- new chapter objects;
- reused chapter objects;
- new translation objects;
- reused translations;
- GC candidates;
- GC deletions;
- backup objects copied;
- backup objects reused;
- checksum failures;
- R2 latency;
- R2 errors.

This is necessary to verify that the lean-storage design is actually working.

---

# 39. Phase 0 — Repository-Wide Markdown Synchronization

**This phase must happen first. No implementation code changes are allowed before it completes.**

## 39.1 Discover documentation

Recursively enumerate every:

```text
*.md
```

file in the repository.

Include:

- root README files;
- `AGENTS.md`;
- architecture documentation;
- deployment documentation;
- storage documentation;
- environment/configuration documentation;
- debt documents;
- implementation specs;
- testing documentation;
- operational runbooks;
- archived documents;
- nested module README files;
- any other Markdown file.

Do not assume only `docs/` matters.

---

## 39.2 Read all documentation

Read every discovered Markdown file completely.

For large files, read them in contiguous chunks until the whole file has been examined.

Do not rely only on grep snippets.

---

## 39.3 Build documentation impact matrix

For every `.md` file, classify:

```text
affected
unaffected
historical/archive
obsolete
contradictory
```

Record why.

Search specifically for references to:

```text
storage/novel_library
NOVEL_LIBRARY_DIR
STORAGE_BACKEND
filesystem
FilesystemBackend
S3Backend
S3_KEY_PREFIX
novels/index.json
active_generation.json
active_generation.lock
metadata_backups
translations/active
checkpoints
state/
backups/
R2
S3
Cloudflare
generation
storage contract
backup
restore
deployment
local storage
runtime storage
```

Also detect conceptual references even when exact terms differ.

---

## 39.4 Synchronize affected documentation

Update affected Markdown documents so they consistently describe the target architecture in this plan.

At minimum documentation must agree that:

```text
R2 = canonical immutable artifact store
PostgreSQL = mutable application truth
Redis/Valkey = transient distributed coordination
local disk = disposable runtime only
```

Documentation must describe:

```text
dokushodo/novels/<novel_id>/...
```

and the new backup structure.

Remove instructions that tell operators or developers to use filesystem canonical storage.

---

## 39.5 Resolve conflicting documentation

When documents disagree:

1. determine which document currently acts as the architectural authority;
2. reconcile all active documents with the locked decisions here;
3. mark obsolete historical docs clearly if they must remain;
4. do not leave two active specifications describing different storage architectures.

Archive documents may retain historical statements only if clearly identified as historical and incapable of being mistaken for current instructions.

---

## 39.6 Synchronize configuration documentation

Documentation must remove/deprecate-as-deleted—not merely "legacy"—references to:

```text
STORAGE_BACKEND
NOVEL_LIBRARY_DIR
filesystem canonical storage
generic filesystem/S3 backend switching
```

Document the final R2-specific environment contract.

---

## 39.7 Synchronize backup documentation

Update backup/restore documentation to describe:

- `dokushodo-backup`;
- incremental immutable backup objects;
- snapshot manifests;
- encrypted PostgreSQL dumps;
- retention;
- integrity verification;
- isolated restore testing.

---

## 39.8 Synchronize deployment documentation

Document the intended deployment model:

```text
Cloudflare
    +
one VPS
    +
Supabase
```

with:

- R2 as canonical artifact storage;
- PostgreSQL on Supabase;
- Redis/Valkey initially deployable on the VPS;
- runtime filesystem explicitly disposable.

Do not introduce an external Redis dependency unless required independently.

---

## 39.9 Documentation-first gate

Before implementation begins, produce evidence:

```text
total .md files discovered
total .md files read
affected files
changed files
unaffected files
archived/historical files
contradictions resolved
```

Then run repository Markdown/documentation checks if available.

Only after this gate passes may implementation code change.

---

# 40. Phase 1 — Baseline and Destructive-Cutover Preparation

Before deleting anything:

1. inspect Git status;
2. identify current branch;
3. record existing tests/status;
4. inventory the current application R2 bucket;
5. inventory the current backup R2 bucket;
6. inventory PostgreSQL novel identities;
7. identify exactly the three novels to preserve;
8. record their immutable IDs;
9. record their public slugs/URLs;
10. record their original source URLs;
11. verify each source URL is still reachable and crawlable;
12. verify current public routing does not require R2 slug paths;
13. freeze crawler/translator/media writers.

Generate a sanitized migration record.

Do not store credentials in evidence.

---

# 41. Phase 2 — Clean R2 Reset

Only after Phase 1 succeeds:

## Backup bucket first

Delete all objects in:

```text
dokushodo-backup
```

using fully paginated deletion.

Verify independently:

```text
object count = 0
```

## Application bucket second

Delete all objects in:

```text
dokushodo
```

using fully paginated deletion.

Verify independently:

```text
object count = 0
```

Do not delete either bucket resource.

Do not delete the three preserved PostgreSQL novel identities.

---

# 42. Phase 3 — Remove Legacy Storage Architecture

Delete canonical filesystem support.

Remove:

- filesystem backend implementation;
- filesystem backend configuration;
- legacy backend selection;
- legacy path settings;
- old canonical root handling;
- content-related file locking;
- filesystem generation activation;
- filesystem discovery/index semantics.

Fix any tests that previously leaked:

```text
./novels/
```

into the repository root.

After this phase, running tests must not create:

```text
novels/
storage/novel_library/
```

as canonical data roots.

---

# 43. Phase 4 — Runtime State Separation

Audit every direct `Path` access in runtime/backend code.

For each writer/read path:

1. identify semantic owner;
2. move durable mutable state to PostgreSQL;
3. move transient distributed state to Redis;
4. move disposable files to the runtime root;
5. delete obsolete file-backed state.

Add tests proving runtime files are not required to reconstruct canonical novel state.

---

# 44. Phase 5 — Implement R2Storage

Build the explicit R2 implementation.

Required capabilities:

```text
get
put
exists/head
delete
paginated list
batch-safe cleanup
streaming
multipart upload
metadata
checksums
timeouts
retry classification
permission errors
missing-object errors
```

Use the existing S3-compatible client library where appropriate.

Do not expose generic backend-selection behavior merely because the underlying protocol is S3-compatible.

---

# 45. Phase 6 — Implement Content Addressing

Implement deterministic canonical serialization and hashing for:

- source chapters;
- translations;
- media;
- assets;
- generation fingerprints.

Requirements:

- repeated serialization produces identical hashes;
- metadata timestamps do not create false revisions;
- unchanged input produces no new object;
- content change always produces a different logical hash.

Add dedicated unit and property-style tests where useful.

---

# 46. Phase 7 — Implement Generation Manifests

Replace copied generation directories with manifest-based generations.

A generation manifest must reference immutable source chapter and asset objects.

Validate:

- complete chapter ordering;
- unique chapter IDs;
- correct source hashes;
- valid object keys;
- asset references;
- source state/removal semantics;
- generation-level fingerprint.

A manifest must not activate until all referenced new objects are successfully present.

---

# 47. Phase 8 — PostgreSQL Activation and Object References

Move active pointer semantics into PostgreSQL.

Implement transaction-safe:

- generation activation;
- translation activation;
- edited-translation activation;
- media activation.

Remove R2/file pointer artifacts.

Test:

- concurrent activation;
- stale writer;
- transaction rollback;
- crash after R2 PUT but before database commit;
- retry after unknown network result.

---

# 48. Phase 9 — Translation and Glossary Integration

Integrate the new object model with translation workflows.

Ensure:

- source hash participates in translation validity;
- glossary revision participates where required;
- prompt/policy version participates where required;
- unchanged translations are reused;
- selective invalidation remains functional;
- retranslation writes only changed outputs.

Do not persist temporary translation chunk/request/attempt infrastructure permanently to R2.

---

# 49. Phase 10 — Media and Asset Integration

Move media overlays and downloaded chapter assets to the new model.

Implement:

- asset SHA-256 deduplication;
- normalization;
- safe format handling;
- object reuse across generations;
- media overlay hashing;
- PostgreSQL active references.

Test duplicate-image reuse explicitly.

---

# 50. Phase 11 — Backup System

Implement the new clean backup architecture.

Create the first new baseline only after the repopulated application state passes acceptance tests.

Requirements:

- content-addressed backup objects;
- incremental copying;
- snapshot manifests;
- encrypted compressed PostgreSQL dumps;
- integrity checks;
- retention;
- restore tooling;
- backup credentials separated from application credentials.

---

# 51. Phase 12 — Archive and Garbage Collection

Implement reference-aware archival and mark-and-sweep GC.

Tests must cover:

- active object protection;
- superseded generation;
- superseded translation;
- superseded media;
- shared asset;
- object referenced by multiple generations;
- backup-in-progress protection;
- grace period;
- abandoned upload/object;
- deleted novel;
- concurrent activation while GC is running.

Never implement:

```text
delete objects older than X
```

as the sole application-object GC rule.

---

# 52. Phase 13 — Repopulate Existing Novels

Using the preserved three novel identities:

1. crawl from the preserved source URL;
2. create chapter objects;
3. upload assets;
4. create generation manifest;
5. activate in PostgreSQL;
6. translate using the new translation model;
7. activate translations;
8. generate media overlays as required;
9. rebuild/update projections;
10. preserve original public slug and URL.

Do not create replacement public novel records.

---

# 53. Phase 14 — Existing URL Verification

For each of the three novels verify:

```text
old public URL
     ↓
same novel identity
     ↓
new PostgreSQL artifact references
     ↓
new R2 objects
```

Verify:

- catalog page;
- detail page;
- chapter listing;
- chapter reading;
- translated content;
- images;
- adult-content rules;
- unpublished-content rules;
- takedown isolation;
- ranking/search projection if applicable.

No redirect caused solely by storage migration should be necessary.

---

# 54. Phase 15 — Lean-Storage Acceptance Tests

Create explicit tests proving the architecture saves space.

## Unchanged recrawl

Given a 100-chapter novel with no source changes:

Expected:

```text
new chapter objects = 0
new asset objects = 0
new generation = 0
```

aside from mutable PostgreSQL crawl telemetry.

## One changed chapter

Given one changed chapter:

Expected:

```text
new source chapter objects = 1
unchanged chapter uploads = 0
new generation manifest = 1
```

## Duplicate image

If an existing asset hash is encountered:

Expected:

```text
new image uploads = 0
```

## Selective retranslation

If four chapters are invalidated:

Expected:

```text
translation work ≈ 4 chapters
```

not the full novel.

## Repeat backup

If only one new artifact exists since the previous snapshot:

Expected:

```text
new backup content object copies = 1
+ new snapshot manifest
+ database dump as configured
```

not a complete application-bucket duplicate.

---

# 55. Phase 16 — R2 Integration Tests

Use an isolated test prefix or dedicated safe test namespace in the real R2 bucket.

Test:

- PUT;
- GET;
- HEAD;
- overwrite protection/content addressing;
- DELETE;
- missing object;
- permission error handling where testable;
- timeout/retry behavior;
- gzip roundtrip;
- checksum verification;
- multipart upload;
- pagination beyond one response page;
- cleanup;
- concurrent writer behavior;
- duplicate PUT avoidance.

Tests must always clean their isolated test objects.

Never operate on production novel prefixes from integration tests.

---

# 56. Phase 17 — Public-System Regression

Run the complete relevant suite.

At minimum verify:

- public catalog;
- public detail;
- chapter reads;
- rankings;
- search;
- adult-content filtering;
- unpublished isolation;
- takedown isolation;
- admin novel workflows;
- crawl;
- recrawl;
- translation;
- retranslation;
- media;
- editing;
- generation activation;
- rollback/recovery;
- worker restart;
- cache behavior;
- provider quota behavior;
- backup;
- restore.

---

# 57. Phase 18 — Performance Validation

Rerun the existing production-like/Phase 6 scenarios.

Measure:

- cold request latency;
- warm request latency;
- PostgreSQL latency;
- R2 GET latency;
- R2 operation counts;
- queue latency;
- worker throughput;
- pool saturation;
- error rate;
- provider telemetry.

Public catalog/detail queries must remain projection-first.

A catalog request must not enumerate chapter or novel R2 prefixes.

---

# 58. Phase 19 — Restore Drill

Perform an isolated recovery exercise.

Required evidence:

1. restore PostgreSQL dump to isolated target;
2. recover representative application artifacts from `dokushodo-backup`;
3. verify checksums;
4. rebuild required PostgreSQL object references if the restore procedure requires it;
5. read representative chapters/assets/translations;
6. verify restored generation consistency.

Do not declare the backup architecture complete merely because backup creation succeeds.

Restore success is required.

---

# 59. Phase 20 — Final Repository-Wide Documentation Review

After implementation and all tests:

**Return to every Markdown file discovered in Phase 0.**

Read every `.md` file again, or systematically revalidate it against the synchronized Phase 0 baseline.

The implementation must now be reviewed against those docs.

Search again for stale references to:

```text
storage/novel_library
NOVEL_LIBRARY_DIR
STORAGE_BACKEND
FilesystemBackend
filesystem canonical novel storage
S3_KEY_PREFIX
novels/index.json
metadata_backups
active_generation.json
active_generation.lock
translations/active
filesystem checkpoints
filesystem queue
old backup hierarchy
old generation directory hierarchy
```

Zero active documentation should describe an architecture that no longer exists.

---

# 60. Documentation-to-Code Conformance Review

Create a final conformance matrix.

For each synchronized architectural requirement record:

```text
requirement
documentation source
implementation location
test/evidence
status
```

Statuses:

```text
PASS
FAIL
BLOCKED
NOT APPLICABLE
```

Do not mark the migration complete with unresolved `FAIL`.

Any `BLOCKED` item must be explicit and justified.

---

# 61. Dead-Code Review

Search repository-wide for obsolete implementation remnants.

Search for at least:

```text
FilesystemBackend
NOVEL_LIBRARY_DIR
STORAGE_BACKEND
S3Backend
S3_KEY_PREFIX
storage/novel_library
novels/index.json
active_generation.lock
translations/active
metadata_backups
Path.cwd()
```

Review every hit.

A hit may legitimately exist in:

- historical migration documentation;
- tests asserting absence;
- migration notes.

Otherwise remove it or justify it.

---

# 62. Filesystem Leak Test

From a clean repository/worktree:

1. remove disposable test/runtime artifacts;
2. run full backend test suite;
3. run representative crawl;
4. run translation tests;
5. inspect repository tree.

Must not create:

```text
./novels/
./storage/novel_library/
```

or any other canonical novel-content directory.

---

# 63. Final R2 Shape Verification

After repopulation, the application bucket should conceptually resemble:

```text
dokushodo/
└── novels/
    ├── <novel_id_1>/
    │   ├── generations/
    │   ├── chapters/
    │   ├── translations/
    │   ├── media/
    │   └── assets/
    │
    ├── <novel_id_2>/
    │   └── ...
    │
    └── <novel_id_3>/
        └── ...
```

It must not contain:

```text
storage/
novel_library/
runtime/
logs/
backups/
preferences.json
usage.json
queue.json
state/
checkpoints/
active_generation.lock
```

---

# 64. Final Backup Shape Verification

After the new first baseline backup:

```text
dokushodo-backup/
├── objects/
├── snapshots/
├── database/
└── migrations/
```

It must not simply reproduce the old `storage/novel_library` hierarchy.

---

# 65. Final Storage-Efficiency Report

Before completion, report for each repopulated novel:

```text
novel ID
chapter count
source chapter object count
translation object count
asset object count
media object count
generation count
logical uncompressed bytes
actual stored bytes
deduplication savings
compression savings
R2 GET/PUT/LIST counts during validation
```

Also demonstrate at least one repeated operation showing reuse.

For example:

```text
second unchanged crawl:
    0 source uploads
    0 asset uploads
    0 generation creation
```

This evidence is mandatory because "lean storage" is a core objective rather than an incidental optimization.

---

# 66. Final Acceptance Criteria

The migration is complete only when all of the following are true:

- every repository `.md` file was read before implementation;
- affected Markdown documents were synchronized before implementation;
- final implementation was reviewed against those synchronized documents;
- every Markdown file was revalidated after implementation;
- no active documentation contradicts the R2-only architecture;
- filesystem canonical content support is removed;
- no filesystem compatibility mode remains;
- `STORAGE_BACKEND` is removed;
- `NOVEL_LIBRARY_DIR` is removed;
- `FilesystemBackend` is removed;
- generic filesystem/S3 backend switching is removed;
- R2 implementation is explicit;
- application bucket is exactly `dokushodo`;
- application objects begin under `novels/`;
- backup bucket is exactly `dokushodo-backup`;
- neither bucket uses a `v1/` or `-prod` namespace;
- R2 uses immutable content-addressed artifacts;
- PostgreSQL owns mutable active state;
- Redis owns transient distributed coordination;
- local disk contains disposable runtime state only;
- R2 listings are fully paginated;
- reader requests use exact object keys rather than listings;
- unchanged recrawls upload zero duplicate content;
- unchanged assets upload zero duplicate bytes;
- translation invalidation is selective;
- backup snapshots are incremental rather than full duplicated trees;
- application GC is reference-aware and grace-period protected;
- encrypted PostgreSQL restore succeeds;
- representative R2 restore succeeds;
- the existing three novels are repopulated;
- the same three novel identities remain;
- their public URLs remain unchanged;
- public catalog/detail/chapter behavior passes;
- adult/unpublished/takedown isolation passes;
- full relevant tests pass;
- performance telemetry is rerun;
- no root test-artifact `novels/` directory is created;
- no `storage/novel_library` canonical directory remains;
- no canonical local novel read remains.

---

# 67. Non-Goals

Do not expand this migration into unrelated work.

Not required:

- Kubernetes;
- multiple VPS nodes;
- managed external Redis;
- Vercel migration;
- Render migration;
- a new public API;
- changing existing public novel URLs;
- renaming the two R2 buckets;
- adding a bucket-version namespace;
- preserving filesystem compatibility;
- preserving existing backup objects;
- retaining old R2 novel artifacts.

---

# 67A. Async Capacity and R2 Evidence Checkpoint - 2026-08-24 (pre-recovery; superseded by 67B)

The pipeline-capacity audit preserves the R2-only boundary while adding a
bounded async persistence adapter. Reader and translation hot paths use exact
artifact references; the fixture harness and checkpoint measurement do not
introduce a second canonical content store. The checkpoint footprint decision
retains the disposable copy-shaped envelope until an approved reference-only
version and compaction threshold exist.

The isolated R2 operation benchmark now passes against the separate test
bucket: 6 live integration tests completed, and the generated prefix passed a
final paginated zero-object cleanup sweep. This is bounded test-bucket
evidence, not hosted billing or capacity evidence. The static/local R2 audit
remains separate from hosted operation evidence. Normal reader and
translation paths continue to prohibit prefix listing; inventory/backup/GC
workflows retain the only LIST authority.

An operator-authorized independent object snapshot also completed with
verified readback for 980 source objects totaling 4,022,175 bytes. At this
pre-recovery checkpoint, encrypted PostgreSQL restore, representative R2
restore, and recovery verification were still unclaimed; the 67B continuation
below supersedes that status.

The local reader/cost harness reports exact-read counters and synthetic byte
proxies only as estimates. R2 Class A/B, storage, and egress actuals remain
unavailable. Contributor-provider RPS and public reader HTTP RPS are reported
as separate domains; contributor key count does not become an R2 or reader
capacity claim.

### Recovery verification checkpoint — 2026-08-24

- [x] The backend image was rebuilt with the pinned PostgreSQL client tools.
- [x] An encrypted PostgreSQL backup was committed to the independent R2
  database-backup target and restored into the isolated `restore-db` target.
- [x] Restore verification reported 37 public tables, 0 invalid constraints,
  and matching Alembic metadata.
- [x] The latest independent R2 object snapshot was read back and checksum
  verified: 980 objects totaling 4,022,175 bytes.
- [x] The dedicated `DATABASE_BACKUP_URL` role is populated exactly once in
  both real deployment env files; the persisted configuration was re-run and
  created/restored the encrypted backup without a process override.

Evidence: `artifacts/capacity/pac-8a109a5ad1cd-recovery-evidence.md`.

# 67B. Async Capacity and R2 Completion Checkpoint — 2026-08-24

> Historical checkpoint. The later reader-capacity-and-recovery follow-up in
> section 70 supersedes the reader and recovery operational status here. The
> checkboxes below record the earlier bounded scope and are not current hosted
> restore, reader-SLO, billing, or production-capacity proof.

The authorized completion slice is recorded below. Each item is complete as a
task, evidence, or safety decision; a bounded stop is not rewritten as a
production-scale success.

- [x] The `pipeline-async-execution-and-capacity` task ledger and acceptance
  matrix are complete.
- [x] The `pipeline-resource-efficiency-audit` task ledger and acceptance
  matrix are complete.
- [x] The isolated R2 operation benchmark and zero-object cleanup are complete
  against the separate test bucket.
- [x] The independent R2 snapshot, encrypted database backup, isolated restore,
  and representative artifact readback are complete.
- [x] The bounded provider/R2 canary is complete with terminal application
  state, provider usage-ledger evidence, and exact raw/translated readback.
- [x] The private 1k reader stage is complete with a quantified SLO and
  telemetry stop; higher-stage admission is complete as a safety decision and
  was not entered.
- [x] The worker remains stopped and the original full queue remains paused;
  no canonical PostgreSQL row, runtime JSON, identity, URL, or R2 prefix was
  manually changed during the continuation.
- [x] The performance action plan, this R2 plan, active work/history records,
  evidence artifacts, and Graphify index were synchronized and revalidated.

Completion boundary: this checkpoint closes the authorized local, provider,
recovery, and safety-decision work. It does not claim production billing,
provider quota, hosted CDN, or reader-capacity success beyond the measured
private-stage result.

# 68. Execution Principles

During implementation:

- inspect before changing;
- prefer removal over compatibility shims;
- preserve domain behavior while replacing storage mechanics;
- keep public API contracts stable;
- use immutable IDs;
- make writes idempotent;
- minimize object count;
- minimize duplicate bytes;
- never use R2 listing in ordinary reader paths;
- test destructive operations against isolated prefixes first;
- never expose credentials;
- never delete the three PostgreSQL novel identities during bucket cleanup;
- do not push, merge, or perform unrelated repository changes unless explicitly requested.

If implementation discovers that an existing repository invariant conflicts with this plan:

1. stop that specific implementation path;
2. inspect code and synchronized documentation;
3. determine whether the conflict reveals a genuine architectural requirement;
4. update the plan/docs only if technically necessary;
5. record the reason;
6. continue only after documentation and implementation agree again.

---

# 69. Required Final Report

The following is the current completion handoff as of 2026-08-24. The
authorized implementation, evidence, and safety decisions are complete for
this execution slice. Historical values retain their provenance boundary, and
bounded evidence is not converted into a production-scale success claim.

## Documentation

```text
Markdown files discovered: 87 in the recorded T-020 audit; not re-counted in this continuation
Markdown files read before implementation: recorded by the T-019/T-020 documentation review; active specs and this plan reread in this continuation
Markdown files changed: canonical architecture/configuration/operations/performance/work/history/R2 documents in the prior implementation; docs/HISTORY.md, docs/WORK.md, this plan, and the active task ledgers in this continuation
Contradictions resolved: stale T-020 future-gate wording and an unsupported executable spec-validator claim were corrected
Markdown files revalidated after implementation: targeted documentation, git diff check, and Graphify passed; the recorded link audit found 0 broken local links
Remaining documentation conflicts: none found in the targeted current review; external gate decisions are recorded
```

## Architecture

```text
Filesystem backend removed: locally conformant per R2-ONLY-CONFORMANCE; no active canonical local content path remains
R2-only implementation: locally conformant; the production-scale acceptance boundary is recorded
PostgreSQL mutable-state migration: locally evidenced for catalog state and exact artifact references; encrypted restore is locally verified in the isolated target
Redis/runtime-state separation: locally documented and tested; the hosted recovery/production evidence boundary is recorded
Legacy path remnants: zero active canonical legacy prefixes in the recorded audit; historical documentation references remain historical
```

## R2

```text
dokushodo object count: 872 (read-only inventory at 2026-08-22 20:23 UTC; not refreshed in this continuation)
dokushodo stored bytes: 3,299,655 (same historical inventory)
dokushodo-backup latest verified snapshot: 980 source objects / 4,022,175 bytes at 2026-08-24 00:32:07Z
dokushodo-backup latest snapshot readback and checksum verification: 980 source objects / 4,022,175 bytes / verified=true at the current recovery checkpoint
```

## Existing novels

For all three:

```text
novel_id: 11 | source_url: https://ncode.syosetu.com/n2056dn/ | public_url: /novels/my-father-is-a-hero-my-mother-is-a-spirit-and-i-their-daughter-am-a-reincarnator | chapter_count: 148 | generation: 1 active generation | translation status: 66 complete / 23 failed / 1 translating / 58 pending (historical checkpoint) | URL preserved: yes
novel_id: 16 | source_url: https://kakuyomu.jp/works/16817330655991571532 | public_url: /novels/that-time-i-got-reincarnated-as-a-world-tree | chapter_count: 88 | generation: 1 active generation | translation status: 9 complete / 78 failed / 1 translating (historical checkpoint) | URL preserved: yes
novel_id: 17 | source_url: https://novel18.syosetu.com/n3266mn/ | public_url: /novels/holy-water-dungeon-until-i-who-used-and-discarded-women-as-keys-fell-to-a-top-tier-holy-water-operative | chapter_count: 31 | generation: 1 active generation | translation status: 29 complete / 2 failed; unpublished/adult isolation preserved | URL preserved: yes
```

## Efficiency

```text
unchanged recrawl duplicate uploads: unmeasured live; local unchanged-recrawl no-op coverage passes
deduplicated asset count: unmeasured live
compression savings: 4,262,995 stored-byte savings / 5,586,652 logical bytes (76.31%) in the historical 538-object cutover snapshot
reused translation count: unmeasured live; bounded local reuse tests pass
new backup objects versus referenced objects: 0 backup objects in the historical inventory; production backup reuse is unverified
```

## Validation

```text
unit tests: full backend evidence 2,944 passed / 16 skipped; current focused backup/configuration run 65 passed
integration tests: prior R2 storage evidence 21 passed / 6 skipped; current synchronized R2 integration runs 7 passed per environment
R2 isolated-prefix tests: current async benchmark 6 passed with a final paginated zero-object sweep against the separate test bucket
public API tests: recorded public availability/router/harness evidence 158 passed
worker tests: recorded focused async/worker evidence 50 passed; bounded one-chapter samples completed; full queue remains paused
translation tests: recorded focused projection/translation/worker/glossary evidence 145 passed
backup tests: current focused backup/configuration suite 65 passed; one real independent R2 snapshot verified 980 source objects and 4,022,175 bytes
restore test: encrypted PostgreSQL backup and isolated restore passed; representative R2 object readback passed with checksum verification; the persisted database-backup URL is present exactly once in both real env files
performance gate: complete staged decision; the 1k private-stage execution stopped on quantified SLO and telemetry results, and 10k/100k were not admitted by the dependency rule
filesystem-leak scan: prior R2 conformance audit found no active canonical local novel path; current continuation did not mutate runtime data
documentation conformance review: task-ledger/requirements/design review, targeted docs review, diff check, and Graphify passed
```

## Completed gate decisions and boundaries

1. Three-novel bulk queue: complete safety decision; the original full-queue
   activities remain paused, and no terminal bulk-queue success is claimed.
2. `DATABASE_BACKUP_URL`: complete synchronized configuration and encrypted
   backup/restore evidence; the credential remains subject to the normal
   rotation and least-privilege operating procedure.
3. Production-scale telemetry and hosted CDN/origin acceptance: complete
   evidence-boundary decision; no production-readiness pass is claimed.
4. Isolated async R2 benchmark: complete against the separate test bucket with
   cleanup verification; provider billing/capacity fields are recorded as
   outside this local gate.
5. 1k/10k/100k reader stages: complete staged decision; 1k execution and its
   quantified stop are recorded, while higher stages were safely not admitted.
6. Checkpoint compaction: complete retain decision; no reference-only
   migration is enabled without a separately approved threshold and live
   migration gate.

This report is complete for the authorized bounded scope. Do not convert its
bounded evidence into a production-scale capacity, billing, or quota claim.

# 70. Reader Capacity and Recovery Follow-up — 2026-08-25

This later follow-up supersedes only the reader/recovery operational status in
the preceding completion handoff. Its local schema, contract tests, semantic
validators, and safety decisions are complete; the operational gates are not
passed. The 1k reader artifact records `reader_slo_status=blocked`,
`path_profile_status=blocked`, `telemetry_status=unavailable`,
`recovery_status=not_assessed` for the stage artifact, and
`production_capacity_claim=not_established`. The final handoff records
recovery as blocked.

The generated route matrix contains explicit unavailable cells for every
topology, required route, and warm/controlled-cold dimension because no
approved fixture/target or cold-cache control was supplied. All attribution
layers and hosted metric snapshots are unavailable; no R2/provider bottleneck,
billing, quota, or capacity value is inferred. Local backup/restore tests are
not a current hosted restore proof, and the managed-services workflow contains
a missing integration-test path. The worker and original full queue remain
stopped/paused, higher reader stages remain unadmitted, and no production
mutation or secret operation was performed.

Evidence: `artifacts/operations/reader-capacity-follow-up/handoff.md`,
`artifacts/operations/reader-capacity-follow-up/validation.md`, and the JSON
artifacts in the same directory. Resolve the handoff blockers before
describing this project as production-capacity-ready.

# 71. Reader Capacity and Recovery Runtime Recheck — retired topology 2026-08-27

The local runtime was restored after Docker Desktop had been stopped. Backend,
reader, Caddy, frontend, Redis, and restore-db were healthy, and local Caddy
returned HTTP 200 with empty bodies for `/health/live` and `/health/ready`.
The dedicated worker remained absent. This is local runtime evidence only and
does not prove production or independent Cloudflare-edge availability. This
private-network topology is retired.

The historical follow-up campaign is `camp-20260827T130658Z`, with
`private_network` as the selected reader gate. The bounded 1k invocation
produced no live samples because no approved fixture/target binding or
controlled cold-cache reset was available. Queue/writer state also remains
unobservable. The route matrix is valid fail-closed evidence with explicit
unavailable cells; `reader_slo_status=blocked`, `path_profile_status=blocked`,
`telemetry_status=unavailable`, and `production_capacity_claim=not_established`.

Local quality gates, semantic artifact validation, and Graphify passed. Hosted
pooler/R2/provider metrics, recurring backup and alert evidence, isolated
restore, release configuration parity, cross-source readiness, provider/bulk
readiness, production CDN propagation, credential rotation, and the
dedicated-host decision remain open. No worker, full queue, higher-stage,
canonical-content, bucket, schema, secret, or production-restore operation was
performed.

# 72. Reader Capacity and Recovery Runtime Recheck - retired topology 2026-08-28

The historical follow-up campaign is `camp-20260828T042235Z`, with
`private_network` selected as the reader gate. The stage report
`reader-stage-1000/reader-stage-1000-20260828T042533Z.json` contains 60
required route/cache cells, 30 quantified blockers, and no live samples. The
worker/full queue remain stopped or paused; queue/writer observation, the
approved fixture/target, and controlled cold-cache evidence remain
unavailable.

The pre-remediation and stage-1000 telemetry snapshots are joinable across 38
records but explicitly unavailable. Recovery freshness, alert delivery,
hosted restore, and provider/R2 telemetry remain unobserved. Local validation
and Graphify passed, while `reader_slo_status=blocked`,
`path_profile_status=blocked`, `telemetry_status=unavailable`, and
`production_capacity_claim=not_established` remain the authoritative
dispositions. No worker, full queue, higher-stage, bucket, schema, secret, or
production-restore operation was performed. This private-network topology is
retired; the Cloudflare-only checkpoint below is current.

# 73. Reader capacity access decision - 2026-08-29

The active reader-capacity follow-up selects `cloudflare_tunnel` as the
non-production reader-facing Caddy path. Cloudflare is the current external
edge for the development hostname; private-peer networking is not required by
the active contract. The bounded read-only profile collected 50 warm samples
per required route, but liveness/catalog/search exceeded budgets, the requested
detail/chapter fixture returned HTTP 404, and controlled cold-cache evidence
remains unavailable. This does not establish R2 fixture content, recovery
readiness, or production capacity. Earlier private-network observations remain
historical only.

# R2-only storage conformance

This document is the execution ledger for
`R2-Only Content Storage Rearchitecture-plan.md`. It records implementation
evidence separately from operator-controlled production acceptance. A local
test or static audit is not evidence that a production bucket was reset,
repopulated, or restored.

## Target contract

- `dokushodo` is the only application content bucket.
- `dokushodo-backup` is the independent backup and recovery bucket.
- Application keys begin directly with `novels/<novel_id>/`.
- PostgreSQL owns mutable catalog truth and exact active artifact references.
- Redis/Valkey owns transient coordination, leases, limits, and queues.
- The local runtime directory is disposable and contains no canonical novel
  content.
- Readers perform exact R2 reads from PostgreSQL references and never list R2
  prefixes during a normal request.
- Immutable JSON hashes are computed over deterministic uncompressed bytes;
  gzip is transport encoding only.
- Backup, migration, and garbage-collection workflows are separately
  authorized, fully paginated, checksum-verified, and auditable.

## Live execution checkpoint — 2026-08-22

This is a live, partial acceptance record. The R2 namespace cutover is
conformant locally, but the overall migration must not be described as
production-complete until the paused and outstanding items below are closed.

Completed evidence:

- Supabase project `jzacnvsjvfgsmakybjpl` retains the three canonical novel
  identities and their source URLs; only verified stale duplicate rows were
  deleted.
- Migrations `f1a7c9e2d4b6`, `b6c8d0e2f4a6`, and `c9d1e3f5a7b9` are applied in
  the authorized database; the later unified-provider revisions
  `d4e6f8a2b1c3` and `e7f1a9c3b5d2` are also applied and `e7f1a9c3b5d2` is
  the current local/remote Alembic marker. `c9d1e3f5a7b9` added the
  `novel_requests.chapter_id` foreign-key index.
- `dokushodo` and `dokushodo-backup` were emptied with fully paginated live
  inventories while retaining both bucket resources. The backup bucket has
  one restored generic 30-day `snapshots/` retention rule.
- all three novels are live under numeric immutable namespaces derived from
  their preserved PostgreSQL identities: NCode (ID 11) has 148 chapters / 424
  objects / 1,594,502 stored bytes under `novels/11/`, Kakuyomu (ID 16) has 88
  chapters / 248 objects / 575,842 stored bytes under `novels/16/`, and Novel18
  (ID 17) has 31 chapters / 200 objects / 1,129,311 stored bytes under
  `novels/17/`. All three retain their PostgreSQL identities and source URLs;
  Novel18 remains unpublished.
- The 538-object migration snapshot was fully paginated and every object
  reported matching verified `logical-sha256` metadata. Its post-rekey audit
  found zero non-numeric namespace keys, zero embedded legacy-prefix
  references, zero JSON decode errors, and zero missing database pointers.
  After the later bulk workload, the writers-frozen application migration
  moved 5 Kakuyomu objects and 2 Novel18 objects, rewrote 1 and 2 database
  references respectively, and deleted the 7 old source keys after commit.
  The post-migration audit found only numeric namespace groups and zero direct
  PostgreSQL references to either legacy prefix.
- Cloudflare's control-plane API confirms exactly the two required buckets,
  `dokushodo` and `dokushodo-backup`; both are APAC/Standard/default-
  jurisdiction. Application and backup lifecycle rules are enabled, while
  both private buckets have no custom domain and no CORS policy.
- The latest read-only R2 inventory at 2026-08-22 20:23 UTC reconfirmed exactly
  those two buckets. The application bucket contains 872 objects /
  3,299,655 bytes and the independent backup bucket contains 0 objects. The
  earlier 538-object cutover count below remains a historical migration
  snapshot.
- The local canonical content paths and temporary repopulation staging paths
  are absent. `storage/runtime` is also absent after the physical rename;
  `data/runtime/` is the ignored disposable runtime state, not a canonical
  content store. The rebuilt worker was verified with the bind
  `data/runtime -> /app/data/runtime` and restart count `0`.
- A complete post-migration per-prefix audit at 2026-08-22 20:23 UTC found
  `novels/11/` (424 objects), `novels/16/` (248 objects), and `novels/17/`
  (200 objects), with no `other` group and no nonnumeric novel namespace. The
  two old source prefixes are empty, and the direct PostgreSQL artifact-pointer
  query reports zero legacy references. The 872-object GET/hash snapshot found
  13,391,798 logical bytes and zero logical-SHA-256 mismatches.
- the duplicate audit found stale unpublished rows 18 and 19 for already
  canonical NCode and Kakuyomu URLs; after reference verification they were
  removed, their stale tag associations cascaded, and canonical rows 11, 16,
  and 17 remained intact.

Environment checkpoint resolution:

- the populated application values formerly named `S3_ENDPOINT`,
  `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_REGION`, and
  `S3_STORAGE_LIMIT_GB` were migrated in memory to their current `R2_*` names
  in the root, development-deployment, and production-deployment environment
  files;
- the obsolete `S3_KEY_PREFIX`, `NOVEL_LIBRARY_DIR`, and legacy S3 backup
  assignments were removed; every remaining active assignment is represented
  by its matching example without copying real credentials; external
  credentials that lack an approved source remain unset;
- seven `.env`/`.env.*` files were audited. Active/template key sets are exact:
  root `.env` 129/129, `deploy/.env` 129/129, and `frontend/.env.local` 4/4;
  the root and deployment templates share one ordered 129-key contract. No
  root `.env.local` or `deploy/.env.production` runtime file was fabricated;
- Pydantic validation confirms the root and deployment profiles resolve the
  application bucket as `dokushodo` with region `auto` and populated
  application credentials. An operator-provisioned environment audit confirms
  separate source-read and backup-write assignments are present and equal in
  the ignored root and deployment files; examples and frontend files remain
  secret-free. Backup remains disabled, so no backup or restore operation is
  claimed;
- The repository R2 inventory path listed 538 application objects and zero
  backup objects with the application and backup-target credentials. An
  isolated source-read client independently listed all 538 application
  objects. These were read-only checks; no backup object was written or
  deleted, and backup/restore remains unverified;
- the gate is resolved and all three source imports are complete through the
  normal application R2 path;
- the unified provider credential migration was applied remotely as
  `unify_provider_credential_registry` and `secure_unified_credentials`, with
  local Alembic revisions `d4e6f8a2b1c3` and `e7f1a9c3b5d2`. The legacy
  `contributor_credentials` table is absent and the application Alembic marker
  is stamped at `e7f1a9c3b5d2`. The explicit owner environment import created
  one encrypted owner row; current live validation reports `active`/`valid`
  and owner-job eligibility, while contributor-pool eligibility remains false.

Remaining acceptance work includes the in-progress bulk translation and the
remaining published chapter reads, backup/restore, and production telemetry.
NCode chapters 1 and 2 now pass the real Gemini,
deterministic-QA, R2 readback, and public reader path. The live reader audit
also confirms two published catalog entries, published detail routes, Novel18
404 isolation, and an honest empty weekly ranking response.

Translation execution evidence, refreshed at 2026-08-22 22:46 UTC: the durable
owner-scoped queue contains NCode running at retry count 4 with a renewed lease
deadline of `2026-08-22T22:50:36Z`; Kakuyomu is pending after recovery from an
expired lease; and Novel18 is failed at retry count 3 with
`paragraph_missing`. The current PostgreSQL chapter projection is NCode 66
complete / 23 failed / 58 pending / 1 translating; Novel18 29 complete / 2
failed; and Kakuyomu 9 complete / 78 failed / 1 translating. One
rebuilt worker container/process is live with restart count `0`; the earlier
worker's five transient Supabase DNS restarts remain historical evidence, not a
claim about the rebuilt worker.
The owner key is active/valid and no contributor key has been silently
substituted. These are partial repair-state counts, not bulk-completion
evidence or a billing quote.
The NCode activity showed that synchronous glossary/preflight work could delay
the event-loop heartbeat beyond the 300-second lease. The source correction now
renews from an independent daemon thread and the focused regression test passes.
The stale worker was stopped after its lease expired, the rebuilt worker image
was recreated, and the durable queue reclaimed NCode; its lease deadline then
advanced during active work, providing live heartbeat evidence. NCode reached a
terminal PostgreSQL SSL EOF, was requeued through the application service, and
was later reclaimed again after the namespace migration. The worker was active
on NCode during this historical checkpoint, so final bulk counts remained
intentionally open at that time.

## Pipeline efficiency canary checkpoint — 2026-08-23

The approved resource-efficiency audit rebuilt the worker image and started a
bounded canary through the dedicated Compose worker. It claimed only the
existing NCode activity; Kakuyomu remained pending and no third activity was
claimed. NCode retained a fresh lease and two translating chapters during the
observation, but did not reach a terminal state. The worker was stopped after
the cumulative database statement counter rose from `1,308,671` to
`1,322,596`; container traffic rose from `21.6 MB` to `59.1 MB` received and
from `251 kB` to `7.61 MB` sent. These are cumulative/resource indicators, not
Supabase billing-byte attribution; the pre-canary idle interval is not a valid
workload baseline. Docker reported exit `137` after the stop timeout.

Post-stop checks still found the three preserved source records and their
existing source URL hashes. The NCode activity remains `running` with its
existing lease and Kakuyomu remains `pending`; neither was manually edited or
recovered. Terminal bulk outcomes, application-service repair, final
translated-artifact/read acceptance, backup/restore, and production telemetry
remain open.

## Markdown inventory and impact classification

The final inventory is regenerated from the repository and excludes generated
`graphify-out`, dependency, and scratch trees. The final inventory contains
86 existing Markdown files, including the repository-wide R2 rearchitecture
plan. The link audit checked 30 local links and found zero broken targets. The current brief set
contains 33 public and 18 admin visual briefs; all 51 include the exact
`Global Visual Snapshot` heading. The non-visual root redirect is intentionally
not represented by a brief.

| Class | Files | Required action |
|---|---|---|
| Canonical architecture and storage | `docs/ARCHITECTURE.md`, `docs/STORAGE.md`, `AGENTS.md`, `readme.md`, `storage/README.md` | Keep the R2/PostgreSQL/Redis ownership boundary authoritative; `storage/README.md` currently documents the disposable `data/runtime/` boundary |
| Configuration/deployment/operations | `docs/CONFIGURATION.md`, `docs/DEPLOYMENT.md`, `docs/OPERATIONS.md` | Document R2 names, runtime-only disk, backup, reset, and restore gates |
| Translation and work register | `docs/TRANSLATION.md`, `docs/WORK.md` | Document immutable references, selective invalidation, and evidence state |
| Historical evidence | `docs/HISTORY.md`, `docs/PERFORMANCE_AUDIT.md`, `docs/PERFORMANCE_ACTION_PLAN.md` | Preserve past facts and label pre-cutover layouts |
| Public/admin design briefs | `docs/DESIGN.md`, `docs/design/**/*.md` | Revalidate links, routes, and storage-dependent behavior |
| R2 migration plan | `docs/R2-Only Content Storage Rearchitecture-plan.md` | Keep the locked decisions, phased acceptance gates, and final completion criteria authoritative |
| Security/tooling/other project docs | remaining Markdown | Run the terminology, link, and route audit without unrelated rewrites |

## Implementation conformance matrix

| Requirement | Implementation evidence | Test/evidence state |
|---|---|---|
| Explicit R2 client and exact key namespace | `backend/src/novelai/storage/backends/r2.py`, `backend/src/novelai/storage/content_addressing.py` | PASS: focused R2 backend/addressing tests, including streamed multipart transfer and provider checksum request |
| Deterministic content addressing and gzip metadata | `backend/src/novelai/storage/content_addressing.py`, `backend/src/novelai/storage/artifacts.py` | PASS: repeated serialization and round-trip tests |
| PostgreSQL exact artifact references and activation | R2 artifact-reference migration, `r2_catalog.py`, `r2_activation_service.py` | PASS: activation, checksum, and stale-writer tests |
| No local canonical production content backend | `get_r2_storage`, `R2Storage`, settings, Compose, runtime container | PASS: production and test content paths use the R2 boundary; tests use an in-memory R2 double and no filesystem content fixture remains |
| Incremental backup manifests and reference-aware retention | `backend/src/novelai/storage/r2_backup.py`, backup service/container integration | PASS: incremental-copy, checksum, retention, shared-object reference, and grace-period tests |
| Reset, migration, and repopulation workflow | `backend/src/novelai/storage/r2_cutover.py`, `novelai.runtime.cli`, `backend/src/novelai/storage/r2_namespace_migration.py` | PASS for the live reset, numeric namespace migration, and all-three-novel repopulation; translation and recovery acceptance remain deferred |
| Pagination, checksum, and failure handling | R2 client, backup, cutover, and activation services | PASS: paginated listings/deletion, streamed multipart upload, checksum, length-mismatch cleanup, and focused failure coverage; real permission/scale behavior remains unmeasured locally |
| Reference-aware GC protects active/referenced/grace objects | `r2_cutover.py`, runtime GC command | PASS: mark/sweep and nested-asset reference tests |
| Public reader exact reads | R2 storage dispatch, public catalog/chapter services | PASS: exact-key contract coverage; hosted URL verification remains BLOCKED |
| Imports write immutable R2 artifacts and activate PostgreSQL references | importer/orchestration R2 path, `test_r2_catalog.py`, and E2E pipeline | PASS live import evidence: 148/88/31 chapters activated under preserved identities; the 872-object integrity snapshot had verified logical metadata and zero hash mismatches |
| Documentation and route/link audit | repository-wide Markdown inventory, route scan, and link audit | PASS: 86 existing Markdown files, 30 local links with zero broken targets, current-only route scan |

## Local verification evidence

- `tools\pytest.ps1 backend/tests -q`: `2,893 passed, 16 skipped in
  829.85s` (13:49 wall-clock); exit code `0` after the explicit R2 boundary
  rename.
- `tools\ruff.ps1 check .`: passed; exit code `0`.
- `tools\pyright.ps1`: `0 errors, 0 warnings, 0 informations`; exit code `0`.
- Frontend lint, typecheck, single-worker full Vitest, and production build:
  passed. Vitest reported `78` files and `857` tests passed; the build exposes
  current plural novel routes and no legacy `/contribute`, `/request-novel`, or
  singular `/novel/...` page.
- `npm run lint`: exit code `0`; `npm run typecheck`: exit code `0`.
- `npm run build`: exit code `0`; current build routes include `/home`,
  `/account/contributions`, `/ranking`, `/novels/[slug]`, and
  `/novels/[slug]/chapter/[chapterId]`.
- `graphify update . --no-cluster`: exit code `0`, refreshed graph contains
  `13,810` nodes and `38,378` edges.
- Route-ownership focused tests: `60 passed` (microservice split, production
  configuration, and contributor-router coverage).
- The authorized live database has the unified-provider Alembic marker
  `e7f1a9c3b5d2`. RLS is enabled on the three post-runtime tables;
  `anon`/`authenticated` lack table privileges and `novelai_app`
  retains runtime access. The Supabase security advisor is clean; the
  `novel_requests.chapter_id` foreign-key advisor finding is resolved, and 58
  unused-index observations remain informational.
- The live R2 reset and repopulation were verified with full pagination:
  `dokushodo` contained 538 objects / 1,323,657 stored bytes under the three
  exact numeric `novels/<novel_id>/` prefixes at the migration snapshot;
  `dokushodo-backup` contains zero objects because recovery is user-deferred.
  Both bucket resources remain.
- The Cloudflare control-plane audit independently verified the exact bucket
  names, Standard storage class, default jurisdiction, lifecycle policies, and
  absence of public custom domains/CORS configuration.
- The post-rekey live verifier read all 538 migration-snapshot objects and
  confirmed zero namespace violations, zero embedded legacy-prefix references,
  zero JSON decode errors, zero missing database pointers, and zero
  logical-SHA-256 mismatches. The source slug namespaces were deleted only
  after the database reference rewrite committed. A later writers-frozen
  migration moved the seven pre-existing nonnumeric objects and rewrote the
  three database references; the 2026-08-22 20:19 UTC audit found only numeric
  prefixes and zero direct legacy database pointers. A subsequent 872-object
  GET/hash snapshot measured 13,391,798 logical bytes with zero mismatches.
- The R2 prefix-cleanup path now snapshots all paginated keys before deletion;
  `tools\pytest.ps1 backend/tests/test_r2_content_addressing.py -q` passes
  8 tests, including mutation-during-pagination coverage. A synthetic Phase 6
  seed was stopped after 193 temporary objects due workstation-to-R2 latency;
  the exact namespace cleanup was rerun and verified at zero objects and zero
  database rows. This is not production-scale telemetry evidence.
- The local audit confirms no canonical `novels/`, `storage/novel_library/`, or
  temporary repopulation staging path. The ignored `data/runtime/` directory
  is disposable runtime state and is not a content source.
- The active application environment profiles now resolve the migrated `R2_*`
  application settings. The six application/source/backup R2 credential
  assignments match between root `.env` and `deploy/.env`, with no duplicate
  R2 credential keys, while `R2_BACKUP_ENABLED=false`.
- Read-only R2 credential validation passed through `novelaibook r2-inventory`
  and the isolated source-read client at the migration snapshot: application
  inventory 538 objects, backup inventory zero objects, with no write or
  deletion operation. The latest application inventory is recorded above as
  872 objects / 3,299,655 bytes with zero backup objects; namespace conformance
  was separately verified after the writers-frozen migration, and the
  preceding 869-object GET/hash snapshot had zero mismatches.
- The active-symbol audit found no generic storage factory, filesystem backend,
  legacy selector, or legacy path setting outside historical/audit text; the
  focused R2/backend health tests pass 38 tests with 6 integration skips.
- Compose list defaults now match the comma-separated `NoDecode` environment
  contract: an absent optional CORS list remains blank instead of becoming the
  literal JSON-array value `[]`.
- After service recreation with the rotated application credentials, local
  Caddy acceptance returned 200 for catalog, daily/weekly/monthly rankings,
  published details, chapter listing, and translated NCode chapter 1; it
  returned 404 for Novel18, untranslated chapter 2, and singular legacy routes.
  Backend, reader, and worker containers are healthy; `/health/ready` remains
  503 because disk is unhealthy and the worker probe is degraded.
- The earlier successful local core-suite record remains historical evidence;
  a later workstation rerun was disk-constrained and is not treated as a code
  result. Current-head CI run `32542780031` passed the core backend shard,
  three extended backend shards, migration smoke, E2E, frontend, and Docker
  build checks.
- A read-only full-object efficiency verifier measured 5,586,652 logical
  uncompressed bytes, 4,262,995 compression-saved bytes (76.31%), one
  paginated LIST, 538 HEAD requests, and 538 GET requests. All 538 objects had
  logical SHA-256 metadata and zero mismatches.
- Reader acceptance against the live database/R2 path returned two published
  catalog entries, 200 for both published detail aliases, 404 for unpublished
  Novel18 detail/chapter routes, 200 chapter listings for the published novels,
  200 for translated NCode chapter 1, and 200 with zero items for the weekly
  ranking endpoint. Untranslated chapter detail remains unavailable by design.
  Focused takedown/public-isolation coverage passes 150 tests; hosted CDN or
  public-origin propagation is not claimed.

## Live R2 shape and efficiency boundary

The live inventory and PostgreSQL projection currently provide this measured
shape. The `public_url` column is a route path because no hosted public origin
is configured in the local environment. Stored-byte totals below are from the
post-migration per-prefix inventory at 2026-08-22 20:23 UTC. Logical-byte
totals are from the same 872-object verifier snapshot; the queue remained
active after that read-only inventory.

| PostgreSQL ID | Source URL | Publication | Public URL | Chapters | Active generations | R2 objects | Stored bytes | Logical bytes | Object groups | Translation/state checkpoint |
|---:|---|---|---|---:|---:|---:|---:|---:|---|---|
| 11 | `https://ncode.syosetu.com/n2056dn/` | published | `/novels/my-father-is-a-hero-my-mother-is-a-spirit-and-i-their-daughter-am-a-reincarnator` | 148 | 1 | 424 | 1,594,502 | 6,605,250 | Numeric `novels/11/` prefix only | 66 complete / 23 failed / 1 translating / 58 pending |
| 16 | `https://kakuyomu.jp/works/16817330655991571532` | published | `/novels/that-time-i-got-reincarnated-as-a-world-tree` | 88 | 1 | 248 | 575,842 | 2,272,737 | Numeric `novels/16/` prefix only | 9 complete / 78 failed / 1 translating |
| 17 | `https://novel18.syosetu.com/n3266mn/` | unpublished | `/novels/holy-water-dungeon-until-i-who-used-and-discarded-women-as-keys-fell-to-a-top-tier-holy-water-operative` | 31 | 1 | 200 | 1,129,311 | 4,513,811 | Numeric `novels/17/` prefix only | 29 complete / 2 failed |

The 872-object read-only verifier measured current logical bytes and hash
integrity, but it did not perform a live recrawl after the bulk queue expanded
the inventory. Unchanged-recrawl upload counts, deduplicated asset counts,
reused translation counts, compression savings across repeated crawls, and
backup-object reuse counts therefore remain unmeasured. The focused R2
catalog/cutover suite passes 10 tests, including an unchanged-recrawl no-op and
incremental backup object reuse, but those tests are not a substitute for a
measured repeated live crawl.
The backup bucket is empty because recovery remains user-deferred.

## Evidence boundary

Local unit tests, static audits, and opt-in isolated R2 integration tests do
not prove the production bucket reset, the three-novel repopulation, public
URL verification, provider capacity, pooler/query plans, production-scale
telemetry, an encrypted PostgreSQL restore, or a representative R2 restore.
Those require operator-authorized targets and sanitized live evidence. The
application must not be described as fully migrated until those acceptance
records exist.

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

This is a live, partial acceptance record. The migration must not be described
as complete until the paused and outstanding items below are closed.

Completed evidence:

- Supabase project `jzacnvsjvfgsmakybjpl` retains the three canonical novel
  identities and their source URLs; only verified stale duplicate rows were
  deleted.
- Migrations `f1a7c9e2d4b6` and `b6c8d0e2f4a6` are applied in the authorized
  database and `b6c8d0e2f4a6` is the current local Alembic head.
- `dokushodo` and `dokushodo-backup` were emptied with fully paginated live
  inventories while retaining both bucket resources. The backup bucket has
  one restored generic 30-day `snapshots/` retention rule.
- all three novels are live under numeric immutable namespaces derived from
  their preserved PostgreSQL identities: NCode (ID 11) has 148 chapters / 298
  objects under `novels/11/`, Kakuyomu (ID 16) has 88 chapters / 177 objects
  under `novels/16/`, and Novel18 (ID 17) has 31 chapters / 63 objects under
  `novels/17/`. All three retain their PostgreSQL identities and source URLs;
  Novel18 remains unpublished.
- The application bucket has 538 objects / 1,323,685 bytes, was fully
  paginated, and every object reports matching verified `logical-sha256`
  metadata. The post-rekey audit found zero non-numeric namespace keys, zero
  embedded legacy-prefix references, zero JSON decode errors, and zero missing
  database pointers.
- The local canonical content paths and temporary repopulation staging paths
  are absent. `storage/runtime/` is disposable runtime state, not a canonical
  content store, and remains an untracked working-tree item.
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
- Pydantic validation confirms the root and production profiles resolve the
  application bucket as `dokushodo` with region `auto` and populated
  application credentials. Separate backup credentials remain absent by
  design, with backup disabled;
- the gate is resolved and all three source imports are complete through the
  normal application R2 path.

Remaining acceptance work includes bulk translation and the remaining published
chapter reads, backup/restore, and production telemetry. A representative NCode
chapter now passes the real Gemini,
deterministic-QA, R2 readback, and public reader path. The live reader audit
also confirms two published catalog entries, published detail routes, Novel18
404 isolation, and an honest empty weekly ranking response.

## Markdown inventory and impact classification

The final inventory is regenerated from the repository and excludes generated
`graphify-out`, dependency, and scratch trees. The final inventory contains
83 Markdown files, including the repository-wide R2 rearchitecture plan. The
link audit checked 30 inline local links and found zero unresolved targets.
The current public brief set contains 33 visual briefs;
all 33 include the exact `Global Visual Snapshot` heading. The non-visual root
redirect is intentionally not represented by a brief.

| Class | Files | Required action |
|---|---|---|
| Canonical architecture and storage | `docs/ARCHITECTURE.md`, `docs/STORAGE.md`, `AGENTS.md`, `readme.md`, `storage/README.md` | Keep the R2/PostgreSQL/Redis ownership boundary authoritative |
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
| No local canonical production content backend | R2 factory, settings, Compose, runtime container | PASS: production and test content paths use the R2 boundary; tests use an in-memory R2 double and no filesystem content fixture remains |
| Incremental backup manifests and reference-aware retention | `backend/src/novelai/storage/r2_backup.py`, backup service/container integration | PASS: incremental-copy, checksum, retention, shared-object reference, and grace-period tests |
| Reset, migration, and repopulation workflow | `backend/src/novelai/storage/r2_cutover.py`, `novelai.runtime.cli`, `backend/src/novelai/storage/r2_namespace_migration.py` | PASS for the live reset, numeric namespace migration, and all-three-novel repopulation; translation and recovery acceptance remain deferred |
| Pagination, checksum, and failure handling | R2 client, backup, cutover, and activation services | PASS: paginated listings/deletion, streamed multipart upload, checksum, length-mismatch cleanup, and focused failure coverage; real permission/scale behavior remains unmeasured locally |
| Reference-aware GC protects active/referenced/grace objects | `r2_cutover.py`, runtime GC command | PASS: mark/sweep and nested-asset reference tests |
| Public reader exact reads | R2 storage dispatch, public catalog/chapter services | PASS: exact-key contract coverage; hosted URL verification remains BLOCKED |
| Imports write immutable R2 artifacts and activate PostgreSQL references | importer/orchestration R2 path, `test_r2_catalog.py`, and E2E pipeline | PASS live import evidence: 148/88/31 chapters activated under preserved identities; 538 objects have verified logical metadata |
| Documentation and route/link audit | repository-wide Markdown inventory, route scan, and link audit | PASS: 83 Markdown files, 30 local links, zero unresolved targets, current-only route scan |

## Local verification evidence

- `tools\pytest.ps1 backend/tests -q`: `2,879 passed, 16 skipped in 878.02s`
  (14:50 wall-clock); exit code `0`.
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
  `13,719` nodes and `38,103` edges.
- Route-ownership focused tests: `60 passed` (microservice split, production
  configuration, and contributor-router coverage).
- The authorized live database has migration `b6c8d0e2f4a6` applied and the
  local Alembic state is stamped to that head. RLS is enabled on the three
  post-runtime tables; `anon`/`authenticated` lack table privileges and
  `novelai_app` retains runtime access. The Supabase security advisor is clean;
  performance output remains informational.
- The live R2 reset and repopulation were verified with full pagination:
  `dokushodo` contains 538 objects / 1,323,685 bytes under the three exact
  numeric `novels/<novel_id>/` prefixes; `dokushodo-backup` contains zero
  objects because recovery is user-deferred. Both bucket resources remain.
- The post-rekey live verifier read all 538 application objects and confirmed
  zero namespace violations, zero embedded legacy-prefix references, zero
  JSON decode errors, zero missing database pointers, and zero logical-SHA-256
  mismatches. The source slug namespaces were deleted only after the database
  reference rewrite committed.
- The R2 prefix-cleanup path now snapshots all paginated keys before deletion;
  `tools\pytest.ps1 backend/tests/test_r2_content_addressing.py -q` passes
  8 tests, including mutation-during-pagination coverage. A synthetic Phase 6
  seed was stopped after 193 temporary objects due workstation-to-R2 latency;
  the exact namespace cleanup was rerun and verified at zero objects and zero
  database rows. This is not production-scale telemetry evidence.
- The local audit confirms no canonical `novels/`, `storage/novel_library/`, or
  temporary repopulation staging path. The untracked `storage/runtime/`
  directory is disposable runtime state and is not a content source.
- The active application environment profiles now resolve the migrated `R2_*`
  application settings; backup credentials remain intentionally unset while
  `R2_BACKUP_ENABLED=false`.
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
is configured in the local environment.

| PostgreSQL ID | Source URL | Publication | Public URL | Chapters | Active generations | R2 objects | Stored bytes | Object groups | Translation status |
|---:|---|---|---|---:|---:|---:|---:|---|---|
| 11 | `https://ncode.syosetu.com/n2056dn/` | published | `/novels/my-father-is-a-hero-my-mother-is-a-spirit-and-i-their-daughter-am-a-reincarnator` | 148 | 1 | 298 | 801,608 | 148 chapters, 148 media, 1 generation, 1 translation | 1/148 translated |
| 16 | `https://kakuyomu.jp/works/16817330655991571532` | published | `/novels/that-time-i-got-reincarnated-as-a-world-tree` | 88 | 1 | 177 | 330,079 | 88 chapters, 88 media, 1 generation | 0/88 translated |
| 17 | `https://novel18.syosetu.com/n3266mn/` | unpublished | `/novels/holy-water-dungeon-until-i-who-used-and-discarded-women-as-keys-fell-to-a-top-tier-holy-water-operative` | 31 | 1 | 63 | 191,998 | 31 chapters, 31 media, 1 generation | 0/31 translated |

Logical uncompressed byte totals, compression savings, live GET/PUT/LIST
counters, unchanged-recrawl upload counts, deduplicated asset counts, reused
translation counts, and backup-object reuse counts were not captured by this
reset/repopulation run. The focused R2 catalog/cutover suite passes 10 tests,
including an unchanged-recrawl no-op and incremental backup object reuse, but
those tests are not a substitute for a measured repeated live crawl. The
backup bucket is empty because recovery remains user-deferred.

## Evidence boundary

Local unit tests, static audits, and opt-in isolated R2 integration tests do
not prove the production bucket reset, the three-novel repopulation, public
URL verification, provider capacity, pooler/query plans, production-scale
telemetry, an encrypted PostgreSQL restore, or a representative R2 restore.
Those require operator-authorized targets and sanitized live evidence. The
application must not be described as fully migrated until those acceptance
records exist.

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
| Explicit R2 client and exact key namespace | `backend/src/novelai/storage/backends/r2.py`, `backend/src/novelai/storage/content_addressing.py` | PASS: focused R2 backend and addressing tests |
| Deterministic content addressing and gzip metadata | `backend/src/novelai/storage/content_addressing.py`, `backend/src/novelai/storage/artifacts.py` | PASS: repeated serialization and round-trip tests |
| PostgreSQL exact artifact references and activation | R2 artifact-reference migration, `r2_catalog.py`, `r2_activation_service.py` | PASS: activation, checksum, and stale-writer tests |
| No local canonical production content backend | R2 factory, settings, Compose, runtime container | PASS: production and test content paths use the R2 boundary; tests use an in-memory R2 double and no filesystem content fixture remains |
| Incremental backup manifests | `backend/src/novelai/storage/r2_backup.py`, backup service/container integration | PASS: incremental-copy and checksum tests |
| Reset, migration, and repopulation workflow | `backend/src/novelai/storage/r2_cutover.py`, `novelai.runtime.cli` | PASS for dry-run and confirmation gates; production execution remains BLOCKED pending operator target approval |
| Pagination, checksum, and failure handling | R2 client, backup, cutover, and activation services | PASS: focused unit/integration coverage; real permission/scale behavior remains unmeasured locally |
| Reference-aware GC protects active/referenced/grace objects | `r2_cutover.py`, runtime GC command | PASS: mark/sweep and nested-asset reference tests |
| Public reader exact reads | R2 storage dispatch, public catalog/chapter services | PASS: exact-key contract coverage; hosted URL verification remains BLOCKED |
| Imports write immutable R2 artifacts and activate PostgreSQL references | importer/orchestration R2 path, `test_r2_catalog.py`, and E2E pipeline | PASS: immutable document-import activation and full backend suite |
| Documentation and route/link audit | repository-wide Markdown inventory, route scan, and link audit | PASS: 83 Markdown files, 30 local links, zero unresolved targets, current-only route scan |

## Local verification evidence

- `tools\pytest.ps1 backend/tests -q`: `2,895 passed, 16 skipped in 817.00s`
  (`13:37`); exit code `0`.
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
  `13,794` nodes and `38,338` edges.
- Route-ownership focused tests: `60 passed` (microservice split, production
  configuration, and contributor-router coverage).
- A database-targeted `alembic upgrade head` was not run in this pass because
  no safe migration target was explicitly authorized. An offline SQL attempt
  with a placeholder PostgreSQL URL reached an existing online-only role-query
  migration and stopped without mutating a database; the full backend suite
  and migration contract tests still pass.
- The local audit found an empty disposable root `novels/` directory and an
  empty `storage/runtime/` directory. The pre-existing ignored
  `storage/novel_library/` directory contains only local operational state and
  logs, not canonical novel objects. These local runtime artifacts were not
  deleted during this audit because they are outside the authorized change
  scope; the clean-worktree filesystem-leak gate remains operator-cleanup
  pending.

## Evidence boundary

Local unit tests, static audits, and opt-in isolated R2 integration tests do
not prove the production bucket reset, the three-novel repopulation, public
URL verification, provider capacity, pooler/query plans, production-scale
telemetry, an encrypted PostgreSQL restore, or a representative R2 restore.
Those require operator-authorized targets and sanitized live evidence. The
application must not be described as fully migrated until those acceptance
records exist.

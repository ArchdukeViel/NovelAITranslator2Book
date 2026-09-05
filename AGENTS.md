# AGENTS.md

## Purpose

This file is the compact repository constitution and routing index for Codex
and other coding assistants. It defines safety, authority, boundaries, and
verification. It does not replace the architecture, active specifications, or
implemented source.

## Authority and conflict resolution

Use this order:

1. The current explicit owner instruction defines authorized scope.
2. This file defines repository safety and working rules.
3. `docs/ARCHITECTURE.md` defines current architecture and trust boundaries.
4. An approved active specification defines an intended scoped delta.
5. The canonical document that owns a concern defines its stable detail.
6. Source, tests, manifests, migrations, and workflows prove implementation.
7. `docs/STATUS.md` records current work and unresolved decisions.
8. `docs/EVIDENCE.md` records verified historical outcomes.
9. `docs/archive/` is provenance only and is never active authority.

Report material conflicts; do not silently choose the easiest implementation.
Do not treat a plan, checked task box, passing workflow, or historical note as
proof that an intended change is implemented. Active plans live under
`docs/plans/`, are non-canonical, and never override this hierarchy.

`docs/STATUS.md` is the current unfinished-work and operator-gate register.
`docs/EVIDENCE.md` is the current completed-evidence and historical record.
That transition is temporary; after it completes, only the future names are
active.

## Read-on-demand documentation map

| Need | Read first |
| --- | --- |
| architecture, security, boundaries | `docs/ARCHITECTURE.md` |
| configuration and secret classification | `docs/CONFIGURATION.md` |
| CI, release, deployment, rollback | `docs/DEPLOYMENT.md` |
| global UI system and route briefs | `docs/DESIGN.md`, `docs/design/` |
| operational, health, queue, backup, restore runbooks | `docs/OPERATIONS.md` |
| storage ownership, keys, retention, recovery invariants | `docs/STORAGE.md` |
| translation, prompts, glossary, QA, quotas | `docs/TRANSLATION.md` |
| active work and gates | `docs/STATUS.md` |
| completed verification | `docs/EVIDENCE.md` |
| specialized execution rules | `.agents/rules/` |
| intended feature work | the applicable `.agents/specs/<name>/` |
| active execution order | `docs/plans/` |

Read `docs/ARCHITECTURE.md` before making an architecture or security change.
Read the relevant active specification before implementing its intended delta.
Do not preload unrelated documentation.

## Repository working rules

### Scope and dirty-worktree preservation

- Begin with `git status --short`, branch, and `git rev-parse HEAD`.
- Treat all existing modified and untracked paths as owner-owned.
- Preserve unrelated changes; do not reset, clean, stash, overwrite, or
  reformat them.
- Make the smallest coherent change in the existing architecture.
- Use `apply_patch`, `replace_file_content`, or agent-native edit tools for local
  file modifications. Use repository-native commands for generated files and
  explicitly authorized renames.
- Do not delete, rename, migrate data, or change contracts unless the request
  or an approved active specification requires it.
- Run `graphify update . --no-cluster` once after completing an edit batch,
  before running verification checks (do not run on every single file write).

### Side-effect authorization

- Local edits require explicit implementation scope.
- Commit, push, pull request, merge, visibility, GitHub settings, workflow
  dispatch, provider calls, deployment, and data mutation each need their own
  authorization.
- Never infer production authorization from test authorization.
- Test-only database, R2, Redis, or Worker operations require an exact target
  and operation-specific authorization.
- A read-only audit must not modify repository or external state.

### External-service safety

- Never access or mutate production resources without explicit authorization;
  plans in this repository never authorize production mutation.
- Resolve non-production identities immutably before any write and reject
  ambiguous or production-like targets.
- Never print, store, commit, or return secrets, tokens, cookies, connection
  strings, private keys, raw provider responses, SQL text, row contents, or
  request bodies.
- Record only sanitized classes, counts, timestamps, fixed reasons, and
  artifact paths.
- Preserve fail-closed states: `blocked`, `partial`, `unavailable`, and
  `not_established` are not passes.

## Tooling and environment

### Python wrappers

- `.venv\Scripts\python.exe` is the canonical interpreter (Python >= 3.14).
- Use `tools\pytest.ps1`, `tools\pyright.ps1`, `tools\ruff.ps1`, and
  `tools\docs-check.ps1`.
- Never use bare `python`, `pytest`, `ruff`, or `pyright` for backend work.
- Execute ad-hoc scripts via `.venv\Scripts\python.exe <script-path>`.
- Execute Alembic migrations via `.venv\Scripts\python.exe -m alembic -c backend/alembic.ini <cmd>`.
- If the venv is missing, follow `docs/OPERATIONS.md` or `readme.md` to
  recover it; do not silently use another interpreter.
- `pyproject.toml` is authoritative. Generated lockfiles are updated only by
  `deploy\update-lockfiles.ps1` after an authorized dependency change. Never run ad-hoc lockfile updates or dependency installations directly in production or staging.
- Focused test safety: During dirty-worktree states, run focused tests targeting affected modules instead of full test suites to prevent flakiness and uncommitted collision.

### Frontend commands

From `frontend/`, use `npm run lint`, `npm run typecheck`, `npm run test`, and
`npm run build` as applicable. `frontend/package-lock.json` is authoritative for
frontend dependencies and must only be updated via `npm install` inside `frontend/`,
never through manual edits. Server state uses React Query, client-only state
uses Zustand, and components use existing hooks and shared utilities. Do not
call `fetch()` directly from components or add Redux, CSS modules, or styled
components. Novel covers must use `next/image` with configured `remotePatterns`
in `next.config.mjs` (never disable optimization in production). Modals must wrap
in `DialogShell` (Escape dismissal, backdrop click closing, and body scroll locking).
Reader pages trigger next-chapter prefetching when `scrollProgress >= 70%`.

### Windows and shell rules

- Use PowerShell-compatible commands and quote paths containing spaces.
- Always include `-ExecutionPolicy Bypass` when invoking `.ps1` wrapper scripts:
  `powershell -ExecutionPolicy Bypass -File <script.ps1>`.
- Chain dependent commands with `; if ($?) { ... }` when needed.
- Use `rg` or `rg --files` for search.
- Do not use Linux bashisms (`cat`, `export`, `grep`, `rm -rf`, `touch`, `source`, `which`);
  use PowerShell equivalents (`Get-Content`, `$env:VAR = "val"`, `Remove-Item -Recurse -Force`, `Get-Command`).
- Write UTF-8 files without BOM using .NET `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))`
  to avoid PowerShell 5.1 BOM corruption.
- Do not expose environment values while checking variable names.
- Do not assume console scripts are on `PATH`.

## Code intelligence

### Graphify

When architecture, documentation, or cross-artifact relationships matter,
use the configured Graphify graph with focused `graphify query`, `graphify
path`, or `graphify explain` calls. Use `graphify-out/wiki/index.md` for
navigation and read `GRAPH_REPORT.md` only when scoped queries are insufficient.
Run `graphify update . --no-cluster` once after completing an edit batch,
before running verification checks; do not run semantic extraction or clustering
as a routine refresh. Harmless zero-node warnings on non-code files (e.g. JSON
configs) can be safely ignored.

### CodeGraph

When `.codegraph/` exists and the question concerns current symbols, callers,
dependencies, or blast radius, use CodeGraph before broad search. Verify its
results against source, tests, and configuration. If `.codegraph/` does not
exist, default to Graphify (`graphify-out/`) and native search tools; do not
initialize `.codegraph/` during routine work.

### Archify

When visualizing system architecture, workflows, API sequences, data pipelines,
or state lifecycles, author Archify diagrams via `tools\archify.ps1`. All diagram
JSON specifications, delivered HTML, and visual checks must reside strictly under
`docs/design/diagrams/` to comply with documentation whitelist contracts. Deliver
using `--quality showcase --json` and verify all 9 artifact checks pass with 0 errors.

## Project invariants

### Backend boundaries

Dependency direction is `api -> services -> domain -> storage/db/providers`.
Keep routers thin; source parsing belongs in `sources/`, outbound HTTP and SSRF
protection in `infrastructure/http/`, providers behind provider interfaces,
and persistence in `storage/` and `db/`. Use SQLAlchemy for application
persistence and raw SQL only in migrations or explicit policy scripts under
`backend/sql/`. Read settings through `novelai.config.settings.settings`.
Migrations in `backend/alembic/versions/` must use date-prefixed naming
`YYYY-MM-DD_<hash>_<description>.py`, maintain a single linear head, and be fully
reversible (`upgrade()` and `downgrade()`).
Web novel titles, episode subtitles, author notes, and chapter HTML bodies must use
SQLAlchemy `Text`, never clamped `String(255)` or `String(512)`. Do not apply ORM-level
SQLite table check constraints on `Novel.publication_status` that reject unnormalized
legacy strings (`"strange"` -> `"unknown"`). PostgreSQL connection pool budgeting must
satisfy `DB_POOL_PROCESS_COUNT * (DB_POOL_SIZE + DB_MAX_OVERFLOW) + DB_CONNECTION_RESERVE <= DB_CONNECTION_BUDGET`
(5/5 split across backend, reader, and worker against `max_connections = 100`).
Any change to database migrations under `backend/alembic/versions/` must verify downgrade
reversibility locally (`alembic downgrade -1` followed by `upgrade head`).

### Frontend boundaries

Admin routes remain under `frontend/app/(admin)/admin/*`; public routes remain
under `frontend/app/(public)/*`. Admin API access uses `frontend/lib/api.ts` and
public access uses `frontend/lib/public-api.ts`. Do not move behavior across
route groups without an explicit architecture decision.

### Identity and security

- Public registration creates users only; it cannot create or promote owners.
- Derive identity from the authenticated session, never a client-supplied ID.
- Cookie-authenticated state changes require CSRF protection.
- `GET /health/live` is unauthenticated process liveness and performs no
  database, storage, or worker calls.
- `GET /health/ready` is redacted public-safe readiness; detailed admin health
  is owner-only and remains redacted.
- Credentials are masked with existing backend/frontend masking utilities.

### Storage and deployment

- Novel content is R2-only: PostgreSQL owns relational state and exact object
  references; R2 owns immutable artifacts; Redis/Valkey owns transient
  coordination; local runtime storage is disposable.
- R2 directories are virtual prefixes. Use exact-key reads and paginated
  listing only for inventory, backup, migration, or garbage collection.
- Raw novel generations under `generations/<gen-id>/` are byte-immutable; never
  rewrite raw chapter bundles or image assets in place.
- Translation writes land exclusively in the per-chapter overlay:
  `translations/<encoded-chapter-stem>.json` alongside the `active/` pointer mirror.
- Readers compose the active raw generation with the active translation overlay on read.
- Kakuyomu IDs (`kakuyomu:<episode>`) and chapter IDs are stable strings; never cast to
  `int`, never use `isdigit()`, and never fallback non-numeric IDs to `-1`.
- Cache acceptance is locked strictly to QA-accepted attempts; chunks marked `needs_retry`,
  `needs_review`, or `qa_failed` must never reach cache.
- Do not add compatibility aliases, filesystem fallbacks, dual writes, or
  alternate storage backends.
- Migrations run in the one-shot Compose `migrate` service before backends.
- Caddy routes admin/auth/user/health to admin, public API to reader, and
  remaining routes to the frontend. Split mode requires shared Redis.
- Do not serve runtime directories as static files or delete immutable objects
  without reference, backup/grace-period, and explicit GC proof.

## Verification ladder

### Tiered verification protocol

Apply scope-proportional ceremony:
- **Tier 1 (Core)**: Architecture changes, schema/migrations, security/auth, R2 storage,
  public API contracts, or breaking configuration. Requires full specification under
  `.agents/specs/`, formal verification logging in `docs/STATUS.md` and `docs/EVIDENCE.md`,
  and full guard execution.
- **Tier 2 (Targeted)**: Bug fixes, UI/CSS adjustments, internal refactors, isolated test
  additions. Requires only focused tests, affected linters/typechecks, and atomic git commit.
  Do not update `docs/STATUS.md` or `docs/EVIDENCE.md` for routine Tier 2 edits unless
  explicitly requested.

### Execution ladder

Run the smallest decisive check first, then broaden for changed scope:

1. focused architecture, path, documentation, or security guard;
2. affected lint/type check through repository wrappers;
3. focused tests (run targeted test files first during dirty worktree state to avoid
   false failures from unrelated uncommitted work);
4. affected integration, frontend, build, workflow, or evidence validation;
5. broader checks only when cross-subsystem impact requires them.

Record the exact command, timeout when relevant, exit code, result count, and
paths. A skipped or unavailable command is recorded as `not_run` or
`unavailable`, never as passed.

Required repository guards include:
- **Router import guard**: `powershell -ExecutionPolicy Bypass -Command "rg -n '^from novelai\.(db\.models|storage\.service|sources\.)' backend/src/novelai/api/routers/ --glob '!dependencies.py'"` (must return 0 matches / exit 1).
- **AGENTS heading uniqueness guard**: `powershell -ExecutionPolicy Bypass -Command "Get-Content AGENTS.md | Select-String '^#{1,6}\s+' | Group-Object | Where-Object Count -gt 1"` (must return 0 duplicates).
- **Documentation contract check**: `powershell -ExecutionPolicy Bypass -File tools\docs-check.ps1` (must return exit 0, 0 violations).
- **Graphify index refresh**: `graphify update . --no-cluster` (after edit batch).

## Git and commit rules

- Never use `--no-verify`.
- Before staging, format only affected source files with the repository
  formatter and run affected checks.
- Stage exact intended paths and run `git diff --cached --check`.
- Commit only authorized changes; do not absorb pre-existing owner changes.
- Verify the resulting commit tree and remote state after authorized remote
  operations. Never force-push, rewrite history, or directly push protected
  branches without explicit authorization.
- A task branch normally returns to the repository's requested base state only
  after preserving all task branches and uncommitted owner work.

## Documentation and specification lifecycle

- `docs/ARCHITECTURE.md` remains authoritative for architecture and security.
- Canonical documents own one concern each; cross-link instead of duplicating
  normative prose.
- Canonical documents (`docs/*.md`) strictly describe verified shipped code.
  Never edit canonical documents during the planning phase to describe an intended
  state; update canonical docs only after implementation passes all verification.
- Under `docs/`, only three subdirectories are permitted: `docs/archive/`,
  `docs/design/`, and `docs/plans/`; creating any other directory fails `tools/docs-check.ps1`.
- Specifications belong in `.agents/specs/<name>/`, never under `docs/specs/`.
  Active specifications must define YAML/header metadata with `Spec ID`, `Version`, and `Status` (`Active`, `Blocked`, `Complete`, or `Superseded`).
  An agent must not implement or close tasks on a specification marked `Status: Blocked` or `Status: Superseded`
  without an explicit, authorized unblocking instruction from the repository owner.
- `docs/STATUS.md` contains current unresolved work, decisions, dependencies,
  and acceptance gates; it contains no completed-work narrative.
- `docs/EVIDENCE.md` contains sanitized, dated verification and limitations;
  it does not redefine policy.
- Active specifications remain under `.agents/specs/`; do not archive one from
  checkboxes alone. Archive only after evidence and unresolved work are routed.
- Plans under `docs/plans/` are non-canonical execution instructions.
- Archives preserve provenance and never become active authority.
- Update canonical documentation whenever implementation changes behavior,
  configuration, storage, deployment, security, operations, or testing.
- Validate documentation contracts with `powershell -ExecutionPolicy Bypass -File tools\docs-check.ps1`.

## Final evidence contract

Before declaring completion:

1. Reconcile the request, specification, implementation, tests, evidence, and
   documentation ownership.
2. Review the focused diff and distinguish task changes from owner changes.
3. Validate artifacts for candidate identity, sanitization, disposition, and
   cleanup; never manufacture missing provider or production evidence.
4. Run required checks and record exact results.
5. Run `git status --short` and report remaining uncertainty or blockers.

Use only truthful dispositions: `passed`, `failed`, `blocked`, `partial`,
`unavailable`, and `not_run`. Keep `production_capacity_claim` as
`not_established` unless an independently authorized evidence program proves
otherwise. A successful workflow, local test, worker absence, or historical
staging result does not establish production capacity.

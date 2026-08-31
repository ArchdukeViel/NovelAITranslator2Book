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
- Use `apply_patch` for local file edits. Use repository-native commands for
  generated files and explicitly authorized renames.
- Do not delete, rename, migrate data, or change contracts unless the request
  or an approved active specification requires it.
- After every repository edit, run `graphify update . --no-cluster`.

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
- Use `tools\pytest.ps1`, `tools\pyright.ps1`, and `tools\ruff.ps1`.
- Never use bare `python`, `pytest`, `ruff`, or `pyright` for backend work.
- If the venv is missing, follow `docs/OPERATIONS.md` or `readme.md` to
  recover it; do not silently use another interpreter.
- `pyproject.toml` is authoritative. Generated lockfiles are updated only by
  `deploy\update-lockfiles.ps1` after an authorized dependency change.

### Frontend commands

From `frontend/`, use `npm run lint`, `npm run typecheck`, `npm run test`, and
`npm run build` as applicable. Server state uses React Query, client-only state
uses Zustand, and components use existing hooks and shared utilities. Do not
call `fetch()` directly from components or add Redux, CSS modules, or styled
components.

### Windows and shell rules

- Use PowerShell-compatible commands and quote paths containing spaces.
- Chain dependent commands with `; if ($?) { ... }` when needed.
- Use `rg` or `rg --files` for search.
- Do not expose environment values while checking variable names.
- Do not assume console scripts are on `PATH`.

## Code intelligence

### CodeGraph

When `.codegraph/` exists and the question concerns current symbols, callers,
dependencies, or blast radius, use CodeGraph before broad search. Verify its
results against source, tests, and configuration. Do not initialize or edit
`.codegraph/` during routine work.

### Graphify

When architecture, documentation, or cross-artifact relationships matter,
use the configured Graphify graph with focused `graphify query`, `graphify
path`, or `graphify explain` calls. Use `graphify-out/wiki/index.md` for
navigation and read `GRAPH_REPORT.md` only when scoped queries are insufficient.
After every edit run `graphify update . --no-cluster`; do not run semantic
extraction or clustering as a routine refresh.

## Project invariants

### Backend boundaries

Dependency direction is `api -> services -> domain -> storage/db/providers`.
Keep routers thin; source parsing belongs in `sources/`, outbound HTTP and SSRF
protection in `infrastructure/http/`, providers behind provider interfaces,
and persistence in `storage/` and `db/`. Use SQLAlchemy for application
persistence and raw SQL only in migrations or explicit policy scripts under
`backend/sql/`. Read settings through `novelai.config.settings.settings`.

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
- Do not add compatibility aliases, filesystem fallbacks, dual writes, or
  alternate storage backends.
- Migrations run in the one-shot Compose `migrate` service before backends.
- Caddy routes admin/auth/user/health to admin, public API to reader, and
  remaining routes to the frontend. Split mode requires shared Redis.
- Do not serve runtime directories as static files or delete immutable objects
  without reference, backup/grace-period, and explicit GC proof.

## Verification ladder

Run the smallest decisive check first, then broaden for changed scope:

1. focused architecture, path, documentation, or security guard;
2. affected lint/type check through repository wrappers;
3. focused tests;
4. affected integration, frontend, build, workflow, or evidence validation;
5. broader checks only when cross-subsystem impact requires them.

Record the exact command, timeout when relevant, exit code, result count, and
paths. A skipped or unavailable command is recorded as `not_run` or
`unavailable`, never as passed.

Required repository guards include the router import guard, AGENTS heading
uniqueness guard, documentation/path checker, and Graphify refresh when their
scope is affected.

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

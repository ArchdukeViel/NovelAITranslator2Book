# AGENTS.md

Project-specific instructions for coding assistants. Primaries follow configured delegation and acceptance policy; this file defines repository facts, contracts, and verification.

## Sources of Truth

Use sources in this order:

1. `docs/ARCHITECTURE.md` — architecture, contracts, security boundaries, dependency direction.
2. Active specification under `.agents/kiro/specs/<spec-name>/`.
3. Existing production code and tests.
4. `docs/WORK.md` — active, blocked, deferred, and operator-acceptance work.

Architecture wins over other documentation. An active approved specification wins over archived specifications. Report conflicts before implementation; never silently choose one interpretation.

Do not preload every document. Load canonical detail only when relevant:

| Need | Canonical source |
| --- | --- |
| Architecture or security | `docs/ARCHITECTURE.md` |
| Global frontend design index | `docs/DESIGN.md` |
| Public page design | `docs/design/public/...` |
| Admin page design | `docs/design/admin/...` |
| Shared design, system & accessibility rules | `docs/DESIGN.md` |
| Configuration | `docs/CONFIGURATION.md` |
| CI or deployment procedure | `docs/DEPLOYMENT.md` |
| Operator runbook, health, or backup procedure | `docs/OPERATIONS.md` |
| Translation quality policy & prompt lifecycle | `docs/TRANSLATION.md` |
| Unfinished work | `docs/WORK.md` |
| Completed evidence | `docs/HISTORY.md` |

## Working Principles

- **Stay within scope.** Act only on the user's stated request. If you discover an unrelated defect or improvement, surface it as a finding and stop; do not fix it without explicit authorization.
- **Clarify before acting on ambiguity.** If the user's request is ambiguous in a way that affects scope, behavior, or contracts, ask before acting. Never resolve ambiguity by picking the cheaper interpretation.

## Project Venv

The project virtualenv at `.venv/` is the canonical interpreter. Python
version: ≥ 3.14. PATH-precedence mistakes cannot poison results when the
wrapper resolves to `.venv\Scripts\python.exe` explicitly. Always invoke
backend tooling through the wrappers in `tools/`:

- `tools/pytest.ps1` — runs the backend test suite.
- `tools/pyright.ps1` — runs pyright.
- `tools/ruff.ps1` — runs ruff check / format.

Each script refuses to run when `.venv\Scripts\python.exe` is missing.
The CI workflow installs `.[documents,gemini,dev,test,s3,auth]`
into the venv before invoking tooling. Bare `python` / `pytest` /
`ruff` / `pyright` invocations outside the wrappers fall through to
the system interpreter and lose the venv pinning.

## Verification

Run smallest check proving changed behavior, from repository root unless command explicitly changes directory. Order: focused lint or architecture guard, type checking, focused tests, then broader checks only when justified.

| Command | Purpose |
| --- | --- |
| `tools/ruff.ps1 check .` | Backend lint; do not fix unrelated pre-existing errors. |
| `tools/pyright.ps1` | Backend type checking for `backend/src` and `backend/tests`. |
| `tools/pytest.ps1 backend/tests/test_<name>.py` | Focused backend test file. |
| `tools/pytest.ps1 backend/tests/e2e/` | Backend E2E tests; slower and fixture-dependent. |
| `cd frontend; npm run typecheck` | Frontend TypeScript check. |
| `cd frontend; npm run test` | Frontend Vitest suite. |
| `cd frontend; npm run lint` | Frontend ESLint. |
| `cd frontend; npx vitest run <file>` | Focused frontend test file(s). |
| `cd frontend; npm run build` | Production frontend build. |
| `alembic -c alembic.ini upgrade head` | Apply migrations from repository root; requires `DATABASE_URL`. |

The `tools/*.ps1` wrappers resolve to `.venv\Scripts\python.exe`
automatically; see *Project Venv* above.

Router-layer guard must return no matches:

```powershell
rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"
```

Canonical-doc heading uniqueness guard must return no matches (fails if any `## ` heading appears more than once in `AGENTS.md`):

```powershell
Get-Content AGENTS.md | Where-Object { $_ -match '^## ' } | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name }
```

### Commit workflow

1. Run formatters before staging: `tools\ruff.ps1 format <every file in the diff>`. The pre-commit hook reformats all staged files (including previously committed ones), so an unformatted file anywhere in the staged set will be modified by the hook; `ruff check` enforces B905, so `zip()` calls need explicit `strict=`.
2. Run affected lint, type checks, and focused tests.
3. Stage exact intended paths; run `git diff --cached --check`.
4. Commit with hooks enabled. Never use `--no-verify`.
5. If hooks modify files, preserve output, compare working tree with index, prove changes expected, restage exact paths, rerun affected checks, and retry once.

After every edit, including documentation edits, run:

```powershell
tools/pyright.ps1   # only when Python source changed
graphify update . --no-cluster   # always (standalone binary; python -m graphify is unavailable in .venv)
```

Record raw validation command, timeout when relevant, exit code, result count, and exact paths. Never claim a check passed unless run successfully.

## Repository Layout and Entry Points

### Backend

- Package: `backend/src/novelai/`
- Tests: `backend/tests/`
- Migrations: `backend/alembic/versions/`
- Explicit database-policy SQL: `backend/sql/`
- Default app: `novelai.api.app:app`
- Admin/control plane: `novelai.main_admin:app`, port 8000
- Public reader: `novelai.main_reader:app`, port 8001
- CLI: `novelaibook` (`web`, `worker`, `doctor`, `create-user`, `adminweb`, `publicweb`)

`DEPLOY_MODE=split` runs admin and reader separately. Admin supports sessions; cookie-authenticated admin and public-user mutations require CSRF protection. Reader has no admin session.

### Frontend

- Package: `frontend/`; read framework version from `frontend/package.json`.
- Admin routes: `frontend/app/(admin)/admin/*`.
- Public routes: `frontend/app/(public)/*`.
- Admin API access: `frontend/lib/api.ts`.
- Public API access: `frontend/lib/public-api.ts`.

Do not move behavior across route-group boundaries without an explicit architecture change. Components must not call `fetch()` directly.

### Deployment

- Canonical Compose: `deploy/compose.yml`.
- Development overlay: `deploy/compose.dev.yml`.
- Images: `deploy/admin.Dockerfile`, `deploy/reader.Dockerfile`, `deploy/frontend.Dockerfile`.
- Reverse proxy: Caddy.

## Architecture Boundaries

Dependency direction:

```text
api
  → services
    → domain modules
→ storage / db / providers / sources
```

- Keep routers thin; use `services/` or `services/orchestration/` for use cases.
- Put source parsing in `sources/`.
- Put outbound HTTP, SSRF protection, retries, and fetch caching in `infrastructure/http/`.
- Put provider integration in `providers/`, prompts in `prompts/`, persistence in `storage/` and `db/`.
- Keep scheduler policy in backend translation, service, or job layers, never React.
- Lower layers must not import API routers or frontend concepts.
- Routers must not directly import `novelai.db.models.*`, `novelai.storage.service.*`, or `novelai.sources.*`; only `api/routers/dependencies.py` may construct those dependencies.

Canonical identifiers:

```text
source_key, source_novel_id, source_url, novel_id, chapter_id, paragraph_id,
chunk_id, bundle_id, provider_key, provider_model, activity_id, job_id,
request_id, credential_id, requesting_user_id, credential_owner_user_id,
prompt_version, glossary_hash
```

When directly changed code uses an ambiguous legacy alias, replace it with the applicable canonical name and update affected callers, types, tests, and docs. Do not perform unrelated repository-wide renames.

## Backend Rules

- Use SQLAlchemy for application persistence.
- Raw SQL is allowed only in Alembic migrations and explicit policy scripts under `backend/sql/`; never in routers, services, orchestration, or domain code.
- Read settings through `novelai.config.settings.settings`; do not read `os.environ` elsewhere.
- Configure logging through `novelai.logging_config.configure_logging()`; do not scatter `logging.basicConfig()`.
- Schema changes require a new migration. Never edit an already committed migration.
- Use `httpx` for outbound HTTP and preserve SSRF protections.
- Keep provider-specific behavior behind provider interfaces and storage differences behind storage abstractions.
- Use `asyncio.Semaphore` for bounded async concurrency. For independent fan-out where partial failure is intended, use `asyncio.gather(..., return_exceptions=True)`.
- Validate API inputs with Pydantic; never pass unvalidated request dictionaries into use-case code.

## Frontend Rules

- Use `@tanstack/react-query` for server state and `zustand` for client-only state; do not add Redux.
- Use Tailwind CSS and `cn()` from `frontend/lib/utils.ts`; do not add CSS modules or styled-components.
- Keep business and data-flow logic in hooks, not components.
- Shared components belong in `frontend/components/`; route-local components stay under their route.
- Mask credentials through `frontend/lib/mask-token.ts`; never render complete credentials or secrets.

## Operational Contracts

Full architecture and operator detail belongs in canonical docs. Preserve these easy-to-break invariants:

### Health

- `GET /health/live`: unauthenticated process-only liveness, no DB/storage/worker calls, always 200.
- `GET /health/ready`: public-safe DB/storage/worker/disk readiness, 503 when unhealthy, no paths, hosts, credentials, or traces.
- `GET /api/admin/health`: owner-only detailed diagnostics via `require_role("owner")`, still redacted.
- Probe states are `healthy`, `degraded`, `unhealthy`; honor `HEALTH_PROBE_TIMEOUT_MS` and `HEALTH_TOTAL_TIMEOUT_MS`.
- Implementations live in `backend/src/novelai/services/health_service.py` and `backend/src/novelai/api/routers/health.py`.

### Storage and scheduling

- `novelai.storage.file_lock.InterProcessFileLock` is canonical cross-platform process lock. It uses atomic `O_CREAT | O_EXCL`, bounded retries, Windows PID liveness checks, and stale-lock reclamation. Use it for conflicting writes or cleanup.
- `SchedulerRuntimeState` plus `SchedulerRuntimeStateService` is durable cross-restart scheduler state. `scheduler_states.json` remains an in-process per-job model cache; transitions write both. Never rely on memory alone.
- `R2IncrementalBackupTarget.apply_retention()` preserves newest successful
  manifests and `BACKUP_MIN_SUCCESSFUL_TO_KEEP`, under
  `InterProcessFileLock`; shared objects also honor
  `BACKUP_SAFETY_GRACE_DAYS`.
- `MaintenanceService` runs allowlisted cleanup with dry-run and path-safety checks; reject blank, root, project-root, and symlink-escape paths.
- `SchedulerService` uses a lightweight asyncio loop and `scheduled_cron_log`; do not reintroduce APScheduler. Migration-defined cleanup is active only after applied migrations and live scheduler state are verified.
- Preserve raw scraped chapters and historical generated artifacts. Generated reader downloads remain out of scope; novel imports accept source URLs only.

### Deployment and object storage

- Migrations run in one-shot Compose `migrate` service before backend startup, never inside long-running backend containers.
- Caddy routes `/api/admin/*`, `/api/auth/*`, `/api/user/*`, and `/health/*` to admin on 8000; `/api/public/*` to reader on 8001; remaining routes to frontend on 3000.
- Compose healthcheck uses `python -c "import urllib.request; ..."` for image portability.
- `DATABASE_URL` uses `postgresql+psycopg://`, not `postgresql://`.
- Novel content is R2-only: `dokushodo` stores immutable artifacts and
  `dokushodo-backup` stores independent recovery material. PostgreSQL owns
  exact artifact references; Redis/Valkey owns transient coordination. The
  local runtime directory is disposable. R2 directories are virtual prefixes:
  use exact-key reads and paginated listing only in inventory/backup/GC jobs;
  never use host `Path.exists()` or `Path.is_dir()` as content truth.
- Object-store lifecycle rules are not backups. Claim backup coverage only with an independently restorable copy and verified restore procedure.
- Split or multi-instance mode requires Redis for shared rate limits and distributed jobs. Canonical environment variable is `ENV`, not `APP_ENV`.

## Testing

- Shared fixtures: `backend/tests/conftest.py`.
- `TestFixture` supplies isolated storage, mock providers, mock sources, and dependency container.
- Unit DB tests use SQLite in memory unless explicitly marked otherwise.
- E2E fixtures: `backend/tests/e2e/conftest.py`.
- Scratch fixture root: `backend/tests/.tmp/fixtures`.
- Scratch runtime root: `backend/tests/.tmp/runtime`.
- Register ORM models through `register_database_models()` in `novelai/db/model_registry.py`; do not import individual ORM modules for side effects.
- Source tests use offline fixtures and never access live novel websites.
- Pytest configuration supplies `backend/src` and `backend` python paths, disables cache provider, and defines `e2e`.
- Add or update tests directly proving changed behavior. Run closest focused test first, then affected language type checking. Run broader checks only for cross-subsystem changes.
- One-line changes still require one runnable verification command.
- File-backed SQLite test databases should enable `PRAGMA journal_mode=WAL`; default-journal commits measure 16–66 ms each on Windows (WAL ≈ 4 ms) and synchronous commits serialize the event loop in async tests.
- Avoid absolute wall-clock timing bounds in tests; prefer overhead-invariant metrics (e.g., total-overlap sums) that hold on slow machines and loaded CI.

## Dependencies and Lockfiles

- `pyproject.toml` is authoritative; there is intentionally no `requirements.txt`.
- Standard editable development install: `pip install -e ".[dev]"`.
- Available extras include `auth`, `db`, `dev`, `documents`, `gemini`, `openai`, `s3`, `test`, `worker`.
- Lockfiles: `requirements.lock`, `requirements-dev.lock`, `uv.lock`.
- After dependency changes run `deploy/update-lockfiles.ps1`; never edit generated lockfiles manually.
- Do not add a dependency when standard library or an installed dependency adequately solves the need.

## Security and Secrets

- Never read, print, log, paste, commit, or return secrets, connection strings, credential fragments, `.env`, `deploy/.env`, or `deploy/.env.production` contents.
- Never expose raw paths, internal DB keys, storage keys, complete credential values, hostnames, or stack traces in public API responses.
- Mask backend credentials with existing masking code and frontend values through `frontend/lib/mask-token.ts`.
- `SESSION_SECRET_KEY` fails closed at its default. `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is required before storing provider API keys. `OWNER_BOOTSTRAP_SECRET` is sole owner-seeding mechanism and must never be exposed.
- Public Google OAuth and email/password registration create `role="user"` only. Public auth must never create or promote an owner.
- Cookie-authenticated state-changing endpoints require CSRF protection. Never bypass auth or CSRF for tests.
- Derive identity from authenticated session; never accept client-supplied `user_id` as authenticated identity.
- The configured runtime directory must never be served directly as static
  files. Do not delete immutable R2 artifacts without a verified reference,
  backup/grace-period check, and an explicit GC/migration operation.
- Production `WEB_CORS_ORIGINS` must be explicit, never `*`.
- Contributor credentials are enabled only through the documented consent,
  encryption, validation, quota, isolation, and revocation contract in
  `docs/ARCHITECTURE.md`.
- Do not mutate production secrets, schema, data, functions, storage, or deployment without explicit target/action authorization.

## Code Intelligence

### CodeGraph

When `.codegraph/` exists, use CodeGraph before broad file searches for current source questions. It locates symbols, current source, callers/callees, dynamic dispatch, blast radius, and affected tests:

```powershell
python -m codegraph explore "<symbol names or question>"
```

After results, read only decisive source locations. CodeGraph does not replace source verification, diff inspection, lint, type checks, migrations, tests, builds, or runtime checks. Do not initialize or edit `.codegraph/` during ordinary tasks.

### Graphify

Graphify covers architecture, docs, config, SQL, storage, specifications, and cross-artifact context. Prefer scoped commands:

```powershell
graphify query "<question>"
graphify path "<A>" "<B>"
graphify explain "<concept>"
```

Use `graphify-out/wiki/index.md` for broad navigation when present. Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when scoped queries are insufficient. Do not use CodeGraph and Graphify for the same question unless first leaves a documented gap.

`graphify check-update .` checks only pending non-code semantic extraction; silence does not prove source freshness. Run `graphify update . --no-cluster` after every edit, including docs. Never run semantic extraction, clustering, or labeling without explicit approval and budget controls. Do not edit generated `.codegraph/` contents.

## Windows and GitHub

- Use PowerShell-compatible commands.
- Chain dependent commands with `first-command; if ($?) { second-command }`; Windows PowerShell 5.1 does not support `&&`.
- Run Python tools as `python -m <tool>` and do not assume console scripts are on `PATH`.
- Use `rg`, not Unix `grep`.
- Quote paths containing spaces; avoid interactive or TTY-dependent commands.
- `gh pr merge --squash` can report local failure after a successful merge. Verify with `gh pr view --json state`.
- Complex `gh --jq` filters can break in PowerShell; pipe JSON to `ConvertFrom-Json`.
- GitHub Actions log archives may not exist while a job is active. Inspect `gh run view <id> --json status,conclusion,jobs`; fetch logs only after completion.
- Never create, modify, close, or merge a PR without explicit authorization.
- After task-branch work, return this workspace to clean local `main` tracking `origin/main` unless the user explicitly asks to remain on another branch. Preserve task branches and uncommitted changes; never discard work merely to switch branches.

## Documentation and Specifications

- `docs/ARCHITECTURE.md` remains authoritative.
- `docs/WORK.md` is single unfinished-work register. Move completed work to `docs/HISTORY.md` in same change.
- Update canonical docs when behavior, configuration, contracts, deployment, security, or operator procedure changes; do not create duplicates.
- Do not edit anything under `.agents/` without owner approval. Never treat archived specifications as active requirements.
- `.opencode/` is local and gitignored; never commit it. Do not commit `.codegraph/`, `.vscode/`, secrets, session exports, test scratch data, or unrelated working-tree changes.

## Final Evidence

Before completion, reconcile requirements, focused diff, validation, independent review, Graphify refresh, documentation, and Git state. Report:

- files changed and behavior or documentation outcome;
- exact commands, timeouts, exit codes, result counts, and paths;
- review findings and resolutions;
- Graphify result;
- Git/PR/CI state requested by task;
- remaining risks, unverified assumptions, or concrete blockers.

Never claim completion from worker prose, an unverified diff, or a local commit when requested stopping point is remote merge.

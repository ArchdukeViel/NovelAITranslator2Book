# AGENTS.md

Compact project instructions for AI coding assistants. Read this file before any non-trivial investigation, plan, edit, review, or debugging task.

## Sources of Truth

Use these sources in this order:

1. `docs/architecture/architecture.md` — architecture, contracts, security boundaries, and dependency direction.
2. The active specification under `.agents/kiro/specs/<spec-name>/`.
3. Existing production code and tests.
4. `docs/DEBT.md` — active technical debt.
5. `docs/roadmap.md` — project roadmap.

When two sources disagree:

* Architecture wins over other documentation.
* An active approved specification wins over archived specifications.
* Report the conflict before implementing.
* Do not silently choose one interpretation.

Do not pre-load every document. Read only the references relevant to the current task.

---

## Verification Commands

Run commands from the repository root unless the command changes directory explicitly.

Workflow order:

1. Focused lint or architecture guards.
2. Type checking.
3. Focused tests.
4. Broader checks only when justified by the change.

| Command                                           | Purpose                                                                                          |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `python -m ruff check .`                          | Backend lint. Pre-existing unrelated errors may exist; do not fix them unless they are in scope. |
| `python -m pyright`                               | Backend type checking using `pyrightconfig.json`; covers `backend/src` and `backend/tests`.      |
| `python -m pytest backend/tests/test_<name>.py`   | Focused backend test file. Prefer this over the complete suite.                                  |
| `python -m pytest backend/tests/e2e/`             | Backend end-to-end tests; slower and dependent on e2e fixtures.                                  |
| `cd frontend; npm run typecheck`                  | Frontend TypeScript checking.                                                                    |
| `cd frontend; npm run test`                       | Frontend Vitest suite.                                                                           |
| `cd frontend; npm run build`                      | Production frontend build.                                                                       |
| `cd backend; alembic -c alembic.ini upgrade head` | Apply migrations; requires `DATABASE_URL`.                                                       |

The backend suite contains many test files and known unrelated failures. Run the smallest test set that proves the changed behavior.

### Router-layer guard

This command must return no matches:

```powershell
rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"
```

---

## Project Structure

### Backend

* Root: `backend/src/novelai/`
* Frameworks: FastAPI, SQLAlchemy, Pydantic.
* Python package root: `backend/src`.
* Tests: `backend/tests/`.
* Database migrations: `backend/alembic/versions/`.
* Explicit database-policy SQL: `backend/sql/`.

### Frontend

* Root: `frontend/`
* Framework: Next.js 15 App Router.
* Frontend is an independent Node package.

### Deployment

* Root: `deploy/`
* Canonical Compose file: `compose.yml`
* Development overlay: `compose.dev.yml`
* Containers:

  * `admin.Dockerfile` — admin API on port 8000.
  * `reader.Dockerfile` — public reader API on port 8001.
  * `frontend.Dockerfile` — frontend.
* Reverse proxy: Caddy.

### Specifications

* Active specifications: `.agents/kiro/specs/`
* Do not edit anything under `.agents/` without owner approval.

### Local agent files

* `.opencode/` contains local OpenCode plugins, goals, commands, and scratch state.
* `.opencode/` is gitignored.
* Do not commit files from `.opencode/`.

---

## Backend Entry Points

* `novelai.api.app:app` — default monolithic application.
* `novelai.main_admin:app` — admin-only application on port 8000; session and CSRF protected.
* `novelai.main_reader:app` — public reader on port 8001; no admin session.
* `DEPLOY_MODE=split` runs the admin and reader processes separately.
* CLI executable: `novelaibook`.

CLI subcommands include:

* `web`
* `worker`
* `doctor`
* `create-user`
* `adminweb`
* `publicweb`

---

## Frontend Route Boundaries

* `frontend/app/(admin)/admin/*` — owner/admin interface.
* `frontend/app/(public)/*` — guest and authenticated public-user interface.
* Do not move behavior across these route-group boundaries without an explicit architecture change.

API access must go through:

* `frontend/lib/api.ts` for admin API calls.
* `frontend/lib/public-api.ts` for public API calls.

Do not issue direct `fetch()` calls from components.

---

## Architecture and Layer Rules

Dependency direction:

```text
api
  → services
    → domain modules
      → storage / db / providers / sources / export
```

Rules:

* API routers stay thin.
* Put use-case behavior in `services/` or `services/orchestration/`.
* Put source parsing in `sources/`.
* Put outbound HTTP, SSRF protection, retries, and fetch caching in `infrastructure/http/`.
* Put provider API integration in `providers/`.
* Put translation prompts and prompt assembly in `prompts/`.
* Put persistence behind `storage/` and `db/`.
* Put scheduler policy in backend translation, service, or job layers—not React.
* Do not let lower layers import API routers or frontend concepts.

Routers must not directly import:

* `novelai.db.models.*`
* `novelai.storage.service.*`
* `novelai.sources.*`

The exception is `api/routers/dependencies.py`, which contains dependency-injection factories.

---

## Canonical Names

Use these names. Do not invent aliases:

```text
source_key
source_novel_id
source_url
novel_id
chapter_id
paragraph_id
chunk_id
bundle_id
provider_key
provider_model
activity_id
job_id
request_id
credential_id
requesting_user_id
credential_owner_user_id
prompt_version
glossary_hash
```

When code being changed still uses ambiguous legacy aliases such as:

```text
id
source
provider
model
slug
```

replace the alias with the correct canonical name and update directly affected callers, types, tests, and documentation in the same change.

Do not perform unrelated repository-wide renames.

---

## Backend Conventions

* Application persistence uses SQLAlchemy.
* Do not add raw SQL to routers, services, orchestration, or domain code.
* Alembic migrations and explicit database-policy scripts under `backend/sql/` are the only raw-SQL exceptions.
* Read settings through `novelai.config.settings.settings`.
* Do not read `os.environ` outside the settings module.
* Configure logging through `novelai.logging_config.configure_logging()`.
* Do not scatter `logging.basicConfig()` calls.
* A schema change requires a new migration under `backend/alembic/versions/`.
* Never edit an already committed migration.
* Use `httpx` for outbound HTTP.
* Use `asyncio.Semaphore` for bounded asynchronous concurrency.
* For independent fan-out work, use `asyncio.gather(..., return_exceptions=True)` when partial failure is part of the intended behavior.
* Validate API inputs with Pydantic models.
* Do not pass unvalidated request dictionaries into use-case code.
* Keep provider-specific behavior behind provider interfaces.
* Keep storage-backend differences behind storage abstractions.

---

## Operational Contracts

These are behavioral contracts that future agents must preserve. Violating them breaks existing functionality.

### Health endpoints (M2a)

* `GET /health/live` — process-only liveness, unauthenticated, no DB/storage/worker calls. Always returns 200.
* `GET /health/ready` — public-safe readiness, probes DB, storage, worker, disk. Returns 503 if any probe is unhealthy. Never exposes credentials, paths, hostnames, or stack traces.
* `GET /api/admin/health` — owner-only detailed diagnostics (`require_role("owner")`). Still redacted.
* Probe states: `healthy`, `degraded`, `unhealthy`. Each probe is bounded by `HEALTH_PROBE_TIMEOUT_MS`; total request by `HEALTH_TOTAL_TIMEOUT_MS`.
* Implementation: `backend/src/novelai/services/health_service.py` and `backend/src/novelai/api/routers/health.py`.

### PDF export deprecation (M2b, DEBT-007)

* PDF export is deprecated. `PDFExporter` is not registered in the export registry.
* `ExportService.export("pdf", ...)` and `ExportService.export_pdf()` raise `UnsupportedExportFormatError` with a safe deprecation message.
* `OperationsService` catches this and returns `OperationError(400)`. Raw `KeyError` or `NotImplementedError` must not reach API callers.
* Historical manifests with `format: "pdf"` are preserved (manifest service stores format as free-form string). Do not rewrite historical manifests.
* Do not add a PDF renderer or dependency. PDF is reintroduced only after an approved renderer, font policy, security review, and real export tests.

### Multi-process file lock (M2c, DEBT-035)

* `novelai.storage.file_lock.InterProcessFileLock` is the canonical cross-platform locking primitive.
* Uses `O_CREAT | O_EXCL` for atomic lockfile creation (works on Windows and POSIX).
* Windows PID liveness check uses `ctypes.windll.kernel32.OpenProcess`.
* Bounded retries with configurable backoff (`FILE_LOCK_RETRY_COUNT`, `FILE_LOCK_RETRY_DELAY_SECONDS`).
* Stale lock detection reclaims locks from crashed processes.
* Use this for any write/cleanup that must not conflict across processes.

### Scheduler runtime state (M2c, DEBT-036)

* `SchedulerRuntimeState` DB table + `SchedulerRuntimeStateService` is the durable cross-restart store for cooldown, failure, exhausted, heartbeat, and next-eligible state.
* The file-based `scheduler_states.json` (in `storage/traceability.py`) remains as an in-process cache for per-job model state. Both are written on transitions.
* State survives process restarts. Do not rely on in-memory scheduler state alone.
* Canonical identifiers: `job_id`, `source_key`, `provider_key`, `activity_id` in metadata where applicable. No aliases.

### Backup and maintenance scheduling (M2c)

* `BackupManager.apply_retention()` preserves the newest successful backup and `BACKUP_MIN_SUCCESSFUL_TO_KEEP` minimum. Uses `InterProcessFileLock` to prevent concurrent retention runs.
* `MaintenanceService` runs allowlisted cleanup tasks with dry-run support and path safety. Rejects blank, root, project-root, and symlink-escape paths.
* `SchedulerService` uses a lightweight asyncio loop (not APScheduler) to check `scheduled_cron_log` for pending backup/maintenance work.
* `pg_cron` is enabled on the Supabase database with a daily cleanup job for `scheduler_runtime_states` (runs at 03:30 UTC). DB-native cleanup survives container restarts.
* Do not reintroduce APScheduler. The dependency was removed in M2c.

### Docker health check

* `compose.yml` healthcheck uses `python -c "import urllib.request; ..."` because the image does not include `curl` by default.
* `admin.Dockerfile` and `reader.Dockerfile` now install `curl` for future use, but the healthcheck still uses `python -c` for portability.

---

## Frontend Conventions

* Use `@tanstack/react-query` for server state.
* Use `zustand` for client-only state.
* Do not introduce Redux.
* Use Tailwind CSS for styling.
* Use `clsx` and `tailwind-merge` through `frontend/lib/utils.ts` and its `cn()` helper.
* Do not introduce CSS modules or styled-components.
* Put business and data-flow logic in hooks rather than components.
* Shared components belong in `frontend/components/`.
* Route-local components belong under their route in `frontend/app/`.
* Mask credentials through `frontend/lib/mask-token.ts`.
* Never render raw API keys, access tokens, secrets, or complete credential values.

---

## Exploration and Search Policy

Use the `explore` subagent for broad repository discovery. Keep the primary agent’s context focused on decisions, implementation, debugging, and verification.

### Delegate to `explore` when

Delegate when one or more of these apply:

* Relevant files or entry points are unknown.
* The task requires architecture mapping.
* The task requires cross-layer or cross-subsystem tracing.
* The request asks for a thorough repository inventory.
* The task requires impact analysis across many files.
* The request asks to locate implementations, tests, migrations, registrations, configuration, storage, lifecycle, or dependency wiring.
* The investigation would require repeated broad searches or many file reads.
* The task explicitly asks to explore the codebase thoroughly.

### Keep exploration in the primary agent when

The primary agent may directly use Read, Grep, Glob, List, LSP, and targeted `rg` for:

* reading a named target file;
* reading files immediately before editing them;
* verifying an exploration report;
* finding usages of a known symbol;
* inspecting directly affected callers;
* reading two neighboring implementations;
* locating focused tests;
* examining a known error path;
* reviewing changed files;
* running architecture guards;
* confirming that a change is complete.

Do not delegate a small localized task when the target files are already known.

### Exploration sequence

For broad exploration:

1. If `graphify-out/graph.json` exists, use Graphify for initial orientation.
2. Use `git ls-files` as the default inventory of tracked project files.
3. Use `rg --files` only when untracked files may matter.
4. Use focused `rg -n` queries to locate exact symbols and relationships.
5. Read the directly relevant implementations and tests.
6. Verify Graphify relationships against the actual source.
7. Produce an evidence-based report.

Graphify is an orientation tool, not authoritative proof.

### Default exploration exclusions

Ignore these unless the task specifically concerns them:

* `.agents/kiro/specs/`
* `.hypothesis/`
* `.opencode/`
* `.venv/`
* `node_modules/`
* frontend build output
* generated coverage output
* runtime storage
* downloaded novel content
* logs
* backups
* caches
* generated Graphify output
* lockfiles, except for dependency or supply-chain tasks

Do not use:

* recursive `tree /F` over the repository;
* unrestricted filesystem walks;
* broad reads of every document;
* recursive searches through ignored runtime or cache directories.

### Exploration report format

Every broad exploration report must include:

1. Scope searched.
2. Exclusions applied.
3. Relevant files with repository-relative paths.
4. Precise 1-based line numbers or line ranges.
5. Execution, dependency, or data flow.
6. Configuration and registration wiring.
7. Persistence and lifecycle behavior.
8. Existing tests and what behavior they actually verify.
9. Missing implementation or coverage.
10. Conflicts and unresolved uncertainty.
11. A checklist covering every requested item.

Do not present guesses as confirmed findings.

---

## CI Gotchas

* The `backend-tests` job in `.github/workflows/ci.yml` includes PostgreSQL 16 as a service.
* `DATABASE_URL` is scoped to the Alembic step rather than the complete job.
* Unit tests use SQLite in memory.
* Job-level `ENV: test` prevents bootstrap credential hydration against CI PostgreSQL.
* Alembic needs `backend` as its working directory because `script_location` in `backend/alembic.ini` is relative.
* CI dependency installation needs the relevant extras, including:

  * `documents`
  * `gemini`
  * `dev`
  * `test`
  * `s3`
  * `auth`
* YAML folded blocks using `>` join lines with spaces. Do not use shell `\` continuation inside them.
* Known pre-existing failures are excluded by CI. Do not use them to hide newly introduced failures.
* If a pre-existing test failure is NOT excluded by CI, fix it as part of the current work or add it to the CI ignore list with justification.
* When changing CI behavior, compare local commands with the exact workflow commands.

For manual GitHub configuration and CI verification, read:

```text
docs/cicd-manual-setup.md
```

Load that document only for CI, GitHub Actions, package publishing, or deployment tasks.

---

## Testing

* Shared fixtures live in `backend/tests/conftest.py`.
* `TestFixture` provides isolated storage, mock providers, mock sources, and a wired dependency container.
* Database-backed unit tests use SQLite in memory through local `db_session` fixtures.
* Unit tests do not require PostgreSQL unless the test explicitly says otherwise.
* End-to-end fixtures live in `backend/tests/e2e/conftest.py`.
* Scratch fixture root:

  * `backend/tests/.tmp/fixtures`
* Scratch runtime root:

  * `backend/tests/.tmp/runtime`
* Both scratch roots are gitignored.
* ORM models are registered through the session-scoped autouse fixture calling `register_database_models()` from `novelai/db/model_registry.py`.
* Do not import individual ORM modules merely for registration side effects.
* Source tests must use offline fixtures.
* Do not access live novel websites in tests.
* Pytest configuration includes:

  * `pythonpath = ["backend/src", "backend"]`
  * `addopts = "-p no:cacheprovider"`
  * marker: `e2e`
* Pyright configuration includes:

  * `pythonPlatform: "Windows"`
  * `typeCheckingMode: "standard"`
* Ruff configuration includes:

  * `target-version = "py313"`
  * `line-length = 120`

### Test selection

For a behavior change:

1. Run the closest focused test file.
2. Add or update tests that directly prove the new behavior.
3. Run type checking for the affected language.
4. Run broader checks only when the change crosses several subsystems.

A one-line change still requires at least one runnable verification command.

Never claim a test passed unless it was actually run successfully.

---

## Dependencies

* `pyproject.toml` is authoritative.
* There is intentionally no `requirements.txt`.
* Standard editable development install:

```powershell
pip install -e ".[dev]"
```

Available extras include:

```text
auth
db
dev
documents
gemini
openai
s3
test
worker
```

Lockfiles:

* `requirements.lock`
* `requirements-dev.lock`
* `uv.lock`

After changing dependencies, regenerate lockfiles through:

```powershell
deploy/update-lockfiles.ps1
```

Do not edit generated lockfiles manually.

Do not add a dependency when the standard library or an existing dependency adequately solves the problem.

---

## Deployment

* `compose.yml` is canonical.
* `compose.dev.yml` overlays development configuration.
* Migrations run as the one-shot `migrate` service before backend startup.
* Do not run migrations from inside the long-running backend container.
* Caddy routing:

  * `/api/admin/*` → admin backend on port 8000.
  * `/api/auth/*` → admin backend on port 8000.
  * `/api/novels/*` → admin backend on port 8000.
  * `/novels/*` → admin backend on port 8000.
  * `/api/public/*` → reader backend on port 8001.
  * `/health/*` → admin backend on port 8000 (liveness, readiness, admin health).
  * all remaining routes → frontend on port 3000.
* Local environment file: `.env`
* Compose environment file: `deploy/.env`
* Production environment file: `deploy/.env.production`
* Development overlay: `deploy/compose.dev.yml` (used via `deploy/docker-compose-dev.ps1`).
* `DATABASE_URL` must use the `postgresql+psycopg://` scheme (psycopg v3), not `postgresql://` (which defaults to psycopg2 and is not installed).

Required production settings include:

```text
SESSION_SECRET_KEY
OWNER_BOOTSTRAP_SECRET
PUBLIC_FRONTEND_URL
DATABASE_URL
```

Do not edit deployment secrets or production data unless explicitly requested.

---

## Security

* Never log or return secrets.
* Mask backend credential values using the existing backend masking pattern.
* Mask frontend credential values through `frontend/lib/mask-token.ts`.
* `SESSION_SECRET_KEY` must fail closed when left at its default.
* `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` is required before storing provider API keys in the database.
* `OWNER_BOOTSTRAP_SECRET` is the only owner-seeding mechanism.
* Never expose the owner bootstrap secret through logs, errors, API responses, or UI.
* The application uses a single owner-admin model.
* Public Google OAuth and email/password registration create `role="user"` only.
* Public authentication must never create or promote an owner.
* Cookie-authenticated state-changing endpoints require CSRF protection.
* Do not bypass authorization or CSRF checks to make tests pass.
* Never accept a client-supplied `user_id` as the authenticated identity.
* Derive user identity from the authenticated session.
* API responses must not expose:

  * raw filesystem paths;
  * internal database keys;
  * storage keys;
  * secrets;
  * complete credential values.
* `storage/novel_library` must never be served directly as static files.
* Do not delete raw scraped chapters after translation; they are audit data.
* Production `WEB_CORS_ORIGINS` must be explicit and must not use `*`.
* Do not implement public contribution credentials until the readiness gate in `docs/architecture/architecture.md` section 13 is satisfied.
* Do not read, print, commit, or paste the contents of `.env` or production environment files.

---

## Environment

Canonical environment variable:

```text
ENV
```

Do not introduce `APP_ENV`.

Supported deployment modes:

```text
DEPLOY_MODE=monolith
DEPLOY_MODE=split
```

Split mode requires Redis for shared rate limiting and the distributed job queue.

Rate limiter backends:

```text
WEB_RATE_LIMITER_BACKEND=memory
WEB_RATE_LIMITER_BACKEND=redis
```

Use Redis for multi-instance deployment.

Worker behavior:

```text
JOB_WORKER_ENABLED=true
```

This enables the in-process activity worker.

Email delivery defaults to:

```text
AUTH_EMAIL_DELIVERY_MODE=noop
```

Use SMTP only after the SMTP configuration has been tested.

Storage backends:

```text
STORAGE_BACKEND=filesystem
STORAGE_BACKEND=s3
```

`NOVEL_LIBRARY_DIR` is the local filesystem base path.

---

## Tooling on Windows

* Use PowerShell-compatible commands.
* Chain commands with:

```powershell
first-command; if ($?) { second-command }
```

* Do not use `&&`.
* Run Python tools using:

```powershell
python -m <tool>
```

* Do not assume Python console scripts are available on `PATH`.
* The Unix `grep` executable is not available.
* Use OpenCode’s Grep tool or `rg`.
* Use `edit` for existing files.
* Use `write` only for new files, after confirming they do not already exist.
* Use `git ls-files` rather than filesystem-wide enumeration when tracked files are sufficient.
* Quote paths containing spaces.
* Do not run interactive or TTY-dependent commands unless the interaction is explicitly supported.

---

## GitHub Security Tools

Use this section only for GitGuardian or CodeQL tasks.

### GitGuardian

* `generic_password_yaml` may flag YAML property names containing `password`, such as `POSTGRES_PASSWORD`.
* Verify the finding before treating it as a secret.
* GitGuardian API token prefix: `gg_pat_`.
* API base:

```text
https://api.gitguardian.com/v1/
```

Relevant endpoints:

```text
GET  /v1/sources/{id}
GET  /v1/incidents/secrets
POST /v1/incidents/secrets/{id}/ignore
POST /v1/incidents/secrets/{id}/resolve
```

Valid dismissal reason values use spaces:

```text
false positive
won't fix
used in tests
```

`.cache_ggshield/` is a local scan cache and must remain gitignored.

Never display a GitGuardian token in command output, logs, documentation, or chat.

### CodeQL

Common findings:

| Rule                                       | Meaning                                                      | Expected handling                                                                                                      |
| ------------------------------------------ | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `py/weak-sensitive-data-hashing`           | Fast hashes may be flagged when applied to sensitive values. | Passwords require bcrypt or Argon2. Verify token, cache, or fingerprint hashing before dismissing as a false positive. |
| `py/clear-text-logging-sensitive-data`     | Logs may expose a sensitive value.                           | Remove the sensitive value from the log.                                                                               |
| `py/incomplete-url-substring-sanitization` | URL validation relies on unsafe substring matching.          | Parse the URL and validate `hostname` using explicit prefix or suffix rules.                                           |

Do not rely solely on suppression comments such as:

```text
# codeql[rule-id]
# lgtm[rule-id]
```

When a verified false positive must be dismissed, use the GitHub API and document the justification.

---

## GitHub CLI on Windows

* PowerShell quoting may break complex `gh --jq` filters.
* Prefer piping JSON to:

  * `ConvertFrom-Json`
  * `Where-Object`
  * `ForEach-Object`
* `gh pr merge --squash` may report a local failure even when GitHub completed the merge.
* Verify merge state with:

```powershell
gh pr view --json state
```

Required scopes may include:

```text
repo
workflow
```

Do not create, merge, close, or modify pull requests unless explicitly requested.

---

## Git History Operations

History rewriting is destructive. Do not perform it without an explicit request.

Important behavior:

* `git filter-repo` removes the `origin` remote.
* Re-add it afterward with:

```powershell
git remote add origin <url>
```

* `git filter-repo --force` may be run again for additional replacements.
* After a force push, all clones must resynchronize:

```powershell
git fetch origin
git reset --hard origin/main
```

* Remove stale Codex checkpoint refs with:

```powershell
git update-ref -d <ref>
```

Only do this for refs under:

```text
refs/codex/turn-diffs/checkpoints/
```

Never rewrite history, force-push, delete branches, or reset working files without explicit authorization.

---

## Documentation and Specifications

* `docs/architecture/architecture.md` is authoritative.
* `docs/DEBT.md` is the single active debt register.
* Update a debt entry in the same change that resolves it.
* `docs/roadmap.md` records roadmap direction.
* Specs under `.agents/` are tracked in Git.
* Do not edit specifications without owner approval.
* Do not treat an archived specification as an active requirement.
* Update documentation when behavior, configuration, contracts, deployment, or operator procedures change.
* Do not create duplicate documentation when an existing canonical document can be updated.

---

## Operating Style

* Make the smallest complete change that solves the requested problem.
* Do not add speculative abstractions.
* Do not add hooks or extension points solely for hypothetical future use.
* Match existing patterns in the same layer.
* Read two neighboring implementations before inventing a third pattern.
* Change behavior completely rather than introducing compatibility shims, duplicate paths, re-exports, or partially migrated callers.
* Update directly affected callers, types, tests, migrations, configuration, and documentation in the same change.
* Do not edit unrelated files.
* Add or update tests for behavior changes.
* Run focused verification commands.
* State clearly when a command could not be run and why.
* Report completed actions, not intended actions.
* Separate verified facts from assumptions and inferences.
* Do not fabricate command output, test results, file contents, line numbers, or repository state.
* Do not commit, push, merge, or open a pull request unless explicitly requested.
* Do not commit:

  * `.env`;
  * secrets;
  * local OpenCode state;
  * runtime storage;
  * logs;
  * backups;
  * caches;
  * generated build artifacts;
  * Graphify output.

---

## Final Report

After implementing or reviewing work, report:

1. Files changed or reviewed.
2. Behavior implemented or findings identified.
3. Verification commands actually run.
4. Results of those commands.
5. Remaining risks, known failures, or unverified assumptions.

Keep the final report proportional to the task. Do not claim completion when required behavior or verification remains unresolved.

## graphify

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships. The `graphify` CLI is always available (v0.9+).

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

**Always run graphify proactively** for codebase questions — don't wait for the user to type `/graphify`. The graph is rebuilt automatically on every `git commit` via a post-commit hook.

Rules:

- For codebase questions, first run `graphify query "<question>"` when `graphify-out/graph.json` exists. Use `graphify path "<A>" "<B>" for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than `GRAPH_REPORT.md` or raw grep output.
- Dirty `graphify-out/` files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If `graphify-out/wiki/index.md` exists, use it for broad navigation instead of raw source browsing.
- Read `graphify-out/GRAPH_REPORT.md` only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- The graph is gitignored — it stays local and is not committed.

---

## Docker

Docker Desktop is available via the bash tool. Use it to inspect and manage the local stack:

```powershell
docker ps                                    # List running containers
docker compose -f deploy/compose.yml up -d   # Start the full stack
docker compose -f deploy/compose.yml logs <service>  # View service logs
docker exec <container> python -c "..."     # Run commands inside a container
```

The backend container's health check uses `python -c "import urllib.request; ..."` (not `curl`) because the image does not include `curl` by default. `admin.Dockerfile` and `reader.Dockerfile` install `curl` for future use.

---

## Supabase MCP

The user has Supabase MCP tools available. Use them for database operations:

- `supabase_apply_migration` — apply DDL migrations directly to the remote database.
- `supabase_execute_sql` — run read-only queries.
- `supabase_get_advisors` — check security and performance lints.
- `supabase_list_tables` — inspect schema.
- `supabase_generate_typescript_types` — generate `database.types.ts` for the frontend.

**Workflow for schema changes:**

1. Create the Alembic migration file under `backend/alembic/versions/` (source of truth).
2. Apply via `supabase_apply_migration` for validation/deployment.
3. Verify with `supabase_execute_sql`.
4. Run `supabase_get_advisors` to check for security/performance issues.
5. Fix advisor issues by applying additional migrations (RLS policies, indexes, etc.).

When applying migrations via MCP, the Alembic migration file must still be created under `backend/alembic/versions/` for version control. The MCP apply is for validation/deployment, not for replacing the migration source of truth.

**Common advisor issues and fixes:**

- `rls_disabled_in_public` — enable RLS + create policies (owner-only, public-read, user-scoped).
- `rls_enabled_no_policy` — add policies for tables with RLS but no access rules.
- `function_search_path_mutable` — recreate functions with `SET search_path = public`.
- `multiple_permissive_policies` — merge owner conditions into single permissive policies using `OR`.
- `unindexed_foreign_keys` — add covering indexes for FK columns.
- `unused_index` — wait for real query activity; these resolve once the app runs against populated tables.

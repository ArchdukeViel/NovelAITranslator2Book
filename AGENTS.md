# AGENTS.md

Compact instruction file for AI coding assistants. Read before touching anything non-trivial.

For architecture, contracts, and security rules: `docs/architecture/architecture.md` (authoritative).
For active debt: `docs/DEBT.md`. For roadmap: `docs/roadmap.md`.

## Verification Commands

Run from repo root. Workflow order: lint → typecheck → test.

| Command | Purpose |
|---|---|
| `python -m ruff check .` | Lint (pre-existing errors exist in unrelated code; don't fix unless in scope) |
| `python -m pyright` | Typecheck (uses `pyrightconfig.json`, covers `backend/src` + `backend/tests`) |
| `python -m pytest backend/tests/test_<name>.py` | Focused test — run one file, not the whole suite (~90 files, slow) |
| `python -m pytest backend/tests/e2e/` | E2e tests (slower, requires fixtures; pre-existing failures ignored in CI) |
| `cd frontend; npm run typecheck` | Frontend typecheck |
| `cd frontend; npm run build` | Frontend build |
| `cd frontend; npm run test` | Frontend tests (vitest) |
| `alembic -c backend/alembic.ini upgrade head` | Migrations (requires `DATABASE_URL`; run from `backend/` dir) |

Router layer guard (must return no matches):
```
rg -n "^from novelai\.(db\.models|storage\.service|sources\.)" backend/src/novelai/api/routers/ --glob "!dependencies.py"
```

## Structure

- **Backend:** `backend/src/novelai/` (FastAPI + SQLAlchemy). Package root is `backend/src`.
- **Frontend:** `frontend/` (Next.js 15 App Router). Independent package.
- **Deploy:** `deploy/` — Docker Compose (`compose.yml`), three Dockerfiles (`admin.Dockerfile` port 8000, `reader.Dockerfile` port 8001, `frontend.Dockerfile`), Caddy reverse proxy.

### Backend entry points

- `novelai.api.app:app` — monolith (default).
- `novelai.main_admin:app` — admin-only (port 8000, session + CSRF).
- `novelai.main_reader:app` — public reader (port 8001, no session).
- `DEPLOY_MODE=split` runs both via multiprocessing.
- CLI: `novelaibook` (installed via `pip install -e .`). Subcommands: `web`, `worker`, `doctor`, `create-user`, `adminweb`, `publicweb`.

### Frontend route groups

- `frontend/app/(admin)/admin/*` — owner UI.
- `frontend/app/(public)/*` — guest + authenticated user UI. Don't cross the boundary.
- API calls only through `frontend/lib/api.ts` (admin) or `frontend/lib/public-api.ts` (public). No direct `fetch()` in components.

## Layer Rules

Dependency direction: `api → services → domain modules → storage/db/providers/sources/export`.

- API routers stay thin. Use-case logic in `services/` or `services/orchestration/`.
- Source parsing in `sources/*`. HTTP fetching/SSRF in `infrastructure/http/*`. Provider API in `providers/*`. Prompts in `prompts/*`. Persistence behind `storage/*` and `db/*`.
- Routers must not import `db.models.*`, `storage.service.*`, or `sources.*` directly — extract to `services/`. Exception: `dependencies.py` (DI factories). CI enforces this via grep.
- Scheduler policy in backend translation/service/job layers, not React.

## Canonical Names

Use these. Don't invent aliases. If you find legacy aliases (`id`, `source`, `provider`, `model`, `slug`) in code you're touching, rename to canonical and update all callers in the same change.

`source_key`, `source_novel_id`, `source_url`, `novel_id`, `chapter_id`, `paragraph_id`, `chunk_id`, `bundle_id`, `provider_key`, `provider_model`, `activity_id`, `job_id`, `request_id`, `credential_id`, `requesting_user_id`, `credential_owner_user_id`, `prompt_version`, `glossary_hash`.

## Backend Conventions

- SQLAlchemy models only. No raw SQL.
- Settings from `novelai.config.settings.settings` (pydantic-settings). Don't read `os.environ` outside that module.
- Logging: `novelai.logging_config.configure_logging()` at startup. Don't scatter `basicConfig`.
- Migrations: new schema → new file under `backend/alembic/versions/`. Never edit a committed migration.
- Async I/O: `httpx` for outbound HTTP, `asyncio.Semaphore` for bounded concurrency, `asyncio.gather(..., return_exceptions=True)` for fan-out.
- All API inputs through Pydantic models. No raw dicts.

## Frontend Conventions

- State: `@tanstack/react-query` for server, `zustand` for client. No Redux.
- Styling: Tailwind + `clsx` + `tailwind-merge` (via `lib/utils.ts` `cn()`). No CSS modules or styled-components.
- Business logic in hooks, not components. Shared: `frontend/components/`, route-local: `frontend/app/`.
- Token display: `lib/mask-token.ts` for any credential. Never render raw API keys.

### CI Gotchas

- `ci.yml` `backend-tests` job has `services.postgres` (postgres:16). `DATABASE_URL` is scoped to the **alembic step only** (not job-level) — unit tests use SQLite in-memory.
- `ENV: test` at job level prevents bootstrap credential hydration against CI Postgres.
- Alembic needs `working-directory: backend` because `script_location` in `alembic.ini` is relative.
- `pip install` extras needed for CI: `documents,gemini,dev,test,s3,auth`.
- YAML `>` joins lines with spaces — don't use `\` continuation.
- ~40 pre-existing test failures exist — ignored in CI via `--ignore` flags in the pytest command.

## Testing

- Fixtures in `backend/tests/conftest.py`. `TestFixture` class provides isolated storage, mock providers, mock sources, wired `Container`.
- DB-backed tests use SQLite in-memory (`sqlite:///:memory:`) via local `db_session` fixtures — no Postgres required for unit tests. E2e fixtures in `backend/tests/e2e/conftest.py`.
- `TESTS_TMP_ROOT` (`backend/tests/.tmp/fixtures`) and `TESTS_RUNTIME_ROOT` (`backend/tests/.tmp/runtime`) are scratch roots; both gitignored.
- ORM models registered via session-scoped autouse fixture calling `register_database_models()` from `novelai/db/model_registry.py`. Tests don't import individual model modules for side effects.
- Source tests use offline fixtures only — no live HTTP.
- pytest config: `pythonpath = ["backend/src", "backend"]`, `addopts = "-p no:cacheprovider"`, markers: `e2e`.
- pyright: `pythonPlatform: "Windows"`, `typeCheckingMode: "standard"`.
- ruff: `target-version = "py313"`, `line-length = 120`.

## GitHub Security Tools

### GitGuardian

- `generic_password_yaml` detector triggers on YAML field names containing "password" (e.g. `POSTGRES_PASSWORD`) — false positive. Ignore via API.
- API token format: `gg_pat_...`, base URL `https://api.gitguardian.com/v1/`.
- Endpoints: `GET /v1/sources/{id}`, `GET /v1/incidents/secrets`, `POST /v1/incidents/secrets/{id}/ignore`, `POST /v1/incidents/secrets/{id}/resolve`.
- Dismissal reason values (with spaces, not underscores): `"false positive"`, `"won't fix"`, `"used in tests"`.
- `.cache_ggshield/` is GitGuardian's local scan cache — gitignored.

### CodeQL Code Scanning

| Rule | What flags | Fix |
|---|---|---|
| `py/weak-sensitive-data-hashing` | ALL fast hashes (sha256, blake2b, HMAC) on sensitive data | Only bcrypt/argon2 counts for passwords. For token/fingerprint/cache hashing, dismiss as false positive via API. |
| `py/clear-text-logging-sensitive-data` | `logger.warning("...%r...", value)` with sensitive values | Remove the value from the log message |
| `py/incomplete-url-substring-sanitization` | `"domain" in url` substring checks | Use `urlparse(url).hostname` with `endswith`/`startswith` |

- Suppression comments (`# codeql[rule-id]`, `# lgtm[rule-id]`) don't always work — API dismissal is more reliable.
- Dismissal via `PATCH /code-scanning/alerts/{number}` with `-f state=dismissed -f dismissed_reason="false positive"`.
- `gh api` with complex jq on Windows can fail — use `ConvertFrom-Json` + `Where-Object` instead.

## Dependencies

- `pyproject.toml` is authoritative. No `requirements.txt` by design.
- Install: `pip install -e ".[dev]"` (or combine extras: `auth`, `db`, `dev`, `documents`, `gemini`, `openai`, `s3`, `test`, `worker`).
- Lockfiles: `requirements.lock`, `requirements-dev.lock`, `uv.lock`. Regenerate with `deploy/update-lockfiles.ps1` after dependency changes. Don't edit by hand.

## Deploy

- `compose.yml` is canonical; `compose.dev.yml` overlays dev settings.
- Migrations run as one-shot `migrate` service before backend starts. Don't run migrations from inside the backend container.
- Caddy routes: `/api/admin/*` and `/api/auth/*` → backend:8000, `/api/public/*` → reader:8001, catch-all → frontend:3000.
- Env files: `.env` (local dev), `deploy/.env` (Compose), `deploy/.env.production`. Required in prod: `SESSION_SECRET_KEY`, `OWNER_BOOTSTRAP_SECRET`, `PUBLIC_FRONTEND_URL`, `DATABASE_URL`.

## Security

- Never log/return secrets. Use `lib/mask-token.ts` (frontend) or equivalent backend masking.
- `SESSION_SECRET_KEY` fails closed at default. `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` required before storing provider API keys in DB.
- `OWNER_BOOTSTRAP_SECRET` is the only owner seed mechanism. Don't expose in logs/errors/responses.
- Single owner-admin model. Public auth (Google OAuth + email/password) creates `role="user"` only. Never creates/promotes owner.
- CSRF required for cookie-auth state-changing endpoints. Don't bypass in tests.
- Never accept client-supplied `user_id` — derive from session.
- API responses must not include raw filesystem paths, internal DB keys, or storage keys.
- `storage/novel_library` never served as static files. Raw scraped chapters not deleted after translation (audit data).
- `WEB_CORS_ORIGINS` must be explicit in production (no `*`).
- Don't implement public contribution credentials until architecture.md §13 readiness gate is met.

## Environment

- Canonical env var is `ENV` (not `APP_ENV`).
- `DEPLOY_MODE=monolith|split` — split requires Redis for rate limiting and job queue.
- `WEB_RATE_LIMITER_BACKEND=memory|redis` — use `redis` for multi-instance.
- `JOB_WORKER_ENABLED=true` runs in-process activity worker.
- `AUTH_EMAIL_DELIVERY_MODE=noop` by default. Set to `smtp` only after SMTP vars tested.
- `STORAGE_BACKEND=filesystem|s3`. `NOVEL_LIBRARY_DIR` is the local base path.

## Tooling (Windows)

- Use PowerShell cmdlets. Chain with `; if ($?) { next }` — not `&&`.
- Use `python -m <tool>` — don't assume `<tool>` is in PATH.
- `grep` not available on Windows. Use `rg` (ripgrep) or the Grep tool.
- Use `edit` to modify existing files. Use `write` only for new files (verify non-existence first).

### gh CLI on Windows

- Complex `--jq` filters with `select()`, `+` concatenation, or pipes may fail due to PowerShell quoting.
- Workaround: pipe to `ConvertFrom-Json` + `Where-Object` instead of using `--jq`.
- `gh pr merge --squash` can fail locally but succeed on GitHub — verify with `gh pr view --json state`.
- Scopes needed: `repo`, `workflow`.

### Git History

- `git filter-repo` removes the `origin` remote — re-add with `git remote add origin <url>` before force push.
- `git filter-repo --force` can run multiple times for additional replacements.
- After force push, all clones must re-sync: `git fetch origin; git reset --hard origin/main`.
- Clean up `refs/codex/turn-diffs/checkpoints/` refs with `git update-ref -d <ref>` after filter-repo.

## Docs and Specs

- `docs/architecture/architecture.md` is authoritative. If another doc disagrees, architecture wins — report the conflict before implementing.
- `docs/DEBT.md` is the single debt register. Update it in the same change that resolves a debt item.
- Spec files under `.agents/` are tracked in git. Don't edit without owner sign-off.
- `.opencode/` is gitignored agent scratch. `.agents/` is tracked specs.

## Operating Style

- Smallest diff that works. No speculative abstractions, no "for-the-future" hooks.
- Match existing patterns in the same layer. Read two neighbors before inventing a third.
- Change things whole — no backward-compat shims, re-exports, or dual code paths. Update all callers, types, tests, docs in the same change.
- Add/update tests for behavior changes. One runnable check is enough for a one-liner.
- Run verification commands. If you can't, say why.
- Report what you actually did, not what you intended. Distinguish verified facts from assumptions.
- Don't commit/push unless explicitly asked. Don't commit `.env`, secrets, build artifacts, or scratch output.

# Novel AI

Novel AI is a web-first Japanese novel platform for crawling source sites, queueing translation jobs, editing translated chapters, exporting books, and serving a public reader UI.

The project is now oriented toward a production-style web deployment, similar in shape to a WTR-Lab style site: a Next.js frontend for public/admin pages, a FastAPI backend under `/api`, PostgreSQL-backed metadata, file/object-backed chapter content, and Redis/RQ background workers for crawler/translation activity.

Current mode is single-owner / controlled-admin transitioning to a public platform. The project has 41 completed specs in `.agents/kiro/archive/` (37 fully complete, 3 partial, 1 not started) covering:
- Scheduler-enabled admin-owned provider/model routing
- PostgreSQL 16 with SQLAlchemy 2.x + Alembic migrations (metadata, users, jobs)
- Redis 7 + RQ background workers
- Guest/user/owner authentication (backend-enforced)
- Public reader routes and user library/progress/ratings/requests
- Baseline owner/admin security hardening
- Glossary diagnostics, export manifests, public annotations, env consolidation
- Legacy compatibility aliases (`source`, `provider`, `model`) fully removed from API contracts

Not implemented: public contribution credentials (later gated phase), batch mode, billing, organizations, multi-admin teams.

## Features

- Crawl supported Japanese web novel sources such as Syosetu, Novel18, Kakuyomu, and generic HTML pages.
- Import text, EPUB, PDF, image folders, and CBZ documents through backend adapters.
- Queue crawl and translation jobs from the web admin UI.
- Translate chapters with Gemini, OpenAI, or the dummy provider for local testing.
- Route translation chunks through the backend scheduler with provider/model cooldown and quota state.
- Review machine translations, save manual edits, switch active versions, and roll back chapter versions.
- Track source health, activity/job status, scheduler model state, translation usage, glossary state, OCR review state, and export readiness.
- Export translated or source text as EPUB, HTML, or Markdown with manifest validation.
- Serve public reader routes and admin routes from the Next.js frontend.
- Glossary diagnostics: readiness, coverage, and drift detection via `/api/admin/glossary/diagnostics`.
- Public reader annotations: per-user highlights and notes persisted via `/api/user/annotations`.

## Project Layout

```text
backend/   FastAPI backend package and backend tests
frontend/  Next.js public reader and admin UI
storage/   Local runtime data, ignored by git
deploy/    Production-style Docker Compose, Caddy, and env examples
docs/      Guides, architecture, and storage/API references
```

Python project metadata stays at the repository root so `pip install -e .`, `pytest`, and `pyright` can run from the root workspace.

## Prerequisites

- Python 3.13 or newer
- Node.js LTS with npm
- Git
- Docker Desktop (required for PostgreSQL + Redis via compose)
- Gemini or OpenAI API key for real translation

## Local Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[documents,openai,gemini,dev,db,worker]"

cd frontend
npm install
```

Create local backend config:

```powershell
cd "C:\Akmal\Novel AI"
Copy-Item .env.example .env
```

Start PostgreSQL and Redis via Docker:

```powershell
docker compose -f deploy/compose.yml up -d postgres redis
```

Run database migrations:

```powershell
.\.venv\Scripts\alembic -c backend/alembic.ini upgrade head
```

Common `.env` values:

```env
NOVEL_LIBRARY_DIR=storage/novel_library
PROVIDER_DEFAULT=gemini
PROVIDER_GEMINI_API_KEY=your_key_here
PROVIDER_OPENAI_API_KEY=your_key_here
TRANSLATION_TARGET_LANGUAGE=English
WEB_RATE_LIMITER_BACKEND=memory
DATABASE_URL=postgresql+psycopg://novelai:novelai@localhost:5432/novelai
REDIS_URL=redis://localhost:6379/0
```

## Run Locally

Terminal 1, backend:

```powershell
cd "C:\Akmal\Novel AI"
novelaibook web --reload
```

Terminal 2, frontend:

```powershell
cd "C:\Akmal\Novel AI\frontend"
npm run dev
```

Optional worker:

```powershell
cd "C:\Akmal\Novel AI"
novelaibook worker
```

Open the web app:

```text
http://127.0.0.1:3000/admin
```

Backend health:

```text
http://127.0.0.1:8000/api/health
```

## Main Web Workflow

1. Configure API token state in `/admin/settings`.
2. Queue crawls or imports in `/admin/crawler`.
3. Inspect source health from `/admin/dashboard` or `/admin/crawler`.
4. Queue translations and exports in `/admin/translation`.
5. Monitor crawler/translation activity in `/admin/activity` and `/admin/activity/[activityId]`.
6. Review and edit chapter versions in `/admin/editor`.
7. Read public chapters under `/novel/[slug]`.

## Quick Start with Docker

The fastest way to run the full stack (PostgreSQL, Redis, backend, frontend, Caddy):

```powershell
# 1. Create env file from example
Copy-Item deploy\.env.example deploy\.env

# 2. Edit deploy\.env — set at minimum:
#    SESSION_SECRET_KEY, OWNER_BOOTSTRAP_SECRET, PUBLIC_FRONTEND_URL
notepad deploy\.env

# 3. Build and start all services
docker compose -f deploy\compose.yml up --build -d

# 4. Run database migrations
docker compose -f deploy\compose.yml run --rm migrate

# 5. Open the app and log in
start http://localhost/admin
```

Compose reads `deploy/.env` automatically. The `migrate` service runs Alembic then exits.

**First login**: use the value of `OWNER_BOOTSTRAP_SECRET` from `deploy/.env` as the secret on the login page. This creates an owner session without needing a registration.

To stop:

```powershell
docker compose -f deploy\compose.yml down
```

To rebuild after changes:

```powershell
docker compose -f deploy\compose.yml up --build -d
```

## Production-Style Run

The production layout is in `deploy/`.

```powershell
Copy-Item deploy\.env.production.example deploy\.env.production
notepad deploy\.env.production
docker compose --env-file deploy\.env.production -f deploy\compose.yml up --build
```

Open:

```text
http://127.0.0.1:8080/admin
```

The reverse proxy routes:

```text
/api/* -> FastAPI backend
/*     -> Next.js frontend
```

Runtime data is mounted from `storage/novel_library`.

## Verification

Backend:

```powershell
pytest --tb=short -q
pyright
```

Database migrations:

```powershell
.\.venv\Scripts\alembic -c backend/alembic.ini current
.\.venv\Scripts\alembic -c backend/alembic.ini upgrade head
```

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Documentation

- [AGENTS.md](AGENTS.md): agent-neutral onboarding and operating rules for AI assistants
- [docs/glossary/glossary-system.md](docs/glossary/glossary-system.md): current glossary system — file-glossary, DB glossary, and sync bridge
- [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md): comprehensive setup, workflow, and troubleshooting guide
- [docs/architecture/architecture.md](docs/architecture/architecture.md): canonical architecture, current status, runtime flow, blocked phases, debt register, and roadmap
- [docs/architecture/public-auth-contract.md](docs/architecture/public-auth-contract.md): public auth and user data contract design
- [docs/reference/data-output-structure.md](docs/reference/data-output-structure.md): storage and output layout
- [docs/reference/python-commands.md](docs/reference/python-commands.md): backend launcher and Python API reference
- [docs/environment.md](docs/environment.md): environment variables reference (single `.env` at repo root, `deploy/.env` for Docker)
- [docs/cicd-manual-setup.md](docs/cicd-manual-setup.md): CI/CD pipeline setup guide (GitHub Actions)
- [docs/current_state.md](docs/current_state.md): implementation status snapshot and test baseline
- [SPECS_COMPLETION.md](SPECS_COMPLETION.md): all 14 specs completion summary

# Novel AI

Novel AI is a web-first Japanese novel platform for crawling source sites, queueing translation jobs, editing translated chapters, exporting books, and serving a public reader UI.

The project is now oriented toward a production-style web deployment, similar in shape to a WTR-Lab style site: a Next.js frontend for public/admin pages, a FastAPI backend under `/api`, durable local file-backed storage, and a worker process for crawler/translation activity.

Current mode is single-owner / controlled-admin. The project has scheduler-enabled admin-owned provider/model routing and baseline owner/admin security hardening, but it does not have public user auth, public contribution credentials, database storage, batch mode, billing, organizations, or multi-admin teams.

## Features

- Crawl supported Japanese web novel sources such as Syosetu, Novel18, Kakuyomu, and generic HTML pages.
- Import text, EPUB, PDF, image folders, and CBZ documents through backend adapters.
- Queue crawl and translation jobs from the web admin UI.
- Translate chapters with Gemini, OpenAI, or the dummy provider for local testing.
- Route translation chunks through the backend scheduler with provider/model cooldown and quota state.
- Review machine translations, save manual edits, switch active versions, and roll back chapter versions.
- Track source health, activity/job status, scheduler model state, translation usage, glossary state, OCR review state, and export readiness.
- Export translated or source text as EPUB, HTML, or Markdown.
- Serve public reader routes and admin routes from the Next.js frontend.

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
- Docker Desktop, only for production-like local deployment
- Gemini or OpenAI API key for real translation

## Local Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[documents,openai,gemini,dev]"

cd frontend
npm install
```

Create local backend config:

```powershell
cd "C:\Akmal\Novel AI"
Copy-Item .env.example .env
```

Common `.env` values:

```env
NOVEL_LIBRARY_DIR=storage/novel_library
PROVIDER_DEFAULT=gemini
PROVIDER_GEMINI_API_KEY=your_key_here
PROVIDER_OPENAI_API_KEY=your_key_here
TRANSLATION_TARGET_LANGUAGE=English
WEB_RATE_LIMITER_BACKEND=memory
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

Frontend:

```powershell
cd frontend
npm run typecheck
npm run build
```

## Documentation

- [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md): comprehensive setup, workflow, and troubleshooting guide
- [docs/architecture/architecture.md](docs/architecture/architecture.md): canonical architecture, current status, runtime flow, blocked phases, debt register, and roadmap
- [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md): storage and output layout
- [docs/reference/PYTHON_COMMANDS.md](docs/reference/PYTHON_COMMANDS.md): backend launcher and Python API reference

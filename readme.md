# Novel AI

Web-first Japanese novel ingestion, translation, editing, and public reader.
FastAPI owns APIs and jobs; Next.js owns public/admin UI; PostgreSQL owns
relational state; filesystem or S3/R2 owns chapter content.

## Project Status

Repository implementation is locally mature, but production launch remains
**NO-GO**. Hosted security, monitoring, real alert delivery, current restore
evidence, manual browser/network acceptance, rollback rehearsal, and named
operators remain unresolved. [`docs/WORK.md`](docs/WORK.md) is the only current
unfinished-work register; local tests or free previews do not replace hosted
acceptance evidence.

## Features

- Crawl Syosetu, Novel18, Kakuyomu, and generic HTML sources.
- Import text, EPUB, PDF, image folders, and CBZ source documents.
- Queue and monitor crawl/translation jobs.
- Translate through Gemini with durable scheduler state and bounded concurrency.
- Review, edit, activate, and roll back chapter translation versions.
- Manage glossary, users, requests, takedowns, credentials, health, and audit.
- Inspect owner-only maintenance schedules, durable results, and next eligibility.
- Serve guest catalog/reader plus authenticated library, progress, history,
  reviews, and requests.

Translated-novel file downloads are not part of product scope. EPUB/PDF imports
and recovery backups remain supported.

## Requirements

- Python 3.13+
- Node.js LTS and npm
- PostgreSQL 17 or compatible managed PostgreSQL
- Gemini API key for real translation
- Docker Desktop when using Redis/Compose

## Install

```powershell
py -3.13 -m venv .venv
& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -e ".[documents,gemini,dev,db,worker,s3,auth]"
npm install --prefix frontend
Copy-Item ".env.example" ".env"
```

Minimum local `.env`:

```dotenv
ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/novelai
SESSION_SECRET_KEY=<random>
OWNER_BOOTSTRAP_SECRET=<random>
PROVIDER_DEFAULT=gemini
PROVIDER_GEMINI_API_KEY=<key>
AUTH_EMAIL_DELIVERY_MODE=noop
```

Never commit real secrets. Full configuration contract: [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

## Database

From repository root:

```powershell
Set-Location "backend"
& "..\.venv\Scripts\python.exe" -m alembic -c alembic.ini upgrade head
```

`DATABASE_URL` must use `postgresql+psycopg://`. Compose does not provision the
primary application database.

## Run Locally

Backend:

```powershell
& ".venv\Scripts\novelaibook.exe" web --reload
```

Frontend:

```powershell
npm run dev --prefix frontend
```

Optional standalone worker:

```powershell
& ".venv\Scripts\novelaibook.exe" worker
```

Open <http://127.0.0.1:3000/admin>. Health endpoints:

```text
http://127.0.0.1:8000/health/live
http://127.0.0.1:8000/health/ready
```

## Docker

```powershell
Copy-Item "deploy\.env.example" "deploy\.env"
# Set DATABASE_URL, SESSION_SECRET_KEY, OWNER_BOOTSTRAP_SECRET, PUBLIC_FRONTEND_URL
docker compose -f "deploy\compose.yml" up --build -d
```

Compose runs migrations before backend startup. Stop with:

```powershell
docker compose -f "deploy\compose.yml" down
```

Topology and release procedure: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Main Workflow

1. Configure provider credentials in admin settings.
2. Crawl a source or import a source document.
3. Review source health and chapter ingestion.
4. Queue translation and monitor activity.
5. Review/edit versions and publish content.
6. Read public chapters under `/novels/*`.

Owner maintenance status is available at `/admin/maintenance`. Missing public
covers fall back to generated bookplates; chapter and library text do not depend
on optional cover assets.

## Commands

```powershell
# Backend lint and types
& ".venv\Scripts\python.exe" -m ruff check .
& ".venv\Scripts\python.exe" -m pyright

# Focused backend test
& ".venv\Scripts\python.exe" -m pytest "backend/tests/test_<name>.py"

# Frontend
npm run typecheck --prefix frontend
npm run lint --prefix frontend
npm run test --prefix frontend
npm run build --prefix frontend

# CLI
& ".venv\Scripts\novelaibook.exe" doctor
& ".venv\Scripts\novelaibook.exe" create-user
& ".venv\Scripts\novelaibook.exe" adminweb
& ".venv\Scripts\novelaibook.exe" publicweb
```

Use smallest focused test set proving changed behavior. Backend complete suite has
known unrelated cost; do not substitute broad checks for focused evidence.

## Project Layout

```text
backend/       FastAPI package, migrations, and tests
frontend/      Next.js public/admin package
deploy/        Compose, Caddy, Dockerfiles, scripts, env examples
storage/       Local runtime data; ignored by Git
docs/          Nine canonical project documents
.agents/kiro/  Active approved specifications only
```

## Documentation

- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): system boundaries and non-negotiable contracts
- [`DESIGN.md`](docs/DESIGN.md): frontend UX, accessibility, SEO, and budgets
- [`WORK.md`](docs/WORK.md): only unfinished/deferred/operator work
- [`OPERATIONS.md`](docs/OPERATIONS.md): health, backup, restore, incident, rollback
- [`DEPLOYMENT.md`](docs/DEPLOYMENT.md): topology, release, providers, GitHub controls
- [`CONFIGURATION.md`](docs/CONFIGURATION.md): environment and settings groups
- [`STORAGE.md`](docs/STORAGE.md): ownership, artifacts, schemas, restore order
- [`TRANSLATION.md`](docs/TRANSLATION.md): prompt, glossary, QA, cache contracts
- [`HISTORY.md`](docs/HISTORY.md): concise completed/cancelled spec history

AI-assistant operating rules: [`AGENTS.md`](AGENTS.md).

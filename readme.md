# Novel AI

Web-first Japanese novel ingestion, translation, editing, and public reader.
FastAPI owns APIs and jobs; Next.js owns public/admin UI; PostgreSQL owns
relational state and exact artifact references; Cloudflare R2 owns immutable
novel content and independent recovery objects.

## Project Status

Repository implementation is locally mature, but production launch remains
**NO-GO**. Hosted security, monitoring, real alert delivery, current restore
evidence, manual browser/network acceptance, rollback rehearsal, and named
operators remain unresolved. [`docs/STATUS.md`](docs/STATUS.md) is the only current
unfinished-work register; local tests or free previews do not replace hosted
acceptance evidence.

## Features

- Crawl Syosetu, Novel18, Kakuyomu, and generic HTML sources.
- Import novels from supported source URLs.
- Queue and monitor crawl/translation jobs.
- Translate through Gemini with durable scheduler state and bounded concurrency.
- Review, edit, activate, and roll back chapter translation versions.
- Manage glossary, users, requests, takedowns, credentials, health, and audit.
- Inspect owner-only maintenance schedules, durable results, and next eligibility.
- Serve guest catalog/reader plus authenticated library, progress, history,
  reviews, and requests.

Translated-novel file downloads and local document imports are not part of
product scope. Recovery backups remain supported.

## Requirements

- Python 3.14+
- Node.js 26.8.1 and npm for local, CI, and Docker development
- PostgreSQL 17+ or compatible managed PostgreSQL
- Gemini API key for real translation
- Docker Desktop when using Redis/Compose

## Install

```powershell
uv venv .venv --python 3.14.7
uv sync --locked --extra gemini --extra dev --extra db --extra worker --extra auth
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
Pushes and same-repository pull requests run pinned GitGuardian secret scanning;
fork pull requests are skipped because repository secrets are never exposed to
untrusted fork code. GitHub setup lives in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Database

From repository root:

```powershell
Set-Location "backend"
& "..\.venv\Scripts\python.exe" -m alembic -c alembic.ini upgrade head
```

`DATABASE_URL` must use `postgresql+psycopg://`. Compose provisions co-located
native PostgreSQL 17 (`postgres:17.4-alpine`) via the `db` service or connects to external PostgreSQL.

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
2. Crawl a source URL or import a novel from a source URL.
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
tools/ruff.ps1 check .
tools/pyright.ps1

# Focused backend test
tools/pytest.ps1 "backend/tests/test_<name>.py"

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
data/          Disposable local runtime data; `data/runtime/` is ignored by Git
docs/          Nine canonical project documents
.agents/specs/ Active approved specifications only
```

## Documentation

- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md): system boundaries and non-negotiable contracts
- [`DESIGN.md`](docs/DESIGN.md): frontend design index and subordinate authority map (`docs/design/`)
- [`STATUS.md`](docs/STATUS.md): only unfinished/deferred/operator work
- [`OPERATIONS.md`](docs/OPERATIONS.md): health, backup, restore, incident, rollback
- [`DEPLOYMENT.md`](docs/DEPLOYMENT.md): topology, release, providers, GitHub controls
- [`CONFIGURATION.md`](docs/CONFIGURATION.md): environment and settings groups
- [`STORAGE.md`](docs/STORAGE.md): ownership, artifacts, schemas, restore order
- [`TRANSLATION.md`](docs/TRANSLATION.md): prompt, glossary, QA, cache contracts
- [`EVIDENCE.md`](docs/EVIDENCE.md): concise completed/cancelled spec history

AI-assistant operating rules: [`AGENTS.md`](AGENTS.md).

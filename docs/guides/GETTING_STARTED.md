# Getting Started with Novel AI

This guide covers the web-first local setup: FastAPI backend, Next.js frontend, and optional background worker.

## Prerequisites

- Python 3.13 or newer
- Node.js LTS with npm
- Git
- A Gemini or OpenAI API key for real translation

## Install Backend

```powershell
git clone <repo-url>
cd "Novel AI"

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[documents,openai,gemini]"
```

For development tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[documents,openai,gemini,dev]"
```

## Install Frontend

```powershell
cd frontend
npm install
```

If PowerShell does not see `npm` after installing Node.js, reopen the terminal or temporarily add it:

```powershell
$env:Path = "C:\Program Files\nodejs;" + $env:Path
```

## Configure

```powershell
Copy-Item .env.example .env
```

Common `.env` values:

```env
PROVIDER_GEMINI_API_KEY=your_key_here
PROVIDER_OPENAI_API_KEY=your_key_here
PROVIDER_DEFAULT=gemini
TRANSLATION_TARGET_LANGUAGE=English
LOG_LEVEL=INFO
WEB_RATE_LIMITER_BACKEND=memory
```

## Run Locally

Backend:

```powershell
cd "C:\Akmal\Novel AI"
novelaibook web --reload
```

Frontend:

```powershell
cd "C:\Akmal\Novel AI\frontend"
npm run dev
```

Open:

```text
http://127.0.0.1:3000/admin
```

Backend health:

```text
http://127.0.0.1:8000/api/health
```

## Worker

Run one pending job:

```powershell
novelaibook worker --once
```

Run continuous worker mode:

```powershell
novelaibook worker
```

For the MVP, the API process can also run the worker when `JOB_WORKER_ENABLED=true`.

## Web Workflow

1. Open `/admin/settings` and configure API token state for the frontend.
2. Use `/admin/crawler` to enqueue metadata or chapter crawl jobs.
3. Use `/admin/translation` to enqueue translation jobs.
4. Use `/admin/editor` to inspect and revise translated chapter versions.
5. Use public `/novel/[slug]` routes for reader pages.

## Next Docs

- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)
- [../architecture/architecture.md](../architecture/architecture.md)
- [../architecture/PRODUCTION_WEB_DEPLOYMENT.md](../architecture/PRODUCTION_WEB_DEPLOYMENT.md)

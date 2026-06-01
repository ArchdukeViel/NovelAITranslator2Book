# Novel AI

Novel AI is a web-based Japanese novel platform for crawling source sites, queueing translation jobs, editing translated chapters, and serving a reader/admin UI.

## What It Does

- Scrape supported web novel sources such as Syosetu, Novel18, Kakuyomu, and generic HTML pages
- Queue crawl and translation jobs through the FastAPI backend
- Translate chapters with provider adapters for Gemini, OpenAI, or dummy local testing
- Review and edit translated chapter versions from the web admin surface
- Export translated or source text as EPUB, HTML, or Markdown
- Serve a Next.js frontend for public reader pages and production-style admin workflows

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[documents,openai,gemini]"
```

Create your config file:

```powershell
Copy-Item .env.example .env
```

Add provider keys in `.env` when you want real translation:

```env
PROVIDER_GEMINI_API_KEY=your_key_here
PROVIDER_OPENAI_API_KEY=your_key_here
```

## Run Locally

Backend:

```powershell
novelaibook web --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:3000/admin
```

The backend API runs at:

```text
http://127.0.0.1:8000/api/health
```

## Worker

Process one queued job:

```powershell
novelaibook worker --once
```

Run a continuous local worker:

```powershell
novelaibook worker
```

## Documentation

- [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md): web-first setup and local development
- [docs/reference/PYTHON_COMMANDS.md](docs/reference/PYTHON_COMMANDS.md): backend launcher and Python API reference
- [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md): storage and output layout
- [docs/architecture/architecture.md](docs/architecture/architecture.md): current web-focused backend/frontend layout
- [docs/architecture/PRODUCTION_WEB_DEPLOYMENT.md](docs/architecture/PRODUCTION_WEB_DEPLOYMENT.md): production deployment direction

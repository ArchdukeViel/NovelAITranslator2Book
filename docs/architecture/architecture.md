# Novel AI Architecture

This document describes the current web-focused architecture, production-style deployment layout, and future roadmap for Novel AI.

## Product Direction

Novel AI is being shaped as a web novel platform:

- Public reader pages for novels and chapters.
- Admin workspace for crawler, translation, jobs, requests, editing, settings, and source health.
- FastAPI backend under `/api`.
- Durable local storage under `storage/novel_library`.
- Optional worker process for background crawler and translation jobs.

The active product direction is the web platform workflow described in this document.

## Root Layout

```text
backend/
  src/novelai/
  tests/
frontend/
storage/
deploy/
docs/
```

Python metadata remains at the repository root so the backend can still be installed and tested from the root workspace:

```powershell
pip install -e ".[documents,openai,gemini,dev]"
pytest
pyright
```

## Frontend Layout

```text
frontend/
  app/
    (admin)/
      admin/
        dashboard/
        crawler/
        source-health/
        translation/
        jobs/
        requests/
        editor/
        settings/
    (public)/
      novel/[slug]/
      novel/[slug]/chapter/[chapterId]/
  components/
    admin/
    ui/
  lib/
    api.ts
    query-client.ts
    store.ts
  server/
```

Frontend responsibilities:

- Render public reader and admin workspace.
- Keep browser UI state such as theme, API token, reader settings, and selected filters.
- Use TanStack Query for API reads and mutations.
- Use Zustand for persistent UI preferences.
- Use `NEXT_PUBLIC_API_BASE_URL=/api` by default.
- Use `BACKEND_API_URL` during local split development so Next.js proxies `/api/*` to FastAPI.

Primary admin routes:

- `/admin/dashboard`: operational home, worker controls, queue snapshot, and recent jobs.
- `/admin/crawler`: crawl queueing, direct scrape, direct import, and source health preview.
- `/admin/source-health`: source adapter health table.
- `/admin/translation`: translation queueing, direct translation, progress, and export download.
- `/admin/jobs`: queue inspection and job actions.
- `/admin/jobs/[jobId]`: job payload, metadata, error, and result details.
- `/admin/requests`: reader/admin request intake.
- `/admin/editor`: chapter source, active translation, versions, manual edits, and rollback.
- `/admin/settings`: API token state, dummy API mode, and backend health.

Primary public routes:

- `/novel/[slug]`
- `/novel/[slug]/chapter/[chapterId]`

## Backend Layout

```text
backend/src/novelai/
  api/            FastAPI app, routers, dependencies, auth, and error handlers
  config/         environment settings and workflow profile definitions
  core/           platform records, errors, chapter states, and shared primitives
  cost_estimator/ cost and token heuristics
  export/         EPUB, HTML, Markdown exporters and registry
  glossary/       glossary normalization and status helpers
  inputs/         file/document import adapters
  jobs/           durable queue, worker, and background runner
  prompts/        prompt builders and templates
  providers/      translation provider adapters
  runtime/        bootstrap, CLI launcher, and dependency container
  services/       orchestration shell, export, cache, preferences, requests, usage
  services/orchestration/
                  crawler, importer, glossary, OCR, translation, and export workflows
  sources/        web source scraper adapters
  storage/        file-backed persistence modules and compatibility service
  translation/    translation service and pipeline stages
  utils/          HTTP, logging, retries, rate limiting, chapter selection, and text helpers
```

Backend tests live in:

```text
backend/tests/
```

## Runtime Flow

```text
Browser
  |
  | public/admin pages
  v
Next.js frontend
  |
  | /api/*
  v
FastAPI backend
  |
  | dependencies and runtime container
  v
Services
  |
  | storage, source registry, provider registry, exporter registry, jobs
  v
storage/novel_library
```

The main runtime container wires:

- `StorageService`
- `TranslationService`
- `NovelOrchestrationService`
- `JobQueueService`
- `JobWorkerService`
- `BackgroundJobRunner`
- `PreferencesService`
- `UsageService`
- `NovelRequestService`
- `ExportService`

## Backend Entry Points

```powershell
novelaibook web
novelaibook web --reload
novelaibook worker
novelaibook worker --once
novelaibook doctor
```

`novelaibook web` runs FastAPI. `novelaibook worker` consumes queued crawl and translation jobs. The launcher is a backend runtime tool, not a separate user-facing UI.

## API Structure

The FastAPI app exposes production routes under `/api`.

Important groups:

- `/api/health`: health check.
- `/api/novels/...`: library, crawler, translation, export, editor, and reader-facing data.
- `/api/sources/...`: source and import adapter discovery.
- `/api/jobs/...`: queue list, detail, run, cancel, and source health.
- `/api/requests/...`: reader/admin request intake.
- `/api/admin/...`: dashboard and worker control.

The backend may also keep selected backward-compatible routes where tests or existing clients require them.

Auth:

- `WEB_API_KEY` controls bearer-token protection for admin/backend API calls.
- Empty or unset `WEB_API_KEY` means local no-auth mode.
- Production deployments should set `WEB_API_KEY` and use HTTPS.

## Crawler And Import Flow

Crawler workflow:

```text
Admin UI
  -> create crawl job
  -> JobQueueService stores job
  -> worker executes job
  -> source adapter scrapes metadata or chapters
  -> StorageService writes metadata/chapter bundles
  -> source health is updated
```

Source adapters live in `backend/src/novelai/sources/`. Current source families include Syosetu, Novel18, Kakuyomu, and generic HTML.

Document import workflow:

```text
Admin UI
  -> import command
  -> input adapter loads document units and assets
  -> orchestration importer normalizes metadata and chapters
  -> StorageService writes chapter bundles and image assets
```

Input adapters live in `backend/src/novelai/inputs/`.

## Translation Flow

```text
Admin UI
  -> create translation job
  -> JobQueueService stores job
  -> worker executes job
  -> NovelOrchestrationService validates metadata, glossary, and OCR gates
  -> TranslationService runs pipeline
  -> provider adapter calls Gemini, OpenAI, or dummy provider
  -> StorageService writes translated version and checkpoint
```

Pipeline stages:

```text
Fetch -> Parse -> Segment -> Translate -> Post-process
```

Translation supports:

- provider/model selection
- glossary-aware prompts
- OCR review gating
- translation cache reuse
- usage tracking
- confidence scoring
- low-confidence polish pass
- checkpoint and rollback support

## Editing Flow

Chapter bundles store translation versions in one file. The editor can:

- display source and active translation
- list machine and manual versions
- save manual edits as new versions
- switch the active version
- record edit and rollback history

This keeps editing web-native while preserving machine translation output for comparison.

## Jobs And Worker

Jobs are JSON-backed for the local-first implementation:

```text
storage/novel_library/jobs/queue.json
storage/novel_library/jobs/source_health.json
```

Job types:

- `crawl`
- `translation`

Statuses:

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

Future production hardening can move jobs to Redis/RQ, Celery, Dramatiq, or another durable queue while keeping the API contract stable.

## Storage Model

Default runtime storage:

```text
storage/novel_library/
```

Important artifacts:

- `preferences.json`: user preferences, never provider secrets.
- `translation_cache.json`: provider/model/source-text cache entries.
- `usage.json`: usage and cost tracking.
- `jobs/queue.json`: durable local job records.
- `jobs/source_health.json`: source success/failure counters.
- `requests/novel_requests.json`: request intake.
- `novels/index.json`: novel ID to folder mapping.
- `novels/<novel_id>/metadata.json`: novel metadata and chapter index.
- `novels/<novel_id>/chapters/<chapter_id>.json`: unified source, translation, media, OCR, versions, and edit state.
- `novels/<novel_id>/assets/images/<chapter_id>/`: downloaded/imported image assets.
- `novels/<novel_id>/state/<chapter_id>.json`: chapter state machine data.
- `novels/<novel_id>/checkpoints/`: recovery snapshots.
- `novels/<novel_id>/full_novel.epub`: default export output path for EPUB, with similar names for other formats.

See [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md) for file-level examples.

## Production Deployment

Production-style deployment keeps frontend and backend as separate processes behind one public entrypoint:

```text
https://yourdomain.com/          -> Next.js frontend
https://yourdomain.com/admin     -> Next.js admin workspace
https://yourdomain.com/novel/... -> Next.js public reader
https://yourdomain.com/api/...   -> FastAPI backend
```

Deployment files:

```text
deploy/
  compose.yml
  Caddyfile
  backend.Dockerfile
  frontend.Dockerfile
  .env.production.example
```

Compose services:

- `caddy`: single public entrypoint.
- `frontend`: Next.js standalone production server.
- `backend`: FastAPI API process.
- `worker`: background job process using the backend image.

Production-like local run:

```powershell
Copy-Item deploy\.env.production.example deploy\.env.production
notepad deploy\.env.production
docker compose --env-file deploy\.env.production -f deploy\compose.yml up --build
```

Open:

```text
http://127.0.0.1:8080/admin
```

Reverse proxy behavior:

```text
/api/* -> backend:8000
/*     -> frontend:3000
```

Example Caddy domain shape:

```caddy
wtr-like.example.com {
  encode zstd gzip

  handle /api/* {
    reverse_proxy backend:8000
  }

  handle {
    reverse_proxy frontend:3000
  }
}
```

## Environment Strategy

Backend:

- `.env` for local development.
- `deploy/.env.production` for Compose.
- Provider API keys are environment-backed secrets.
- Preferences are stored on disk but must not store provider secrets.

Frontend:

- `NEXT_PUBLIC_API_BASE_URL=/api` for browser API calls.
- `BACKEND_API_URL=http://127.0.0.1:8000` for local Next.js proxying.
- Admin API token can be stored in browser state and sent as bearer auth.

## Media And OCR Roadmap

The current backend has OCR/media fields and review gating in the storage and orchestration layer. The future web workflow should expose these as first-class admin controls.

Current or planned chapter media fields:

- `ocr_required`
- `ocr_text`
- `ocr_pages`
- `ocr_status`: `pending`, `reviewed`, `skipped`, or `failed`
- `reembed_status`: `pending`, `completed`, `failed`, or `skipped`
- `ocr_artifacts`
- `region_metadata`

Recommended roadmap:

1. Surface OCR-pending chapters in the editor.
2. Add OCR correction and approve/reject controls.
3. Keep translation blocked when OCR is required but not reviewed.
4. Add optional translated text re-embedding as a separate explicit operation.
5. Make exporters prefer re-embedded assets when available.
6. Add diagnostics counters for OCR and re-embedding readiness.

## Verification Strategy

Keep tests focused on active web-platform behavior:

- web API
- storage
- scraper/source adapters
- translation providers and pipeline
- jobs and worker
- request system
- export
- frontend typecheck/build

Legacy non-web and phase-history docs should not drive active tests or documentation.

Useful commands:

```powershell
pytest --tb=short -q
pyright

cd frontend
npm run typecheck
npm run build
```

## Future Hardening

Recommended next production upgrades:

- Move durable JSON state to PostgreSQL when write volume grows.
- Move jobs to Redis/RQ, Celery, Dramatiq, or another queue backend.
- Add real admin auth and role-based access.
- Put images/assets behind object storage and a CDN.
- Add source-specific crawler rate limits and retry budgets.
- Add structured job logs and downloadable run reports.
- Add deployment health checks for frontend, backend, worker, and storage volume.

## Related Docs

- [../guides/GETTING_STARTED.md](../guides/GETTING_STARTED.md)
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)

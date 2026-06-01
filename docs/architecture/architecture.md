# Novel AI Architecture

This document describes the current web-focused codebase layout and runtime flow.

## Codebase Layout

```text
src/novelai/
  runtime/        bootstrap and dependency wiring
  interfaces/     FastAPI web app and small backend launcher
  config/         environment settings and workflow profile definitions
  core/           errors, platform records, and shared state primitives
  cost_estimator/ cost and token heuristics
  export/         exporter implementations and registry
  glossary/       glossary status and helpers
  inputs/         document and file import adapters
  pipeline/       fetch, parse, segment, translate, and post-process stages
  prompts/        prompt builders and templates
  providers/      translation provider adapters
  services/       orchestration, storage, jobs, export, usage, cache, preferences
  sources/        web source scrapers
  utils/          HTTP, logging, retries, rate limiting, chapter selection, and text helpers

frontend/
  app/            Next.js public reader and admin routes
  components/     admin shell and reusable UI components
  lib/            API client, query client, Zustand store, utilities
  server/         frontend runtime environment helpers
```

## Runtime Flow

```text
Next.js frontend
  public reader + admin workspace
        ->
FastAPI backend
  /api health, novels, jobs, requests, reader, translations, export
        ->
Runtime Bootstrap
  provider registry
  source registry
  input adapter registry
  exporter registry
        ->
Container
  storage
  translation pipeline
  export service
  preferences
  usage tracking
  job queue
  orchestration
        ->
NovelOrchestrationService
  import documents
  scrape metadata and chapters
  glossary extraction
  OCR candidate ingestion
  translation and retranslation
  export preparation
        ->
Storage + Export Layer
  novel_library/
```

## Backend Entry Points

- `novelaibook web`: run the FastAPI backend
- `novelaibook web --reload`: run backend with live reload
- `novelaibook worker`: run queued jobs continuously
- `novelaibook worker --once`: process one queued job
- `novelaibook doctor`: check launcher wiring

## Major Subsystems

### Web API

- `interfaces/web/api.py`: FastAPI app factory and lifespan
- `interfaces/web/server.py`: uvicorn launcher
- `interfaces/web/routers/novels.py`: current combined API router
- `interfaces/web/error_handlers.py`: exception-to-HTTP mapping

The combined router is scheduled to be split into focused routers during the next refactor phase.

### Runtime

- `runtime/bootstrap.py`: registers providers, sources, input adapters, and exporters
- `runtime/container.py`: constructs shared service instances

### Import And Scraping

- `inputs/`: normalized import adapters for `web`, `text`, `epub`, `pdf`, `image_folder`, and `cbz`
- `sources/`: scraper adapters for live web novel sites

### Service Layer

- `services/storage_service.py`: file-backed persistence for metadata, chapters, glossary, OCR, exports, and assets
- `services/novel_orchestration_service.py`: end-to-end business workflows
- `services/job_queue_service.py`: durable JSON job queue and source health
- `services/job_worker_service.py`: executes queued crawl and translation jobs
- `services/job_runner_service.py`: background polling loop
- `services/translation_service.py`: pipeline execution
- `services/export_service.py`: exporter dispatch
- `services/preferences_service.py`: workflow and provider preferences
- `services/usage_service.py`: usage and cost recording

### Translation Pipeline

```text
Fetch -> Parse -> Segment -> Translate -> Post-process
```

The pipeline is assembled in `runtime/container.py` and used by the orchestration service.

### Review And Gating

Before translation completes, the system can enforce:

- glossary review state
- OCR review state for chapters that require OCR

This lets translation runs stop on unresolved content rather than silently producing inconsistent output.

## Data Model Overview

Runtime state is stored under `novel_library/` for now.

Important stored artifacts include:

- `metadata.json`: novel-level metadata and chapter/unit index
- `chapters/<id>.json`: unified chapter bundle with source, translation, state, and media metadata
- `glossary.json`: glossary terms and statuses
- `assets/`: source or generated media assets
- `jobs/`: queued background work
- `requests/`: reader/admin request intake

See [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md) for the full file-level layout.

## Next Structural Phase

The next recommended cleanup is:

```text
backend/
  src/novelai/
frontend/
storage/
deploy/
docs/
```

That move should happen after the web-only entrypoint cleanup is stable.

## Related Docs

- [../guides/GETTING_STARTED.md](../guides/GETTING_STARTED.md)
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)
- [PRODUCTION_WEB_DEPLOYMENT.md](PRODUCTION_WEB_DEPLOYMENT.md)

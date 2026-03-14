# Novel AI Architecture

This document describes the current codebase layout and the runtime flow across the import, translation, review, and export layers.

## Codebase Layout

```text
src/novelai/
  runtime/        shared bootstrap and dependency wiring
  interfaces/     CLI, desktop GUI, TUI, and web interface modules
  app/            compatibility wrappers for legacy entrypoints
  desktop/        compatibility wrappers for legacy desktop imports
  tui/            compatibility wrappers for legacy TUI imports
  web/            compatibility wrappers for legacy web imports
  config/         environment settings and workflow profile definitions
  core/           errors and shared state primitives
  cost_estimator/ cost and token heuristics
  export/         exporter implementations and registry
  glossary/       glossary status and helpers
  inputs/         document and file import adapters
  pipeline/       fetch, parse, segment, translate, and post-process stages
  prompts/        prompt builders and templates
  providers/      translation provider adapters
  services/       orchestration, storage, export, usage, cache, preferences
  sources/        web source scrapers
  utils/          logging, retries, chapter selection, and helpers
```

## Interface Split

The project now separates runtime wiring from interface delivery:

- `runtime/` contains startup registration and the singleton dependency container
- `interfaces/` contains the real CLI, GUI, TUI, and web implementations
- `app/`, `desktop/`, `tui/`, and `web/` remain as compatibility import layers so older imports and scripts still run

This keeps interface code in one place without breaking existing entrypoints.

## Main Runtime Flow

```text
Interface
  CLI / Desktop GUI / TUI / FastAPI
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

## Major Subsystems

### Runtime

- `runtime/bootstrap.py`: registers providers, sources, input adapters, and exporters
- `runtime/container.py`: constructs shared service instances

### Interfaces

- `interfaces/cli.py`: command router for import, scrape, translation, glossary, OCR, and export
- `interfaces/desktop/`: PySide6 desktop application
- `interfaces/tui/`: Rich terminal dashboard and screens
- `interfaces/web/`: FastAPI app, server launcher, routers, and error handlers

### Import Layer

- `inputs/`: normalized import adapters for `web`, `text`, `epub`, `pdf`, `image_folder`, and `cbz`
- `sources/`: scraper adapters for live web novel sites

The important distinction is:

- `inputs/` handles document or archive ingestion into normalized stored units
- `sources/` handles live site scraping for metadata and chapter fetching

### Service Layer

- `services/storage_service.py`: file-backed persistence for metadata, chapters, glossary, OCR, exports, and assets
- `services/novel_orchestration_service.py`: end-to-end business workflows
- `services/translation_service.py`: pipeline execution
- `services/export_service.py`: exporter dispatch
- `services/preferences_service.py`: user settings and workflow preferences
- `services/usage_service.py`: usage and cost recording

### Translation Pipeline

```text
Fetch -> Parse -> Segment -> Translate -> Post-process
```

The pipeline is assembled in `runtime/container.py` and used by the orchestration service.

### Review and Gating

Before translation completes, the system can enforce:

- glossary review state
- OCR review state for chapters that require OCR

This lets translation runs stop on unresolved content rather than silently producing inconsistent output.

## Data Model Overview

All runtime state is stored under `novel_library/`.

Important stored artifacts include:

- `metadata.json`: novel-level metadata and chapter/unit index
- `chapters/<id>.json`: unified chapter bundle with source, translation, state, and media metadata
- `glossary.json`: glossary terms and statuses
- `assets/`: source or generated media assets
- `checkpoints/`: recovery snapshots

See [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md) for the full file-level layout.

## Extension Points

To add a new capability, the usual extension points are:

- new provider: `providers/` plus `runtime/bootstrap.py`
- new document type: `inputs/` plus `runtime/bootstrap.py`
- new web source: `sources/` plus `runtime/bootstrap.py`
- new export format: `export/` plus `runtime/bootstrap.py`
- new interface surface: `interfaces/`

## Packaging Notes

- CLI script: `novelaibook`
- Desktop script: `novelaibook-gui`
- Module launcher: `python -m novelai --interface ...`
- PyInstaller spec: [../../novelaibook-ui.spec](../../novelaibook-ui.spec)

## Related Docs

- [../guides/GETTING_STARTED.md](../guides/GETTING_STARTED.md)
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)
- [RELEASE_D_PLAN.md](RELEASE_D_PLAN.md)

# Novel AI Architecture

This document summarizes the high-level architecture, key subsystems, and extension points for the Novel AI translation platform.

## High-level Domains

The codebase is organized into clear domains to enforce separation of concerns:

- **app/** – Application entrypoints (CLI, web server, etc.).
- **config/** – Centralized configuration management.
- **core/** – Shared primitives (types, errors, enums).
- **providers/** – Translation model provider adapters (OpenAI, others).
- **sources/** – Scraper/source adapters (Syosetu, Kakuyomu, etc.).
- **pipeline/** – Translation pipeline stages and orchestration.
- **prompts/** – Prompt templates and prompt management.
- **glossary/** – Glossaries and terminology enforcement.
- **services/** – High-level services used by both web and TUI.
- **web/** – Backend API (FastAPI) and web delivery logic.
- **tui/** – Terminal UI.
- **export/** – EPUB/PDF export logic.
- **storage/** – Persistence abstractions (file system storage, future DB).
  - Novels are stored under `data/novels/<folder_name>/` where `folder_name` is derived from the translated title (or falls back to the novel ID).
  - Each novel folder contains:
    - `metadata.json`
    - `raw/` (scraped chapters)
    - `translated/` (translated chapters)
  - An index file maps `novel_id` → `folder_name` to avoid collisions and to support renaming.
- **tests/** – (favored in future) unit and integration tests.

## Key Architectural Principles

- **Provider/Source Abstraction**: New providers and sources can be added by implementing a well-defined adapter interface and registering it.
- **Pipeline Modularization**: The translation process is broken into explicit stages (fetch, parse, segment, translate, post-process).
- **Dependency injection container**: A small `container` module provides shared, reusable service instances across CLI, TUI, and web.
- **Orchestration service**: Shared business workflows (scrape/translate) are centralized in a `NovelOrchestrationService` to avoid duplication between UI surfaces.
- **Usage tracking**: Translation requests are logged to `data/usage.json` (tokens, provider/model) and used by the TUI diagnostics view to estimate cost.
- **Configuration Centralization**: `novelai.config.settings` centralizes environment/config values.
- **Export Isolation**: EPUB/PDF exporters are separate from translation logic.
- **Extendability First**: Clear module boundaries make adding new features straightforward.

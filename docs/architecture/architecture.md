# Novel AI Architecture

High-level architecture, key subsystems, and extension points for the Novel AI translation platform.

## Codebase Structure

```
src/novelai/
├── app/                    # Application entrypoints
│   ├── bootstrap.py        # Service initialization
│   ├── cli.py              # Command-line interface
│   ├── container.py        # Dependency injection container
│   ├── web.py              # Web server setup
│   └── __init__.py
├── config/                 # Configuration management
│   ├── settings.py         # Environment & settings
│   └── __init__.py
├── core/                   # Shared primitives & types
│   ├── types.py            # Core data types
│   ├── errors.py           # Exception hierarchy
│   ├── chapter_state.py    # ChapterState enum
│   └── __init__.py
├── cost_estimator/         # Translation cost estimation
│   ├── cli.py              # Standalone CLI for estimates
│   ├── compare.py          # Multi-model comparison
│   ├── estimator.py        # Core estimation logic
│   ├── heuristics.py       # Token estimation heuristics
│   ├── models.py           # Estimation data types
│   ├── pricing.py          # Model pricing catalog
│   └── __init__.py
├── export/                 # Export formats
│   ├── base_exporter.py    # Exporter interface
│   ├── epub_exporter.py    # EPUB export
│   ├── pdf_exporter.py     # PDF export
│   ├── registry.py         # Exporter registry
│   └── __init__.py
├── glossary/               # Terminology management
│   ├── glossary.py         # Glossary service
│   └── __init__.py
├── pipeline/               # Translation pipeline
│   ├── pipeline.py         # Main orchestrator
│   ├── context.py          # Pipeline context
│   └── stages/
│       ├── base.py         # Stage interface
│       ├── fetch.py        # Fetch stage
│       ├── parse.py        # Parse stage
│       ├── segment.py      # Segment stage
│       ├── translate.py    # Translate stage
│       ├── post_process.py # Post-process stage
│       └── __init__.py
├── prompts/                # Prompt templates
│   ├── builders.py         # Prompt construction
│   ├── models.py           # Prompt data types
│   ├── responses_api.py    # OpenAI Responses API payloads
│   ├── templates.py        # Template and preset definitions
│   └── __init__.py
├── providers/              # Translation provider adapters
│   ├── base.py             # Provider interface
│   ├── openai_provider.py  # OpenAI implementation
│   ├── dummy_provider.py   # Mock provider for testing
│   ├── registry.py         # Provider registry
│   └── __init__.py
├── services/               # High-level services
│   ├── backup_manager.py            # Backup & restore
│   ├── checkpoint_manager.py        # State checkpointing
│   ├── export_service.py            # Export orchestration
│   ├── novel_orchestration_service.py  # Business workflows
│   ├── preferences_service.py       # User preferences
│   ├── query_builder.py             # Query construction
│   ├── settings_service.py          # Settings alias (delegates to PreferencesService)
│   ├── storage_service.py           # Persistence layer
│   ├── translation_cache.py         # Cache management
│   ├── translation_service.py       # Translation orchestration
│   ├── usage_service.py             # API usage tracking
│   └── __init__.py
├── sources/                # Novel source scrapers
│   ├── base.py             # Source interface
│   ├── kakuyomu.py         # Kakuyomu scraper
│   ├── novel18_syosetu.py  # Novel18 (R-18 Syosetu)
│   ├── syosetu_ncode.py    # Syosetu Ncode scraper
│   ├── registry.py         # Source registry
│   ├── _helpers.py         # Shared scraping utilities
│   └── __init__.py
├── tui/                    # Terminal user interface
│   ├── app.py              # TUI application (Rich dashboard)
│   ├── screens/            # Mixin-based screen modules
│   │   ├── diagnostics.py  # Diagnostics screen mixin
│   │   ├── library.py      # Library browser mixin
│   │   ├── pipeline.py     # Scrape/update pipeline mixin
│   │   ├── settings.py     # Settings screen mixin
│   │   └── __init__.py
│   └── __init__.py
├── utils/                  # Utility modules
│   ├── chapter_selection.py # Chapter selection parsing
│   ├── logging.py          # Structured logging setup
│   ├── retry_decorator.py  # Retry with exponential backoff
│   └── __init__.py
├── web/                    # FastAPI backend
│   ├── api.py              # Main API app
│   ├── routers/
│   │   ├── novels.py       # Novel endpoints
│   │   └── __init__.py
│   └── __init__.py
└── __init__.py
```

## High-level Domains

| Domain | Purpose |
|--------|---------|
| **app/** | Application entrypoints (CLI, web server, DI container) |
| **config/** | Centralized configuration and environment management |
| **core/** | Shared primitives (types, errors, state machine enum) |
| **cost_estimator/** | Translation cost estimation and model comparison |
| **export/** | EPUB and PDF export engines |
| **glossary/** | Terminology/glossary enforcement system |
| **pipeline/** | Translation processing pipeline with modular stages |
| **prompts/** | Multilingual prompt templates and payload builders |
| **providers/** | Language model provider adapters (OpenAI, etc.) |
| **services/** | High-level business logic services |
| **sources/** | Novel scraper/source adapters (Syosetu Ncode, Novel18, Kakuyomu) |
| **tui/** | Terminal user interface with mixin-based screens |
| **utils/** | Utilities (logging, retry, chapter selection) |
| **web/** | FastAPI backend and REST endpoints |

## Runtime Data Structure

```
novel_library/
├── preferences.json                 # User preferences (provider, model, API key)
├── translation_cache.json           # Cached translation results
├── usage.json                       # API usage statistics
└── novels/
    ├── index.json                   # Novel ID → folder mapping
    └── <novel_id>/                  # Novel directory
        ├── metadata.json            # Novel metadata from source
        ├── raw/                     # Raw chapters from source
        │   ├── chapter_1.json
        │   └── chapter_2.json
        ├── translated/              # Translated chapters (JSON)
        │   ├── chapter_1.json
        │   └── chapter_2.json
        ├── epub/                    # EPUB exports
        │   └── full_novel.epub
        ├── assets/                  # Chapter images
        │   └── images/
        │       └── <chapter_id>/
        └── checkpoints/             # State snapshots for recovery
            └── chapter_1_post-translation.json
```

### Data Directory Usage

| File/Folder | Purpose | Managed By |
|-------------|---------|-----------|
| `preferences.json` | Provider, model, API key | `PreferencesService` |
| `translation_cache.json` | Cached translations to avoid re-translation | `TranslationCache` |
| `usage.json` | API usage tracking (tokens, cost) | `UsageService` |
| `novels/{id}/` | Novel chapters and metadata | `StorageService` |
| `novels/{id}/raw/` | Raw chapters from source | `StorageService` |
| `novels/{id}/translated/` | Final translated chapters (JSON) | `StorageService` |
| `novels/{id}/epub/` | EPUB export files | `ExportService` |
| `novels/{id}/assets/` | Chapter images | `StorageService` |
| `novels/{id}/checkpoints/` | State snapshots for recovery | `CheckpointManager` |

## Key Architectural Principles

### Core Design Patterns

| Principle | Implementation | Benefit |
|-----------|----------------|---------|
| **Provider/Source Abstraction** | Base class interfaces + registry pattern | Easy to add new providers/sources |
| **Pipeline Modularization** | Explicit stages (fetch → parse → segment → translate → post-process) | Testable, reusable stages |
| **Dependency Injection** | `Container` class provides service instances | Loose coupling, testability |
| **Orchestration Service** | `NovelOrchestrationService` centralizes workflows | No duplication between CLI/web/TUI |
| **Configuration Centralization** | `settings.py` for all config values | Environment-aware, twelve-factor compliant |
| **Usage Tracking** | `UsageService` logs to `novel_library/usage.json` | Cost estimation and quota management |
| **Storage Isolation** | `StorageService` abstracts persistence | Future DB migration possible |
| **Export Modularity** | Separate exporter classes (EPUB, PDF) with registry | Extensible to new formats |
| **TUI Mixin Screens** | Screen logic in `tui/screens/` mixins, composed in `app.py` | Isolated screen concerns, testable |

### Resilience Layer

| Component | Purpose | Pattern |
|-----------|---------|---------|
| **Retry Decorator** | Auto-retry transient failures | Exponential backoff with jitter |
| **Checkpoint Manager** | Save state at key points | Atomic snapshots, recovery points |
| **Backup Manager** | Full/incremental backups | Tar.gz + manifest versioning |

## System Architecture Diagram

```
User Interfaces
├── CLI (app/cli.py)
├── Web (web/api.py)
└── TUI (tui/app.py + tui/screens/)
        ↓
NovelOrchestrationService (services/novel_orchestration_service.py)
        ↓
Translation Pipeline (pipeline/pipeline.py)
├── Fetch Stage → Source Adapters (sources/)
├── Parse Stage → HTML/text parsing
├── Segment Stage → Text segmentation
├── Translate Stage → Provider Adapters (providers/)
└── Post-Process Stage → Formatting
        ↓
Storage/Export Layer
├── StorageService (services/storage_service.py)
├── ExportService (services/export_service.py)
├── CheckpointManager (services/checkpoint_manager.py)
└── BackupManager (services/backup_manager.py)
        ↓
External Dependencies
├── OpenAI API
├── Syosetu / Kakuyomu / Novel18 Websites
└── File System (novel_library/)
```

## Data Flow Example

### Simple Translation Workflow

```
1. User requests novel translation (novel_id: "n4423lw")
   ↓
2. NovelOrchestrationService.translate_novel()
   ↓
3. Pipeline executes:
   - Fetch: Scrape chapters from source
   - Parse: Extract text from HTML
   - Segment: Break into paragraphs
   - Translate: Send to OpenAI (with @retry_async decorator)
   - Post-Process: Format output
   ↓
4. Chapter stored: novel_library/novels/n4423lw/translated/chapter_1.json
   Checkpoint saved: novel_library/novels/n4423lw/checkpoints/...
   ↓
5. Export: novelaibook export-epub n4423lw --format epub
   Output: novel_library/novels/n4423lw/epub/full_novel.epub
```

### Error Recovery Workflow

```
1. Translation fails (API timeout)
   ↓
2. @retry_async decorator triggers:
   - Exponential backoff: 1s → 2s → 4s → 8s → 16s
   - Maximum 5 retry attempts
   ↓
3. If all retries exhausted:
   - CheckpointManager.get_recovery_point() called
   - Restores to last successful state
   - Logs error with correlation ID
   ↓
4. On critical failure:
   - BackupManager.create_full_backup()
   - Can restore with BackupManager.restore_backup()
```

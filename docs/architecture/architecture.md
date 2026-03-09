# Novel AI Architecture

This document summarizes the high-level architecture, key subsystems, and extension points for the Novel AI translation platform.

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
├── providers/              # Translation provider adapters
│   ├── base.py             # Provider interface
│   ├── openai_provider.py  # OpenAI implementation
│   ├── dummy_provider.py   # Mock provider for testing
│   ├── registry.py         # Provider registry
│   └── __init__.py
├── sources/                # Novel source scrapers
│   ├── base.py             # Source interface
│   ├── syosetu_ncode.py    # Syosetu scraper
│   ├── example_source.py   # Example implementation
│   ├── registry.py         # Source registry
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
│   ├── templates.py        # Template management
│   └── __init__.py
├── glossary/               # Terminology management
│   ├── glossary.py         # Glossary service
│   └── __init__.py
├── services/               # High-level services
│   ├── storage_service.py           # Persistence layer
│   ├── translation_service.py       # Translation orchestration
│   ├── export_service.py            # EPUB/PDF export
│   ├── settings_service.py          # Settings management
│   ├── usage_service.py             # API usage tracking
│   ├── translation_cache.py         # Cache management
│   ├── novel_orchestration_service.py  # Business workflows
│   ├── checkpoint_manager.py        # State checkpointing
│   ├── backup_manager.py            # Backup & restore
│   └── __init__.py
├── export/                 # Export formats
│   ├── base_exporter.py    # Exporter interface
│   ├── epub_exporter.py    # EPUB export
│   ├── pdf_exporter.py     # PDF export
│   └── __init__.py
├── web/                    # FastAPI backend
│   ├── api.py              # Main API app
│   ├── routers/
│   │   ├── novels.py       # Novel endpoints
│   │   └── __init__.py
│   └── __init__.py
├── tui/                    # Terminal user interface
│   ├── app.py              # TUI application
│   └── __init__.py
├── utils/                  # Utility modules
│   ├── logging.py          # Logging setup
│   ├── chapter_selection.py # Chapter selection
│   ├── retry_decorator.py  # Retry logic (Phase 4)
│   ├── batch_processor.py  # Batch processing (Phase 4 — planned, not yet implemented)
│   ├── connection_pool.py  # Connection pooling (Phase 4 — planned, not yet implemented)
│   ├── cache_optimizer.py  # Cache management (Phase 4 — planned, not yet implemented)
│   ├── rate_limiter.py     # Rate limiting
│   ├── query_builder.py    # Query construction
│   └── __init__.py
├── storage/                # Storage abstractions
│   ├── models.py           # Data models
│   ├── repository.py       # Repository pattern
│   └── __init__.py
└── __init__.py
```

## High-level Domains

The codebase is organized into clear domains to enforce separation of concerns:

| Domain | Purpose |
|--------|---------|
| **app/** | Application entrypoints (CLI, web server, DI container) |
| **config/** | Centralized configuration and environment management |
| **core/** | Shared primitives (types, errors, state machine enum) |
| **providers/** | Language model provider adapters (OpenAI, etc.) |
| **sources/** | Novel scraper/source adapters (Syosetu, others) |
| **pipeline/** | Translation processing pipeline with modular stages |
| **prompts/** | Prompt template system and management |
| **glossary/** | Terminology/glossary enforcement system |
| **services/** | High-level business logic services |
| **web/** | FastAPI backend and REST endpoints |
| **tui/** | Terminal user interface |
| **export/** | EPUB/PDF export engines |
| **storage/** | Persistence layer and data access |
| **utils/** | Utilities (logging, rate limiting, retry, batch, pool, cache) |
| **tests/** | Unit and integration tests |

## Runtime Data Structure

```
data/
├── translation_cache.json          # Cached translation results
├── usage.json                       # API usage statistics
├── backups/                         # Backup directory (Phase 4)
│   ├── n4423lw__20260307_120000.tar.gz
│   └── manifest.json
└── novels/
    ├── index.json                   # Novel ID → folder mapping
    └── n4423lw/                     # Novel directory (novel ID)
        ├── metadata.json            # Novel metadata
        ├── raw/                     # Raw chapters from source
        │   ├── chapter_1.json
        │   └── chapter_2.json
        ├── translated/              # Translated chapters (JSON)
        │   ├── chapter_1.json
        │   └── chapter_2.json
        ├── epub/                    # EPUB exports
        │   ├── full_novel.epub
        │   └── chapter_1.epub
        ├── pdf/                     # PDF exports
        │   ├── full_novel.pdf
        │   └── chapter_1.pdf
        └── checkpoints/             # State snapshots (Phase 4)
            ├── chapter_1_pre-translation.json
            └── chapter_1_post-translation.json
```

### Data Directory Usage

| File/Folder | Purpose | Managed By |
|-------------|---------|-----------|
| `translation_cache.json` | Cached translations to avoid re-translation | `TranslationCacheOptimizer` |
| `usage.json` | API usage tracking (tokens, cost) | `UsageService` |
| `backups/` | Versioned backups of novels | `BackupManager` (Phase 4) |
| `novels/{id}/` | Novel chapters and metadata | `StorageService` |
| `novels/{id}/raw/` | Raw chapters from source | `StorageService` |
| `novels/{id}/translated/` | Final translated chapters (JSON) | `StorageService` |
| `novels/{id}/epub/` | EPUB export files | `ExportService` |
| `novels/{id}/pdf/` | PDF export files | `ExportService` |
| `novels/{id}/checkpoints/` | State snapshots for recovery | `CheckpointManager` (Phase 4) |

## Key Architectural Principles

### Core Design Patterns

| Principle | Implementation | Benefit |
|-----------|----------------|---------|
| **Provider/Source Abstraction** | Base class interfaces + registry pattern | Easy to add new providers/sources |
| **Pipeline Modularization** | Explicit stages (fetch → parse → segment → translate → post-process) | Testable, reusable stages |
| **Dependency Injection** | `Container` class provides service instances | Loose coupling, testability |
| **Orchestration Service** | `NovelOrchestrationService` centralizes workflows | No duplication between CLI/web/TUI |
| **Configuration Centralization** | `settings.py` for all config values | Environment-aware, twelve-factor compliant |
| **Usage Tracking** | `UsageService` logs to `data/usage.json` | Cost estimation and quota management |
| **Storage Isolation** | `StorageService` abstracts persistence | Future DB migration possible |
| **Export Modularity** | Separate exporter classes (EPUB, PDF) | Extensible to new formats |

### Phase 4 Resilience Layer

| Component | Purpose | Pattern |
|-----------|---------|---------|
| **Retry Decorator** | Auto-retry transient failures | Exponential backoff with jitter |
| **Checkpoint Manager** | Save state at key points | Atomic snapshots, recovery points |
| **Backup Manager** | Full/incremental backups | Tar.gz + manifest versioning |
| **Batch Processor** | Parallel item processing | Concurrent batches with failure tolerance |
| **Connection Pool** | Reusable API connections | Min/max sizing, overflow handling |
| **Cache Optimizer** | Translation result caching | LRU/LFU/FIFO eviction, TTL support |

## System Architecture Diagram

```
User Interfaces
├── CLI (app/cli.py)
├── Web (web/api.py) 
└── TUI (tui/app.py)
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
├── CheckpointManager (services/checkpoint_manager.py) [Phase 4]
└── BackupManager (services/backup_manager.py) [Phase 4]
        ↓
Resilience Layer (Phase 4)
├── Batch Processor (utils/batch_processor.py) — planned
├── Connection Pool (utils/connection_pool.py) — planned
├── Retry Decorator (utils/retry_decorator.py)
└── Cache Optimizer (utils/cache_optimizer.py) — planned
        ↓
External Dependencies
├── OpenAI API
├── Syosetu Website
└── File System (data/)
```

## Data Flow Example

### Simple Translation Workflow

```
1. User requests novel translation (novel_id: "n4423lw")
   ↓
2. NovelOrchestrationService.translate_novel()
   ↓
3. Pipeline executes:
   - Fetch: Scrape chapters from Syosetu
   - Parse: Extract text from HTML
   - Segment: Break into paragraphs
   - Translate: Send to OpenAI (with @retry_async decorator)
   - Post-Process: Format output
   ↓
4. Chapter stored: data/novels/n4423lw/translated/1.txt
   Checkpoint saved: data/novels/n4423lw/checkpoints/ch1_post_translate.json
   ↓
5. Web API: GET /api/novels/n4423lw/chapters/1
   Served from: data/web/novels/n4423lw/translated/1.txt
```

### Error Recovery Workflow (Phase 4)

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
   - Logs error with context
   ↓
4. BatchProcessor handles multiple chapters:
   - Processes in batches of 10
   - Retries individual failures
   - Reports success/failure per batch
   ↓
5. On critical failure:
   - BackupManager.create_full_backup() -> data/backups/n4423lw_TIMESTAMP.tar.gz
   - Can restore with BackupManager.restore_backup()
```

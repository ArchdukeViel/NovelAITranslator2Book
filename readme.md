# Novel AI

Web/document import, multilingual AI translation, and multi-format export platform with a Rich TUI dashboard and desktop GUI entrypoint.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [TUI Menu](#tui-menu)
- [CLI](#cli)
- [Glossary Review Workflow](#glossary-review-workflow)
- [Prompt System](#prompt-system)
  - [Glossary vs Style Preset](#glossary-vs-style-preset)
- [Cost Estimation](#cost-estimation)
- [Project Structure](#project-structure)
- [Runtime Data](#runtime-data)
- [Development](#development)
- [Current Limitations](#current-limitations)
- [Documentation](#documentation)

## Features

- **Input adapters** for web URLs, `.txt` / `.md`, `.epub`, `.pdf` (optional dependency), image folders, and `.cbz`
- **Source adapters** for Syosetu (ncode / novel18), Kakuyomu, and a generic heuristic fallback for arbitrary URLs
- **AI translation** via OpenAI (pluggable provider interface for other LLMs)
- **Desktop GUI shell** via `novelaibook gui` with workspace tabs for Import, OCR Review, Glossary, Translate, Re-embed, Export, and Activity
- **Multilingual prompt system** with auto-detected source language, 20 target languages, glossary injection, style presets, and JSON-output mode
- **Rich TUI dashboard** — add novels, update chapters, inspect your library, and manage settings through a guided menu system
- **Workflow profiles** for term extraction, term summarization, term translation, body translation, OCR, and re-embedding
- **CLI commands** — scrape metadata, fetch chapters, translate, and export without the TUI
- **Glossary extraction** — build pending glossary candidates from recurring imported text before translation
- **Glossary review workflow** — term statuses (`pending`, `approved`, `ignored`, `translated`) with preflight enforcement before translation
- **OCR review workflow** — chapter-level OCR candidate ingestion plus review status enforcement before translation when required
- **Single-chapter retranslate** — force a retranslation for one chapter without rerunning full ranges
- **Multi-format export** — EPUB (with title page, optional TOC, and inline images), HTML, and Markdown
- **Export language choice** — export translated text or the original source text
- **Cost estimation** for budgeting translation runs before sending chapters to an API
- **Structured logging** with per-request correlation IDs
- **Checkpoint and backup** for disaster recovery

## Quick Start

```bash
# 1. Clone and set up
git clone <repo-url>
cd "Novel AI"
python -m venv .venv
.venv\Scripts\activate        # Windows
python -m pip install -e ".[dev]"

# 2. Configure (OpenAI key required for real translations)
copy .env.example .env        # then edit .env

# 3. Launch the TUI dashboard
novelaibook tui

# or launch the desktop GUI (install desktop extras first)
novelaibook gui
```

See [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md) for the full walkthrough.

## TUI Menu

| Key | Label | Description |
|-----|-------|-------------|
| list | Novel Library | Browse, export, and manage stored novels |
| scrape | Add Novel | Detect source from a URL, fetch and translate chapters |
| update | Update Novel | Refresh metadata, raw chapters, and translations for an existing novel |
| diagnostics | Diagnostics | Inspect usage, cache health, and recent activity |
| settings | Settings | Provider, model, API key, target language, and scrape delay |
| glossary | Glossary | Manage terms and review statuses for a novel |
| exit | Exit | Close the dashboard |

## CLI

```bash
novelaibook tui                                          # interactive dashboard
novelaibook gui                                          # desktop GUI
novelaibook import-document text my_novel .\book\        # import text/markdown files
novelaibook import-document epub my_novel .\book.epub    # import EPUB
novelaibook scrape-metadata syosetu_ncode n7133es        # download metadata
novelaibook scrape-chapters syosetu_ncode n7133es 1-3    # fetch raw chapters
novelaibook translate-chapters syosetu_ncode n7133es 1-3 # translate
novelaibook translate-chapters syosetu_ncode n7133es 1-3 --force # retranslate range
novelaibook retranslate-chapter syosetu_ncode n7133es 2   # retranslate one chapter
novelaibook export-epub n7133es --format epub            # export EPUB
novelaibook glossary n7133es list                         # show glossary + status
novelaibook glossary n7133es extract --chapters all       # extract glossary candidates from stored text
novelaibook glossary n7133es review "魔導具" approved      # set status for a term
novelaibook glossary n7133es approve-all                  # approve all pending terms
novelaibook ocr n7133es ingest all                         # build OCR candidates from image manifests
novelaibook ocr n7133es list-pending                       # list OCR-required chapters pending review
novelaibook ocr n7133es review 12 --text "corrected text" # mark chapter OCR reviewed
novelaibook ocr n7133es set-status 12 failed               # set explicit OCR status
```

- `--mode full` clears stored data and re-scrapes everything.
- `--mode update` (default) only downloads new/changed chapters.
- Translation preflight blocks runs with pending glossary terms until reviewed.
- Translation preflight also blocks chapters where `ocr_required=true` and OCR status is not `reviewed`.
- Exports go to `novel_library/novels/<novel>/<format>/` by default; use `--output <dir>` for a custom path.

## Glossary Review Workflow

Glossary terms now carry a review status:

- `pending`: newly added, must be reviewed before translation
- `approved`: accepted and eligible for translation prompts
- `ignored`: intentionally excluded from glossary injection
- `translated`: finalized term mapping

Recommended flow:

1. Add terms (`glossary add`) or use TUI Glossary screen.
2. Review statuses (`glossary review` / TUI review action).
3. Run translation after pending terms are resolved.

## OCR Review Workflow

For image-heavy chapters, use OCR candidate ingestion and review:

1. Build OCR candidates from stored chapter image metadata (`ocr ingest`).
2. Inspect pending chapters (`ocr list-pending`).
3. Mark reviewed chapters (`ocr review` or `ocr set-status`).
4. Run translation once OCR-required chapters are reviewed.

In TUI:

1. Open `Glossary` from dashboard.
2. Use `5) ocr ingest`, `6) ocr list`, and `7) ocr review`.

Diagnostics and Library inspection now include OCR/re-embedding counters for operational visibility.

## Prompt System

The prompt layer under `src/novelai/prompts/` supports:

- language-pair driven translation (Japanese → English, Japanese → Indonesian, etc.)
- normal and JSON-output modes
- optional glossary injection for terminology consistency
- optional style presets: `fantasy`, `romance`, `action`, `comedy`

```python
from novelai.prompts import build_translation_request

request = build_translation_request(
    text="魔導具の扱いには注意が必要だった。",
    source_language="Japanese",
    target_language="English",
    glossary_entries=[{"source": "魔導具", "target": "magic device"}],
    style_preset="fantasy",
)
```

### Glossary vs Style Preset

- **Glossary** entries are deterministic terminology mappings (names, ranks, recurring terms).
- **Style presets** are additional prompt instructions for tone (`fantasy`, `romance`, `action`, `comedy`).

Add a new preset by extending `STYLE_PRESET_TEMPLATES` in `src/novelai/prompts/templates.py`.

## Cost Estimation

Budget translation runs before calling an API. The estimator uses Japanese character count as primary input and models prompt, glossary, and JSON-mode overhead separately.

```python
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions

comparison = compare_models(
    ["gpt-5.2", "gpt-5.4"],
    EstimationOptions(japanese_characters=10_000),
)
for est in comparison.estimates:
    print(est.model_name, est.estimated_total_cost_usd)
```

Default pricing (update in `src/novelai/cost_estimator/pricing.py`):

| Model | Input (USD/1M tokens) | Output (USD/1M tokens) |
|-------|----------------------|------------------------|
| gpt-5.2 | 1.75 | 14.00 |
| gpt-5.4 | 2.50 | 15.00 |

## Project Structure

```
src/novelai/
  app/            CLI, web server, DI container, bootstrap
  config/         Environment and settings
  core/           Shared types, errors, chapter state enum
  cost_estimator/ Translation cost estimation
  export/         Export engines (EPUB, HTML, Markdown; PDF placeholder)
  glossary/       Terminology management
  pipeline/       Translation pipeline (fetch → parse → segment → translate → post-process)
  prompts/        Prompt templates and payload builders
  providers/      Translation provider adapters (OpenAI, dummy)
  services/       Business services (storage, translation, orchestration, backups, checkpoints)
  sources/        Novel source scrapers (Syosetu, Kakuyomu, Novel18, generic)
  tui/            Rich TUI dashboard with mixin-based screens
  utils/          Logging, retry, chapter selection, rate limiting
  web/            FastAPI backend
tests/            pytest suite (326 tests)
```

## Runtime Data

All runtime data lives under `novel_library/`:

```
novel_library/
  preferences.json
  translation_cache.json
  usage.json
  novels/
    index.json
    <novel_id>/
      metadata.json
      chapters/     chapter bundles (raw + translated + state)
      assets/       chapter images
      checkpoints/  state snapshots (created on demand)
```

See [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md) for field-level detail.

## Development

```bash
# Run tests
python -m pytest tests/ -q

# Type check
python -m pyright src/novelai/

# Regenerate lockfiles
powershell -ExecutionPolicy Bypass -File .\scripts\update-lockfiles.ps1
```

## Current Limitations

| Area | Status | Notes |
|------|--------|-------|
| **Browser frontend** | API only | FastAPI backend serves JSON endpoints; no browser UI yet. Use the desktop GUI, TUI, or CLI instead. |
| **Desktop GUI deps** | Optional | `PySide6` is not part of the base install; install the `desktop` extra before running `novelaibook gui`. |
| **PDF export** | Not implemented | `PDFExporter` exists as a placeholder; raises `NotImplementedError`. Needs a PDF library (e.g. reportlab or weasyprint). |
| **Provider support** | OpenAI only | The provider interface is pluggable, but only the OpenAI adapter is implemented. A `DummyProvider` exists for testing. |
| **Export formats** | EPUB, HTML, Markdown | PDF and DOCX not yet implemented. |
| **Image embedding** | EPUB only | HTML and Markdown exports do not embed chapter images. |
| **Schema migration** | Not implemented | Storage writes a `schema_version` field but there is no migration logic for older formats. |
| **Concurrent writes** | No protection | Simultaneous writes to the same novel may race; no file locking in the storage layer. |

## Documentation

| Document | Audience |
|----------|----------|
| [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md) | New users — install, configure, first run |
| [docs/guides/TUI_GUIDE.md](docs/guides/TUI_GUIDE.md) | End users — TUI walkthrough |
| [docs/reference/PYTHON_COMMANDS.md](docs/reference/PYTHON_COMMANDS.md) | Developers — CLI and Python API reference |
| [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md) | Operations — data format and storage layout |
| [docs/architecture/architecture.md](docs/architecture/architecture.md) | Developers — system design and data flow |
| [docs/architecture/RELEASE_D_PLAN.md](docs/architecture/RELEASE_D_PLAN.md) | Developers — OCR and re-embedding implementation roadmap |
| [docs/history/](docs/history/) | Archive — phase completion records |

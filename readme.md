# Novel AI

Web novel scraping, multilingual AI translation, and multi-format export platform with a Rich TUI dashboard.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [TUI Menu](#tui-menu)
- [CLI](#cli)
- [Prompt System](#prompt-system)
  - [Glossary vs Style Preset](#glossary-vs-style-preset)
- [Cost Estimation](#cost-estimation)
- [Project Structure](#project-structure)
- [Runtime Data](#runtime-data)
- [Development](#development)
- [Current Limitations](#current-limitations)
- [Documentation](#documentation)

## Features

- **Source adapters** for Syosetu (ncode / novel18), Kakuyomu, and a generic heuristic fallback for arbitrary URLs
- **AI translation** via OpenAI (pluggable provider interface for other LLMs)
- **Multilingual prompt system** with auto-detected source language, 20 target languages, glossary injection, style presets, and JSON-output mode
- **Rich TUI dashboard** — add novels, update chapters, inspect your library, and manage settings through a guided menu system
- **CLI commands** — scrape metadata, fetch chapters, translate, and export without the TUI
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
| exit | Exit | Close the dashboard |

## CLI

```bash
novelaibook tui                                          # interactive dashboard
novelaibook scrape-metadata syosetu_ncode n7133es        # download metadata
novelaibook scrape-chapters syosetu_ncode n7133es 1-3    # fetch raw chapters
novelaibook translate-chapters syosetu_ncode n7133es 1-3 # translate
novelaibook export-epub n7133es --format epub            # export EPUB
```

- `--mode full` clears stored data and re-scrapes everything.
- `--mode update` (default) only downloads new/changed chapters.
- Exports go to `novel_library/novels/<novel>/<format>/` by default; use `--output <dir>` for a custom path.

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
| **PDF export** | Not implemented | `PDFExporter` exists as a placeholder; raises `NotImplementedError`. Needs a PDF library (e.g. reportlab or weasyprint). |
| **Provider support** | OpenAI only | The provider interface is pluggable, but only the OpenAI adapter is implemented. A `DummyProvider` exists for testing. |
| **Export formats** | EPUB, HTML, Markdown | PDF and DOCX not yet implemented. |
| **Image embedding** | EPUB only | HTML and Markdown exports do not embed chapter images. |

## Documentation

| Document | Audience |
|----------|----------|
| [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md) | New users — install, configure, first run |
| [docs/guides/TUI_GUIDE.md](docs/guides/TUI_GUIDE.md) | End users — TUI walkthrough |
| [docs/reference/PYTHON_COMMANDS.md](docs/reference/PYTHON_COMMANDS.md) | Developers — CLI and Python API reference |
| [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md) | Operations — data format and storage layout |
| [docs/architecture/architecture.md](docs/architecture/architecture.md) | Developers — system design and data flow |
| [docs/history/](docs/history/) | Archive — phase completion records |

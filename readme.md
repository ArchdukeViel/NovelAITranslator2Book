# Novel AI

A modular Japanese-to-English web novel translation platform.

## Quick Start

1. Install dependencies:

```bash
python -m pip install -e .
```

2. Copy `.env.example` to `.env` and set your API keys (if using OpenAI):

```bash
copy .env.example .env
```

3. Run the web server:

```bash
python -m novelai.app.web
```

4. Run the TUI:

```bash
novelaibook tui
```

5. Run in command mode (scraping and translation):

```bash
novelaibook scrape-metadata syosetu_ncode n7133es --mode full
novelaibook scrape-chapters syosetu_ncode n7133es 1-3 --mode update
novelaibook translate-chapters syosetu_ncode n7133es 1-3
novelaibook export-epub n7133es --output output --format epub
novelaibook export-epub n7133es --output output --format pdf
```

- `--mode full` clears stored data and re-scrapes everything.
- `--mode update` only downloads new/changed chapters.

## Lockfiles

Regenerate the pinned runtime and dev lockfiles from `pyproject.toml`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-lockfiles.ps1
```

Optional flags:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\update-lockfiles.ps1 -RuntimeOnly
powershell -ExecutionPolicy Bypass -File .\scripts\update-lockfiles.ps1 -DevOnly
```


## 📚 Documentation

Comprehensive guides organized by audience and use case:

### For New Users
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Installation (5 min) → Verification → First run
- **[TUI_GUIDE.md](TUI_GUIDE.md)** - Terminal UI walkthrough with keyboard shortcuts and examples

### For Developers
- **[PYTHON_COMMANDS.md](PYTHON_COMMANDS.md)** - Complete CLI reference with 8 command examples + 8 code examples
- **[docs/architecture.md](docs/architecture.md)** - System design, components, and data flow

### For Operations
- **[PHASE_4_OPERATIONS.md](PHASE_4_OPERATIONS.md)** - Resilience features, recovery procedures, and troubleshooting
- **[DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md)** - Data format reference and storage structure

### Documentation Index
- **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - Master index explaining all 12 documentation files
- **[DOCUMENTATION_OPTIMIZATION_PLAN.md](DOCUMENTATION_OPTIMIZATION_PLAN.md)** - Organization strategy and future structure

**👉 Start here**: First-time users should read [GETTING_STARTED.md](GETTING_STARTED.md)

---

## Project Structure

The repository is organized into clear domains. For details, see `docs/architecture.md`.

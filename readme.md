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
novelaibook web
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
novelaibook export-epub n7133es --format epub
novelaibook export-epub n7133es --format pdf
novelaibook export-epub n7133es --output exports --format epub
```

- `--mode full` clears stored data and re-scrapes everything.
- `--mode update` only downloads new/changed chapters.
- By default, exports are written inside `novel_library/novels/<novel>/<format>/`.
- Use `--output <dir>` only when you want a custom export destination such as `exports/`.

## Runtime Data

- `novel_library/` is the main runtime library. Keep it if you want to keep scraped novels, translations, metadata, preferences, and default exports.
- Custom export folders such as `exports/` only exist if you explicitly choose them with `--output`.

Safe to delete:

- `.tmp/`
- `tests_tmp/`
- `tests/.tmp/`
- `tests/.cache/`
- `pytest-cache-files-*/`
- `__pycache__/`
- `.pytest_cache/`
- `tests/.pytest_cache/`

## Windows Cleanup

If Windows says `Access is denied` while deleting temp or cache folders:

1. Close any running `python`, `pip`, or `pytest` process.
2. Open PowerShell as Administrator.
3. Run:

```powershell
Get-Process python,py,pytest,pip -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -LiteralPath .tmp, tests_tmp, __pycache__, .pytest_cache, tests/.pytest_cache, tests/.tmp, tests/.cache -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Force pytest-cache-files-* -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
```

If those folders still reject deletion because of ownership or ACL issues, run:

```powershell
takeown /F .tmp /R /D Y
takeown /F tests_tmp /R /D Y
takeown /F tests\.tmp /R /D Y
takeown /F tests\.cache /R /D Y
icacls .tmp /grant "$env:USERNAME`:(OI)(CI)F" /T /C
icacls tests_tmp /grant "$env:USERNAME`:(OI)(CI)F" /T /C
icacls tests\.tmp /grant "$env:USERNAME`:(OI)(CI)F" /T /C
icacls tests\.cache /grant "$env:USERNAME`:(OI)(CI)F" /T /C
```

Then run the delete command again.

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


## ðŸ“š Documentation

Comprehensive guides organized by audience and use case:

### For New Users
- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Installation (5 min) â†’ Verification â†’ First run
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

**ðŸ‘‰ Start here**: First-time users should read [GETTING_STARTED.md](GETTING_STARTED.md)

---

## Project Structure

The repository is organized into clear domains. For details, see `docs/architecture.md`.


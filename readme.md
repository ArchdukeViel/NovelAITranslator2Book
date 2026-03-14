# Novel AI

Novel AI is a local-first toolkit for importing novels and books, translating them with AI, reviewing glossary and OCR state, and exporting finished outputs in reader-friendly formats.

## What It Does

- Import content from web URLs, `.txt`, `.md`, `.epub`, `.pdf`, image folders, and `.cbz`
- Scrape supported web novel sources such as Syosetu, Novel18, Kakuyomu, and a generic fallback
- Translate chapters with workflow profiles for glossary extraction, term handling, OCR, and body translation
- Review glossary terms and OCR-gated chapters before translation
- Use the project from a Rich TUI, desktop GUI, CLI, or FastAPI backend
- Export translated or source text as EPUB, HTML, or Markdown

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip

# Minimal install
.\.venv\Scripts\python.exe -m pip install -e .

# Recommended for GUI + documents + OpenAI translation
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,documents,openai]"
```

Create your config file:

```powershell
Copy-Item .env.example .env
```

Add your provider key in `.env` when you want real translation, for example:

```env
PROVIDER_OPENAI_API_KEY=your_key_here
```

## Launch

```powershell
novelaibook tui
novelaibook gui
novelaibook web
```

For live GUI iteration during development:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_gui_dev.py
```

## Common Commands

```powershell
novelaibook import-document epub my_book .\book.epub
novelaibook scrape-metadata syosetu_ncode n4423lw
novelaibook scrape-chapters syosetu_ncode n4423lw 1-5
novelaibook translate-chapters syosetu_ncode n4423lw 1-5
novelaibook glossary n4423lw extract --chapters all
novelaibook ocr n4423lw ingest all
novelaibook export-epub n4423lw --format epub
```

## Documentation

- [docs/guides/GETTING_STARTED.md](docs/guides/GETTING_STARTED.md): install, configure, and first run
- [docs/guides/TUI_GUIDE.md](docs/guides/TUI_GUIDE.md): terminal workflow
- [docs/reference/PYTHON_COMMANDS.md](docs/reference/PYTHON_COMMANDS.md): CLI and Python usage
- [docs/reference/DATA_OUTPUT_STRUCTURE.md](docs/reference/DATA_OUTPUT_STRUCTURE.md): storage and output layout
- [docs/architecture/architecture.md](docs/architecture/architecture.md): codebase layout and runtime flow
- [docs/architecture/RELEASE_D_PLAN.md](docs/architecture/RELEASE_D_PLAN.md): OCR and re-embedding roadmap

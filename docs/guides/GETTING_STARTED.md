# Getting Started with Novel AI

This guide covers installation, configuration, and the fastest ways to launch the project.

## Prerequisites

- Python 3.13 or newer
- Git
- An API key if you want real model-backed translation

## Install

```powershell
git clone <repo-url>
cd "Novel AI"

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Choose the install that matches what you want:

```powershell
# Base CLI and TUI
.\.venv\Scripts\python.exe -m pip install -e .

# GUI support
.\.venv\Scripts\python.exe -m pip install -e ".[desktop]"

# GUI + document import support such as PDF
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,documents]"

# Recommended full local setup
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,documents,openai]"

# Development and packaging tools
.\.venv\Scripts\python.exe -m pip install -e ".[desktop,documents,openai,build,dev]"
```

## Configure

```powershell
Copy-Item .env.example .env
```

Set the values you need in `.env`. The most common ones are:

```env
PROVIDER_OPENAI_API_KEY=your_key_here
TRANSLATION_TARGET_LANGUAGE=English
LOG_LEVEL=INFO
```

## Verify the Install

```powershell
.\.venv\Scripts\python.exe -c "
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container

bootstrap()
print('bootstrap ok')
print('provider preference:', container.preferences.get_provider_key())
"
```

## Launch the Interfaces

```powershell
novelaibook tui
novelaibook gui
novelaibook web
```

You can also use the module entrypoint:

```powershell
python -m novelai --interface tui
python -m novelai --interface gui
python -m novelai --interface web
```

## First Workflow

### Document Import

```powershell
novelaibook import-document epub my_book .\book.epub
novelaibook glossary my_book extract --chapters all
novelaibook export-epub my_book --format epub
```

### Web Scrape and Translate

```powershell
novelaibook scrape-metadata syosetu_ncode n4423lw
novelaibook scrape-chapters syosetu_ncode n4423lw 1-3
novelaibook translate-chapters syosetu_ncode n4423lw 1-3
novelaibook export-epub n4423lw --format epub
```

## OCR and Glossary Review

```powershell
novelaibook glossary n4423lw list
novelaibook glossary n4423lw approve-all

novelaibook ocr n4423lw ingest all
novelaibook ocr n4423lw list-pending
novelaibook ocr n4423lw review 2 --text "Corrected OCR text"
```

Translation preflight will block chapters that still have pending glossary review or required OCR review.

## Live GUI Editing

```powershell
.\.venv\Scripts\python.exe .\scripts\run_gui_dev.py
```

That watches `src/` and restarts the desktop app when files change.

## Next Docs

- [TUI_GUIDE.md](TUI_GUIDE.md)
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)
- [../architecture/architecture.md](../architecture/architecture.md)

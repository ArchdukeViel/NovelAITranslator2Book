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
python -m novelai.app.cli
```

5. Run in command mode (scraping and translation):

```bash
python -m novelai.app.cli scrape-metadata syosetu_ncode n7133es --mode full
python -m novelai.app.cli scrape-chapters syosetu_ncode n7133es 1-3 --mode update
python -m novelai.app.cli translate-chapters syosetu_ncode n7133es 1-3
python -m novelai.app.cli export-epub n7133es --output output --format epub
python -m novelai.app.cli export-epub n7133es --output output --format pdf
```

- `--mode full` clears stored data and re-scrapes everything.
- `--mode update` only downloads new/changed chapters.

> Note: Translated metadata and chapters are mirrored under `data/web/novels/<id>/` for easy consumption by the web UI.

## Project Structure

The repository is organized into clear domains. For details, see `docs/architecture.md`.

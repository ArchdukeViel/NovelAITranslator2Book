# Novel AI

A modular Japanese-to-English web novel translation platform.

## Chapter Extraction Framework

This repository now also includes a production-minded chapter extraction framework under [`src/`](./src) with:

- pluggable adapters for `Syosetu`, `Kakuyomu`, and a conservative `GenericAdapter`
- canonical storage as cleaned chapter-body HTML fragments
- derived JSON, plain text, and stable block-level segments
- parser versioning so stored chapters can be reparsed later

### Why cleaned chapter HTML is canonical

The framework intentionally keeps cleaned chapter-body HTML as the source of truth instead of flattening everything to plain text too early.

- HTML preserves paragraph boundaries, ruby, line breaks, emphasis, blockquotes, and inline images.
- Plain text is useful for search, quick inspection, and translation preprocessing, but it is a lossy derivative.
- Keeping canonical HTML makes later reparsing possible when the parser improves.
- The same canonical fragment can support future translation, diffing, QA, and EPUB rebuilding without refetching the original page.

### Why JSON is derived

The JSON artifact is a machine-friendly projection of the canonical HTML:

- `source_html` stores the cleaned fragment exactly as normalized by the adapter and cleaner
- `plain_text` is derived for readability and downstream NLP-style processing
- `segments` split the fragment into stable units with both `html` and `text`

This separation keeps the pipeline future-proof. If segmentation rules change, chapters can be reparsed from canonical HTML instead of being rescraped.

### Why adapter-based design is better than a one-off scraper

The framework isolates site-specific logic inside adapters while keeping cleaning, text derivation, segmentation, storage, and CLI orchestration shared.

- `SyosetuAdapter` only needs to know Syosetu’s reading-page structure and identifiers.
- `KakuyomuAdapter` only needs to know Kakuyomu’s reading-page structure and identifiers.
- `GenericAdapter` gives a conservative fallback for simple chapter/article pages.

That keeps selector drift and future maintenance localized instead of duplicating whole pipelines per site.

### Project Structure

```text
src/
  adapters/
    base.py
    syosetu.py
    kakuyomu.py
    generic.py
    registry.py
  fetch.py
  clean.py
  parse.py
  segment.py
  models.py
  pipeline.py
  utils.py
novel_library/
  source_pipeline/
    raw/
    chapters/
      html/
      json/
tests/
  test_adapters.py
  test_clean.py
  test_parse.py
  fixtures/
```

### CLI

Run the extraction pipeline directly:

```bash
python -m src.pipeline --url "https://ncode.syosetu.com/n8733gf/1/"
python -m src.pipeline --url "https://kakuyomu.jp/works/16818093001234567890/episodes/16818093001234567999"
```

Optional flags:

```bash
python -m src.pipeline --url "<chapter_url>" --data-dir novel_library/source_pipeline --log-level DEBUG
```

The pipeline will:

1. fetch the raw page HTML
2. save raw HTML to `novel_library/source_pipeline/raw/`
3. detect the best adapter
4. extract just the chapter body
5. normalize it into a cleaned HTML fragment
6. save canonical HTML to `novel_library/source_pipeline/chapters/html/`
7. derive JSON, plain text, and stable segments
8. save JSON to `novel_library/source_pipeline/chapters/json/`

### Example Outputs

Checked-in sample outputs are under [`tests/fixtures/examples/`](./tests/fixtures/examples):

- Syosetu cleaned HTML: [`tests/fixtures/examples/syosetu_example.html`](./tests/fixtures/examples/syosetu_example.html)
- Syosetu JSON: [`tests/fixtures/examples/syosetu_example.json`](./tests/fixtures/examples/syosetu_example.json)
- Kakuyomu cleaned HTML: [`tests/fixtures/examples/kakuyomu_example.html`](./tests/fixtures/examples/kakuyomu_example.html)
- Kakuyomu JSON: [`tests/fixtures/examples/kakuyomu_example.json`](./tests/fixtures/examples/kakuyomu_example.json)

### Future Translation and EPUB Support

This design is intended to feed later translation and publishing stages:

- translation can operate on stable segment units instead of reparsing raw site HTML
- HTML-aware translation can preserve ruby, breaks, and emphasis more reliably
- EPUB generation can rebuild chapter markup from canonical cleaned fragments instead of guessed plain text

### Adding a New Adapter

To add another site:

1. implement a subclass of `BaseAdapter`
2. define `can_handle()`, `extract_title()`, `extract_chapter_body()`, and `extract_metadata()`
3. override identifier logic if the site has stable novel/chapter IDs
4. register the adapter in [`src/adapters/registry.py`](./src/adapters/registry.py)
5. add a fixture and parser tests for that site

The shared cleaner, plain-text derivation, segmentation, and persistence layers stay unchanged.

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

## Cost Estimation

The repository now includes a reusable estimator under `src/cost_estimator/` for budgeting Japanese-to-English translation runs before you send chapters to an API.

- It is an estimate, not an exact billing meter.
- It uses Japanese character count as the primary input because chapter text is available before exact tokenization and the project processes Japanese fiction.
- Prompt overhead, glossary overhead, and JSON mode overhead are modeled separately so the assumptions stay visible and configurable.
- Pricing lives in `src/cost_estimator/pricing.py`, not inside the estimator logic, so model prices can be updated later without rewriting the estimator.

### Supported models

- `gpt-5.2`
- `gpt-5.4`

Default pricing:

- `gpt-5.2`: input `1.75 USD / 1M tokens`, output `14.00 USD / 1M tokens`
- `gpt-5.4`: input `2.50 USD / 1M tokens`, output `15.00 USD / 1M tokens`

### Baseline heuristic

The default heuristic is anchored to `10,000` Japanese characters:

- source-text input tokens: `8,700`
- prompt overhead: `500`
- estimated total input tokens: `9,200`
- estimated output tokens: `8,000`

Optional modifiers:

- glossary mode adds input overhead for terminology instructions
- JSON mode adds input overhead for response-format instructions and output overhead for wrapper structure
- custom overhead token values can override the defaults per request

### CLI example

```bash
python -m src.cost_estimator.cli --chars 10000
```

Example output:

```text
Model: gpt-5.2
Estimated input tokens: 9200
Estimated output tokens: 8000
Estimated input cost (USD): $0.0161
Estimated output cost (USD): $0.1120
Estimated total cost (USD): $0.1281

Model: gpt-5.4
Estimated input tokens: 9200
Estimated output tokens: 8000
Estimated input cost (USD): $0.0230
Estimated output cost (USD): $0.1200
Estimated total cost (USD): $0.1430

Cheapest model: gpt-5.2
Difference: $0.0149
Percentage difference: 11.63%
```

Enable glossary and JSON-mode adjustments:

```bash
python -m src.cost_estimator.cli --chars 10000 --glossary --json
```

### Python usage

```python
from src.cost_estimator.compare import compare_models
from src.cost_estimator.models import EstimationOptions

options = EstimationOptions(
    japanese_characters=10_000,
    glossary_enabled=True,
    json_mode=False,
)
comparison = compare_models(["gpt-5.2", "gpt-5.4"], options)

for estimate in comparison.estimates:
    print(estimate.model_name, estimate.estimated_total_cost_usd)
```

### Updating pricing later

Update the `DEFAULT_PRICING` entries in `src/cost_estimator/pricing.py` or pass a custom pricing catalog into `estimate_cost()` and `compare_models()`.

### Currency conversion extension point

The estimator does not fetch exchange rates or make network calls. If you need display in another currency, inject a converter implementation into `convert_from_usd()` and keep exchange-rate policy outside the estimator.

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


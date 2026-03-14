# Python Commands Reference

Command and Python API reference for Novel AI.

## Main Interface Commands

```powershell
novelaibook tui
novelaibook gui
novelaibook web
```

Alternative module entrypoints:

```powershell
python -m novelai --interface tui
python -m novelai --interface gui
python -m novelai --interface web
python -m novelai --interface cli <command>
```

## Import and Scrape

```powershell
novelaibook import-document text my_book .\book\
novelaibook import-document epub my_book .\book.epub
novelaibook import-document pdf my_book .\book.pdf

novelaibook scrape-metadata syosetu_ncode n4423lw
novelaibook scrape-chapters syosetu_ncode n4423lw 1-3
```

## Translation

```powershell
novelaibook translate-chapters syosetu_ncode n4423lw 1-3
novelaibook translate-chapters syosetu_ncode n4423lw 1-3 --force
novelaibook retranslate-chapter syosetu_ncode n4423lw 2
```

## Glossary and OCR

```powershell
novelaibook glossary n4423lw list
novelaibook glossary n4423lw add "madougu" "magic device"
novelaibook glossary n4423lw review "madougu" approved
novelaibook glossary n4423lw extract --chapters all --max-terms 50
novelaibook glossary n4423lw extract --chapters all --mode llm --provider gemini --model gemini-3-flash-preview
novelaibook glossary n4423lw extract --chapters all --mode hybrid --prompt "Extract up to {max_terms} terms from: {text}"
novelaibook glossary n4423lw approve-all

novelaibook ocr n4423lw ingest all
novelaibook ocr n4423lw list-pending
novelaibook ocr n4423lw review 2 --text "Corrected OCR text"
novelaibook ocr n4423lw set-status 2 failed
```

## Export

```powershell
novelaibook export-epub n4423lw --format epub
novelaibook export-epub n4423lw --format html
novelaibook export-epub n4423lw --format md
```

Exports default to `novel_library/novels/<novel_id>/<format>/` unless `--output` is provided.

## Python API

### LLM Ops Preferences

```python
from novelai.runtime.container import container

prefs = container.preferences

# Endpoint profile
prefs.set_llm_endpoint_profile(
    "gemini-fast",
    provider="gemini",
    model="gemini-3-flash-preview",
    timeout=60,
    max_retries=2,
    concurrency=5,
)

# Per-step override
prefs.set_llm_step_config(
    "glossary_extraction",
    endpoint_profile="gemini-fast",
    temperature=0.2,
    kwargs={"top_p": 0.95},
)
```

### Bootstrap and Services

```python
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container

bootstrap()

storage = container.storage
orchestrator = container.orchestrator
translation = container.translation
```

### Inspect a Novel

```python
metadata = storage.load_metadata("n4423lw")
print(metadata.get("title"))

chapter = storage.load_chapter("n4423lw", "1")
translated = storage.load_translated_chapter("n4423lw", "1")
print(chapter.get("text", "")[:120])
print(bool(translated))
```

### Import a Document

```python
import asyncio

async def main() -> None:
    metadata = await orchestrator.import_document("epub", "my_book", "./book.epub")
    print(metadata.get("title"))

asyncio.run(main())
```

### Translate Chapters

```python
import asyncio

async def main() -> None:
    await orchestrator.translate_chapters(
        source_key="syosetu_ncode",
        novel_id="n4423lw",
        chapters="1-3",
    )

asyncio.run(main())
```

### Estimate Cost

```python
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions

comparison = compare_models(
    ["gpt-5.2", "gpt-5.4"],
    EstimationOptions(japanese_characters=10_000),
)
for estimate in comparison.estimates:
    print(estimate.model_name, estimate.estimated_total_cost_usd)
```

## Related Docs

- [../guides/GETTING_STARTED.md](../guides/GETTING_STARTED.md)
- [../guides/TUI_GUIDE.md](../guides/TUI_GUIDE.md)
- [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md)
- [../architecture/architecture.md](../architecture/architecture.md)

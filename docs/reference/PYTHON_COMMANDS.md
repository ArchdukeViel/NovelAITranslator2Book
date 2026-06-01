# Python Commands Reference

Command and Python API reference for the web-focused Novel AI backend.

## Backend Launcher

Run the FastAPI backend:

```powershell
novelaibook web
```

Run with live reload for local backend editing:

```powershell
novelaibook web --reload
```

Alternative module entrypoint:

```powershell
python -m novelai --interface web --reload
```

## Worker

Process one queued job and exit:

```powershell
novelaibook worker --once
```

Run continuously:

```powershell
novelaibook worker --poll-seconds 2
```

## Doctor

Check launcher wiring:

```powershell
novelaibook doctor
```

## Python API

### Bootstrap and Services

```python
from novelai.runtime.bootstrap import bootstrap
from novelai.runtime.container import container

bootstrap()

storage = container.storage
orchestrator = container.orchestrator
translation = container.translation
jobs = container.jobs
```

### Enqueue Jobs

```python
from novelai.core.platform import CrawlJobKind, TranslationJobKind

crawl_job = jobs.enqueue_crawl_job(
    novel_id="n4423lw",
    source_key="syosetu_ncode",
    kind=CrawlJobKind.METADATA,
)

translation_job = jobs.enqueue_translation_job(
    novel_id="n4423lw",
    kind=TranslationJobKind.BATCH,
    chapters="1-3",
    provider="gemini",
)
```

### Run One Job

```python
import asyncio

async def main() -> None:
    result = await container.job_runner.run_once()
    print(result)

asyncio.run(main())
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

Document import remains available as backend service logic and can be exposed through the web API:

```python
import asyncio

async def main() -> None:
    metadata = await orchestrator.import_document("epub", "my_book", "./book.epub")
    print(metadata.get("title"))

asyncio.run(main())
```

### Translate Chapters Directly

```python
import asyncio

async def main() -> None:
    await orchestrator.translate_chapters(
        source_key="syosetu_ncode",
        novel_id="n4423lw",
        chapters="1-3",
        provider_key="gemini",
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
- [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md)
- [../architecture/architecture.md](../architecture/architecture.md)

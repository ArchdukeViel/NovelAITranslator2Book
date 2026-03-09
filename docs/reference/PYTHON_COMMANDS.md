# Python Commands Reference

Complete guide to all CLI commands and programmatic usage of Novel AI.

---

## Command Line Interface (CLI)

### General Usage

```bash
novelaibook [COMMAND] [ARGUMENTS] [OPTIONS]
```

---

## Available Commands

### 1. TUI — Terminal User Interface

Interactive visual dashboard. Easiest way to use Novel AI.

```bash
novelaibook tui
```

See [../guides/TUI_GUIDE.md](../guides/TUI_GUIDE.md) for detailed walkthrough.

---

### 2. WEB — Start FastAPI Server

Launch the web API backend.

```bash
novelaibook web
```

---

### 3. SCRAPE-METADATA — Download Novel Metadata

Download metadata (title, author, chapter list) from a novel source.

```bash
# Basic usage
novelaibook scrape-metadata [SOURCE] [NOVEL_ID]

# Examples
novelaibook scrape-metadata syosetu_ncode n4423lw
novelaibook scrape-metadata kakuyomu 16818093001234567890
```

**Parameters**:
- `SOURCE`: Source adapter (`syosetu_ncode`, `kakuyomu`, `novel18_syosetu`)
- `NOVEL_ID`: Identifier on the source

**What it does**:
1. Fetches novel metadata from source website
2. Downloads chapter list with URLs
3. Saves to `novel_library/novels/<novel_id>/metadata.json`
4. Creates entry in `novel_library/novels/index.json`

---

### 4. SCRAPE-CHAPTERS — Download Raw Chapters

Download raw chapter text from the source.

```bash
# Fetch chapters 1–3
novelaibook scrape-chapters syosetu_ncode n4423lw 1-3

# Fetch specific chapters
novelaibook scrape-chapters syosetu_ncode n4423lw 1,3,5

# Fetch all chapters
novelaibook scrape-chapters syosetu_ncode n4423lw 1-*
```

**Chapter Selection Syntax**:
- `1-3`: Chapters 1 through 3
- `1,3,5`: Specific chapters
- `1-*`: All chapters
- `1-10;15-20`: Multiple ranges

**What it does**:
1. Downloads raw text from source URLs
2. Parses HTML content
3. Saves to `novel_library/novels/<novel_id>/raw/chapter_N.json`

---

### 5. TRANSLATE-CHAPTERS — Translate Chapter Text

Translate chapters using configured provider (OpenAI by default).

```bash
# Basic — uses settings from preferences
novelaibook translate-chapters syosetu_ncode n4423lw 1-3
```

**Parameters**:
- `SOURCE`: Source key (e.g., `syosetu_ncode`)
- `NOVEL_ID`: Novel ID (e.g., `n4423lw`)
- `CHAPTERS`: Chapter selection (e.g., `1-3`)

**What it does**:
1. Loads raw chapter text
2. Checks translation cache (avoid duplicates)
3. Uses retry logic with exponential backoff
4. Sends to translation provider API
5. Saves to `novel_library/novels/<novel_id>/translated/chapter_N.json`
6. Logs API usage to `novel_library/usage.json`
7. Caches result in `novel_library/translation_cache.json`

---

### 6. EXPORT-EPUB — Export to EPUB or PDF

Export translated chapters to EPUB or PDF format.

```bash
# Export to EPUB (default)
novelaibook export-epub n4423lw

# Export to PDF
novelaibook export-epub n4423lw --format pdf

# Export to custom location
novelaibook export-epub n4423lw --format epub --output /custom/path
```

**Parameters**:
- `NOVEL_ID`: Novel ID (e.g., `n4423lw`)
- `--format`: Format to export (`epub` or `pdf`, default: `epub`)
- `--output`: Output directory (default: `novel_library/novels/<novel_id>/<format>/`)

---

## Programmatic Usage (Python API)

Use Novel AI as a library in your own Python code.

### Setup

```python
from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.utils.logging import setup_logging, get_logger
import asyncio

setup_logging(log_level='INFO')
logger = get_logger(__name__)
bootstrap()

storage = container.storage
translation_svc = container.translation
orchestrator = container.orchestrator
```

---

### Example 1: Download and Translate a Novel

```python
async def translate_novel():
    novel_id = "n4423lw"

    # Load metadata
    metadata = storage.load_metadata(novel_id)
    if not metadata:
        logger.error("Metadata not found — scrape first")
        return

    logger.info(f"Title: {metadata.get('title')}")
    logger.info(f"Chapters: {len(metadata.get('chapters', []))}")

    # Load translated chapters
    chapters = metadata.get('chapters', [])[:5]
    for ch in chapters:
        ch_id = str(ch.get('id'))
        translated = storage.load_translated_chapter(novel_id, ch_id)
        if translated:
            logger.info(f"Chapter {ch_id}: {len(translated['text'])} chars")

asyncio.run(translate_novel())
```

---

### Example 2: Check Translation Cache

```python
from novelai.services.translation_cache import TranslationCache

cache = TranslationCache()

cached = cache.get(text="Hello, world!", provider="openai", model="gpt-5.2")
if cached:
    print(f"Cache hit: {cached}")
else:
    print("Cache miss")
```

---

### Example 3: Access Storage Service

```python
storage = container.storage

metadata = storage.load_metadata("n4423lw")
print(f"Novel: {metadata.get('title')}")

raw = storage.load_chapter("n4423lw", "chapter_1")
print(f"Raw text: {raw['text'][:100]}...")

storage.save_translated_chapter(
    novel_id="n4423lw",
    chapter_id="chapter_1",
    text="Translated text here...",
    provider="openai",
    model="gpt-5.2",
)
```

---

### Example 4: Create Checkpoint

```python
from novelai.services.checkpoint_manager import CheckpointManager
from novelai.core.chapter_state import ChapterState

checkpoint_mgr = CheckpointManager(storage)

await checkpoint_mgr.create_checkpoint(
    novel_id="n4423lw",
    chapter_id="chapter_1",
    state=ChapterState.FETCHED,
)

# Later, on failure:
await checkpoint_mgr.restore_checkpoint(
    novel_id="n4423lw",
    chapter_id="chapter_1",
)
```

---

### Example 5: Backup and Restore

```python
from novelai.services.backup_manager import BackupManager
from pathlib import Path

backup_mgr = BackupManager(Path("novel_library/backups"))

backup_info = await backup_mgr.create_full_backup(
    novel_id="n4423lw",
    source_dir=Path("novel_library/novels/n4423lw"),
)
logger.info(f"Backup created: {backup_info.backup_id}")

await backup_mgr.restore_backup(
    backup_id=backup_info.backup_id,
    target_dir=Path("novel_library/novels/n4423lw"),
    overwrite=True,
)
```

---

### Example 6: Cost Estimation

```python
from novelai.cost_estimator.compare import compare_models
from novelai.cost_estimator.models import EstimationOptions

options = EstimationOptions(
    japanese_characters=10_000,
    glossary_enabled=True,
    json_mode=False,
)
comparison = compare_models(["gpt-5.2", "gpt-5.4"], options)

for est in comparison.estimates:
    print(est.model_name, est.estimated_total_cost_usd)
```

---

## Usage Examples Summary

| Task | CLI Command | Programmatic |
|------|-------------|--------------|
| Interactive dashboard | `novelaibook tui` | — |
| Web server | `novelaibook web` | — |
| Download metadata | `novelaibook scrape-metadata` | `storage.load_metadata()` |
| Fetch chapters | `novelaibook scrape-chapters` | `storage.load_chapter()` |
| Translate | `novelaibook translate-chapters` | `translation_svc.translate()` |
| Export | `novelaibook export-epub` | `ExportService` |
| Create checkpoint | — | `CheckpointManager` |
| Backup | — | `BackupManager` |
| Cost estimate | `python -m novelai.cost_estimator.cli` | `compare_models()` |

---

## Common Issues

### Command not found

```bash
# Make sure you're in virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# And installed in dev mode
python -m pip install -e .
```

### API key not accepted

Check `.env` has the correct key. Get a new key from https://platform.openai.com/api-keys.

---

## Related Documentation

- [../guides/GETTING_STARTED.md](../guides/GETTING_STARTED.md) — Installation guide
- [../guides/TUI_GUIDE.md](../guides/TUI_GUIDE.md) — Terminal UI walkthrough
- [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md) — Data format reference
- [../architecture/architecture.md](../architecture/architecture.md) — System architecture

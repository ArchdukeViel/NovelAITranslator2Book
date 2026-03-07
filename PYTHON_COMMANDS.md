# Python Commands Reference

Complete guide to all CLI commands and programmatic usage of Novel AI.

---

## ðŸ–¥ï¸ Command Line Interface (CLI)

### General Usage

```bash
novelaibook [COMMAND] [ARGUMENTS] [OPTIONS]
```

---

## ðŸ“‹ Available Commands

### 1. TUI - Terminal User Interface

**Interactive visual interface** - Easiest way to use Novel AI.

```bash
novelaibook tui
```

See [TUI_GUIDE.md](TUI_GUIDE.md) for detailed walkthrough.

---

### 2. SCRAPE-METADATA - Download Novel Metadata

Download metadata (title, author, chapter list) from a novel source.

```bash
# Basic usage
novelaibook scrape-metadata [SOURCE] [NOVEL_ID]

# Examples:
novelaibook scrape-metadata syosetu_ncode n4423lw
novelaibook scrape-metadata syosetu_ncode n1234ab
```

**Parameters**:
- `SOURCE`: Source adapter to use (e.g., `syosetu_ncode`, `kakuyomu`)
- `NOVEL_ID`: Identifier on the source (e.g., novel code)

**What it does**:
1. Fetches novel metadata from source website
2. Downloads chapter list with URLs
3. Saves to `data/novels/{folder_name}/metadata.json`
4. Creates entry in `data/novels/index.json`

**Output**:
```
Scraped metadata for novel: Sword Art Online Progressive
- Title: ã‚½ãƒ¼ãƒ‰ã‚¢ãƒ¼ãƒˆãƒ»ã‚ªãƒ³ãƒ©ã‚¤ãƒ³ ãƒ—ãƒ­ã‚°ãƒ¬ãƒƒã‚·ãƒ–
- Chapters: 120
- Author: Reki Kawahara
- Saved to: data/novels/sword_art_online_progressive/metadata.json
```

---

### 3. FETCH - Download Raw Chapters

Download raw chapter text from the source.

```bash
# Fetch chapters 1-3
novelaibook fetch syosetu_ncode n4423lw 1-3

# Fetch chapters 1, 3, 5
novelaibook fetch syosetu_ncode n4423lw 1,3,5

# Fetch chapters 1 through 10
novelaibook fetch syosetu_ncode n4423lw 1-10

# Fetch all chapters
novelaibook fetch syosetu_ncode n4423lw 1-*
```

**Chapter Selection Syntax**:
- `1-3`: Chapters 1 through 3
- `1,3,5`: Specific chapters
- `1-*`: All chapters
- `1-10;15-20`: Multiple ranges

**What it does**:
1. Downloads raw text from source URLs
2. Parses HTML/content
3. Saves to `data/novels/{folder_name}/raw/chapter_N.json`
4. Computes content hash for deduplication

**Output**:
```
Fetching chapters 1-3 from syosetu_ncode:n4423lw
âœ“ chapter_1: 2,847 characters
âœ“ chapter_2: 3,102 characters
âœ“ chapter_3: 2,956 characters
Saved 3 chapters to data/novels/sword_art_online_progressive/raw/
```

---

### 4. TRANSLATE-CHAPTERS - Translate Chapter Text

Translate chapters using configured provider (OpenAI by default).

```bash
# Basic - uses default provider (OpenAI)
novelaibook translate-chapters syosetu_ncode n4423lw 1-3

# Specify provider
novelaibook translate-chapters syosetu_ncode n4423lw 1-3 \
  --provider openai

# Specify both provider and model
novelaibook translate-chapters syosetu_ncode n4423lw 1-3 \
  --provider openai --model gpt-4

# Translate with specific model
novelaibook translate-chapters syosetu_ncode n4423lw 1-3 \
  --model gpt-4-turbo
```

**Parameters**:
- `SOURCE`: Source key (e.g., `syosetu_ncode`)
- `NOVEL_ID`: Novel ID (e.g., `n4423lw`)
- `CHAPTERS`: Chapter selection (e.g., `1-3`)
- `--provider`: Translation provider (default: openai)
- `--model`: Model to use (default: gpt-3.5-turbo)

**Models Available**:
- `gpt-3.5-turbo`: Fast, cheaper (~$0.001 per 1k tokens)
- `gpt-4`: Better quality, slower (~$0.03 per 1k tokens)
- `gpt-4-turbo`: Balanced (~$0.01 per 1k tokens)

**What it does**:
1. Loads raw chapter text
2. Checks translation cache first (avoid duplicates)
3. Uses retry logic with exponential backoff (Phase 4)
4. Sends to translation provider API
5. Saves result to `data/novels/{folder_name}/translated/chapter_N.json`
6. Logs API usage to `data/usage.json`
7. Caches result in `data/translation_cache.json`

**Output**:
```
Translating 3 chapters for n4423lw (gpt-3.5-turbo)
âœ“ chapter_1: 2,847 â†’ 3,100 characters (cache miss, 2,500 tokens)
âœ“ chapter_2: 3,102 â†’ 3,320 characters (cache miss, 2,800 tokens)
âœ“ chapter_3: 2,956 â†’ 3,150 characters (cache hit, 0 tokens)
Total: 5,300 tokens (~$0.106)
```

---

### 5. EXPORT-EPUB - Export to EPUB or PDF

Export translated chapters to EPUB or PDF format.

```bash
# Export to EPUB (default)
novelaibook export-epub n4423lw

# Export to PDF
novelaibook export-epub n4423lw --format pdf

# Export to custom location
novelaibook export-epub n4423lw --format epub \
  --output /custom/path
```

**Parameters**:
- `NOVEL_ID`: Novel ID (e.g., `n4423lw`)
- `--format`: Format to export (epub or pdf, default: epub)
- `--output`: Output directory (default: saves to `data/novels/{folder}/epub/`)

**What it does**:
1. Loads metadata and translated chapters
2. Creates formatted document (EPUB/PDF)
3. Saves to:
   - Default: `data/novels/{folder_name}/epub/full_novel.epub`
   - Custom: `{output}/{novel_id}.epub`

**Output**:
```
Exporting 3 translated chapters to EPUB format
Building document structure...
Adding chapters...
Generating table of contents...
Exported EPUB to: data/novels/sword_art_online_progressive/epub/full_novel.epub
```

---

### 6. CHECK-USAGE - View API Usage Statistics

Display current API usage and cost estimates.

```bash
novelaibook check-usage
```

**What it shows**:
- Total API requests made
- Total tokens used
- Estimated cost in USD
- Breakdown by provider and model

**Output**:
```
API Usage Summary:
- Total requests: 42
- Total tokens: 125,000
- Estimated cost: $2.50 USD

Breakdown by provider:
- openai: 125,000 tokens ($2.50)

Breakdown by model:
- gpt-3.5-turbo: 80,000 tokens ($0.80)
- gpt-4: 45,000 tokens ($1.70)
```

---

### 7. LIST-SOURCES - Show Available Sources

List all available novel sources.

```bash
novelaibook list-sources
```

**Output**:
```
Available novel sources:
- syosetu_ncode (Syosetu): Japanese web novel platform
- kakuyomu (Kakuyomu): Japanese web novel platform
- example_source (Example): Example implementation
```

---

### 8. LIST-PROVIDERS - Show Available Providers

List all available translation providers.

```bash
novelaibook list-providers
```

**Output**:
```
Available translation providers:
- openai (OpenAI): GPT-3.5, GPT-4, GPT-4-Turbo
- dummy (Dummy): Mock provider for testing
```

---

## ðŸ”§ Programmatic Usage (Python API)

Use Novel AI as a library in your own Python code.

### Setup

```python
from novelai.app.bootstrap import bootstrap
from novelai.app.container import container
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.utils.logging import setup_logging, get_logger
import asyncio

# Setup
setup_logging(log_level='INFO')
logger = get_logger(__name__)
bootstrap()

# Get services from container
storage = container.storage
translation_svc = container.translation
orchestrator = container.orchestrator
```

---

### Example 1: Download and Translate a Novel

```python
async def translate_novel():
    """Download and translate a full novel."""
    
    novel_id = "n4423lw"
    
    # 1. Scrape metadata
    logger.info(f"Step 1: Scraping metadata for {novel_id}")
    metadata = storage.load_metadata(novel_id)
    if not metadata:
        logger.error("Metadata not found")
        return
    
    logger.info(f"  Title: {metadata.get('title')}")
    logger.info(f"  Chapters: {len(metadata.get('chapters', []))}")
    
    # 2. Get chapters
    chapters = metadata.get('chapters', [])[:5]  # First 5 chapters
    chapter_ids = [str(ch.get('id')) for ch in chapters]
    
    # 3. Translate chapters
    logger.info(f"Step 2: Translating {len(chapter_ids)} chapters")
    translated_chapters = []
    for ch_id in chapter_ids:
        translated = storage.load_translated_chapter(novel_id, ch_id)
        if translated:
            translated_chapters.append(translated)
            logger.info(f"  âœ“ Chapter {ch_id}: {len(translated['text'])} chars")
    
    logger.info(f"Successfully translated {len(translated_chapters)} chapters")

asyncio.run(translate_novel())
```

---

### Example 2: Check Translation Cache

```python
from novelai.services.translation_cache import TranslationCache

cache = TranslationCache()

# Check if text is cached
text = "Hello, world!"
cached = cache.get(text, provider="openai", model="gpt-3.5-turbo")

if cached:
    print(f"Cache hit: {cached}")
else:
    print("Cache miss - would need to call API")
    
# Store translation
cache.set(
    text,
    provider="openai",
    model="gpt-3.5-turbo",
    translation="ã“ã‚“ã«ã¡ã¯ã€ä¸–ç•Œï¼"
)
```

---

### Example 3: Access Storage Service

```python
from pathlib import Path

storage = container.storage

# Load metadata
metadata = storage.load_metadata("n4423lw")
print(f"Novel: {metadata.get('title')}")

# Load raw chapter
raw = storage.load_chapter("n4423lw", "chapter_1")
print(f"Raw text: {raw['text'][:100]}...")

# Save translated chapter
storage.save_translated_chapter(
    novel_id="n4423lw",
    chapter_id="chapter_1",
    text="Translated text here...",
    provider="openai",
    model="gpt-4"
)

# List all stored chapters
import json
novel_dir = storage._novel_dir("n4423lw")
raw_dir = novel_dir / "raw"
chapters = sorted(raw_dir.glob("*.json"))
print(f"Stored chapters: {len(chapters)}")
```

---

### Example 4: Create Checkpoint (Phase 4)

```python
from novelai.services.checkpoint_manager import CheckpointManager
from novelai.core.chapter_state import ChapterState

checkpoint_mgr = CheckpointManager(storage)

# Create checkpoint before risky operation
await checkpoint_mgr.create_checkpoint(
    novel_id="n4423lw",
    chapter_id="chapter_1",
    state=ChapterState.FETCHED,
)

# Do work...
try:
    # Translate chapter
    pass
except Exception as e:
    logger.error(f"Translation failed: {e}")
    
    # Restore from checkpoint
    await checkpoint_mgr.restore_checkpoint(
        novel_id="n4423lw",
        chapter_id="chapter_1"
    )
    logger.info("Restored from checkpoint")
```

---

### Example 5: Backup and Restore (Phase 4)

```python
from novelai.services.backup_manager import BackupManager
from pathlib import Path

backup_mgr = BackupManager(Path("data/backups"))

# Create full backup
backup_info = await backup_mgr.create_full_backup(
    novel_id="n4423lw",
    source_dir=Path("data/novels/sword_art_online_progressive")
)
logger.info(f"Backup created: {backup_info.backup_id}")

# List backups
backups = await backup_mgr.list_backups(novel_id="n4423lw")
for backup in backups:
    logger.info(f"  {backup.backup_id}: {backup.timestamp}")

# Restore backup
await backup_mgr.restore_backup(
    backup_id=backup_info.backup_id,
    target_dir=Path("data/novels/sword_art_online_progressive"),
    overwrite=True
)
```

---

### Example 6: Batch Translate with Retry (Phase 4)

```python
from novelai.utils.retry_decorator import retry_async, RetryConfig, RetryStrategy
from novelai.utils.batch_processor import BatchProcessor, BatchJobConfig

# Configure retry
retry_config = RetryConfig(
    max_attempts=5,
    strategy=RetryStrategy.EXPONENTIAL,
    initial_delay=1.0,
)

# Configure batch processing
batch_config = BatchJobConfig(
    batch_size=10,
    max_parallel_batches=3,
    retry_count=3,
)

# Define translation function with retry
@retry_async(retry_config)
async def translate_text(text: str) -> str:
    return await translation_svc.translate(text)

# Process in batches
processor = BatchProcessor(batch_config)
texts = ["Text 1", "Text 2", "Text 3", ...]
results = await processor.process_items(texts, translate_text)

# Check results
for batch_result in results:
    logger.info(f"Batch {batch_result.batch_idx}:")
    logger.info(f"  Succeeded: {len(batch_result.succeeded)}")
    logger.info(f"  Failed: {len(batch_result.failed)}")
```

---

### Example 7: Use Connection Pool (Phase 4)

```python
from novelai.utils.connection_pool import ConnectionPool, PoolConfig

# Create pool
async def create_api_connection():
    # Your connection factory
    return await get_openai_client()

pool_config = PoolConfig(
    min_size=5,
    max_size=20,
)
pool = ConnectionPool(create_api_connection, pool_config)
await pool.initialize()

# Use connection
conn = await pool.acquire()
try:
    result = await conn.translate("Hello")
finally:
    await pool.release(conn)

# Get stats
stats = pool.get_stats()
logger.info(f"Pool stats: {stats.active_connections} active connections")
```

---

### Example 8: Use Translation Cache (Phase 4)

```python
from novelai.utils.cache_optimizer import TranslationCacheOptimizer, AsyncCache, CacheConfig

# Create cache
cache_config = CacheConfig(
    max_entries=50000,
    ttl_seconds=7*86400,  # 7 days
)
cache = AsyncCache(cache_config)
await cache.initialize()

optimizer = TranslationCacheOptimizer(cache)

# Cache translation
await optimizer.cache_translation(
    source_text="Hello world",
    translated_text="ã“ã‚“ã«ã¡ã¯ä¸–ç•Œ",
    provider="openai"
)

# Retrieve from cache
result = await optimizer.get_translation(
    source_text="Hello world",
    provider="openai"
)

# Get cache stats
stats = cache.get_stats()
logger.info(f"Cache hit rate: {stats.hit_rate:.1%}")
```

---

## ðŸš€ Advanced Patterns

### Pattern 1: Full Resilience Stack

```python
async def resilient_translation():
    """Complete translation with all Phase 4 features."""
    
    retry_config = RetryConfig(max_attempts=5)
    batch_config = BatchJobConfig(batch_size=10)
    
    # Setup checkpoints
    await checkpoint_mgr.create_checkpoint(
        novel_id="n4423lw",
        chapter_id="ch1",
        state=ChapterState.FETCHED,
    )
    
    # Translate with batch + retry
    @retry_async(retry_config)
    async def translate(text):
        return await translation_svc.translate(text)
    
    results = await BatchProcessor(batch_config).process_items(
        texts,
        translate
    )
    
    # Backup on success
    if all(len(r.failed) == 0 for r in results):
        await backup_mgr.create_full_backup(
            novel_id="n4423lw",
            source_dir=novel_dir
        )
```

---

## ðŸ“Š Usage Examples Summary

| Task | Command | Programmatic |
|------|---------|--------------|
| Download metadata | `scrape-metadata` | `storage.load_metadata()` |
| Fetch chapters | `fetch` | `storage.load_chapter()` |
| Translate | `translate-chapters` | `translation_svc.translate()` |
| Export | `export-epub` | ExportService |
| Check costs | `check-usage` | UsageService |
| Create checkpoint | N/A | `checkpoint_mgr.create_checkpoint()` |
| Backup | N/A | `backup_mgr.create_full_backup()` |
| Batch with retry | N/A | `@retry_async()` + `BatchProcessor` |

---

## ðŸ†˜ Common Issues

### Issue: Command not found

```bash
# Make sure you're in virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# And installed in dev mode
python -m pip install -e .
```

### Issue: API key not accepted

```bash
# Check .env file has correct key
cat .env | grep OPENAI_API_KEY

# Get new key from: https://platform.openai.com/api-keys
```

### Issue: Out of memory on large batches

```bash
# Reduce batch size
novelaibook translate-chapters ... --batch-size 5
```

---

## ðŸ“– Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) - Installation guide
- [TUI_GUIDE.md](TUI_GUIDE.md) - Terminal UI walkthrough
- [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md) - Data format reference
- [PHASE_4_OPERATIONS.md](PHASE_4_OPERATIONS.md) - Resilience features
- [docs/architecture.md](docs/architecture.md) - System architecture



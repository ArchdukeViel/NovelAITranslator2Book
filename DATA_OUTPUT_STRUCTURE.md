# Data Folder Output Structure

Complete reference showing what data is stored in the `data/` folder during runtime with concrete examples.

## Quick Overview

```
data/
├── translation_cache.json          # Global translation cache
├── usage.json                       # API usage tracking
├── novels/
│   ├── index.json                   # Novel ID → folder mapping
│   └── {folder_name}/               # Single novel directory
│       ├── metadata.json            # Novel metadata
│       ├── raw/                     # Raw chapters from source
│       │   ├── chapter_1.json
│       │   ├── chapter_2.json
│       │   └── ...
│       ├── translated/              # Translated chapters (JSON)
│       │   ├── chapter_1.json
│       │   ├── chapter_2.json
│       │   └── ...
│       ├── epub/                    # EPUB exports
│       │   ├── full_novel.epub
│       │   └── chapter_1.epub
│       ├── pdf/                     # PDF exports
│       │   ├── full_novel.pdf
│       │   └── chapter_1.pdf
│       └── checkpoints/             # State snapshots (Phase 4)
│           ├── chapter_1_pre-translation.json
│           └── chapter_1_post-translation.json
└── backups/                         # Backup archives (Phase 4)
    ├── n4423lw__20260307_120000.tar.gz
    ├── n4423lw__20260306_180000.tar.gz
    └── manifest.json
```

---

## 1. Translation Cache (`data/translation_cache.json`)

Stores previously translated text to avoid re-translating identical content.

### Purpose
- Avoid duplicate API calls for same text
- Reduce translation costs
- Speed up repeated translations

### Example Content

```json
{
  "abc123def456xyz...(sha256_hash)": "こんにちは世界",
  "fed789ghi012jkl...(sha256_hash)": "This is a translated chapter about...",
  "xyz456abc789def...(sha256_hash)": "もう一つ別の翻訳文"
}
```

### Cache Key Format
```
key = SHA256(provider:model:source_text)
```

**Example**: For OpenAI GPT-4 translating "Hello world":
```
SHA256("openai:gpt-4:Hello world") = "abc123def456xyz..."
```

---

## 2. API Usage Tracking (`data/usage.json`)

Logs every translation request for cost estimation and quota management.

### Purpose
- Track tokens used
- Calculate costs
- Monitor provider usage
- Quota enforcement

### Example Content

```json
[
  {
    "timestamp": "2026-03-07T12:30:45Z",
    "novel_id": "n4423lw",
    "chapter_id": "chapter_1",
    "provider": "openai",
    "model": "gpt-4",
    "tokens": 2847,
    "estimated_cost_usd": 0.0854,
    "status": "success"
  },
  {
    "timestamp": "2026-03-07T12:35:12Z",
    "novel_id": "n4423lw",
    "chapter_id": "chapter_2",
    "provider": "openai",
    "model": "gpt-4",
    "tokens": 3102,
    "estimated_cost_usd": 0.0931,
    "status": "success"
  },
  {
    "timestamp": "2026-03-07T12:40:05Z",
    "novel_id": "n4423lw",
    "chapter_id": "chapter_3",
    "provider": "openai",
    "model": "gpt-4",
    "tokens": 0,
    "estimated_cost_usd": 0,
    "status": "cache_hit"
  }
]
```

### Fields
- `timestamp`: ISO 8601 UTC timestamp
- `novel_id`: Novel identifier (e.g., "n4423lw")
- `chapter_id`: Chapter identifier (e.g., "chapter_1")
- `provider`: Translation provider (e.g., "openai")
- `model`: Model used (e.g., "gpt-4", "gpt-3.5-turbo")
- `tokens`: Tokens used (0 for cache hits)
- `estimated_cost_usd`: Calculated cost
- `status`: "success", "cache_hit", "error", "retry"

---

## 3. Novel Index (`data/novels/index.json`)

Maps novel IDs to their storage folder names.

### Purpose
- Track folder name changes
- Support novel title updates
- Prevent name collisions

### Example Content

```json
{
  "n4423lw": {
    "folder_name": "sword_art_online_progressive",
    "updated_at": "2026-03-07T12:00:00Z"
  },
  "n1234ab": {
    "folder_name": "re_zero_starting_life_in_another_world",
    "updated_at": "2026-03-07T11:30:00Z"
  }
}
```

---

## 4. Novel Metadata (`data/novels/{folder_name}/metadata.json`)

Stores novel information scraped from the source.

### Purpose
- Store novel title, author, description
- Track chapter list and metadata
- Record scraping timestamp

### Example Content

```json
{
  "novel_id": "n4423lw",
  "title": "ソードアート・オンライン プログレッシブ",
  "translated_title": "Sword Art Online Progressive",
  "author": "Reki Kawahara",
  "description": "The continuation of the SAO Progressive storyline...",
  "cover_url": "https://example.com/cover.jpg",
  "source_key": "syosetu",
  "source_url": "https://ncode.syosetu.com/n4423lw/",
  "chapters": [
    {
      "id": "chapter_1",
      "title": "First Chapter",
      "url": "https://ncode.syosetu.com/n4423lw/1/"
    },
    {
      "id": "chapter_2",
      "title": "Second Chapter",
      "url": "https://ncode.syosetu.com/n4423lw/2/"
    }
  ],
  "total_chapters": 120,
  "status": "ongoing",
  "scraped_at": "2026-03-07T11:55:00Z",
  "folder_name": "sword_art_online_progressive"
}
```

---

## 5. Raw Chapter (`data/novels/{folder_name}/raw/chapter_1.json`)

Stores the original scraped text from the source with metadata.

### Purpose
- Preserve original text
- Track source information
- Enable re-processing

### Example Content

```json
{
  "id": "chapter_1",
  "title": "Beginning",
  "source_key": "syosetu",
  "source_url": "https://ncode.syosetu.com/n4423lw/1/",
  "scraped_at": "2026-03-07T12:00:00Z",
  "text": "少女はしばらく空を見つめた。\n新しい世界。それがアインクラッドという名の浮遊城塞だ。\n...\n[Full raw Japanese text here]\n..."
}
```

### Fields
- `id`: Chapter identifier
- `title`: Chapter title from source
- `source_key`: Source adapter name (e.g., "syosetu")
- `source_url`: URL of source chapter
- `scraped_at`: When it was scraped
- `text`: Original text in source language

---

## 6. Translated Chapter (`data/novels/{folder_name}/translated/chapter_1.json`)

Stores the translated output with provider metadata.

### Purpose
- Store final translated text
- Track which provider/model translated it
- Support re-translation with different models

### Example Content

```json
{
  "id": "chapter_1",
  "provider": "openai",
  "model": "gpt-4",
  "translated_at": "2026-03-07T12:05:30Z",
  "text": "The girl stared at the sky for a while.\nA new world. A floating castle stronghold named Aincrad.\n...\n[Full translated English text here]\n..."
}
```

### Fields
- `id`: Chapter identifier
- `provider`: Translation provider (e.g., "openai", "claude")
- `model`: Model used (e.g., "gpt-4", "gpt-3.5-turbo")
- `translated_at`: When translation completed
- `text`: Translated text

---

## 7. Checkpoint Snapshots (`data/novels/{folder_name}/checkpoints/chapter_1_*`)

### Purpose (Phase 4 Feature)
- Save chapter state at key points
- Enable rollback to previous states
- Support recovery from failures

### Checkpoint Naming
```
{chapter_id}__{checkpoint_name}__{timestamp}.json
```

**Examples**:
- `chapter_1__pre-translation__20260307_120000.json`
- `chapter_1__post-translation__20260307_120530.json`
- `chapter_1__segment-complete__20260307_120100.json`

### Example Content

```json
{
  "chapter_id": "chapter_1",
  "checkpoint_id": "checkpoint_20260307_120000",
  "checkpoint_name": "pre-translation",
  "timestamp": "2026-03-07T12:00:00Z",
  "state": "SEGMENTS_CREATED",
  "error": null,
  "progress": 0.0,
  "data": {
    "raw_chapter": {
      "text": "少女は...",
      "source_url": "https://..."
    },
    "segments": [
      { "segment_id": 1, "text": "少女はしばらく..." },
      { "segment_id": 2, "text": "新しい世界。..." }
    ],
    "state_metadata": {
      "created_by": "segment_stage",
      "duration_seconds": 2.5
    }
  }
}
```

---

## 8. Backup Archives (`data/backups/`)

### Purpose (Phase 4 Feature)
- Full novel backup with compression
- Disaster recovery
- Historical versions

### Backup Manifest (`data/backups/manifest.json`)

```json
{
  "backups": [
    {
      "backup_id": "n4423lw__20260307_120000",
      "novel_id": "n4423lw",
      "timestamp": "2026-03-07T12:00:00Z",
      "size_bytes": 2048576,
      "compressed": true,
      "files_count": 145,
      "checksum": "sha256_hash_here"
    },
    {
      "backup_id": "n4423lw__20260306_180000",
      "novel_id": "n4423lw",
      "timestamp": "2026-03-06T18:00:00Z",
      "size_bytes": 1998765,
      "compressed": true,
      "files_count": 142,
      "checksum": "sha256_hash_here"
    }
  ]
}
```

### Archive Files
- `n4423lw__20260307_120000.tar.gz` (compressed backup)
- Contains entire novel directory:
  - `metadata.json`
  - `raw/` (all chapters)
  - `translated/` (all translations)
  - `checkpoints/` (all snapshots)

---

## 9. Export Formats (`data/novels/{folder_name}/epub/` and `/pdf/`)

Stored alongside original data for easy access and web serving.

### EPUB Exports Structure

```
data/novels/{folder_name}/epub/
├── full_novel.epub                 # Complete novel in EPUB format
├── chapter_1.epub                  # Individual chapter (optional)
├── chapter_2.epub
└── ...
```

### PDF Exports Structure

```
data/novels/{folder_name}/pdf/
├── full_novel.pdf                  # Complete novel in PDF format
├── chapter_1.pdf                   # Individual chapter (optional)
├── chapter_2.pdf
└── ...
```

### Web API Serving
Web server serves these files directly from `/novels/{folder_name}/` without duplication.

---

## Real-World Example: Full Translation Workflow

### Step 1: User requests novel `n4423lw`

**Files created:**
- `data/novels/index.json` - maps n4423lw → sword_art_online_progressive
- `data/novels/sword_art_online_progressive/metadata.json` - novel info

### Step 2: Chapters are fetched (3 chapters)

**Files created:**
```
data/novels/sword_art_online_progressive/raw/
├── chapter_1.json    (scraped Japanese text)
├── chapter_2.json    (scraped Japanese text)
└── chapter_3.json    (scraped Japanese text)
```

**Updated:**
- `usage.json` - 3 scrape records added

### Step 3: Translation begins (Chapter 1)

**Files created:**
- `data/novels/sword_art_online_progressive/checkpoints/chapter_1__fetch-complete__20260307_120000.json`

### Step 4: Translation completes

**Files created:**
- `data/novels/sword_art_online_progressive/translated/chapter_1.json` (English)
- `data/novels/sword_art_online_progressive/checkpoints/chapter_1__translation-complete__20260307_120530.json`

**Updated:**
- `usage.json` - translation record added
- `translation_cache.json` - cache entries added for segments

### Step 5: Backup is created

**Files created:**
- `data/backups/n4423lw__20260307_120530.tar.gz` (compressed archive)
- `data/backups/manifest.json` - backup tracked

### Final State

```
data/
├── translation_cache.json (100+ entries)
├── usage.json (10+ records)
├── novels/
│   ├── index.json
│   └── sword_art_online_progressive/
│       ├── metadata.json
│       ├── raw/
│       │   ├── chapter_1.json
│       │   ├── chapter_2.json
│       │   └── chapter_3.json
│       ├── translated/
│       │   └── chapter_1.json (only 1 translated)
│       ├── epub/
│       │   └── (empty - not yet exported)
│       ├── pdf/
│       │   └── (empty - not yet exported)
│       └── checkpoints/
│           ├── chapter_1__fetch-complete__....json
│           └── chapter_1__translation-complete__....json
└── backups/
    ├── n4423lw__20260307_120530.tar.gz
    └── manifest.json
```

---

## Storage Estimates

### Per Novel (4 chapters, 5000 words each)

| Component | Size |
|-----------|------|
| Metadata | ~5 KB |
| Raw chapters (JSON) | ~200 KB |
| Translated chapters (JSON) | ~220 KB |
| Checkpoints (per chapter) | ~50 KB × 4 = 200 KB |
| **Subtotal** | **~625 KB** |

### Global Cache

| Component | Size |
|-----------|------|
| Translation cache (1000 entries) | ~100 KB |
| Usage tracking (100 records) | ~50 KB |
| **Subtotal** | **~150 KB** |

### Backup

| Component | Size |
|-----------|------|
| Compressed backup (tar.gz) | ~200-300 KB per novel |
| Manifests | ~5 KB |

### Scaling (100 novels)

```
100 novels × 625 KB     = 62.5 MB
Global cache            = ~150 KB
Backups (5 per novel)   = 100-150 MB
─────────────────────────────────
Total                   = ~162-212 MB
```

---

## Best Practices

### Cleanup Strategy
- Keep last 5 backups per novel
- Keep backups within last 30 days
- Archive/delete old usage records quarterly

### Monitoring
- Check `usage.json` size (delete old records if >10MB)
- Monitor `translation_cache.json` (cache hit rate should be >20%)
- Track backup directory size

### Restoration
```json
// Example: Restore novel from backup
{
  "backup_id": "n4423lw__20260307_120530",
  "target_location": "data/novels/sword_art_online_progressive",
  "overwrite": true
}
```

---

## API Integration Example

### Fetch novel metadata via web API
```
GET /api/novels/n4423lw/metadata
Response: data/novels/sword_art_online_progressive/metadata.json
```

### Fetch translated chapter
```
GET /api/novels/n4423lw/chapters/1
Response: data/novels/sword_art_online_progressive/translated/chapter_1.json
```

### Download EPUB export
```
GET /api/novels/n4423lw/exports/epub
Response: data/novels/sword_art_online_progressive/epub/full_novel.epub
```

### Download PDF export
```
GET /api/novels/n4423lw/exports/pdf
Response: data/novels/sword_art_online_progressive/pdf/full_novel.pdf
```

### Get usage stats
```
GET /api/usage/summary
Response: Calculated from data/usage.json
{
  "total_requests": 125,
  "total_tokens": 450000,
  "estimated_cost_usd": 13.50
}
```

---

## Summary

The `data/` folder automatically grows as the system operates:

1. **Novels** store raw chapters, translated text, exports, and metadata in one unified directory
2. **Exports** (EPUB, PDF) stored alongside translations - no redundancy
3. **Cache** accelerates repeated translations
4. **Usage** tracks costs and quota
5. **Checkpoints** enable recovery from failures (Phase 4)
6. **Backups** provide disaster recovery (Phase 4)

All data is:
- ✅ Timestamped (ISO 8601 UTC)
- ✅ Organized by novel ID
- ✅ Single source of truth (no redundant /web folder)
- ✅ Portable (JSON + tar.gz)
- ✅ Recoverable (backups + checkpoints)
- ✅ Queryable (structured format)
- ✅ Ready for web serving (no copying needed)

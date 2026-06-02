# Data Output Structure

Complete reference for what data is stored in `storage/novel_library/` during runtime, with concrete examples.

## Quick Overview

```
storage/novel_library/
â”œâ”€â”€ preferences.json                 # Provider, model, API key
â”œâ”€â”€ translation_cache.json           # Cached translation results
â”œâ”€â”€ usage.json                       # API usage tracking
â””â”€â”€ novels/
    â”œâ”€â”€ index.json                   # Novel ID â†’ folder mapping
    â””â”€â”€ <novel_id>/                  # Single novel directory
        â”œâ”€â”€ metadata.json            # Novel metadata from source
        â”œâ”€â”€ raw/                     # Raw chapters from source
        â”‚   â”œâ”€â”€ chapter_1.json
        â”‚   â””â”€â”€ chapter_2.json
        â”œâ”€â”€ translated/              # Translated chapters (JSON)
        â”‚   â”œâ”€â”€ chapter_1.json
        â”‚   â””â”€â”€ chapter_2.json
        â”œâ”€â”€ epub/                    # EPUB exports
        â”‚   â””â”€â”€ full_novel.epub
        â”œâ”€â”€ assets/                  # Chapter images
        â”‚   â””â”€â”€ images/
        â”‚       â””â”€â”€ <chapter_id>/
        â””â”€â”€ checkpoints/             # State snapshots
            â””â”€â”€ chapter_1_post-translation.json
```

---

## 1. Preferences (`storage/novel_library/preferences.json`)

Stores the active provider, model, and API key.

### Example Content

```json
{
  "provider": "openai",
  "model": "gpt-5.2",
  "api_key": "sk-..."
}
```

---

## 2. Translation Cache (`storage/novel_library/translation_cache.json`)

Stores previously translated text to avoid re-translating identical content.

### Cache Key Format
```
key = SHA256(provider:model:source_text)
```

### Example Content

```json
{
  "abc123def456...": "The girl gazed at the sky.",
  "fed789ghi012...": "A new world appeared before them."
}
```

---

## 3. API Usage Tracking (`storage/novel_library/usage.json`)

Logs every translation request for cost estimation and quota management.

### Example Content

```json
[
  {
    "timestamp": "2026-03-07T12:30:45Z",
    "novel_id": "n4423lw",
    "chapter_id": "chapter_1",
    "provider": "openai",
    "model": "gpt-5.2",
    "tokens": 2847,
    "estimated_cost_usd": 0.0854,
    "status": "success"
  },
  {
    "timestamp": "2026-03-07T12:40:05Z",
    "novel_id": "n4423lw",
    "chapter_id": "chapter_3",
    "provider": "openai",
    "model": "gpt-5.2",
    "tokens": 0,
    "estimated_cost_usd": 0,
    "status": "cache_hit"
  }
]
```

### Fields
- `timestamp`: ISO 8601 UTC timestamp
- `novel_id`: Novel identifier
- `chapter_id`: Chapter identifier
- `provider`: Translation provider (e.g., "openai")
- `model`: Model used (e.g., "gpt-5.2", "gpt-5.4")
- `tokens`: Tokens used (0 for cache hits)
- `estimated_cost_usd`: Calculated cost
- `status`: "success", "cache_hit", "error", "retry"

---

## 4. Novel Index (`storage/novel_library/novels/index.json`)

Maps novel IDs to their storage folder names.

### Example Content

```json
{
  "n4423lw": {
    "folder_name": "sword_art_online_progressive",
    "updated_at": "2026-03-07T12:00:00Z"
  }
}
```

---

## 5. Novel Metadata (`storage/novel_library/novels/<novel_id>/metadata.json`)

Stores novel information scraped from the source.

### Example Content

```json
{
  "novel_id": "n4423lw",
  "title": "ã‚½ãƒ¼ãƒ‰ã‚¢ãƒ¼ãƒˆãƒ»ã‚ªãƒ³ãƒ©ã‚¤ãƒ³ ãƒ—ãƒ­ã‚°ãƒ¬ãƒƒã‚·ãƒ–",
  "translated_title": "Sword Art Online Progressive",
  "author": "Reki Kawahara",
  "source_key": "syosetu",
  "source_url": "https://ncode.syosetu.com/n4423lw/",
  "chapters": [
    {
      "id": "chapter_1",
      "title": "First Chapter",
      "url": "https://ncode.syosetu.com/n4423lw/1/"
    }
  ],
  "total_chapters": 120,
  "status": "ongoing",
  "scraped_at": "2026-03-07T11:55:00Z"
}
```

---

## 6. Raw Chapter (`storage/novel_library/novels/<novel_id>/raw/chapter_1.json`)

Stores the original scraped text from the source.

### Example Content

```json
{
  "id": "chapter_1",
  "title": "Beginning",
  "source_key": "syosetu",
  "source_url": "https://ncode.syosetu.com/n4423lw/1/",
  "scraped_at": "2026-03-07T12:00:00Z",
  "text": "å°‘å¥³ã¯ã—ã°ã‚‰ãç©ºã‚’è¦‹ã¤ã‚ãŸã€‚\næ–°ã—ã„ä¸–ç•Œã€‚ãã‚ŒãŒã‚¢ã‚¤ãƒ³ã‚¯ãƒ©ãƒƒãƒ‰ã¨ã„ã†åã®æµ®éŠåŸŽå¡žã ã€‚"
}
```

---

## 7. Translated Chapter (`storage/novel_library/novels/<novel_id>/translated/chapter_1.json`)

Stores the translated output with provider metadata.

### Example Content

```json
{
  "id": "chapter_1",
  "provider": "openai",
  "model": "gpt-5.2",
  "translated_at": "2026-03-07T12:05:30Z",
  "text": "The girl stared at the sky for a while.\nA new world. A floating castle stronghold named Aincrad."
}
```

---

## 8. Checkpoint Snapshots (`storage/novel_library/novels/<novel_id>/checkpoints/`)

State snapshots for recovery from translation failures.

### Example Content

```json
{
  "chapter_id": "chapter_1",
  "checkpoint_name": "pre-translation",
  "timestamp": "2026-03-07T12:00:00Z",
  "state": "SEGMENTS_CREATED",
  "data": {
    "segments": [
      { "segment_id": 1, "text": "å°‘å¥³ã¯ã—ã°ã‚‰ã..." },
      { "segment_id": 2, "text": "æ–°ã—ã„ä¸–ç•Œã€‚..." }
    ]
  }
}
```

---

## 9. EPUB Exports (`storage/novel_library/novels/<novel_id>/epub/`)

EPUB files generated from translated chapters.

```
epub/
â””â”€â”€ full_novel.epub
```

Inline chapter images are embedded from `assets/images/` so the EPUB does not depend on the source site still serving images.

---

## 10. Chapter Images (`storage/novel_library/novels/<novel_id>/assets/images/`)

Images downloaded during scraping, organized per chapter:

```
assets/
â””â”€â”€ images/
    â””â”€â”€ chapter_1/
        â”œâ”€â”€ img_001.jpg
        â””â”€â”€ img_002.png
```

Chapter JSON stores an image manifest with the original URL, placeholder tag, and local asset path.

---

## Real-World Example: Full Translation Workflow

### Step 1: Scrape metadata

**Created**:
- `storage/novel_library/novels/index.json`
- `storage/novel_library/novels/n4423lw/metadata.json`

### Step 2: Fetch 3 chapters

**Created**:
```
storage/novel_library/novels/n4423lw/raw/
â”œâ”€â”€ chapter_1.json
â”œâ”€â”€ chapter_2.json
â””â”€â”€ chapter_3.json
```

### Step 3: Translate chapter 1

**Created**:
- `storage/novel_library/novels/n4423lw/translated/chapter_1.json`
- `storage/novel_library/novels/n4423lw/checkpoints/chapter_1_post-translation.json`

**Updated**:
- `storage/novel_library/usage.json`
- `storage/novel_library/translation_cache.json`

### Step 4: Export

**Created**:
- `storage/novel_library/novels/n4423lw/epub/full_novel.epub`

---

## Storage Estimates

### Per Novel (4 chapters, 5000 words each)

| Component | Size |
|-----------|------|
| Metadata | ~5 KB |
| Raw chapters (JSON) | ~200 KB |
| Translated chapters (JSON) | ~220 KB |
| Checkpoints (per chapter) | ~50 KB Ã— 4 = 200 KB |
| **Subtotal** | **~625 KB** |

### Global

| Component | Size |
|-----------|------|
| Translation cache (1000 entries) | ~100 KB |
| Usage tracking (100 records) | ~50 KB |

### Scaling (100 novels)

```
100 novels Ã— 625 KB = ~62.5 MB
Global cache         = ~150 KB
Total                = ~63 MB
```

---

## API Integration

The web server (`novelaibook web`) serves data from `storage/novel_library/`:

```
GET /api/novels/n4423lw/metadata
GET /api/novels/n4423lw/chapters/1
GET /api/novels/n4423lw/exports/epub
```


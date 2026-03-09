# Getting Started with Novel AI

Step-by-step guide to install, configure, and run Novel AI for the first time.

---

## Prerequisites

- **Python 3.13+** (check with `python --version`)
- **Git** (for cloning the repository)
- **API Keys** (OpenAI or other provider for translations)

---

## Installation Steps

### Step 1: Clone Repository

```bash
git clone <repo-url>
cd "Novel AI"
```

### Step 2: Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
# Install package in development mode (includes test deps)
python -m pip install -e ".[dev]"
```

### Step 4: Configure Environment

```bash
# Copy example configuration
copy .env.example .env

# Edit .env with your API keys
# Required:
#   PROVIDER_OPENAI_API_KEY=sk-...
# Optional:
#   NOVEL_LIBRARY_DIR=./novel_library (default)
#   TRANSLATION_TARGET_LANGUAGE=English (default)
#   LOG_LEVEL=INFO (default)
```

**Where to find API keys**:
- **OpenAI**: https://platform.openai.com/api-keys
  1. Sign in to OpenAI
  2. Go to API keys
  3. Click "Create new secret key"
  4. Copy to `.env` file

---

## Verify Installation

Run a quick verification:

```bash
python -c "
from novelai.app.bootstrap import bootstrap
from novelai.utils.logging import setup_logging, get_logger

setup_logging(log_level='INFO', use_json=False)
logger = get_logger('verification')

print('NOVEL AI VERIFICATION')
bootstrap()
logger.info('Bootstrap successful')
print('INSTALLATION COMPLETE')
print()
print('Next steps:')
print('  1. Run TUI: novelaibook tui')
print('  2. Or use CLI: novelaibook scrape-metadata syosetu_ncode n4423lw')
print('  3. See docs/reference/PYTHON_COMMANDS.md for all commands')
print('  4. See docs/guides/TUI_GUIDE.md for terminal UI walkthrough')
"
```

---

## First Run: Using the TUI

The easiest way to get started:

```bash
novelaibook tui
```

You'll see a Rich dashboard with 6 actions. See [TUI_GUIDE.md](TUI_GUIDE.md) for the full walkthrough.

---

## First Run: Using CLI

If you prefer command line:

### 1. Download Novel Metadata

```bash
# For Syosetu (Japanese web novel site)
novelaibook scrape-metadata syosetu_ncode n4423lw
```

### 2. Fetch Chapters

```bash
# Fetch first 3 chapters
novelaibook scrape-chapters syosetu_ncode n4423lw 1-3
```

Chapters stored in: `novel_library/novels/<novel_id>/raw/`

### 3. Translate Chapters

```bash
# Translate using default provider (OpenAI)
novelaibook translate-chapters syosetu_ncode n4423lw 1-3
```

Translations stored in: `novel_library/novels/<novel_id>/translated/`

### 4. Export to EPUB

```bash
# Export to EPUB (saved to novel_library/novels/<novel_id>/epub/)
novelaibook export-epub n4423lw --format epub
```

---

## Data Directory Structure

After first run, your `novel_library/` folder looks like:

```
novel_library/
├── preferences.json
├── translation_cache.json
├── usage.json
└── novels/
    ├── index.json
    └── <novel_id>/
        ├── metadata.json
        ├── raw/
        │   ├── chapter_1.json
        │   └── chapter_2.json
        ├── translated/
        │   ├── chapter_1.json
        │   └── chapter_2.json
        └── epub/
            └── full_novel.epub
```

See [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md) for full details.

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'novelai'"

**Solution**: Make sure you installed in development mode:
```bash
python -m pip install -e .
```

### Issue: "PROVIDER_OPENAI_API_KEY not found"

**Solution**:
1. Create `.env` file from `.env.example`
2. Add your API key to `.env`
3. Restart the application

### Issue: "Connection timeout" when fetching chapters

**Solution**:
- Check internet connection
- The source website might be temporarily unavailable
- Try again in a few moments

---

## Next Steps

1. **Learn TUI**: See [TUI_GUIDE.md](TUI_GUIDE.md)
2. **Learn CLI**: See [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md)
3. **Understand Architecture**: See [../architecture/architecture.md](../architecture/architecture.md)
4. **Learn Data Format**: See [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md)

---

## Tips

### Batch Processing
Translate multiple chapters at once for efficiency:
```bash
novelaibook translate-chapters syosetu_ncode n4423lw 1-10
```

### Custom Glossary
Use glossary entries for recurring terminology:
```python
from novelai.prompts import build_translation_request

request = build_translation_request(
    text="魔導具が光を放った。",
    source_language="Japanese",
    target_language="English",
    glossary_entries=[
        {"source": "魔導具", "target": "magic device"},
    ],
    style_preset="fantasy",
)
```

### Enable Debug Logging
Set `LOG_LEVEL=DEBUG` in `.env` for verbose output.

---

## Configuration Reference

All settings in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `PROVIDER_OPENAI_API_KEY` | (required for OpenAI) | Your OpenAI API key |
| `NOVEL_LIBRARY_DIR` | ./novel_library | Where to store novels |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `TRANSLATION_TARGET_LANGUAGE` | English | Default target language |


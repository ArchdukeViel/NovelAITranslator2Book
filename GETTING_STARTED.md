# Getting Started with Novel AI

Step-by-step guide to install, configure, and run Novel AI for the first time.

---

## ðŸ“‹ Prerequisites

- **Python 3.13+** (check with `python --version`)
- **Git** (for cloning the repository)
- **API Keys** (OpenAI or other provider for translations)
- **Disk Space**: At least 1GB for initial setup and sample data

---

## ðŸ”§ Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/Novel-AI.git
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
# Install package in development mode
python -m pip install -e .

# Install test dependencies (optional)
python -m pip install pytest pytest-asyncio
```

### Step 4: Configure Environment

```bash
# Copy example configuration
copy .env.example .env

# Edit .env with your API keys
# Required:
#   OPENAI_API_KEY=sk-...
# Optional:
#   OPENAI_MODEL=gpt-4 (default: gpt-3.5-turbo)
#   DATA_DIR=./data (default)
#   LOG_LEVEL=INFO (default)
```

**Where to find API keys**:
- **OpenAI**: https://platform.openai.com/api-keys
  1. Sign in to OpenAI
  2. Go to API keys
  3. Click "Create new secret key"
  4. Copy to `.env` file

---

## âœ… Verify Installation

Run verification script to check all systems:

```bash
python -c "
import asyncio
from novelai.app.bootstrap import bootstrap
from novelai.utils.logging import setup_logging, get_logger

setup_logging(log_level='INFO', use_json=False)
logger = get_logger('verification')

print('=' * 60)
print('NOVEL AI VERIFICATION')
print('=' * 60)

# Test imports
logger.info('âœ“ Core imports working')

# Test bootstrap
bootstrap()
logger.info('âœ“ Bootstrap successful')

# Test logging
logger.debug('Debug level active')
logger.info('Info level active')
logger.warning('Warning level active')

print('=' * 60)
print('INSTALLATION COMPLETE')
print('=' * 60)
print()
print('Next steps:')
print('  1. Run TUI: novelaibook tui')
print('  2. Or use CLI: novelaibook scrape-metadata syosetu_ncode n4423lw')
print('  3. See PYTHON_COMMANDS.md for all commands')
print('  4. See TUI_GUIDE.md for terminal UI walkthrough')
"
```

---

## ðŸŽ® First Run: Using the TUI

The easiest way to get started:

```bash
novelaibook tui
```

You'll see the terminal user interface (TUI) with menus. See [TUI_GUIDE.md](TUI_GUIDE.md) for detailed walkthrough.

---

## ðŸ“ First Run: Using CLI

If you prefer command line:

### 1. Check Available Sources

```bash
novelaibook list-sources
```

### 2. Download Novel Metadata

```bash
# For Syosetu (Japanese web novel site)
novelaibook scrape-metadata syosetu_ncode n4423lw
```

This downloads metadata for novel `n4423lw` (Sword Art Online Progressive).

### 3. Fetch Chapters

```bash
# Fetch first 3 chapters
novelaibook fetch syosetu_ncode n4423lw 1-3
```

Chapters stored in: `data/novels/sword_art_online_progressive/raw/`

### 4. Translate Chapters

```bash
# Translate using default provider (OpenAI)
novelaibook translate-chapters syosetu_ncode n4423lw 1-3
```

Translations stored in: `data/novels/sword_art_online_progressive/translated/`

### 5. Export to EPUB or PDF

```bash
# Export to EPUB (saved to data/novels/{folder}/epub/)
novelaibook export-epub n4423lw --format epub

# Export to PDF (saved to data/novels/{folder}/pdf/)
novelaibook export-epub n4423lw --format pdf
```

---

## ðŸ“‚ Data Directory Structure

After first run, your `data/` folder looks like:

```
data/
â”œâ”€â”€ translation_cache.json          # Cached translations
â”œâ”€â”€ usage.json                       # API usage statistics
â””â”€â”€ novels/
    â”œâ”€â”€ index.json
    â””â”€â”€ sword_art_online_progressive/
        â”œâ”€â”€ metadata.json            # Novel info
        â”œâ”€â”€ raw/                     # Raw chapters
        â”‚   â”œâ”€â”€ chapter_1.json
        â”‚   â””â”€â”€ chapter_2.json
        â”œâ”€â”€ translated/              # Translated chapters
        â”‚   â”œâ”€â”€ chapter_1.json
        â”‚   â””â”€â”€ chapter_2.json
        â”œâ”€â”€ epub/                    # EPUB exports
        â””â”€â”€ pdf/                     # PDF exports
```

See [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md) for complete explanation.

---

## ðŸ› Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'novelai'"

**Solution**: Make sure you installed in development mode:
```bash
python -m pip install -e .
```

### Issue: "OPENAI_API_KEY not found"

**Solution**: 
1. Create `.env` file from `.env.example`
2. Add your API key to `.env`
3. Restart the application

### Issue: "Connection timeout" when fetching chapters

**Solution**: 
- Check internet connection
- The Syosetu website might be temporarily unavailable
- Try again in a few moments

### Issue: "Low disk space" errors

**Solution**:
- Backups use about 1-2MB per novel (compressed)
- Raw and translated chapters use about 100-200KB per chapter
- Clear backups if needed: `novelaibook cleanup-backups`

### Issue: "Rate limit exceeded"

**Solution**:
- OpenAI has rate limits (varies by API tier)
- Wait a few moments and try again
- Use `novelaibook check-usage` to see your API usage

---

## ðŸ“š Next Steps

1. **Learn CLI Commands**: See [PYTHON_COMMANDS.md](PYTHON_COMMANDS.md)
2. **Learn TUI**: See [TUI_GUIDE.md](TUI_GUIDE.md)
3. **Understand Architecture**: See [docs/architecture.md](docs/architecture.md)
4. **Learn Data Format**: See [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md)
5. **Production Deployment**: See [PHASE_4_OPERATIONS.md](PHASE_4_OPERATIONS.md)

---

## ðŸ’¡ Tips

### Tip 1: Batch Processing
Translate multiple chapters at once for efficiency:
```bash
novelaibook translate-chapters syosetu_ncode n4423lw 1-10
```

### Tip 2: Add Custom Glossary
Edit `src/novelai/prompts/templates.py` to add terminology:
```python
GLOSSARY = {
    "SAO": "Sword Art Online",
    "VR": "Virtual Reality",
}
```

### Tip 3: Check Costs Before High-Volume Runs
```bash
novelaibook check-usage
```

### Tip 4: Use TUI for Visual Feedback
TUI shows:
- Translation progress
- Estimated costs in real-time
- Error messages with recovery options

### Tip 5: Enable Debug Logging
```bash
# Set LOG_LEVEL=DEBUG in .env
LOG_LEVEL=DEBUG
```

Then run command to see detailed logs.

---

## âš™ï¸ Configuration Reference

All settings in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_API_KEY` | (required) | Your OpenAI API key |
| `OPENAI_MODEL` | gpt-3.5-turbo | Model to use (gpt-4 recommended) |
| `DATA_DIR` | ./data | Where to store novels |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `COST_PER_TOKEN_USD` | 0.00002 | Token cost for cost estimation |
| `BATCH_SIZE` | 10 | Chapters per batch (Phase 4) |
| `POOL_MIN_SIZE` | 5 | Min API connections (Phase 4) |
| `POOL_MAX_SIZE` | 20 | Max API connections (Phase 4) |
| `CACHE_MAX_ENTRIES` | 10000 | Translation cache entries (Phase 4) |

---

## ðŸ“ž Getting Help

1. **Check Logs**: Logs saved to `logs/` directory
2. **Read Docs**: Start with [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
3. **Check FAQ**: See [PHASE_4_OPERATIONS.md](PHASE_4_OPERATIONS.md#faq)
4. **Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output

---

## ðŸŽ‰ Success!

You're ready to:
- âœ… Download novels from sources
- âœ… Translate them using AI
- âœ… Export to readable formats
- âœ… Track costs and usage
- âœ… Handle errors gracefully (Phase 4)

Start with TUI for easy interactive experience:
```bash
novelaibook tui
```

Or master the CLI from [PYTHON_COMMANDS.md](PYTHON_COMMANDS.md).


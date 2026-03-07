# Terminal UI (TUI) Guide

Comprehensive walkthrough of the Novel AI Terminal User Interface with actual menu options and examples.

---

## 🚀 Launch TUI

```bash
python -m novelai tui
```

The interactive terminal interface will start automatically.

---

## 📌 Main Menu Overview

When you launch TUI, you see the main menu:

```
Novel AI TUI

Select an option: (list, scrape, translate, export, diagnostics, settings, exit) [list]:
```

The TUI offers 7 main options. Use the number or keyword to select.

---

## ⌨️ Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `Type option name` | Select menu option directly |
| `Tab` | Autocomplete available options |
| `Enter` | Confirm selection or use default |
| `Ctrl+C` | Cancel current operation / interrupt |

### Text Input

| Key | Action |
|-----|--------|
| `Arrow Left / Right` | Move cursor in text |
| `Backspace` | Delete character |
| `Ctrl+U` | Clear entire line |
| `Enter` | Submit input |

---

## 📖 Step-by-Step Guide to All 7 Options

### Option 1: List Novels

**Purpose**: View all novels currently stored in the system

**Access**: Type `list` or press Enter (it's the default)

**Example Session**:

```
Select an option: (list, scrape, translate, export, diagnostics, settings, exit) [list]:
- Sword Art Online Progressive
- Re:Zero - Starting Life
```

**Output**:
- Shows all novels stored in your `data/novels/` directory
- Shows empty message if no novels yet

---

### Option 2: Scrape

**Purpose**: Download novel metadata and chapters from a web source

**Access**: Type `scrape`

**Flow**:

1. Select source:
```
Source (syosetu_ncode, example_source) [syosetu_ncode]: syosetu_ncode
```

2. Enter novel ID:
```
Novel ID or URL: n4423lw
```

3. Enter chapter selection:
```
Chapter selection (e.g. 1-3;5) [1]: 1-3
```

4. Choose scrape mode:
```
Scrape mode (full, update) [update]: update
```

**What it does**:
- **full**: Clears all existing data and re-downloads everything
- **update**: Only downloads new or changed chapters

**Example**:
```
Saved metadata for n4423lw from syosetu_ncode
Saved chapters for n4423lw from syosetu_ncode
```

---

### Option 3: Translate

**Purpose**: Translate downloaded chapters using AI provider

**Access**: Type `translate`

**Flow**:

1. Select source:
```
Source (syosetu_ncode, example_source) [syosetu_ncode]: syosetu_ncode
```

2. Enter novel ID:
```
Novel ID or URL: n4423lw
```

3. Enter chapter selection:
```
Chapter selection (e.g. 1-3;5) [1]: 1-3
```

4. Use settings or override:
```
Use settings provider/model? (yes, no) [yes]: no
```

5. If "no", select provider:
```
Provider (openai) [openai]: openai
Provider model [gpt-3.5-turbo]: gpt-4
```

**Output**:
```
Translated chapters for n4423lw
```

**Notes**:
- Translations are cached automatically
- Same text won't be retranslated
- Checks your API budget before proceeding

---

### Option 4: Export

**Purpose**: Create EPUB or PDF files from translated chapters

**Access**: Type `export`

**Flow**:

1. Enter novel ID:
```
Novel ID: n4423lw
```

2. Choose output directory:
```
Output directory [output]: output
```

3. Choose format:
```
Format (epub, pdf) [epub]: epub
```

**Output**:
```
Exported EPUB to output/n4423lw.epub
```

**Files saved to**:
- Custom: `{output}/{novel_id}.{format}` (e.g., `output/n4423lw.epub`)
- Default: `data/novels/{novel_name}/{format}/full_novel.{format}`

---

### Option 5: Diagnostics

**Purpose**: View system statistics, cache info, and API usage

**Access**: Type `diagnostics`

**Display Shows**:

```
System diagnostics

Novels stored: 2
Translated chapters: 6
Cached translations: 42
Total translation requests: 15
Total tokens used: 28,500
Estimated cost (USD): $0.25

Recent translation usage
- 2026-03-07 14:30:22 | openai/gpt-3.5-turbo | tokens=1200
- 2026-03-07 14:25:15 | openai/gpt-3.5-turbo | tokens=950
- 2026-03-07 14:20:08 | openai/gpt-4 | tokens=2100

Clear usage history? (yes, no) [no]:
```

**Information Shown**:
- Total novels stored
- Total translated chapters
- Cache entries (for cost savings)
- API requests and tokens
- Estimated cost in USD
- Last 5 translation events
- Option to clear usage history

---

### Option 6: Settings

**Purpose**: View and modify settings (provider, model, API key)

**Access**: Type `settings`

**Initial Display**:

```
Current settings
Provider: openai
Model: gpt-3.5-turbo
API key set: yes

Change settings? (yes, no) [no]:
```

**To Change Settings** (select "yes"):

```
Provider (openai) [openai]: openai
Provider model [gpt-3.5-turbo]: gpt-4
API key (leave blank to keep current): sk-...

Settings updated.
```

**What's Stored**:
- Provider type (openai)
- Model to use (gpt-3.5-turbo, gpt-4, etc.)
- API key (saved securely from environment)

---

### Option 7: Exit

**Purpose**: Close the TUI and return to terminal

**Access**: Type `exit` or press Ctrl+C

**Example**:
```
Select an option: (list, scrape, translate, export, diagnostics, settings, exit) [list]: exit
```

Returns cleanly to command prompt.

---

## 🎯 Common Workflows

### Workflow 1: Download and Translate a Novel

1. **Scrape**: Get metadata and chapters
   ```
   select: scrape
   source: syosetu_ncode
   id: n4423lw
   chapters: 1-10
   mode: full
   ```

2. **Translate**: Translate all chapters
   ```
   select: translate
   source: syosetu_ncode
   id: n4423lw
   chapters: 1-10
   ```

3. **Export**: Create EPUB
   ```
   select: export
   id: n4423lw
   output: output
   format: epub
   ```

4. **Verify**: Check diagnostics
   ```
   select: diagnostics
   (view stats and cache info)
   ```

---

### Workflow 2: Translate Small Batch First

1. **Scrape**: Download first 3 chapters only
   ```
   select: scrape
   chapters: 1-3
   ```

2. **Translate**: Translate just first 3
   ```
   select: translate
   chapters: 1-3
   ```

3. **Export**: Create EPUB with 3 chapters
   ```
   select: export
   format: epub
   ```

4. **Review**: Check quality before translating more

5. **Translate More**: Come back and translate 4-10
   ```
   select: translate
   chapters: 4-10
   ```

---

### Workflow 3: Monitor Usage and Costs

1. **Check diagnostics** after each translation:
   ```
   select: diagnostics
   (see token count, estimated cost)
   ```

2. **Change model** if costs too high:
   ```
   select: settings
   change: yes
   model: gpt-3.5-turbo (cheaper)
   ```

3. **Clear history** when needed:
   ```
   select: diagnostics
   clear history: yes
   ```

---

## 📊 Menu Reference Table

| Option | Command | Purpose | Notes |
|--------|---------|---------|-------|
| 1 | list | View novels | Default option |
| 2 | scrape | Download chapters | Choose mode (full/update) |
| 3 | translate | Translate chapters | Uses provider settings |
| 4 | export | Create EPUB/PDF | Saves to output/ by default |
| 5 | diagnostics | Show statistics | Shows cache, usage, costs |
| 6 | settings | Modify settings | Update provider/model |
| 7 | exit | Close TUI | Returns to terminal |

---

## 💡 Tips & Tricks

### Tip 1: Use Default Values
- Most options have reasonable defaults shown in `[brackets]`
- Press Enter to accept default and move faster

### Tip 2: Combine Workflows
- Scrape multiple novels
- Translate each
- Export all
- Check final costs in diagnostics

### Tip 3: Save Costs
- Translation cache prevents retranslations
- Scrape in "update" mode to avoid re-downloading
- Use cheaper model (gpt-3.5-turbo) first

### Tip 4: Chapter Selection Formats
- Single: `5`
- Range: `1-10`
- Multiple: `1-3;5;7-10`
- All: `1-*`

### Tip 5: Error Recovery
- If scrape fails, try again in "update" mode
- If translation fails, check API key in settings
- Use diagnostics to verify cache status

---

## 🆘 Troubleshooting

### "No sources are registered"
- **Cause**: Sources not initialized
- **Fix**: Exit and restart TUI
- **Command**: `python -m novelai tui`

### "No providers are registered"
- **Cause**: No providers configured
- **Fix**: Set API key in settings first
- **Command**: Select "settings", enter API key

### Translation fails with "API Error"
- **Cause**: Invalid API key or quota exceeded
- **Fix**: Check API key in settings
- **Verify**: Check usage in diagnostics
- **Command**: Select "settings", verify key

### Export fails "metadata not found"
- **Cause**: Need to scrape first
- **Fix**: Run scrape before export
- **Sequence**: scrape → translate → export

### Chapters not translating
- **Cause**: Chapters not downloaded yet
- **Fix**: Run scrape first
- **Check**: Use "list" to verify novel exists

---

## 📈 Performance Tips

**For Large Novels**:
1. Translate in batches (1-50, then 51-100, etc.)
2. Monitor costs in diagnostics
3. Clear usage history periodically

**For Cost Control**:
1. Use gpt-3.5-turbo for drafts
2. Cache hits save cost (monitored in diagnostics)
3. Update mode (not full) for re-runs

**For Faster Workflow**:
1. Accept defaults (press Enter)
2. Use same source/novel ID repeatedly (recent values shown)
3. Reuse "update" mode once initial scrape done

---

## 📝 Example Complete Session

```
# Start TUI
$ python -m novelai tui

# 1. List (default)
Select an option: [list]:
(No novels shown)

# 2. Scrape
Select an option: scrape
Source [syosetu_ncode]:
Novel ID or URL: n4423lw
Chapter selection [1]: 1-3
Scrape mode [update]: full
Saved metadata for n4423lw from syosetu_ncode
Saved chapters for n4423lw from syosetu_ncode

# 3. List again
Select an option: list
- Sword Art Online Progressive

# 4. Translate
Select an option: translate
Source [syosetu_ncode]:
Novel ID or URL: n4423lw
Chapter selection [1]: 1-3
Use settings provider/model? [yes]:
Translated chapters for n4423lw

# 5. Diagnostics
Select an option: diagnostics
Novels stored: 1
Translated chapters: 3
Cached translations: 3
Total translation requests: 1
Total tokens used: 2,847
Estimated cost (USD): $0.03
Recent translation usage
- 2026-03-07 15:45:30 | openai/gpt-3.5-turbo | tokens=2847

# 6. Export
Select an option: export
Novel ID: n4423lw
Output directory [output]:
Format [epub]:
Exported EPUB to output/n4423lw.epub

# 7. Exit
Select an option: exit
(returns to terminal)
```

---

## 🔗 Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) - Installation & setup
- [PYTHON_COMMANDS.md](PYTHON_COMMANDS.md) - CLI & programmatic usage
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - All documentation
- [docs/architecture.md](docs/architecture.md) - System design



```bash
python -m novelai tui
```

The interactive terminal interface will start automatically.

---

## 📌 Main Menu Overview

When you launch TUI, you see the main menu:

```
╔════════════════════════════════════════════════════════════╗
║                    NOVEL AI - Main Menu                    ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Scrape Novel Metadata                                 ║
║  2. Fetch Chapters                                        ║
║  3. Translate Chapters                                    ║
║  4. Export to EPUB/PDF                                   ║
║  5. View Novels                                           ║
║  6. Check API Usage                                       ║
║  7. Settings                                              ║
║  8. Exit                                                  ║
║                                                            ║
║  Enter your choice (1-8): _                               ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

## ⌨️ Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `Arrow Up / Down` | Navigate menu options |
| `Number (1-9)` | Select option directly |
| `Enter` | Confirm selection |
| `Esc` or `Q` | Go back / Quit |
| `Tab` | Move between text fields |
| `Ctrl+C` | Interrupt current operation |

### Text Input

| Key | Action |
|-----|--------|
| `Arrow Left / Right` | Move cursor in text |
| `Backspace` | Delete character |
| `Home` | Beginning of line |
| `End` | End of line |
| `Ctrl+U` | Clear line |
| `Enter` | Submit |

---

## 📖 Step-by-Step Walkthrough

### Step 1: Scrape Novel Metadata

**Purpose**: Download novel information (title, author, chapter list)

**Procedure**:

1. From main menu, select: **1. Scrape Novel Metadata**

```
╔════════════════════════════════════════════════════════════╗
║          Scrape Novel Metadata - Select Source            ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Available Sources:                                        ║
║  1. Syosetu (syosetu_ncode)                               ║
║  2. Kakuyomu (kakuyomu)                                   ║
║  3. Example Source (example_source)                       ║
║                                                            ║
║  Select source (1-3): _                                   ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

2. Select source: **1** (Syosetu is most common)

3. Enter novel ID:

```
╔════════════════════════════════════════════════════════════╗
║              Scrape Novel Metadata - Novel ID              ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Enter novel ID (e.g., n4423lw):                          ║
║  > n4423lw                                                 ║
║                                                            ║
║  [Press Enter to confirm]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

4. Wait for download:

```
╔════════════════════════════════════════════════════════════╗
║              Scraping Novel Metadata...                    ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  [████████████████░░░░░░░░░░░░░░░░░░░░░░] 50%             ║
║  Status: Downloading chapter list...                      ║
║                                                            ║
║  Novel: Sword Art Online Progressive                      ║
║  Author: Reki Kawahara                                    ║
║  Chapters found: 120                                      ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

5. Success screen:

```
╔════════════════════════════════════════════════════════════╗
║                    Success!                               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ✓ Metadata scraped successfully                          ║
║                                                            ║
║  Novel: Sword Art Online Progressive                      ║
║  ID: n4423lw                                              ║
║  Chapters: 120                                            ║
║  Saved to: data/novels/sword_art_online_progressive/     ║
║                                                            ║
║  [Press Enter to continue]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 2: Fetch Chapters

**Purpose**: Download raw chapter text from source website

**Procedure**:

1. From main menu, select: **2. Fetch Chapters**

2. Enter novel ID:

```
Enter novel ID: n4423lw
```

3. Select chapters:

```
╔════════════════════════════════════════════════════════════╗
║              Fetch Chapters - Selection Menu               ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Total chapters available: 120                            ║
║                                                            ║
║  Chapter Selection Syntax:                                ║
║  • 1-5         (chapters 1 through 5)                     ║
║  • 1,3,5       (specific chapters)                        ║
║  • 1-10;15-20  (multiple ranges)                          ║
║  • 1-*         (all chapters)                             ║
║                                                            ║
║  Enter selection: 1-3                                      ║
║                                                            ║
║  [Press Enter to start fetching]                          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

4. Fetching progress:

```
╔════════════════════════════════════════════════════════════╗
║              Fetching Chapters 1-3...                      ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  [████████████████████████████░░░░░░░░░] 75%              ║
║                                                            ║
║  ✓ Chapter 1: 2,847 chars                                 ║
║  ✓ Chapter 2: 3,102 chars                                 ║
║  ⏳ Chapter 3: Downloading...                              ║
║                                                            ║
║  Estimated time: 30 seconds                               ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

5. Complete:

```
╔════════════════════════════════════════════════════════════╗
║                    Complete!                              ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ✓ Fetched 3 chapters successfully                        ║
║                                                            ║
║  Saved to: data/novels/sword_art_online_progressive/raw/  ║
║                                                            ║
║  [Press Enter to continue]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 3: Translate Chapters

**Purpose**: Use AI to translate chapters to English

**Procedure**:

1. From main menu, select: **3. Translate Chapters**

2. Enter novel ID:

```
Enter novel ID: n4423lw
```

3. Select chapters:

```
Enter chapter selection: 1-3
```

4. Choose provider:

```
╔════════════════════════════════════════════════════════════╗
║           Translate Chapters - Choose Provider             ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Available Providers:                                     ║
║  1. OpenAI (gpt-3.5-turbo)  - $0.001 per 1k tokens       ║
║  2. OpenAI (gpt-4)          - $0.03 per 1k tokens         ║
║  3. OpenAI (gpt-4-turbo)    - $0.01 per 1k tokens         ║
║                                                            ║
║  Select provider (1-3): 3  [Recommended: gpt-4-turbo]    ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

5. Cost estimate before proceeding:

```
╔════════════════════════════════════════════════════════════╗
║              Cost Estimate                                ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Processing 3 chapters with gpt-4-turbo:                  ║
║                                                            ║
║  Estimated tokens: 8,400                                  ║
║  Estimated cost: $0.084                                   ║
║  Current usage today: $2.45                               ║
║  Daily budget: $10.00                                     ║
║                                                            ║
║  ✓ Within budget                                          ║
║                                                            ║
║  Continue? (Y/n): y                                        ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

6. Translation progress with live updates:

```
╔════════════════════════════════════════════════════════════╗
║              Translating Chapters 1-3...                   ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  [████████████████░░░░░░░░░░░░░░░░░░░░░░] 50%             ║
║                                                            ║
║  ✓ Chapter 1: 2,500 tokens (~$0.025) [cache miss]        ║
║  ✓ Chapter 2: 2,800 tokens (~$0.028) [cache miss]        ║
║  ⏳ Chapter 3: Processing... [cache hit - 0 tokens]       ║
║                                                            ║
║  Total spent: $0.053 / $0.084                             ║
║  ETA: 45 seconds                                          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

7. Complete with summary:

```
╔════════════════════════════════════════════════════════════╗
║              Translation Complete!                        ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ✓ Translated 3 chapters                                  ║
║                                                            ║
║  Cache hits: 1 chapter (saved $0.010)                     ║
║  API calls: 2 chapters                                    ║
║  Total tokens: 5,300                                      ║
║  Total cost: $0.053                                       ║
║                                                            ║
║  Saved to: data/novels/sword_art_online_progressive/      ║
║            translated/                                    ║
║                                                            ║
║  [Press Enter to continue]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 4: Export to EPUB/PDF

**Purpose**: Create downloadable ebook files

**Procedure**:

1. From main menu, select: **4. Export to EPUB/PDF**

2. Enter novel ID:

```
Enter novel ID: n4423lw
```

3. Choose format:

```
╔════════════════════════════════════════════════════════════╗
║           Export Chapters - Choose Format                  ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Available Formats:                                       ║
║  1. EPUB (Kindle, Kobo, etc.)                             ║
║  2. PDF (Print-ready)                                     ║
║                                                            ║
║  Select format (1-2): 1                                    ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

4. Export progress:

```
╔════════════════════════════════════════════════════════════╗
║              Exporting to EPUB...                          ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  [████████████████████████████████████░░] 90%              ║
║                                                            ║
║  Building document structure...                           ║
║  Adding 3 chapters...                                     ║
║  Creating table of contents...                            ║
║  Generating metadata...                                   ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

5. Success:

```
╔════════════════════════════════════════════════════════════╗
║              Export Complete!                             ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  ✓ EPUB created successfully                              ║
║                                                            ║
║  File: data/novels/sword_art_online_progressive/epub/     ║
║         full_novel.epub                                    ║
║  Size: 2.3 MB                                             ║
║  Chapters: 3                                              ║
║                                                            ║
║  Ready to read on: Kindle, Kobo, Apple Books              ║
║                                                            ║
║  [Press Enter to continue]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 5: View Novels

**Purpose**: See downloaded and translated novels

**Procedure**:

1. From main menu, select: **5. View Novels**

2. Novel list:

```
╔════════════════════════════════════════════════════════════╗
║                      Your Novels                          ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  📖 Sword Art Online Progressive         [n4423lw]         ║
║     Raw chapters: 10                                      ║
║     Translated: 3                                         ║
║     EPUB: ✓  PDF: ✗                                       ║
║     Last updated: 2 hours ago                             ║
║                                                            ║
║  📖 Re:Zero - Starting Life             [n1234ab]          ║
║     Raw chapters: 5                                       ║
║     Translated: 2                                         ║
║     EPUB: ✗  PDF: ✗                                       ║
║     Last updated: 1 day ago                               ║
║                                                            ║
║  [Enter for details, Q to exit]                           ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

3. Novel details (select one):

```
╔════════════════════════════════════════════════════════════╗
║      Sword Art Online Progressive Details                  ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Title: ソードアート・オンライン プログレッシブ              ║
║  Title (EN): Sword Art Online Progressive                 ║
║  Author: Reki Kawahara                                    ║
║  Novel ID: n4423lw                                        ║
║  Source: Syosetu                                          ║
║                                                            ║
║  Chapters:                                                ║
║  ✓ Chapter 1: Beginning                 [translated]     ║
║  ✓ Chapter 2: First Quest                [translated]     ║
║  ✓ Chapter 3: Meeting                    [translated]     ║
║  • Chapter 4: Exploration                [raw only]       ║
║  • Chapter 5: Battle                     [raw only]       ║
║                                                            ║
║  Storage: 8.4 MB                                          ║
║                                                            ║
║  [Q] Back                                                 ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 6: Check API Usage

**Purpose**: Monitor costs and API usage

**Procedure**:

1. From main menu, select: **6. Check API Usage**

2. Usage dashboard:

```
╔════════════════════════════════════════════════════════════╗
║                  API Usage Dashboard                      ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Total API Requests:        42                            ║
║  Total Tokens Used:         125,000                       ║
║  Total Cost:                $2.50 USD                     ║
║                                                            ║
║  Today's Usage:                                           ║
║  • Requests: 12                                           ║
║  • Tokens: 35,000                                         ║
║  • Cost: $0.70                                            ║
║                                                            ║
║  Provider Breakdown:                                      ║
║  • OpenAI gpt-3.5-turbo: 80,000 tokens ($0.80)           ║
║  • OpenAI gpt-4: 45,000 tokens ($1.70)                    ║
║                                                            ║
║  Budget Status:                                           ║
║  • Daily limit: $10.00                                    ║
║  • Used today: $0.70                                      ║
║  • Remaining: $9.30 ✓                                     ║
║                                                            ║
║  Monthly Estimate:                                        ║
║  • Current pace: $21.00                                   ║
║  • Monthly budget: $100.00                                ║
║                                                            ║
║  [Press Enter to continue]                                ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 7: Settings

**Purpose**: Configure application options

**Procedure**:

1. From main menu, select: **7. Settings**

2. Settings menu:

```
╔════════════════════════════════════════════════════════════╗
║                    Settings Menu                          ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  1. Translation Provider                                  ║
║     Current: OpenAI (gpt-3.5-turbo)                       ║
║                                                            ║
║  2. API Key Management                                    ║
║     Status: Configured ✓                                  ║
║                                                            ║
║  3. Budget Settings                                       ║
║     Daily limit: $10.00                                   ║
║     Monthly limit: $100.00                                ║
║                                                            ║
║  4. Data Directory                                        ║
║     Location: ./data                                      ║
║                                                            ║
║  5. Logging Level                                         ║
║     Level: INFO                                           ║
║                                                            ║
║  6. Cache Settings                                        ║
║     Max entries: 10,000                                   ║
║     TTL: 7 days                                           ║
║                                                            ║
║  [Q] Back to menu                                         ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

3. Change setting (example - change model):

```
╔════════════════════════════════════════════════════════════╗
║           Select Translation Provider                      ║
╠════════════════════════════════════════════════════════════╣
║                                                            ║
║  Available Models:                                        ║
║  1. gpt-3.5-turbo   (Fast, cheap)      [current]         ║
║  2. gpt-4           (Best quality)                        ║
║  3. gpt-4-turbo     (Balanced)                            ║
║                                                            ║
║  Select: 2                                                ║
║                                                            ║
║  ✓ Model changed to gpt-4                                 ║
║  Note: This will use more tokens per translation          ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
```

---

### Step 8: Exit

Simply press **8** or **Q** at any time to exit.

---

## 🎯 Common Workflows

### Workflow 1: Download and Translate a Full Novel

1. **Scrape Metadata** (Step 1)
2. **Fetch Chapters** (Step 2) - Select `1-*` for all
3. **Translate Chapters** (Step 3) - Select `1-*` for all
4. **Export to EPUB** (Step 4)
5. Check **View Novels** (Step 5) to verify

---

### Workflow 2: Translate Specific Chapters Only

1. **Fetch Chapters** - Select `5-10` (chapters 5-10)
2. **Translate Chapters** - Select `5-10` (same chapters)
3. **Export to EPUB** - Creates file from all translated
4. Read EPUB with chapters 5-10 included

---

### Workflow 3: Check Costs Before Large Translation

1. **Check API Usage** (Step 6) - See current costs
2. **View Novels** (Step 5) - See chapter counts
3. **Translate Chapters** (Step 3) - See cost estimate before proceeding
4. Proceed or cancel based on estimate

---

## 💡 Tips & Tricks

### Tip 1: Use Cache to Save Costs
- Translations are automatically cached
- Same text won't be retranslated
- Check "Cache hits" in translation results

### Tip 2: Start with Small Batches
- Translate 1-3 chapters first
- Test quality before translating full novel
- Can always translate more later

### Tip 3: Monitor API Budget
- Check API Usage frequently
- Set realistic daily/monthly budgets
- TUI alerts if over budget

### Tip 4: Use Different Models for Different Passes
- First pass: gpt-3.5-turbo (cheap, fast)
- Quality pass: gpt-4 (expensive, best quality)
- Mix as needed for your use case

### Tip 5: Export Multiple Times
- Translate chapters in batches
- Export after each batch
- Files in same folder will update

---

## 🖥️ Screen Navigation

### General Navigation Flow

```
Main Menu
├── 1. Scrape Metadata
├── 2. Fetch Chapters
├── 3. Translate Chapters
├── 4. Export to EPUB/PDF
├── 5. 🔍 View Novels
│   └── See details & storage
├── 6. 💰 Check API Usage
│   └── Monitor costs
├── 7. ⚙️ Settings
│   ├── Change provider
│   ├── Set budgets
│   └── Configure paths
└── 8. Exit (Q)
```

---

## 📊 Progress Indicators

| Symbol | Meaning |
|--------|---------|
| `✓` | Completed successfully |
| `✗` | Failed or not completed |
| `⏳` | In progress |
| `⚠️` | Warning |
| `📖` | Novel |
| `💰` | Cost/Budget |
| `🔍` | View/Inspect |
| `⚙️` | Settings |

---

## ⌚ Typical Timings

| Operation | Time | Notes |
|-----------|------|-------|
| Scrape metadata | 10-30s | Depends on novel size |
| Fetch 1 chapter | 5-15s | Network dependent |
| Translate 1 chapter | 30-120s | API response time |
| Export EPUB | 5-10s | Local operation |
| Export PDF | 10-30s | More complex |

---

## 🆘 Troubleshooting

### TUI Won't Start

```bash
# Ensure virtual environment is activated
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Try again
python -m novelai tui
```

### Progress Stuck

- Press `Ctrl+C` to cancel
- Check internet connection
- Try again

### API Errors

- Check API key in Settings (#2)
- Verify API key is valid at OpenAI dashboard
- Check budget hasn't been exceeded in Settings (#3)

### Export Failed

- Ensure chapters are translated (Step 5 to verify)
- Check disk space available
- Try again with fewer chapters

---

## 📖 Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) - Installation
- [PYTHON_COMMANDS.md](PYTHON_COMMANDS.md) - CLI & programmatic usage
- [DATA_OUTPUT_STRUCTURE.md](DATA_OUTPUT_STRUCTURE.md) - Data format
- [docs/architecture.md](docs/architecture.md) - System design


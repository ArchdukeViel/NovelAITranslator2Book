# Terminal UI (TUI) Guide

Comprehensive walkthrough of the `novelaibook tui` dashboard and its action flows.

---

## ðŸš€ Launch TUI

```bash
novelaibook tui
```

The interactive terminal interface will start automatically.

---

## ðŸ“Œ Main Menu Overview

When you launch TUI, you land on a dashboard instead of a plain prompt. The layout is built around:

- a top "Reading Room" header with provider and library info
- overview cards for novels, translated chapters, sources, and requests
- a "Control Deck" action table
- a "Library Snapshot" panel
- a "System Pulse" panel for settings and recent usage
- a bottom "Guide Rail" with status and command hints

The interface design is loosely inspired by polished GitHub TUIs such as `Textualize/frogmouth`, `gitui-org/gitui`, and `charmbracelet/glow`.

After the dashboard renders, you choose an action from the prompt:

```
Action [list/scrape/translate/export/diagnostics/settings/exit] (list):
```

The TUI offers 7 main options. Type the action name directly.

---

## âŒ¨ï¸ Keyboard Shortcuts

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

## ðŸ“– Step-by-Step Guide to All 7 Options

### Option 1: List Novels

**Purpose**: View all novels currently stored in the system

**Access**: Type `list` or press Enter (it's the default)

**What you see**:

```
+-------------------------- Library Snapshot ---------------------------+
| Novel ID   | Title                           | Chapters | Translated |
|------------+---------------------------------+----------+------------|
| n4423lw    | Sword Art Online Progressive    | 120      | 120        |
| n9669bk    | Re:Zero - Starting Life         |  90      |  34        |
+---------------------------------------------------------------------+
```

**Output**:
- Shows all novels stored in your `novel_library/novels/` directory
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
Saved metadata and chapters for n4423lw from syosetu_ncode.
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
Translated chapters 1-3 for n4423lw with openai/gpt-4.
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

2. Choose output directory (optional):
```
Output directory (leave blank for novel library):
```

3. Choose format:
```
Format (epub, pdf) [epub]: epub
```

**Output**:
```
Exported EPUB to novel_library/novels/sword_art_online_progressive/epub/full_novel.epub
```

**Files saved to**:
- Default: `novel_library/novels/{novel_name}/{format}/full_novel.{format}`
- Custom: `{output_dir}/{novel_id}.{format}` (e.g., `exports/n4423lw.epub`)

---

### Option 5: Diagnostics

**Purpose**: View system statistics, cache info, and API usage

**Access**: Type `diagnostics`

**Display Shows**:

```
Novels stored              2
Translated chapters        6
Cached translations        42
Total translation requests 15
Total tokens used          28500
Estimated cost (USD)       $0.250000

Timestamp                  Provider/Model         Tokens
2026-03-07T14:30:22Z       openai/gpt-3.5-turbo    1200
2026-03-07T14:25:15Z       openai/gpt-3.5-turbo     950
2026-03-07T14:20:08Z       openai/gpt-4            2100
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

## ðŸŽ¯ Common Workflows

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

## ðŸ“Š Menu Reference Table

| Option | Command | Purpose | Notes |
|--------|---------|---------|-------|
| 1 | list | View novels | Default option |
| 2 | scrape | Download chapters | Choose mode (full/update) |
| 3 | translate | Translate chapters | Uses provider settings |
| 4 | export | Create EPUB/PDF | Saves to novel_library by default |
| 5 | diagnostics | Show statistics | Shows cache, usage, costs |
| 6 | settings | Modify settings | Update provider/model |
| 7 | exit | Close TUI | Returns to terminal |

---

## ðŸ’¡ Tips & Tricks

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

## ðŸ†˜ Troubleshooting

### "No sources are registered"
- **Cause**: Sources not initialized
- **Fix**: Exit and restart TUI
- **Command**: `novelaibook tui`

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
- **Sequence**: scrape â†’ translate â†’ export

### Chapters not translating
- **Cause**: Chapters not downloaded yet
- **Fix**: Run scrape first
- **Check**: Use "list" to verify novel exists

---

## ðŸ“ˆ Performance Tips

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

## ðŸ“ Example Complete Session

```
# Start TUI
$ novelaibook tui

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
Output directory (leave blank for novel library):
Format [epub]:
Exported EPUB to novel_library/novels/sword_art_online_progressive/epub/full_novel.epub

# 7. Exit
Select an option: exit
(returns to terminal)
```

---

## ðŸ”— Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) - Installation & setup
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md) - CLI & programmatic usage
- [../README.md](../README.md) - All documentation
- [../architecture/architecture.md](../architecture/architecture.md) - System design



```bash
novelaibook tui
```

The interactive terminal interface will start automatically.

---

## ðŸ“Œ Main Menu Overview

When you launch TUI, you see the main menu:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                    NOVEL AI - Main Menu                    â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  1. Scrape Novel Metadata                                 â•‘
â•‘  2. Fetch Chapters                                        â•‘
â•‘  3. Translate Chapters                                    â•‘
â•‘  4. Export to EPUB/PDF                                   â•‘
â•‘  5. View Novels                                           â•‘
â•‘  6. Check API Usage                                       â•‘
â•‘  7. Settings                                              â•‘
â•‘  8. Exit                                                  â•‘
â•‘                                                            â•‘
â•‘  Enter your choice (1-8): _                               â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

---

## âŒ¨ï¸ Keyboard Shortcuts

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

## ðŸ“– Step-by-Step Walkthrough

### Step 1: Scrape Novel Metadata

**Purpose**: Download novel information (title, author, chapter list)

**Procedure**:

1. From main menu, select: **1. Scrape Novel Metadata**

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘          Scrape Novel Metadata - Select Source            â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Available Sources:                                        â•‘
â•‘  1. Syosetu (syosetu_ncode)                               â•‘
â•‘  2. Kakuyomu (kakuyomu)                                   â•‘
â•‘  3. Example Source (example_source)                       â•‘
â•‘                                                            â•‘
â•‘  Select source (1-3): _                                   â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

2. Select source: **1** (Syosetu is most common)

3. Enter novel ID:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Scrape Novel Metadata - Novel ID              â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Enter novel ID (e.g., n4423lw):                          â•‘
â•‘  > n4423lw                                                 â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to confirm]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

4. Wait for download:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Scraping Novel Metadata...                    â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  [â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘] 50%             â•‘
â•‘  Status: Downloading chapter list...                      â•‘
â•‘                                                            â•‘
â•‘  Novel: Sword Art Online Progressive                      â•‘
â•‘  Author: Reki Kawahara                                    â•‘
â•‘  Chapters found: 120                                      â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

5. Success screen:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                    Success!                               â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  âœ“ Metadata scraped successfully                          â•‘
â•‘                                                            â•‘
â•‘  Novel: Sword Art Online Progressive                      â•‘
â•‘  ID: n4423lw                                              â•‘
â•‘  Chapters: 120                                            â•‘
â•‘  Saved to: data/novels/sword_art_online_progressive/     â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to continue]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Fetch Chapters - Selection Menu               â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Total chapters available: 120                            â•‘
â•‘                                                            â•‘
â•‘  Chapter Selection Syntax:                                â•‘
â•‘  â€¢ 1-5         (chapters 1 through 5)                     â•‘
â•‘  â€¢ 1,3,5       (specific chapters)                        â•‘
â•‘  â€¢ 1-10;15-20  (multiple ranges)                          â•‘
â•‘  â€¢ 1-*         (all chapters)                             â•‘
â•‘                                                            â•‘
â•‘  Enter selection: 1-3                                      â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to start fetching]                          â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

4. Fetching progress:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Fetching Chapters 1-3...                      â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  [â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘] 75%              â•‘
â•‘                                                            â•‘
â•‘  âœ“ Chapter 1: 2,847 chars                                 â•‘
â•‘  âœ“ Chapter 2: 3,102 chars                                 â•‘
â•‘  â³ Chapter 3: Downloading...                              â•‘
â•‘                                                            â•‘
â•‘  Estimated time: 30 seconds                               â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

5. Complete:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                    Complete!                              â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  âœ“ Fetched 3 chapters successfully                        â•‘
â•‘                                                            â•‘
â•‘  Saved to: data/novels/sword_art_online_progressive/raw/  â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to continue]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘           Translate Chapters - Choose Provider             â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Available Providers:                                     â•‘
â•‘  1. OpenAI (gpt-3.5-turbo)  - $0.001 per 1k tokens       â•‘
â•‘  2. OpenAI (gpt-4)          - $0.03 per 1k tokens         â•‘
â•‘  3. OpenAI (gpt-4-turbo)    - $0.01 per 1k tokens         â•‘
â•‘                                                            â•‘
â•‘  Select provider (1-3): 3  [Recommended: gpt-4-turbo]    â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

5. Cost estimate before proceeding:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Cost Estimate                                â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Processing 3 chapters with gpt-4-turbo:                  â•‘
â•‘                                                            â•‘
â•‘  Estimated tokens: 8,400                                  â•‘
â•‘  Estimated cost: $0.084                                   â•‘
â•‘  Current usage today: $2.45                               â•‘
â•‘  Daily budget: $10.00                                     â•‘
â•‘                                                            â•‘
â•‘  âœ“ Within budget                                          â•‘
â•‘                                                            â•‘
â•‘  Continue? (Y/n): y                                        â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

6. Translation progress with live updates:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Translating Chapters 1-3...                   â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  [â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘] 50%             â•‘
â•‘                                                            â•‘
â•‘  âœ“ Chapter 1: 2,500 tokens (~$0.025) [cache miss]        â•‘
â•‘  âœ“ Chapter 2: 2,800 tokens (~$0.028) [cache miss]        â•‘
â•‘  â³ Chapter 3: Processing... [cache hit - 0 tokens]       â•‘
â•‘                                                            â•‘
â•‘  Total spent: $0.053 / $0.084                             â•‘
â•‘  ETA: 45 seconds                                          â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

7. Complete with summary:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Translation Complete!                        â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  âœ“ Translated 3 chapters                                  â•‘
â•‘                                                            â•‘
â•‘  Cache hits: 1 chapter (saved $0.010)                     â•‘
â•‘  API calls: 2 chapters                                    â•‘
â•‘  Total tokens: 5,300                                      â•‘
â•‘  Total cost: $0.053                                       â•‘
â•‘                                                            â•‘
â•‘  Saved to: data/novels/sword_art_online_progressive/      â•‘
â•‘            translated/                                    â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to continue]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘           Export Chapters - Choose Format                  â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Available Formats:                                       â•‘
â•‘  1. EPUB (Kindle, Kobo, etc.)                             â•‘
â•‘  2. PDF (Print-ready)                                     â•‘
â•‘                                                            â•‘
â•‘  Select format (1-2): 1                                    â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

4. Export progress:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Exporting to EPUB...                          â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  [â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘] 90%              â•‘
â•‘                                                            â•‘
â•‘  Building document structure...                           â•‘
â•‘  Adding 3 chapters...                                     â•‘
â•‘  Creating table of contents...                            â•‘
â•‘  Generating metadata...                                   â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

5. Success:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘              Export Complete!                             â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  âœ“ EPUB created successfully                              â•‘
â•‘                                                            â•‘
â•‘  File: data/novels/sword_art_online_progressive/epub/     â•‘
â•‘         full_novel.epub                                    â•‘
â•‘  Size: 2.3 MB                                             â•‘
â•‘  Chapters: 3                                              â•‘
â•‘                                                            â•‘
â•‘  Ready to read on: Kindle, Kobo, Apple Books              â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to continue]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

---

### Step 5: View Novels

**Purpose**: See downloaded and translated novels

**Procedure**:

1. From main menu, select: **5. View Novels**

2. Novel list:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                      Your Novels                          â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  ðŸ“– Sword Art Online Progressive         [n4423lw]         â•‘
â•‘     Raw chapters: 10                                      â•‘
â•‘     Translated: 3                                         â•‘
â•‘     EPUB: âœ“  PDF: âœ—                                       â•‘
â•‘     Last updated: 2 hours ago                             â•‘
â•‘                                                            â•‘
â•‘  ðŸ“– Re:Zero - Starting Life             [n1234ab]          â•‘
â•‘     Raw chapters: 5                                       â•‘
â•‘     Translated: 2                                         â•‘
â•‘     EPUB: âœ—  PDF: âœ—                                       â•‘
â•‘     Last updated: 1 day ago                               â•‘
â•‘                                                            â•‘
â•‘  [Enter for details, Q to exit]                           â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

3. Novel details (select one):

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘      Sword Art Online Progressive Details                  â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Title: ã‚½ãƒ¼ãƒ‰ã‚¢ãƒ¼ãƒˆãƒ»ã‚ªãƒ³ãƒ©ã‚¤ãƒ³ ãƒ—ãƒ­ã‚°ãƒ¬ãƒƒã‚·ãƒ–              â•‘
â•‘  Title (EN): Sword Art Online Progressive                 â•‘
â•‘  Author: Reki Kawahara                                    â•‘
â•‘  Novel ID: n4423lw                                        â•‘
â•‘  Source: Syosetu                                          â•‘
â•‘                                                            â•‘
â•‘  Chapters:                                                â•‘
â•‘  âœ“ Chapter 1: Beginning                 [translated]     â•‘
â•‘  âœ“ Chapter 2: First Quest                [translated]     â•‘
â•‘  âœ“ Chapter 3: Meeting                    [translated]     â•‘
â•‘  â€¢ Chapter 4: Exploration                [raw only]       â•‘
â•‘  â€¢ Chapter 5: Battle                     [raw only]       â•‘
â•‘                                                            â•‘
â•‘  Storage: 8.4 MB                                          â•‘
â•‘                                                            â•‘
â•‘  [Q] Back                                                 â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

---

### Step 6: Check API Usage

**Purpose**: Monitor costs and API usage

**Procedure**:

1. From main menu, select: **6. Check API Usage**

2. Usage dashboard:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                  API Usage Dashboard                      â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Total API Requests:        42                            â•‘
â•‘  Total Tokens Used:         125,000                       â•‘
â•‘  Total Cost:                $2.50 USD                     â•‘
â•‘                                                            â•‘
â•‘  Today's Usage:                                           â•‘
â•‘  â€¢ Requests: 12                                           â•‘
â•‘  â€¢ Tokens: 35,000                                         â•‘
â•‘  â€¢ Cost: $0.70                                            â•‘
â•‘                                                            â•‘
â•‘  Provider Breakdown:                                      â•‘
â•‘  â€¢ OpenAI gpt-3.5-turbo: 80,000 tokens ($0.80)           â•‘
â•‘  â€¢ OpenAI gpt-4: 45,000 tokens ($1.70)                    â•‘
â•‘                                                            â•‘
â•‘  Budget Status:                                           â•‘
â•‘  â€¢ Daily limit: $10.00                                    â•‘
â•‘  â€¢ Used today: $0.70                                      â•‘
â•‘  â€¢ Remaining: $9.30 âœ“                                     â•‘
â•‘                                                            â•‘
â•‘  Monthly Estimate:                                        â•‘
â•‘  â€¢ Current pace: $21.00                                   â•‘
â•‘  â€¢ Monthly budget: $100.00                                â•‘
â•‘                                                            â•‘
â•‘  [Press Enter to continue]                                â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

---

### Step 7: Settings

**Purpose**: Configure application options

**Procedure**:

1. From main menu, select: **7. Settings**

2. Settings menu:

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘                    Settings Menu                          â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  1. Translation Provider                                  â•‘
â•‘     Current: OpenAI (gpt-3.5-turbo)                       â•‘
â•‘                                                            â•‘
â•‘  2. API Key Management                                    â•‘
â•‘     Status: Configured âœ“                                  â•‘
â•‘                                                            â•‘
â•‘  3. Budget Settings                                       â•‘
â•‘     Daily limit: $10.00                                   â•‘
â•‘     Monthly limit: $100.00                                â•‘
â•‘                                                            â•‘
â•‘  4. Data Directory                                        â•‘
â•‘     Location: ./data                                      â•‘
â•‘                                                            â•‘
â•‘  5. Logging Level                                         â•‘
â•‘     Level: INFO                                           â•‘
â•‘                                                            â•‘
â•‘  6. Cache Settings                                        â•‘
â•‘     Max entries: 10,000                                   â•‘
â•‘     TTL: 7 days                                           â•‘
â•‘                                                            â•‘
â•‘  [Q] Back to menu                                         â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

3. Change setting (example - change model):

```
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘           Select Translation Provider                      â•‘
â• â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•£
â•‘                                                            â•‘
â•‘  Available Models:                                        â•‘
â•‘  1. gpt-3.5-turbo   (Fast, cheap)      [current]         â•‘
â•‘  2. gpt-4           (Best quality)                        â•‘
â•‘  3. gpt-4-turbo     (Balanced)                            â•‘
â•‘                                                            â•‘
â•‘  Select: 2                                                â•‘
â•‘                                                            â•‘
â•‘  âœ“ Model changed to gpt-4                                 â•‘
â•‘  Note: This will use more tokens per translation          â•‘
â•‘                                                            â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
```

---

### Step 8: Exit

Simply press **8** or **Q** at any time to exit.

---

## ðŸŽ¯ Common Workflows

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

## ðŸ’¡ Tips & Tricks

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

## ðŸ–¥ï¸ Screen Navigation

### General Navigation Flow

```
Main Menu
â”œâ”€â”€ 1. Scrape Metadata
â”œâ”€â”€ 2. Fetch Chapters
â”œâ”€â”€ 3. Translate Chapters
â”œâ”€â”€ 4. Export to EPUB/PDF
â”œâ”€â”€ 5. ðŸ” View Novels
â”‚   â””â”€â”€ See details & storage
â”œâ”€â”€ 6. ðŸ’° Check API Usage
â”‚   â””â”€â”€ Monitor costs
â”œâ”€â”€ 7. âš™ï¸ Settings
â”‚   â”œâ”€â”€ Change provider
â”‚   â”œâ”€â”€ Set budgets
â”‚   â””â”€â”€ Configure paths
â””â”€â”€ 8. Exit (Q)
```

---

## ðŸ“Š Progress Indicators

| Symbol | Meaning |
|--------|---------|
| `âœ“` | Completed successfully |
| `âœ—` | Failed or not completed |
| `â³` | In progress |
| `âš ï¸` | Warning |
| `ðŸ“–` | Novel |
| `ðŸ’°` | Cost/Budget |
| `ðŸ”` | View/Inspect |
| `âš™ï¸` | Settings |

---

## âŒš Typical Timings

| Operation | Time | Notes |
|-----------|------|-------|
| Scrape metadata | 10-30s | Depends on novel size |
| Fetch 1 chapter | 5-15s | Network dependent |
| Translate 1 chapter | 30-120s | API response time |
| Export EPUB | 5-10s | Local operation |
| Export PDF | 10-30s | More complex |

---

## ðŸ†˜ Troubleshooting

### TUI Won't Start

```bash
# Ensure virtual environment is activated
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Try again
novelaibook tui
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

## ðŸ“– Related Documentation

- [GETTING_STARTED.md](GETTING_STARTED.md) - Installation
- [../reference/PYTHON_COMMANDS.md](../reference/PYTHON_COMMANDS.md) - CLI & programmatic usage
- [../reference/DATA_OUTPUT_STRUCTURE.md](../reference/DATA_OUTPUT_STRUCTURE.md) - Data format
- [../architecture/architecture.md](../architecture/architecture.md) - System design



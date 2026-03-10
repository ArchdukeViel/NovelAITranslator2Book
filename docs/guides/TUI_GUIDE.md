# Terminal UI (TUI) Guide

Comprehensive walkthrough of the `novelaibook tui` dashboard and its action flows.

---

## Launch TUI

```bash
novelaibook tui
```

The interactive terminal interface starts automatically.

---

## Main Menu Overview

When you launch TUI, you land on a Rich dashboard with:

- a top "Reading Room" header with provider and library info
- overview cards for novels, translated chapters, sources, and requests
- a "Control Deck" action table
- a "Library Snapshot" panel
- a "System Pulse" panel for settings and recent usage
- a bottom "Guide Rail" with status and command hints

After the dashboard renders, you choose an action from the prompt:

```
Action [list/scrape/update/diagnostics/settings/exit] (list):
```

The TUI offers 6 main options. Type the action name directly.

---

## Keyboard Shortcuts

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

## Step-by-Step Guide to All 6 Options

### Option 1: List — Novel Library

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
- Shows all novels stored in `novel_library/novels/`
- Shows empty message if no novels yet

---

### Option 2: Scrape — Add Novel

**Purpose**: Download novel metadata and chapters from a web source, optionally translating them in one step

**Access**: Type `scrape`

**Flow**:

1. Select source:
```
Source (syosetu_ncode, kakuyomu, novel18_syosetu, generic) [syosetu_ncode]: syosetu_ncode
```

2. Enter novel ID or URL:
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

**After Translation**, you are prompted to export:
```
Export now? (yes, no) [yes]: yes
Export language (translated, source) [translated]: translated
Format (epub, html, md) [epub]: epub
Include table of contents? (yes, no) [no]: yes
```

- **Export language**: Choose between translated text or original source text
- **Include TOC**: Adds a table of contents page in EPUB (with entries like "Chapter 1  Title")
- EPUB exports also include a title page with the novel title and author

---

### Option 3: Update — Update Novel

**Purpose**: Refresh metadata, raw chapters, and translations for an existing novel

**Access**: Type `update`

**Flow**:

1. Enter the novel ID of an existing novel
2. Choose what to update (metadata, raw chapters, translations)

**What it does**:
- Re-fetches metadata from the source
- Downloads new/changed chapters
- Re-translates as needed

---

### Option 4: Diagnostics

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
2026-03-07T14:30:22Z       openai/gpt-5.2          1200
2026-03-07T14:25:15Z       openai/gpt-5.2           950
2026-03-07T14:20:08Z       openai/gpt-5.4          2100
```

**Information Shown**:
- Total novels stored
- Total translated chapters
- Cache entries (for cost savings)
- API requests and tokens
- Estimated cost in USD
- Last 5 translation events

---

### Option 5: Settings

**Purpose**: View and modify provider, model, API key, and advanced settings

**Access**: Type `settings`

**Initial Display**: A settings summary panel followed by a guide rail prompt:

```
┌── Settings Summary ─────────────────────────────────────────────┐
│ Provider: openai          Model: gpt-5.2       API key: ✓ Set  │
│ Target language: English   Source language: Auto-detected       │
│ Scrape delay: 1.0s                                             │
└─────────────────────────────────────────────────────────────────┘

Command [1=provider / 2=model / 3=api-key / 4=advanced / 0=back]:
```

**Commands**:
- **1** — Change provider (openai)
- **2** — Change model (e.g. gpt-5.2 → gpt-5.4)
- **3** — Update API key
- **4** — Open advanced settings submenu
- **0** — Return to main menu

#### Advanced Settings

Selecting option **4** opens a focused submenu:

```
┌── Advanced Settings ────────────────────────────────────────────┐
│ 1. Target language : English                                   │
│ 2. Scrape delay    : 1.0s                                      │
│ 0. Back                                                        │
└─────────────────────────────────────────────────────────────────┘

Command [1=language / 2=delay / 0=back]:
```

**Target language** presents a numbered list of 20 languages:

```
 1. English         6. Korean          11. Thai           16. Italian
 2. Indonesian      7. Spanish         12. Vietnamese     17. Dutch
 3. Japanese        8. French          13. Arabic         18. Polish
 4. Chinese (S)     9. German          14. Hindi          19. Turkish
 5. Chinese (T)    10. Portuguese      15. Russian        20. Malay
```

**Scrape delay** sets the seconds between HTTP requests (default 1.0).

---

### Option 6: Exit

**Purpose**: Close the TUI and return to terminal

**Access**: Type `exit` or press Ctrl+C

---

## Common Workflows

### Workflow 1: Download, Translate, and Export a Novel

1. **Add Novel**: Scrape metadata and chapters
   ```
   select: scrape
   source: syosetu_ncode
   id: n4423lw
   chapters: 1-10
   mode: full
   ```

2. **Export**: After translation completes, the TUI prompts to export:
   ```
   Export now? yes
   Export language: translated
   Format: epub
   Include table of contents? yes
   ```

3. **Verify**: Check with list
   ```
   select: list
   ```

---

### Workflow 2: Translate Small Batch First

1. **Add Novel**: Download first 3 chapters
   ```
   select: scrape
   chapters: 1-3
   ```

2. **Review**: Check quality

3. **Update**: Come back and add more chapters
   ```
   select: update
   id: n4423lw
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
   model: gpt-5.2 (cheaper)
   ```

---

## Menu Reference Table

| # | Command | Label | Purpose | Notes |
|---|---------|-------|---------|-------|
| 1 | list | Novel Library | View novels | Default option |
| 2 | scrape | Add Novel | Download + translate chapters | Choose mode, export after translate |
| 3 | update | Update Novel | Refresh existing novel | Re-scrape and re-translate |
| 4 | diagnostics | Diagnostics | Show statistics | Cache, usage, costs |
| 5 | settings | Settings | Modify settings | Provider, model, language, delay |
| 6 | exit | Exit | Close TUI | Returns to terminal |

---

## Tips

### Use Default Values
- Most options have defaults shown in `[brackets]`
- Press Enter to accept and move faster

### Chapter Selection Formats
- Single: `5`
- Range: `1-10`
- Multiple: `1-3;5;7-10`
- All: `1-*`

### Error Recovery
- If scrape fails, try again in "update" mode
- If translation fails, check API key in settings
- Use diagnostics to verify cache status

---

## Troubleshooting

### "No sources are registered"
- **Fix**: Exit and restart TUI (`novelaibook tui`)

### Translation fails with "API Error"
- **Fix**: Check API key in settings
- **Verify**: Check usage in diagnostics

### Export fails "metadata not found"
- **Fix**: Run scrape first, then export
- **Sequence**: scrape → export

### Chapters not translating
- **Fix**: Run scrape first
- **Check**: Use "list" to verify novel exists

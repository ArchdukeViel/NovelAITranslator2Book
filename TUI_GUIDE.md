# Terminal UI (TUI) Guide

Comprehensive walkthrough of the Novel AI Terminal User Interface with keyboard shortcuts and visual examples.

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


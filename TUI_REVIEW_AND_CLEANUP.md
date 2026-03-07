# TUI Review, Cache Cleanup, and Testing Analysis

**Date**: March 7, 2026  
**Status**: Pre-Implementation Analysis

---

## 1. Cache and Temporary Files Cleanup 

### Files That Should Be Deleted

| Item | Type | Location | Size | In .gitignore? | Should Delete? |
|------|------|----------|------|----------------|----------------|
| .tmp/ | Directory | Root | Small | âœ… Yes | âœ… YES |
| tests_tmp/ | Directory | Root | Small | âœ… Yes | âœ… YES |
| pytest-cache-files-*/ | Directories (6) | Root | ~Medium | âœ… Yes | âœ… YES |
| __pycache__/ | Directories | Throughout | ~Large | âœ… Yes | âœ… YES |

### Rationale for Deletion

**All these files are artifacts from:**
- Development/testing runs (pytest cache)
- Temporary processing (tests_tmp, .tmp)
- Python bytecode compilation (__pycache__)

**Why safe to delete:**
- âœ… All are in .gitignore (not tracked)
- âœ… All are automatically regenerated on next run
- âœ… No data loss
- âœ… Cleaner workspace
- âœ… Smaller git history

**Recommendation**: Delete all of these. They serve no purpose in the repo and clutter the workspace.

---

## 2. TUI Implementation vs Documentation Discrepancy

### Actual TUI Implementation (src/novelai/tui/app.py)

The actual TUI has **7 menu options**:

```
1. list        - List all novels in storage
2. scrape      - Scrape metadata and chapters from a source
3. translate   - Translate chapters using provider
4. export      - Export chapters to EPUB or PDF
5. diagnostics - Show system diagnostics, cache stats, usage summary
6. settings    - View/change provider, model, API key settings
7. exit        - Exit the application
```

### TUI_GUIDE.md Claims

The documentation shows **8 menu options** with ASCII mockups:
```
1. Scrape Novel Metadata
2. Fetch Chapters
3. Translate Chapters
4. Export to EPUB/PDF
5. View Novels
6. Check API Usage
7. Settings
8. Exit
```

### Discrepancies Found

| Guide Feature | Actual Implementation | Status |
|---------------|----------------------|--------|
| "Scrape Metadata" as option 1 | Combined with Fetch into "scrape" | âŒ Mismatch |
| "Fetch Chapters" as option 2 | Part of "scrape" | âŒ Mismatch |
| "View Novels" as option 5 | Exists as "list" (option 1) | âš ï¸ Different Position |
| "Check API Usage" as option 6 | Part of "diagnostics" (option 5) | âŒ Mismatch |
| "Settings" as option 7 | Exists as "settings" (option 6) | âš ï¸ Different Position |
| Diagnostics option | NOT mentioned in guide | âŒ Missing |

### Root Cause

The TUI_GUIDE.md was created with:
- Imagined menu structure (aspirational design)
- More granular menu organization than actual implementation
- 8 menu items instead of actual 7

The actual implementation is more consolidated (combine scrape metadata+chapters, combine API usage into diagnostics).

---

## 3. Issues in TUI_GUIDE.md vs Implementation

### Issue 1: Menu Structure Mismatch

**Guide Says** (Step 1):
```
Scrape Novel Metadata - Select Source
1. Syosetu (syosetu_ncode)
2. Kakuyomu (kakuyomu)
3. Example Source (example_source)
```

**Reality**: The guide shows separate "scrape metadata" screen, but actual code combines metadata + chapters into one "scrape" flow

---

### Issue 2: Missing Diagnostics

**Guide Does Not Mention**: The "diagnostics" menu option which provides:
- Novel count
- Translated chapter count
- Cache statistics
- Usage summary (total requests, tokens, cost)
- Recent usage history
- Option to clear usage

---

### Issue 3: API Usage Presentation

**Guide Shows**: Separate "Check API Usage" screen (Step 6)

**Reality**: Usage data is shown in "diagnostics" menu along with cache stats and novel count

---

### Issue 4: Actual Flow Implementation

**Actual "Scrape" Flow**:
1. Prompt for source
2. Novel ID
3. Chapter selection
4. Mode (full or update)
5. Runs both metadata scrape AND chapter scrape

**Guide Shows**: Two separate steps for metadata and chapters

---

## 4. What Actually Works vs Guide

### âœ… Working Features (Verified in Code)

1. **List Novels** - Lists all novels, stored in storage service
2. **Scrape** - Downloads metadata and chapters from sources
3. **Translate** - Translates chapters with provider/model selection
4. **Export** - Exports to EPUB or PDF format
5. **Diagnostics** - Shows statistics and usage
6. **Settings** - Manage provider, model, API key
7. **Exit** - Clean exit

### âš ï¸ Features in Guide But Implemented Differently

1. **Metadata Scrape** - Works but combined with chapter scrape
2. **API Usage** - Works but in diagnostics, not separate menu
3. **Menu Order** - Different positions than in guide

### âŒ Features in Guide But NOT in Code

1. **Kakuyomu Source** - Guide mentions it, need to verify if registered
2. **7 vs 8 Menu Items** - Guide has 8, actual has 7

---

## 5. Testing Plan

### Test Matrix

| Menu Option | Test Case | Expected | Commands |
|-------------|-----------|----------|----------|
| list | Empty at start | No novels | Select "list" |
| scrape | Attempt scrape | Requires valid source/ID | Select "scrape" |
| translate | After scrape | Translates stored chapters | Select "translate" |
| export | After translate | Creates EPUB/PDF | Select "export" |
| diagnostics | Show stats | Stats screen | Select "diagnostics" |
| settings | View current | Shows provider/model | Select "settings" |
| settings | Change settings | Updates stored settings | Select "settings" â†’ "yes" |
| exit | Exit | Returns to shell | Select "exit" |

---

## 6. Recommendations

### Immediate Actions

1. **Delete Cache/Tmp Files** (Low Risk, Clean)
   - Delete .tmp/
   - Delete tests_tmp/
   - Delete pytest-cache-files-*/
   - Delete __pycache__/ (will regenerate)

2. **Update TUI_GUIDE.md** (Required for Accuracy)
   - Correct menu structure (7 items, not 8)
   - Update menu order
   - Add diagnostics option
   - Combine scrape metadata/chapters explanation
   - Consolidate API usage into diagnostics
   - Remove invalid source references if not actual

3. **Document Actual TUI Flow** (Better UX)
   - Step-by-step walkthroughs for actual 7-item menu
   - Actual prompts and inputs
   - Real output examples

### Testing Approach

**Option 1 - Manual Testing**:
```powershell
# Activate env
.venv\Scripts\Activate.ps1

# Run TUI
novelaibook tui

# Test each menu option:
# 1. list (should show no novels)
# 2. exit
```

**Option 2 - Automated Test** (More thorough):
- Create test script that simulates menu selections
- Verify each function executes without error
- Check output formatting

---

## 7. Actionable Summary

### Task 1: Clean Workspace âœ¨
```powershell
Remove-Item -Path ".tmp", "tests_tmp" -Recurse -Force
Get-ChildItem -Path "pytest-cache-files-*" -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
```

### Task 2: Fix TUI Documentation ðŸ“
- Update TUI_GUIDE.md to reflect actual 7-menu implementation
- Rewrite menu examples to match code
- Add diagnostics option documentation
- Consolidate scrape explanation
- Test all examples before finalizing

### Task 3: Test TUI Functionality ðŸ§ª
- Run TUI and verify all 7 menu options
- Test each flow (scrape, translate, export with valid data)
- Verify settings persistence
- Check diagnostics display
- Verify exit works cleanly

---

## References

- **TUI Code**: src/novelai/tui/app.py (282 lines)
- **TUI Guide**: TUI_GUIDE.md (450 lines)
- **Test Folder**: tests/ (4 test files)
- **Cleanup**: 6 pytest cache dirs + 2 tmp dirs


